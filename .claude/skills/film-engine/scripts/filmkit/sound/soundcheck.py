"""soundcheck: loudness, peaks, onsets, hit table with presence, determinism. Owner: sound.
numpy + scipy + ffmpeg (ebur128 cross-check, check image).

The hit table proves timing AND presence: each event is matched to the nearest
onset in its own kind's stem (within tol), not only in the full mix. Its
audibility column (audibility: the kind's contribution to the pre-master mix
over the rest of the mix, phone band, best 5 ms) is the one number that reads
the MIX: a mix onset on the groove's grid passes the onset test whether or
not the kind is in the mix. The mutation check mutes one kind in the mix and
scores the muted mix against the unmuted stems: its rows then carry no
contribution, and the same muted build measures the kind's REAL contribution
to the mix at each row. A row whose real contribution is None (the kind adds
nothing to the mix there) is a dropped sound, a fact: step.run fails the row
and the kind reads ESCAPED, with no floor set. The director's floor on the
audibility column (SOUND['audible_db']) is the taste on top of that fact.
Decisions use the 0.5 s K-weighted blocks; ffmpeg momentary loudness is a
cross-check only.

Signals: mono (n,) or stereo (2, n) float arrays. Loudness in LUFS, peaks in
dBTP/dBFS, onsets as sample indices, errors in ms.
"""
import math
import os
import re
import subprocess

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy import signal

from .. import outpath
from . import synth

# Onset detector bands: (lo Hz, hi Hz, follower release ms). Detection parameters, not taste.
ONSET_BANDS = ((30, 180, 30), (180, 1200, 10), (1200, 5000, 5), (5000, 10000, 4), (10000, 18000, 3))
# The audibility band: what a phone speaker passes (a proxy, the critics' band). Measurement, not taste.
PHONE_BAND = (300.0, 8000.0)
AUDIBLE_WIN_MS, AUDIBLE_BEST_MS = 40.0, 5.0

# BS.1770 pre-filter analog prototype (bilinear transform; at 48 kHz it gives the published constants).
_SHELF_HZ, _SHELF_DB, _SHELF_Q, _SHELF_VB_POW = 1681.974450955533, 3.999843853973347, 0.7071752369554196, 0.4996667741545416
_HP_HZ, _HP_Q = 38.13547087602444, 0.5003270373238773


def _k_coeffs(sr):
    """-> ((b, a) high shelf, (b, a) high-pass) BS.1770 pre-filter biquads for sr."""
    k = math.tan(math.pi * _SHELF_HZ / sr)
    vh = 10.0 ** (_SHELF_DB / 20.0)
    vb = vh ** _SHELF_VB_POW
    a0 = 1.0 + k / _SHELF_Q + k * k
    shelf = (np.array([(vh + vb * k / _SHELF_Q + k * k) / a0, 2.0 * (k * k - vh) / a0,
                       (vh - vb * k / _SHELF_Q + k * k) / a0]),
             np.array([1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / _SHELF_Q + k * k) / a0]))
    k = math.tan(math.pi * _HP_HZ / sr)
    a0 = 1.0 + k / _HP_Q + k * k
    hpf = (np.array([1.0, -2.0, 1.0]),
           np.array([1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / _HP_Q + k * k) / a0]))
    return shelf, hpf


def k_weight(x, sr):
    """BS.1770 pre-filter (high shelf + high-pass) along the last axis. Coefficients are computed for
    sr from the analog prototype (at 48000 they equal the published constants within 1e-6)."""
    shelf, hpf = _k_coeffs(sr)
    y = signal.lfilter(shelf[0], shelf[1], np.asarray(x, float), axis=-1)
    return signal.lfilter(hpf[0], hpf[1], y, axis=-1)


def _stereo(x):
    x = np.asarray(x, float)
    return x[None, :] if x.ndim == 1 else x


