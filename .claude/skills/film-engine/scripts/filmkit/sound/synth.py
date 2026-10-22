"""synth: DSP primitives and generic generators. Owner: sound. numpy + scipy.

Primitives guarantee the onset lands on sample 0 (ramp from exactly 0,
phase 0 on sample 0). Every generator returns a peak-normalised mono buffer
(peak 1.0) so bus gains mean what they say. No patch here is a film's sound:
the project's score.py composes these with its own numbers. The default
numbers on the starter generators are neutral placeholders, not a sound design.

Signals are float64 numpy arrays: mono (n,) or stereo (2, n). Frequencies in
Hz, times in seconds, levels in dB, pan -1..1. A per-sample frequency is an
array of length n; a scalar frequency needs n.
"""
import numpy as np
from scipy import signal

TAU = 2.0 * np.pi


def db(x):
    """dB -> linear gain (scalar or array)."""
    return 10.0 ** (np.asarray(x, float) / 20.0)


def mtof(m):
    """MIDI note (float allowed) -> Hz, A4 = 69 = 440 Hz."""
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def rng(seed):
    """-> numpy Generator seeded with seed (determinism: same seed, same noise)."""
    return np.random.default_rng(int(seed))


def _n(dur, sr):
    """Seconds -> sample count, round half up (never Python round())."""
    return int(np.floor(dur * sr + 0.5))


def tvec(dur, sr):
    """-> time vector (n,) in seconds for dur seconds at sr, sample 0 = t 0."""
    return np.arange(_n(dur, sr)) / sr


def ramp(n, sec, sr):
    """-> linear attack 0 -> 1 over sec seconds, starting at exactly 0 on sample 0, length n.
    sec <= one sample gives [0, 1, 1, ...]."""
    e = np.ones(n)
    k = min(n, max(1, int(sec * sr)))
    e[:k] = np.arange(k) / k
    return e


def _f_array(f_hz, n):
    """Scalar or array frequency -> (n,) float array."""
    f = np.asarray(f_hz, float)
    if f.ndim == 0:
        if n is None:
            raise ValueError("a scalar frequency needs n")
        return np.full(int(n), float(f))
    return f


def phase(f_hz, sr, n=None):
    """Per-sample Hz array (or scalar with n) -> phase in radians, exactly 0 on sample 0."""
    f = _f_array(f_hz, n)
    return TAU * np.concatenate([[0.0], np.cumsum(f[:-1])]) / sr


def nrm(x, peak=1.0):
    """Peak-normalise to peak (no change when silent). Works on mono and stereo."""
    m = np.max(np.abs(x)) if np.size(x) else 0.0
    return x * (peak / m) if m > 0 else x


def sine(f_hz, n, sr, ph0=0.0):
    """Sine from a per-sample or scalar frequency; ph0 in radians."""
    return np.sin(phase(f_hz, sr, n) + ph0)


def _cycles(f_hz, n, sr, ph0):
    """-> (phase in cycles 0..1, per-sample cycle increment dt)."""
    f = _f_array(f_hz, n)
    dt = f / sr
    ph = (ph0 + np.concatenate([[0.0], np.cumsum(dt[:-1])])) % 1.0
    return ph, dt


def _blep_saw(ph, dt):
    """Naive saw 2 ph - 1 with polyBLEP corrections at the wrap."""
    y = 2.0 * ph - 1.0
    m = ph < dt
    u = ph[m] / np.maximum(dt[m], 1e-12)
    y[m] -= u + u - u * u - 1.0
    m = ph > 1.0 - dt
    u = (ph[m] - 1.0) / np.maximum(dt[m], 1e-12)
    y[m] -= u * u + u + u + 1.0
    return y


def saw(f_hz, n, sr, ph0=0.0):
    """polyBLEP band-limited saw, -1..1; ph0 in cycles (0..1)."""
    ph, dt = _cycles(f_hz, n, sr, ph0)
    return _blep_saw(ph, dt)


def square(f_hz, n, sr, duty=0.5):
    """polyBLEP square/pulse, -1..1: the difference of two BLEP saws duty cycles apart."""
    ph, dt = _cycles(f_hz, n, sr, 0.0)
    return _blep_saw(ph, dt) - _blep_saw((ph + duty) % 1.0, dt) + (2.0 * duty - 1.0)


