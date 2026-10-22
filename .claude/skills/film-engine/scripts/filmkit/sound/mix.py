"""mix: clock, buses, event dispatch, master chain, file I/O. Owner: sound. numpy + scipy + pedalboard.

Picture-locked hits go on Clock.at(t) = (frame(t) - 1) * spf; musical
subdivisions and event series faster than a frame go on Clock.exact(t).
Seeds come from seed_of(kind, n) (crc32 + n, the ease.seed_of formula), never
from a sorted index. Master order is fixed: high-pass, compressor, makeup
loop to the target, true-peak limiter, then the fade after the limiter. The
WAV is written at 24-bit and re-read; its length is asserted.

Score contract (the project's score.py; every number in it is taste):

  HANDLERS = {kind: fn(event, ctx)}   one handler per event kind in timeline.json; the Dispatcher
                                       raises on a kind with no handler unless SILENT names it
  SILENT = ("kind", ...)               optional: event kinds that make no sound, on purpose
  def music(ctx)                       optional: fills the music buses with the score (beds, grid)
  def bus_chain(buses) -> (2, n)       optional: processes {name: Bus} and returns the pre-master
                                       sum (default: plain sum of every bus)
  MASTER = {target_lufs, window_s, ceiling_dbtp, fade_s, fade_pow, hp_hz, comp}   master() kwargs
  REFERENCE = [LUFS or None per 0.5 s block]   read by the project's sound.py for contour_deltas

  event: {id, t, kind, frame, **fields}; a field place="exact" marks a sub-frame event that the
         handler places with ctx.clock.exact(t) and the hit table expects there.
  ctx:   clock (Clock), buses {name: Bus}, tl (timeline doc), event, seed (int, this event), n
         (occurrence of this kind from 1), add(bus, sig, start, gain_db=0, pan=0, pre=0, tail_ms=3)
         which writes the bus and the kind's stem. A handler places its hit with
         ctx.clock.at(event["t"]) so the transient sits on the first sample of the picture frame.
         The music ctx has event None, n 0 and seed seed_of("music").
"""
import math
import os
import zlib

import numpy as np
import pedalboard as pb
from numpy.lib.stride_tricks import sliding_window_view
from pedalboard.io import AudioFile
from scipy import signal

from .. import timebase
from . import SR, soundcheck, synth


def seed_of(kind, n=0):
    """Stable seed for event kind + occurrence n: zlib.crc32(kind) + n, masked to 32 bits.
    Same formula as ease.seed_of (stdlib twin); adding a kind never reshuffles another kind's noise."""
    return (zlib.crc32(str(kind).encode("utf-8")) + int(n)) & 0xFFFFFFFF


class Clock:
    """fps, sr -> spf = sr // fps (asserts sr % fps == 0). n = round half up of duration * sr."""

    def __init__(self, fps, sr, duration):
        if sr % fps:
            raise ValueError(f"sr {sr} is not a multiple of fps {fps}")
        self.fps, self.sr, self.duration = int(fps), int(sr), float(duration)
        self.spf = self.sr // self.fps
        self.n = int(math.floor(self.duration * self.sr + 0.5))

    def at(self, t):
        """-> first sample of the picture frame of t: (frame(t) - 1) * spf."""
        return (timebase.frame(t, self.fps) - 1) * self.spf

    def exact(self, t):
        """-> round half up of t * sr."""
        return int(math.floor(t * self.sr + 0.5))

    def frame_of(self, sample):
        """-> 1-based frame holding this sample."""
        return int(sample) // self.spf + 1