def block_lufs(x, sr, block_s=0.5):
    """-> per-block ungated K-weighted loudness (LUFS) array over whole blocks of block_s (channels
    summed with unit weights; a mono signal counts once)."""
    y = k_weight(_stereo(x), sr)
    n = int(block_s * sr)
    nb = y.shape[1] // n
    m = (y[:, :nb * n] ** 2).reshape(y.shape[0], nb, n).mean(axis=2).sum(axis=0)
    return -0.691 + 10.0 * np.log10(m + 1e-12)


def integrated_lufs(x, sr):
    """-> gated integrated loudness per BS.1770-4: 400 ms blocks, 100 ms hop, absolute gate -70 LUFS,
    relative gate 10 LU under the absolute-gated mean. -120 when nothing passes the gate."""
    y = k_weight(_stereo(x), sr)
    n, hop = int(0.4 * sr), int(0.1 * sr)
    if y.shape[1] < n:
        return -120.0
    cs = np.concatenate([np.zeros((y.shape[0], 1)), np.cumsum(y ** 2, axis=1)], axis=1)
    starts = np.arange(0, y.shape[1] - n + 1, hop)
    z = ((cs[:, starts + n] - cs[:, starts]) / n).sum(axis=0)
    l = -0.691 + 10.0 * np.log10(z + 1e-12)
    keep = l > -70.0
    if not keep.any():
        return -120.0
    rel = -0.691 + 10.0 * np.log10(z[keep].mean()) - 10.0
    keep &= l > rel
    if not keep.any():
        return -120.0
    return float(-0.691 + 10.0 * np.log10(z[keep].mean()))


def true_peak(x, sr):
    """-> 4x oversampled true peak, linear (max of the upsampled and the sample peak)."""
    x = _stereo(x)
    up = signal.resample_poly(x, 4, 1, axis=1)
    return float(max(np.abs(up).max(), np.abs(x).max()))


def _peak_env_db(y, release_ms, sr):
    """Peak follower in dB: instant attack, exponential release (log-domain running max, no loop)."""
    lr = -1.0 / (release_ms * sr / 1000.0)
    k = np.arange(len(y))
    ln = np.log(np.abs(y) + 1e-9)
    return (k * lr + np.maximum.accumulate(ln - k * lr)) * (20.0 / math.log(10.0))


def onsets(x, sr, bands=None, rise_db=10.0, floor_ms=15.0, refractory_ms=20.0, merge_ms=8.0):
    """Multi-band onset detector. Per band: a peak follower in dB; an onset where it climbs rise_db
    above its floor (minimum over the last floor_ms) and sits above -50 dB, traced back along the
    steep edge to where the rise begins; refractory_ms between onsets. Bands merged: within merge_ms
    the strongest rise wins. bands: [(lo_hz, hi_hz, release_ms)]. -> sample indices (int array)."""
    x = np.asarray(x, float)
    mono = x.mean(axis=0) if x.ndim == 2 else x
    n = len(mono)
    w = int(floor_ms * sr / 1000.0)
    refr = refractory_ms * sr / 1000.0
    found = []
    for lo, hi, rel in (bands or ONSET_BANDS):
        e = _peak_env_db(synth.bp(mono, lo, min(hi, 0.49 * sr), sr), rel, sr)
        floor = sliding_window_view(np.pad(e, (w, 0), mode="edge"), w + 1).min(axis=1)[:n]
        over = (e - floor >= rise_db) & (e > -50.0)
        starts = np.flatnonzero(over & ~np.concatenate([[False], over[:-1]]))
        last = -10 ** 9
        for c in starts:
            if c - last < refr:
                continue
            fl = floor[c]
            i = c
            while i > max(0, c - w) and e[i - 1] > fl + 3.0 and e[i - 1] < e[i] - 0.03:
                i -= 1
            found.append((int(i), float(e[c:c + int(0.005 * sr)].max() - fl)))
            last = c
    found.sort()
    merged = []
    for i, strength in found:
        if merged and i - merged[-1][0] <= merge_ms * sr / 1000.0:
            if strength > merged[-1][2]:
                merged[-1][1:] = [i, strength]
        else:
            merged.append([i, i, strength])
    return np.array([m[1] for m in merged], dtype=int)