def tri(f_hz, n, sr):
    """Triangle -1..1 (naive; its aliasing is -12 dB/octave), 0 on sample 0 like a sine."""
    ph, _ = _cycles(f_hz, n, sr, 0.0)
    return 1.0 - 4.0 * np.abs(((ph + 0.25) % 1.0) - 0.5)


def fm(fc_hz, ratio, index, n, sr, index_env=None):
    """Two-operator FM: carrier fc (scalar or per-sample), modulator fc*ratio, index in radians
    (scalar or per-sample), index_env an optional (n,) multiplier on the index."""
    fc = _f_array(fc_hz, n)
    idx = np.asarray(index, float)
    if index_env is not None:
        idx = idx * np.asarray(index_env, float)
    return np.sin(phase(fc, sr) + idx * np.sin(phase(fc * ratio, sr)))


def noise(n, seed, kind="white"):
    """'white' (Gaussian) | 'pink' (-3 dB/octave, three one-pole stages) noise of length n, peak 1."""
    w = rng(seed).standard_normal(int(n))
    if kind == "white":
        return nrm(w)
    if kind == "pink":
        y = sum(signal.lfilter([g], [1.0, -p], w)
                for p, g in ((0.99765, 0.0990460), (0.96300, 0.2965164), (0.57000, 1.0526913)))
        return nrm(y + 0.1848 * w)
    raise ValueError(f"unknown noise kind {kind!r}")


def env_adsr(n, sr, a, d, s, r):
    """ADSR of length n: linear attack a s from exactly 0, linear decay d s to sustain level s,
    hold, linear release over the last r s to 0."""
    env = np.full(int(n), float(s))
    na, nd, nr = (max(0, min(int(n), int(v * sr))) for v in (a, d, r))
    if na:
        env[:na] = np.arange(na) / na
    if nd:
        seg = env[na:na + nd]
        seg[:] = 1.0 + (s - 1.0) * np.arange(len(seg)) / nd
    if nr:
        env[-nr:] *= np.linspace(1.0, 0.0, nr)
    return env


def env_exp(n, sr, tau, start=1.0):
    """Exponential decay start * e^(-t/tau), length n."""
    return start * np.exp(-(np.arange(int(n)) / sr) / tau)


def _sos(kind, f, sr, order=2):
    return signal.butter(order, f, btype=kind, fs=sr, output="sos")


def lp(x, f, sr, order=2):
    """Butterworth low-pass at f Hz (SOS, zero initial state), along the last axis."""
    return signal.sosfilt(_sos("lowpass", f, sr, order), x, axis=-1)


def hp(x, f, sr, order=2):
    """Butterworth high-pass at f Hz."""
    return signal.sosfilt(_sos("highpass", f, sr, order), x, axis=-1)


def bp(x, lo, hi, sr, order=2):
    """Butterworth band-pass lo..hi Hz."""
    return signal.sosfilt(_sos("bandpass", [lo, hi], sr, order), x, axis=-1)


def _rbj(kind, f, q, sr):
    """RBJ biquad coefficients (b, a) normalised by a0. kind 'lp' | 'hp' | 'bp' (0 dB peak)."""
    w0 = TAU * f / sr
    cw, sw = np.cos(w0), np.sin(w0)
    al = sw / (2.0 * q)
    if kind == "lp":
        b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]
    elif kind == "hp":
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
    elif kind == "bp":
        b = [al, 0.0, -al]
    else:
        raise ValueError(f"unknown filter kind {kind!r}")
    a = [1 + al, -2 * cw, 1 - al]
    return np.array(b) / a[0], np.array(a) / a[0]