class Bus:
    """Stereo buffer (2, n) lasting the whole film. sr is needed for the tail fade (default 48000)."""

    def __init__(self, n, sr=SR):
        self.n, self.sr = int(n), int(sr)
        self.x = np.zeros((2, self.n))

    def add(self, sig, start, gain_db=0.0, pan=0.0, pre=0, tail_ms=3.0):
        """Mix sig (mono (m,) or stereo (2, m)) so its sample `pre` lands on sample `start`; a cos^2 tail
        fade over tail_ms (0 = none) so a cut-off sound never clicks; clipped at both ends; gain in
        dB; mono is panned with pan (-1..1). -> self."""
        sig = np.asarray(sig, float)
        sig = synth.pan(sig, pan) if sig.ndim == 1 else sig.copy()
        k = min(sig.shape[1], int(tail_ms * self.sr / 1000.0))
        if k > 0:
            sig[:, -k:] *= np.cos(np.linspace(0.0, np.pi / 2.0, k)) ** 2
        s0 = int(start) - int(pre)
        a, b = max(0, s0), min(self.n, s0 + sig.shape[1])
        if b > a:
            self.x[:, a:b] += synth.db(gain_db) * sig[:, a - s0:b - s0]
        return self

    def peak_db(self):
        """-> sample peak in dBFS (-120 when silent)."""
        m = float(np.max(np.abs(self.x))) if self.x.size else 0.0
        return 20.0 * math.log10(m) if m > 0 else -120.0


def fx_board(x, sr, *plugins):
    """Run pedalboard plugins on (2, n) float64 (float32 round trip). -> (2, n) float64."""
    return pb.Pedalboard(list(plugins))(np.asarray(x, np.float32), sr).astype(float)


def duck_curve(times_s, n, sr, depth_db=-4.5, attack_s=0.004, tau_s=0.13, place=None):
    """Sidechain gain curve from event times: linear attack over attack_s to depth_db, then exponential
    recovery with tau_s (the defaults are placeholders, not a mix); the deepest duck wins where events
    overlap. place: callable(t) -> sample
    (default round half up of t * sr). -> (n,) linear gain, 1 where nothing ducks."""
    place = place or (lambda t: int(math.floor(t * sr + 0.5)))
    t = np.arange(n) / sr
    duck = np.zeros(n)
    d = 1.0 - synth.db(depth_db)
    for ts in times_s:
        s = int(place(ts))
        if not 0 <= s < n:
            continue
        tl = t[s:] - t[s]
        att = np.clip(tl / attack_s, 0.0, 1.0)
        duck[s:] = np.maximum(duck[s:], d * att * np.exp(-tl / tau_s))
    return 1.0 - duck


class Ctx:
    """What a handler receives. See the score contract in the module docstring."""

    def __init__(self, clock, buses, tl, event, seed, n, stem=None):
        self.clock, self.buses, self.tl = clock, buses, tl
        self.event, self.seed, self.n = event, int(seed), int(n)
        self.stem = stem

    def add(self, bus, sig, start, gain_db=0.0, pan=0.0, pre=0, tail_ms=3.0):
        """Write sig to the named bus and (for an event) to its kind's stem, same placement."""
        self.buses[bus].add(sig, start, gain_db, pan, pre, tail_ms)
        if self.stem is not None:
            self.stem.add(sig, start, gain_db, pan, pre, tail_ms)