def _target(ev, clock):
    """Sample a hit must sit on: clock.exact for place='exact', else clock.at."""
    return clock.exact(ev["t"]) if ev.get("place") == "exact" else clock.at(ev["t"])


def _nearest_ms(on, target, sr):
    """Signed error (ms) of the nearest onset, or None when there is none."""
    if len(on) == 0:
        return None
    return float(on[np.argmin(np.abs(on - target))] - target) / sr * 1000.0


def _mono(x):
    x = np.asarray(x, float)
    return x.mean(axis=0) if x.ndim == 2 else x


def audibility(contrib, rest, targets, sr, band=PHONE_BAND, win_ms=AUDIBLE_WIN_MS, best_ms=AUDIBLE_BEST_MS):
    """-> [dB | None] per target sample: the level of `contrib` (what one kind adds to the pre-master mix,
    mono) over the level of `rest` (the mix without it) in `band`, both band-passed, read in the best_ms
    window (1 ms hop) inside [target, target + win_ms) where that difference is largest: a short transient
    is read where it stands out, not averaged into the 40 ms. None when the raw contribution is all zero
    over that window (the kind is not in the mix there)."""
    c, r = _mono(contrib), _mono(rest)
    lo, hi = band
    cb = synth.bp(c, lo, min(hi, 0.49 * sr), sr)
    rb = synth.bp(r, lo, min(hi, 0.49 * sr), sr)
    ec = np.concatenate([[0.0], np.cumsum(cb * cb)])
    er = np.concatenate([[0.0], np.cumsum(rb * rb)])
    n_best, hop, n_win = int(best_ms * sr / 1000.0), max(1, int(sr / 1000.0)), int(win_ms * sr / 1000.0)
    out = []
    for tgt in targets:
        tgt = int(tgt)
        if tgt < 0 or tgt >= len(c) or not c[tgt:tgt + n_win].any():
            out.append(None)
            continue
        last = min(tgt + n_win, len(c)) - n_best
        starts = range(tgt, last + 1, hop) if last >= tgt else [max(0, len(c) - n_best)]
        out.append(max(10.0 * math.log10((ec[s + n_best] - ec[s] + 1e-20) / (er[s + n_best] - er[s] + 1e-20))
                       for s in starts))
    return out


def hit_table(events, mix, stems, clock, tol_ms=None, min_db=-50.0, pre=None, rests=None):
    """Per event whose kind has a stem: nearest onset in the mix and in the kind's stem, errors in ms,
    the stem's peak dBFS within tol of the target; ok when both errors are within tol (default one
    frame) and the stem peak is >= min_db; 'present' is the stem half of that (own onset within tol
    and loud enough). Events of kinds with no stem (silent kinds) make no row.
    pre (the pre-master mix, (2, n) or mono) with rests {kind: the pre-master mix built with that kind
    muted} adds 'audible_db' per row (audibility of pre - rests[kind] over rests[kind]; None without them
    or when the kind adds nothing to the mix there). 'ok' never reads it: the floor is the director's.
    -> [{'id', 'kind', 't', 'frame', 'target', 'mix_ms', 'stem_ms', 'stem_db', 'present', 'ok', 'audible_db'}]."""
    sr = clock.sr
    tol = 1000.0 / clock.fps if tol_ms is None else float(tol_ms)
    w = int(tol * sr / 1000.0)
    mix_on = onsets(mix, sr)
    stem_on = {}
    rows = []
    for ev in events:
        k = ev["kind"]
        if k not in stems:
            continue
        if k not in stem_on:
            stem_on[k] = onsets(stems[k], sr)
        tgt = _target(ev, clock)
        seg = np.abs(np.asarray(stems[k], float)[max(0, tgt - w):tgt + w + 1])
        pk = float(seg.max()) if seg.size else 0.0
        stem_db = 20.0 * math.log10(pk) if pk > 0 else -120.0
        em = _nearest_ms(mix_on, tgt, sr)
        es = _nearest_ms(stem_on[k], tgt, sr)
        present = es is not None and abs(es) <= tol and stem_db >= min_db
        ok = present and em is not None and abs(em) <= tol
        rows.append({"id": ev.get("id"), "kind": k, "t": ev["t"], "frame": ev.get("frame"),
                     "target": int(tgt), "mix_ms": em, "stem_ms": es, "stem_db": stem_db,
                     "present": bool(present), "ok": bool(ok), "audible_db": None})
    if pre is not None and rests:
        p = _mono(pre)
        for k, rest in rests.items():
            mine = [r for r in rows if r["kind"] == k]
            if not mine:
                continue
            r_ = _mono(rest)
            for row, a in zip(mine, audibility(p - r_, r_, [r["target"] for r in mine], sr)):
                row["audible_db"] = a
    return rows