def sweep(x, fc_hz, sr, q=0.707, kind="lp", block=32):
    """Time-varying RBJ biquad: cutoff per sample (scalar or (n,) array), coefficients updated every
    block samples (the block's middle cutoff), filter state carried across blocks. kind 'lp' | 'hp'
    | 'bp'. Mono or stereo. Cutoff clipped to 20 Hz .. 0.45 sr."""
    x = np.asarray(x, float)
    if x.ndim == 2:
        return np.vstack([sweep(c, fc_hz, sr, q, kind, block) for c in x])
    n = len(x)
    fc = np.broadcast_to(np.asarray(fc_hz, float), (n,))
    y = np.empty(n)
    zi = np.zeros(2)
    for i in range(0, n, block):
        j = min(n, i + block)
        b, a = _rbj(kind, float(np.clip(fc[(i + j - 1) // 2], 20.0, 0.45 * sr)), q, sr)
        y[i:j], zi = signal.lfilter(b, a, x[i:j], zi=zi)
    return y


def pan(x, p):
    """Mono (n,) -> stereo (2, n) constant-power pan, p in -1..1 (scalar or per-sample).
    Unity per side at centre (sqrt 2 scaling), so a centred sound keeps its peak."""
    th = (np.clip(p, -1.0, 1.0) + 1.0) * np.pi / 4.0
    return np.vstack([x * np.cos(th), x * np.sin(th)]) * np.sqrt(2.0)


def delay(x, sr, time_s, feedback, mix):
    """Feedback delay: wet = x delayed time_s with feedback (0..<1), out = (1-mix) x + mix wet.
    Same length as x (the tail past the end is cut; pad x first to keep it)."""
    d = max(1, _n(time_s, sr))
    b = np.zeros(d + 1)
    b[d] = 1.0
    a = np.zeros(d + 1)
    a[0], a[d] = 1.0, -feedback
    wet = signal.lfilter(b, a, np.asarray(x, float), axis=-1)
    return (1.0 - mix) * x + mix * wet


def tanh_drive(x, drive):
    """tanh(drive x) / drive: soft clip with unity small-signal gain (drive > 0)."""
    return np.tanh(drive * x) / drive


# ---- starter generators (generic; a project names its own patches). Every number is an argument;
# the defaults are placeholders. Each returns mono (n,), peak 1, transient on sample 0.

def click(sr, seed, dur=0.01, f=3000.0):
    """Short high-passed noise tick: hp at f Hz, decay tau dur/3, 0.2 ms attack."""
    t = tvec(dur, sr)
    n = len(t)
    y = nrm(hp(noise(n, seed), f, sr)) * np.exp(-t / (dur / 3.0))
    return nrm(y * ramp(n, 0.0002, sr))


def thump(sr, seed, f0=60.0, f1=120.0, dur=0.3, drop=0.05):
    """Pitch-dropping sine body (kick-like): starts at f1 Hz, settles to f0 with time constant drop s,
    amplitude decay tau dur/3, 0.5 ms attack. seed unused (no noise)."""
    t = tvec(dur, sr)
    n = len(t)
    f = f0 + (f1 - f0) * np.exp(-t / drop)
    y = np.sin(phase(f, sr)) * np.exp(-t / (dur / 3.0))
    return nrm(y * ramp(n, 0.0005, sr))


def boing(sr, seed, f0=300.0, f1=900.0, dur=0.25, wobble_hz=12.0):
    """Rising glide f0 -> f1 Hz (time constant dur/4) with a decaying vibrato at wobble_hz
    (10 % depth, tau 0.7 dur), amplitude tau 0.45 dur, 1.5 ms attack. seed unused."""
    t = tvec(dur, sr)
    n = len(t)
    f = f0 + (f1 - f0) * (1.0 - np.exp(-t / (dur / 4.0)))
    f = f * (1.0 + 0.10 * np.sin(TAU * wobble_hz * t) * np.exp(-t / (0.7 * dur)))
    y = np.sin(phase(f, sr)) * np.exp(-t / (0.45 * dur))
    return nrm(y * ramp(n, 0.0015, sr))


def thwack(sr, seed, dur=0.12, tone_hz=180.0):
    """Noise burst (500..3000 Hz, tau dur/4) plus a short tone at tone_hz (tau dur/3), soft-clipped,
    0.3 ms attack (landing / impact)."""
    t = tvec(dur, sr)
    n = len(t)
    smack = nrm(bp(noise(n, seed), 500.0, 3000.0, sr)) * np.exp(-t / (dur / 4.0))
    tone = 0.6 * np.sin(TAU * tone_hz * t) * np.exp(-t / (dur / 3.0))
    return nrm(np.tanh(1.8 * (smack + tone)) * ramp(n, 0.0003, sr))


def whoosh(sr, seed, dur=0.5, f_lo=300.0, f_hi=4000.0, shape="rise"):
    """Band-swept noise (bp, q 1.2) with a sin(pi u)^1.4 amplitude bell. shape 'rise' sweeps
    f_lo -> f_hi, 'fall' f_hi -> f_lo, 'bell' up and back. Not a hit: its onset is soft."""
    t = tvec(dur, sr)
    n = len(t)
    u = np.clip(t / dur, 0.0, 1.0)
    curve = {"rise": u, "fall": 1.0 - u, "bell": np.sin(np.pi * u)}[shape]
    fc = f_lo * (f_hi / f_lo) ** curve
    y = sweep(noise(n, seed), fc, sr, q=1.2, kind="bp") * np.sin(np.pi * u) ** 1.4
    return nrm(y)


def bell(sr, seed, f_hz=880.0, dur=1.2, ratio=3.5, index=2.0):
    """FM bell: carrier f_hz, modulator ratio f_hz, index decaying with tau dur/4 (floor 0.1 index),
    amplitude tau 0.66 dur, 1 ms attack. seed unused."""
    t = tvec(dur, sr)
    n = len(t)
    idx = index * np.exp(-t / (dur / 4.0)) + 0.1 * index
    y = fm(f_hz, ratio, idx, n, sr) * np.exp(-t / (0.66 * dur))
    return nrm(y * ramp(n, 0.001, sr))


def blip(sr, seed, f_hz=1200.0, dur=0.06):
    """UI blip: sine plus 20 % third harmonic, 2 ms attack, decay tau 0.4 dur. seed unused."""
    t = tvec(dur, sr)
    n = len(t)
    ph = TAU * f_hz * t
    y = (np.sin(ph) + 0.2 * np.sin(3.0 * ph)) * np.exp(-t / (0.4 * dur))
    return nrm(y * ramp(n, 0.002, sr))


def riser(sr, seed, dur=1.5, f_lo=200.0, f_hi=6000.0):
    """Noise (bp sweep f_lo -> f_hi, exponential) plus a saw that climbs two octaves, amplitude
    envelope u^2.2 that is largest on the LAST sample (the loudest part is the end). Place it with
    Bus.add(pre=len-1, tail_ms=0) so the end sits on the hit sample; the hit masks the cut."""
    t = tvec(dur, sr)
    n = len(t)
    u = t / dur
    nz = sweep(noise(n, seed), f_lo * (f_hi / f_lo) ** u, sr, q=1.6, kind="bp")
    tone = saw(f_lo * 4.0 ** u, n, sr)
    return nrm((nrm(nz) + 0.4 * tone) * u ** 2.2)


def zap(sr, seed, dur=0.3, f0=4000.0, f1=80.0):
    """Falling square-wave zap f0 -> f1 Hz (exponential), low-pass tracking 4 f + 200 Hz,
    0.5 ms attack, amplitude (1 - u)^0.3 so it ends at 0 (power-down). seed unused."""
    t = tvec(dur, sr)
    n = len(t)
    u = t / dur
    f = f0 * (f1 / f0) ** u
    y = sweep(square(f, n, sr), 4.0 * f + 200.0, sr, q=1.0, kind="lp")
    return nrm(y * ramp(n, 0.0005, sr) * (1.0 - u) ** 0.3)


def chord(sr, notes_midi, dur, osc="saw", detune_cents=7.0, cutoff_hz=None,
          attack_s=0.01, release_s=0.05):
    """Three detuned oscillators (-detune, 0, +detune cents) per MIDI note, osc 'saw' | 'square' |
    'tri' | 'sine', optional Butterworth low-pass at cutoff_hz, cosine attack attack_s from 0 and
    cosine release release_s at the end. Mono (n,), peak 1, n = dur sr."""
    t = tvec(dur, sr)
    n = len(t)
    gen = {"saw": lambda f, k: saw(f, n, sr, ph0=k / 3.0),
           "square": lambda f, k: square(f, n, sr),
           "tri": lambda f, k: tri(f, n, sr),
           "sine": lambda f, k: sine(f, n, sr, ph0=TAU * k / 3.0)}[osc]
    y = np.zeros(n)
    for m in notes_midi:
        for k, cents in enumerate((-detune_cents, 0.0, detune_cents)):
            y += gen(mtof(m) * 2.0 ** (cents / 1200.0), k)
    if cutoff_hz:
        y = lp(y, cutoff_hz, sr)
    a = np.clip(t / max(attack_s, 1e-9), 0.0, 1.0)
    env = 0.5 - 0.5 * np.cos(np.pi * a)
    r = np.clip((t - (dur - release_s)) / max(release_s, 1e-9), 0.0, 1.0)
    env *= 0.5 + 0.5 * np.cos(np.pi * r)
    return nrm(y * env)