class Dispatcher:
    """Walk events, call one handler per kind, keep per-kind stems.

    events: the timeline doc's event list (dicts with id, t, kind, frame, fields), in its order.
    handlers: {kind: fn(event, ctx)}. A kind with no handler raises ValueError (coverage assert)
    unless listed in `silent` (no sound on purpose, no stem). `mute` kinds keep a handler but are
    skipped, leaving an all-zero stem: the mutation check uses it.
    ctx fields: clock, buses {name: Bus}, tl (timeline doc), event, seed (seed_of(kind, n)), n
    (occurrence of the kind from 1), add(bus, sig, start, gain_db=0, pan=0, pre=0, tail_ms=3).
    stems=True keeps a mono float32 stem per handled kind (mean of the panned stereo) for the
    presence check.
    """

    def __init__(self, events, handlers, clock, buses, tl=None, silent=(), stems=True, mute=()):
        self.events, self.handlers, self.clock, self.buses, self.tl = list(events), dict(handlers), clock, buses, tl
        self.silent, self.mute, self.keep_stems = set(silent), set(mute), bool(stems)
        kinds = {e["kind"] for e in self.events}
        missing = sorted(kinds - set(self.handlers) - self.silent)
        if missing:
            raise ValueError(f"score has no handler for event kinds {missing}")
        self.kinds = sorted(kinds - self.silent)

    def run(self):
        """Dispatch every event in order. -> {'count': n, 'kinds': [...], 'stems': {kind: (n,) float32}}."""
        stems = {k: Bus(self.clock.n, self.clock.sr) for k in self.kinds} if self.keep_stems else {}
        count = {}
        done = 0
        for ev in self.events:
            k = ev["kind"]
            if k in self.silent:
                continue
            n = count[k] = count.get(k, 0) + 1
            if k in self.mute:
                continue
            ctx = Ctx(self.clock, self.buses, self.tl, ev, seed_of(k, n), n, stems.get(k))
            self.handlers[k](ev, ctx)
            done += 1
        return {"count": done, "kinds": list(self.kinds),
                "stems": {k: b.x.mean(axis=0).astype(np.float32) for k, b in stems.items()}}

    def check_no_overlap(self, start_kind, end_kind):
        """Pair the i-th start_kind event with the i-th end_kind event (time order); raise ValueError
        when the counts differ, a pair runs backwards, or a pair overlaps the next one."""
        starts = sorted((e for e in self.events if e["kind"] == start_kind), key=lambda e: e["t"])
        ends = sorted((e for e in self.events if e["kind"] == end_kind), key=lambda e: e["t"])
        if len(starts) != len(ends):
            raise ValueError(f"{len(starts)} {start_kind} events but {len(ends)} {end_kind} events")
        for a, b, nxt in zip(starts, ends, starts[1:] + [None]):
            if not (a["t"] < b["t"] and (nxt is None or b["t"] <= nxt["t"])):
                raise ValueError(f"{a['id']} -> {b['id']} overlaps the next {start_kind}")


def master(mix, sr, target_lufs, window_s, ceiling_dbtp=-1.0, fade_s=None, fade_pow=2.6,
           hp_hz=25.0, comp=None, rounds=5, safety=3):
    """High-pass at hp_hz (None = off), compressor (comp dict: threshold_db, ratio, attack_ms,
    release_ms; None = off), makeup loop (up to `rounds`) so the energy-mean K-weighted loudness of
    the 0.5 s blocks inside window_s (t0, t1) hits target_lufs within 0.05 LU (None = no makeup),
    true-peak limiter at ceiling_dbtp - 0.1, up to `safety` extra limiter passes until the true peak
    is <= ceiling_dbtp - 0.05, then the fade (t0, t1) with (1-u)^fade_pow after the limiter.
    mix: (2, n) float64. -> (out (2, n), makeup_db)."""
    x = np.asarray(mix, float)
    if x.ndim == 1:
        x = np.vstack([x, x])
    n = x.shape[1]
    if hp_hz:
        x = synth.hp(x, hp_hz, sr)
    if comp:
        x = fx_board(x, sr, pb.Compressor(threshold_db=comp["threshold_db"], ratio=comp["ratio"],
                                          attack_ms=comp["attack_ms"], release_ms=comp["release_ms"]))
    gain = 0.0
    out = tp_limit(x, sr, ceiling_dbtp - 0.1)
    if target_lufs is not None:
        blk = 0.5
        b0, b1 = int(window_s[0] / blk), int(window_s[1] / blk)
        for _ in range(rounds):
            sel = soundcheck.block_lufs(out, sr, blk)[b0:b1]
            if sel.size == 0:
                raise ValueError(f"window {window_s} holds no whole {blk} s block")
            err = target_lufs - 10.0 * np.log10(np.mean(10.0 ** (sel / 10.0)))
            if abs(err) < 0.05:
                break
            gain += err
            out = tp_limit(x * synth.db(gain), sr, ceiling_dbtp - 0.1)
    for _ in range(safety):
        if 20.0 * np.log10(max(soundcheck.true_peak(out, sr), 1e-12)) <= ceiling_dbtp - 0.05:
            break
        out = tp_limit(out, sr, ceiling_dbtp - 0.15)
    if fade_s:
        f0, f1 = fade_s
        t = np.arange(n) / sr
        u = np.clip((t - f0) / max(f1 - f0, 1e-9), 0.0, 1.0)
        out = out * (1.0 - u) ** fade_pow
    return out, gain