def presence(events, stems, clock, tol_ms=None):
    """-> [event ids] whose own kind's stem has no onset within tol (default one frame) of the target.
    Kinds with no stem are skipped."""
    sr = clock.sr
    tol = 1000.0 / clock.fps if tol_ms is None else float(tol_ms)
    stem_on = {k: onsets(v, sr) for k, v in stems.items()}
    missing = []
    for ev in events:
        k = ev["kind"]
        if k not in stems:
            continue
        err = _nearest_ms(stem_on[k], _target(ev, clock), sr)
        if err is None or abs(err) > tol:
            missing.append(ev.get("id"))
    return missing


def mutation_check(build_fn, kinds, clock, events, stems=None, pre=None, audible=None):
    """build_fn(muted_kinds) -> (mix, stems[, pre]): the build with those kinds muted in the mix (their
    stems all zero). For each kind: build with it muted and expect that kind's rows to fail (caught = every
    one of its rows fails; a kind with no rows is not caught). Only that kind's events go through the hit
    table, so one muted build costs one mix onset pass plus one stem.

    Without `stems`: the muted build's own stems score the rows, so the zero stem fails them (the stem
    path is proven, the mix is never read: a kind missing from the mix with its stem intact escapes).
    With `stems` (the unmuted stems) and `pre` (the unmuted pre-master, (2, n) or mono; build_fn must
    then return the muted pre-master third): the muted mix is scored against the intact stems, with the
    muted pre-master as that kind's rest (its contribution there is zero by construction, so no row passes
    on its audibility), and the REAL audibility of every row, audibility(pre - muted pre, muted pre), is
    measured: caught = the kind's rows all fail on the muted build AND every one of them has a measured
    real audibility (muting the kind changed the pre-master at each target). A kind that was never in the
    mix reads None on every row (muting it changes nothing) and is not caught: the detector could not tell
    the real mix from the muted one. A groove onset on the kind's grid passes the onset test, so the
    audibility is the catch. `audible`, a dict, is filled with {event id: that real audible_db} per row
    (the hit table's column). -> {kind: caught}."""
    out = {}
    p = None if pre is None else _mono(pre)
    for k in kinds:
        built = build_fn([k])
        mix_k, stems_k = built[0], built[1]
        pre_k = _mono(built[2]) if len(built) > 2 and built[2] is not None else None
        mine = [e for e in events if e["kind"] == k]
        if stems is None or p is None or pre_k is None:
            rows = hit_table(mine, mix_k, stems_k, clock)
            out[k] = bool(rows) and not any(r["ok"] for r in rows)
            continue
        rows = hit_table(mine, mix_k, stems, clock, pre=pre_k, rests={k: pre_k})
        real = audibility(p - pre_k, pre_k, [r["target"] for r in rows], clock.sr) if rows else []
        out[k] = (bool(rows) and not any(r["ok"] and r["audible_db"] is not None for r in rows)
                  and all(a is not None for a in real))
        if audible is not None:
            for row, a in zip(rows, real):
                audible[row["id"]] = a
    return out


def determinism_check(build_fn):
    """build_fn() -> the mastered (2, n) array. Build twice; -> True when the two arrays are
    byte-identical (so the WAVs written from them are too)."""
    a = np.asarray(build_fn(), float)
    b = np.asarray(build_fn(), float)
    return a.shape == b.shape and a.tobytes() == b.tobytes()


def contour_deltas(lufs_blocks, reference):
    """-> [(block, measured, reference, delta)]; reference per block (same length, None = unchecked,
    delta None). Raises ValueError on a length mismatch."""
    if len(lufs_blocks) != len(reference):
        raise ValueError(f"{len(lufs_blocks)} measured blocks but {len(reference)} reference blocks")
    return [(i, float(m), r, None if r is None else float(m) - r)
            for i, (m, r) in enumerate(zip(lufs_blocks, reference))]


def _ffmpeg():
    return os.environ.get("FFMPEG") or "ffmpeg"


def ffmpeg_ebur128(path):
    """ffmpeg ebur128 cross-check -> {'momentary': {t: LUFS at every 0.1 s}, 'true_peak_dbfs': x,
    'integrated': y}; raises RuntimeError when the parse finds no momentary value (ffmpeg output
    format changed or ffmpeg failed)."""
    p = subprocess.run([_ffmpeg(), "-hide_banner", "-nostats", "-v", "verbose", "-i", path, "-af",
                        "ebur128=peak=true:framelog=verbose", "-f", "null", "-"],
                       capture_output=True, text=True)
    txt = p.stderr
    mom = {}
    for m in re.finditer(r"t:\s*([\d.]+)\s+TARGET:.*?M:\s*(-?[\d.]+|-inf)", txt):
        mom[round(float(m.group(1)), 1)] = float(m.group(2)) if m.group(2) != "-inf" else -120.0
    if not mom:
        raise RuntimeError(f"ffmpeg ebur128 gave no momentary values for {path}: {txt[-400:]}")
    tp = re.findall(r"Peak:\s*(-?[\d.]+|-inf)\s*dBFS", txt)
    il = re.findall(r"I:\s*(-?[\d.]+)\s*LUFS", txt)
    return {"momentary": mom, "true_peak_dbfs": float(tp[-1]) if tp else None,
            "integrated": float(il[-1]) if il else None}


def _color(c):
    """'#rrggbb' | '0xrrggbb' | name -> ffmpeg colour."""
    c = str(c)
    return "0x" + c[1:] if c.startswith("#") else c


def check_png(wav, png, markers, width=1600, tick_s=0.5, wave_color="0xd0d0d0"):
    """Spectrogram (log frequency, log scale) over waveform with coloured event markers [(t, colour)]
    and ticks every tick_s; the filter graph goes through -filter_complex_script (no command-line
    length limit); written to a temp name and renamed. png stays inside the cwd (outpath.under refuses
    anything else). -> png path."""
    png = outpath.under(os.getcwd(), png)
    from pedalboard.io import AudioFile
    with AudioFile(wav) as f:
        duration = f.frames / f.samplerate
    boxes = [f"drawbox=x={int(t / duration * width)}:y=0:w=2:h=ih:color={_color(c)}@0.6:t=fill"
             for t, c in markers]
    boxes += [f"drawbox=x={int(k * tick_s / duration * width)}:y=ih-12:w=1:h=12:color=white@0.8:t=fill"
              for k in range(1, int(duration / tick_s) + 1)]
    graph = (f"[0:a]showspectrumpic=s={width}x520:legend=0:fscale=log:scale=log:color=intensity[s];"
             f"[0:a]showwavespic=s={width}x260:colors={_color(wave_color)}:scale=sqrt,format=rgb24[w];"
             f"[s][w]vstack" + "".join("," + b for b in boxes))
    script = png + ".filter.txt"
    tmp = os.path.join(os.path.dirname(os.path.abspath(png)), "~" + os.path.basename(png))
    with open(script, "w", encoding="utf-8") as fh:
        fh.write(graph)
    try:
        subprocess.run([_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", wav,
                        "-filter_complex_script", script, "-frames:v", "1", tmp], check=True)
    finally:
        os.remove(script)
    os.replace(tmp, png)
    return png