def tp_limit(x, sr, ceiling_db, look_ms=1.5, release_ms=60.0):
    """Look-ahead limiter on the 4x oversampled peak: the needed gain per sample, a running minimum
    over the look-ahead window ahead of each sample (so the gain is down before the peak arrives),
    box smoothing over the window behind it (every term in the box covers the sample, so the smoothed
    gain never exceeds the needed one, from sample 0 on), then a one-pole release. x (2, n) -> (2, n)."""
    x = np.asarray(x, float)
    n = x.shape[1]
    c = synth.db(ceiling_db)
    up = np.abs(signal.resample_poly(x, 4, 1, axis=1)).max(axis=0)
    pk = np.maximum(up[:n * 4].reshape(n, 4).max(axis=1), np.abs(x).max(axis=0))
    need = np.minimum(1.0, c / np.maximum(pk, 1e-12))
    look = max(1, int(look_ms * sr / 1000.0))
    g1 = sliding_window_view(np.pad(need, (0, look), constant_values=1.0), look + 1).min(axis=1)
    cs = np.concatenate([[0.0], np.cumsum(np.pad(g1, (look, 0), mode="edge"))])
    g2 = (cs[look + 1:] - cs[:-look - 1]) / (look + 1)
    g = np.empty(n)
    a = math.exp(-1.0 / (release_ms * sr / 1000.0))
    prev = 1.0
    for i in range(n):
        prev = min(g2[i], 1.0 - (1.0 - prev) * a)
        g[i] = prev
    return x * g


def write_wav(path, x, sr, bits=24):
    """Write (2, n) float64 as PCM (bits deep) to a temp name, re-read it, assert frames == n,
    channels == 2 and the sample rate, then rename onto path. -> n."""
    x = np.asarray(x, float)
    if x.ndim != 2 or x.shape[0] != 2:
        raise ValueError(f"write_wav needs (2, n), got {x.shape}")
    n = x.shape[1]
    tmp = os.path.join(os.path.dirname(os.path.abspath(path)), "~" + os.path.basename(path))
    with AudioFile(tmp, "w", samplerate=sr, num_channels=2, bit_depth=bits) as f:
        f.write(x.astype(np.float32))
    with AudioFile(tmp) as f:
        frames, channels, rate = f.frames, f.num_channels, f.samplerate
    if (frames, channels, int(rate)) != (n, 2, int(sr)):
        os.remove(tmp)
        raise ValueError(f"WAV re-read gave {frames} frames, {channels} ch, {rate} Hz; wanted {n}, 2, {sr}")
    os.replace(tmp, path)
    return n


def read_wav(path):
    """-> ((channels, n) float64, sr)."""
    with AudioFile(path) as f:
        return f.read(f.frames).astype(float), int(f.samplerate)


def build(score, clock, tl, buses=("music", "fx", "verb"), mute=()):
    """Standard graph: score.music(ctx) fills music buses (optional); Dispatcher(score.HANDLERS) places
    effects (kinds in `mute` are skipped, their stems stay silent); score.bus_chain(buses) returns the
    pre-master (2, n) (default: the plain sum); master(**score.MASTER).
    tl: the timeline doc (its 'events' list is dispatched) or a plain event list.
    -> (out, makeup_db, stems {kind: (n,) float32}, pre)."""
    bus = {name: Bus(clock.n, clock.sr) for name in buses}
    events = tl["events"] if isinstance(tl, dict) else list(tl)
    music = getattr(score, "music", None)
    if music is not None:
        music(Ctx(clock, bus, tl, None, seed_of("music"), 0))
    res = Dispatcher(events, score.HANDLERS, clock, bus, tl, silent=getattr(score, "SILENT", ()),
                     stems=True, mute=mute).run()
    chain = getattr(score, "bus_chain", None)
    pre = np.asarray(chain(bus) if chain is not None else sum(b.x for b in bus.values()), float)
    if pre.shape != (2, clock.n):
        raise ValueError(f"bus_chain returned {pre.shape}, wanted (2, {clock.n})")
    out, makeup = master(pre, clock.sr, **score.MASTER)
    return out, makeup, res["stems"], pre