def report(path, lufs_blocks, reference, tp_db, n_samples, n_expected, makeup_db, rows, ffmpeg=None,
           ceiling_dbtp=None, mutation=None, contour_lu=None, tap_ms=None, tap_kinds=("tap",),
           audible_db=None, audible_kinds=None):
    """Write the sound report: per-block loudness vs reference (and ffmpeg momentary when given),
    peaks, length OK, makeup, hit table (with the 'aud dB' audibility column) with a 'HITS: ok/n' line and
    a 'PRESENCE MISSING: k' line, and the mutation check ({kind: caught} from mutation_check; None = not
    run) as one line per kind and a 'MUTATION: caught/n kinds caught' line ('MUTATION: not run' without
    it). contour_lu: the largest |K - ref| allowed over the blocks that have a reference ('CONTOUR: x.x LU
    max ... OK|OVER'); tap_ms: the largest |mix onset error| allowed on the rows of tap_kinds ('TAPS: x.x
    ms max ... OK|OVER'); audible_db: the floor of the audibility column over the rows of audible_kinds
    (None = every row that has a kind; 'AUDIBLE: x.x dB min over n rows ... (floor y) OK|UNDER'; a listed
    row without a measured value counts as UNDER).
    -> exit code: 0 when every row passes, the length matches, (when ceiling_dbtp is given) the true
    peak is under it, (when mutation is given) every kind is caught, and the contour, tap and audibility
    limits hold."""
    mom = (ffmpeg or {}).get("momentary", {})
    lines = ["SOUND CHECK", "",
             "LOUDNESS PER BLOCK (K = K-weighted ungated 0.5 s block, LUFS; M = ffmpeg momentary at the block end)",
             "  block   t (s)         K       M     ref   K-ref"]
    ref = list(reference) if reference is not None else [None] * len(lufs_blocks)
    for i, m, r, d in contour_deltas(lufs_blocks, ref):
        mm = mom.get(round((i + 1) * 0.5, 1))
        lines.append(f"  {i + 1:>4}  {i * 0.5:>5.1f}-{(i + 1) * 0.5:<5.1f} {m:>7.1f} "
                     f"{'' if mm is None else f'{mm:7.1f}':>7} {'' if r is None else f'{r:7.1f}':>7} "
                     f"{'' if d is None else f'{d:+7.1f}':>7}")
    deltas = [abs(d) for _i, _m, _r, d in contour_deltas(lufs_blocks, ref) if d is not None]
    contour_max = max(deltas) if deltas else 0.0
    contour_ok = contour_lu is None or contour_max <= contour_lu + 1e-9
    lines += [f"  integrated (ffmpeg): {(ffmpeg or {}).get('integrated')} LUFS; makeup gain {makeup_db:+.1f} dB",
              f"CONTOUR: {contour_max:.1f} LU max |K-ref| over {len(deltas)} blocks"
              + ("" if contour_lu is None else f" (limit {contour_lu}) {'OK' if contour_ok else 'OVER'}"), "",
              "PEAK",
              f"TRUE PEAK: {tp_db:.2f} dBTP" + (f" (ceiling {ceiling_dbtp})" if ceiling_dbtp is not None else "")
              + f"; ffmpeg true peak {(ffmpeg or {}).get('true_peak_dbfs')} dBFS", "",
              "LENGTH", f"LENGTH: {n_samples} " + ("OK" if n_samples == n_expected else f"WRONG, must be {n_expected}"), "",
              "HIT TABLE (target = the hit sample; mix/stem = nearest onset error, ms; ok = both within one frame and the stem present;",
              f"           aud = the kind over the rest of the pre-master mix, {int(PHONE_BAND[0])}-{int(PHONE_BAND[1])} Hz, "
              f"best {AUDIBLE_BEST_MS:.0f} ms in {AUDIBLE_WIN_MS:.0f}; none = not measured)",
              "  frame   t (s)  kind          id                 target  mix ms  stem ms  stem dB  aud dB  ok"]
    missing = 0
    for r in rows:
        em = "   none" if r["mix_ms"] is None else f"{r['mix_ms']:+7.1f}"
        es = "   none" if r["stem_ms"] is None else f"{r['stem_ms']:+7.1f}"
        au = r.get("audible_db")
        ea = "   none" if au is None else f"{au:+7.1f}"
        missing += not r.get("present", r["ok"])
        lines.append(f"  {str(r['frame']):>5} {r['t']:>7.3f}  {r['kind']:<13} {str(r['id']):<18} {r['target']:>7} "
                     f"{em} {es} {r['stem_db']:>8.1f} {ea}  {'yes' if r['ok'] else 'NO'}")
    n_ok = sum(r["ok"] for r in rows)
    taps = [r for r in rows if r["kind"] in tuple(tap_kinds or ())]
    tap_errs = [abs(r["mix_ms"]) for r in taps if r["mix_ms"] is not None]
    tap_max = max(tap_errs) if tap_errs else 0.0
    tap_ok = tap_ms is None or (len(tap_errs) == len(taps) and tap_max <= tap_ms + 1e-9)
    auds = [r for r in rows if audible_kinds is None or r["kind"] in tuple(audible_kinds)]
    aud_vals = [r["audible_db"] for r in auds if r.get("audible_db") is not None]
    aud_min = min(aud_vals) if aud_vals else None
    aud_ok = audible_db is None or (len(aud_vals) == len(auds) and aud_min is not None and aud_min >= audible_db - 1e-9)
    aud_kinds = sorted({r["kind"] for r in auds}) if audible_kinds is None else list(audible_kinds)
    lines += [f"HITS: {n_ok}/{len(rows)}", f"PRESENCE MISSING: {missing}",
              f"TAPS: {tap_max:.1f} ms max |mix| over {len(taps)} {'/'.join(tap_kinds or ())} rows"
              + ("" if tap_ms is None else f" (limit {tap_ms}) {'OK' if tap_ok else 'OVER'}"),
              f"AUDIBLE: {'none' if aud_min is None else f'{aud_min:+.1f} dB'} min over {len(aud_vals)}/{len(auds)} measured rows of "
              f"{'/'.join(aud_kinds)}" + ("" if audible_db is None else f" (floor {audible_db}) {'OK' if aud_ok else 'UNDER'}"), "",
              "MUTATION CHECK (one kind muted in the mix per build; caught = every row of that kind then fails)"]
    if mutation is None:
        lines.append("MUTATION: not run")
        n_caught = n_kinds = 0
    else:
        lines += [f"  {k:<13} {'caught' if v else 'ESCAPED'}" for k, v in sorted(mutation.items())]
        n_caught, n_kinds = sum(bool(v) for v in mutation.values()), len(mutation)
        lines.append(f"MUTATION: {n_caught}/{n_kinds} kinds caught")
    tmp = os.path.join(os.path.dirname(os.path.abspath(path)), "~" + os.path.basename(path))
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp, path)
    ok = (n_ok == len(rows) and n_samples == n_expected and (ceiling_dbtp is None or tp_db <= ceiling_dbtp)
          and n_caught == n_kinds and contour_ok and tap_ok and aud_ok)
    return 0 if ok else 1
