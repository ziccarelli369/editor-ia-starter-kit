"""ease: scalar easing, envelopes, keyed tracks, seeded RNG. Owner: core. Standard library only.

Every function here has a twin with the same name and the same numbers in
scripts/ease.mjs. u is a unitless share 0..1 unless stated. tau is seconds
since an event. mulberry32, hash01, seed_of and wrap are bit-identical to the
JS twins (integer math masked to 32 bits; Math.imul semantics). The other
functions use libm sin/cos/exp and agree with V8 to about 1e-15.

No number here is taste: every shape parameter (tp, decay, period, peak_t,
peak, zeta, wn, r) is an argument the project passes.
"""
import math
import zlib

TAU = 2.0 * math.pi


def clamp(x, a=0.0, b=1.0):
    """-> x limited to [a, b]."""
    return a if x < a else b if x > b else x


def lerp(a, b, u):
    """-> a + (b - a) * u (no clamp)."""
    return a + (b - a) * u


def _mix(a, b, u):
    """lerp for a scalar or a tuple/list value (per component)."""
    if isinstance(a, (tuple, list)):
        return tuple(a[i] + (b[i] - a[i]) * u for i in range(len(a)))
    return a + (b - a) * u


def smoothstep(u):
    """0..1 -> 3u^2 - 2u^3, clamped. Equals AE Easy Ease at 33 % influence."""
    u = clamp(u)
    return u * u * (3.0 - 2.0 * u)


def smootherstep(u):
    """0..1 -> 6u^5 - 15u^4 + 10u^3, clamped."""
    u = clamp(u)
    return u * u * u * (u * (6.0 * u - 15.0) + 10.0)


def out_cubic(u):
    """0..1 -> 1 - (1-u)^3, clamped."""
    u = clamp(u)
    return 1.0 - (1.0 - u) ** 3


def in_out_cos(u):
    """0..1 -> 0.5 - 0.5 cos(pi u), clamped."""
    u = clamp(u)
    return 0.5 - 0.5 * math.cos(math.pi * u)


def trap(u, r=0.25):
    """0..1 with a trapezoid speed: smooth ramps over the first and last share r, cruise between.

    Peak speed is 1 / (1 - r) of the mean (1.33 at r = 0.25; smoothstep is 1.5,
    smootherstep 1.875). r in (0, 0.5]; r <= 0 gives a linear ramp.
    """
    u = clamp(u)
    if r <= 0.0:
        return u
    if u < r:
        x = u / r
        d = r * (x ** 3 - x ** 4 / 2.0)
    elif u <= 1.0 - r:
        d = r / 2.0 + (u - r)
    else:
        x = (1.0 - u) / r
        d = 1.0 - r - r * (x ** 3 - x ** 4 / 2.0)
    return d / (1.0 - r)


def win(t, a, b):
    """0 before a, 1 after b, linear between (a == b: a step at b)."""
    if b <= a:
        return 1.0 if t >= b else 0.0
    return clamp((t - a) / (b - a))


def bell(t, a, b):
    """0 outside [a, b], sin^2 bump of height 1 centred in the middle."""
    if t <= a or t >= b:
        return 0.0
    return math.sin(math.pi * (t - a) / (b - a)) ** 2


def impulse(tau, tp=0.04, decay=0.07, period=0.0):
    """Hit envelope: 0 at tau <= 0, 1 at tau = tp, then (1 + x/decay) e^(-x/decay), ringing at period if > 0.

    tau, tp, decay, period in seconds; x = tau - tp. The rise is a quarter sine.
    """
    if tau <= 0.0:
        return 0.0
    if tau < tp:
        return math.sin(0.5 * math.pi * tau / tp)
    x = tau - tp
    v = (1.0 + x / decay) * math.exp(-x / decay)
    if period:
        v *= math.cos(TAU * x / period)
    return v


def spring(tau, start, peak_t, peak):
    """Underdamped spring from start to 1 whose first peak is `peak` at tau = peak_t. start for tau <= 0.

    tau, peak_t in seconds. peak must overshoot 1 on the side away from start
    ((peak - 1) / (1 - start) > 0); start == 1 returns 1.
    """
    if tau <= 0.0:
        return start
    a0 = 1.0 - start
    if a0 == 0.0:
        return 1.0
    q = (peak - 1.0) / a0
    if q <= 0.0:
        raise ValueError("spring: peak must overshoot 1 away from start")
    k = -math.log(q) / peak_t
    return 1.0 - a0 * math.exp(-k * tau) * math.cos(math.pi * tau / peak_t)


def spring_step(tau, zeta, wn):
    """Step response 0 -> 1 of a damped spring (zeta damping ratio, wn rad/s); overshoots when zeta < 1.

    tau in seconds; 0 for tau <= 0. zeta == 1 is critically damped, > 1 overdamped.
    """
    if tau <= 0.0:
        return 0.0
    if zeta < 1.0:
        wd = wn * math.sqrt(1.0 - zeta * zeta)
        z = zeta * wn
        return 1.0 - math.exp(-z * tau) * (math.cos(wd * tau) + (z / wd) * math.sin(wd * tau))
    if zeta == 1.0:
        return 1.0 - math.exp(-wn * tau) * (1.0 + wn * tau)
    s = wn * math.sqrt(zeta * zeta - 1.0)
    r1, r2 = -zeta * wn + s, -zeta * wn - s
    return 1.0 - (r2 * math.exp(r1 * tau) - r1 * math.exp(r2 * tau)) / (r2 - r1)


def keyed(keys, t, ease=None):
    """keys: [(t, value)] sorted. -> value at t, eased (default smoothstep) between keys, held outside.

    value is a scalar or a tuple (mixed per component). Two keys at one t make a step.
    """
    ease = smoothstep if ease is None else ease
    if t <= keys[0][0]:
        return keys[0][1]
    for (ta, va), (tb, vb) in zip(keys, keys[1:]):
        if t < tb:
            return _mix(va, vb, ease((t - ta) / (tb - ta)) if tb > ta else 1.0)
    return keys[-1][1]


def catmull(keys, t):
    """keys: [(t, value)] sorted, value scalar or tuple. -> Catmull-Rom with one-sided end tangents.

    C1 through every key; held outside the key range; one key returns it.
    """
    ts = [k[0] for k in keys]
    ps = [k[1] for k in keys]
    if t <= ts[0]:
        return ps[0]
    if t >= ts[-1]:
        return ps[-1]
    i = max(j for j in range(len(ts) - 1) if ts[j] <= t)

    def tan(j):
        a, b = max(0, j - 1), min(len(ts) - 1, j + 1)
        return _scale(_sub(ps[b], ps[a]), 1.0 / (ts[b] - ts[a]))

    h = ts[i + 1] - ts[i]
    u = (t - ts[i]) / h
    c0 = 2 * u ** 3 - 3 * u ** 2 + 1
    c1 = (u ** 3 - 2 * u ** 2 + u) * h
    c2 = -2 * u ** 3 + 3 * u ** 2
    c3 = (u ** 3 - u ** 2) * h
    m0, m1 = tan(i), tan(i + 1)
    if isinstance(ps[i], (tuple, list)):
        return tuple(c0 * ps[i][k] + c1 * m0[k] + c2 * ps[i + 1][k] + c3 * m1[k] for k in range(len(ps[i])))
    return c0 * ps[i] + c1 * m0 + c2 * ps[i + 1] + c3 * m1


def _sub(a, b):
    if isinstance(a, (tuple, list)):
        return tuple(a[k] - b[k] for k in range(len(a)))
    return a - b


def _scale(a, s):
    if isinstance(a, (tuple, list)):
        return tuple(x * s for x in a)
    return a * s


def wrap(a):
    """Angle -> (-pi, pi]."""
    return a - TAU * math.ceil((a - math.pi) / TAU)


def unwrap_to(target, current):
    """-> the angle equal to target mod 2pi that is nearest current (current + wrap(target - current))."""
    return current + wrap(target - current)


def unwrap_series(values):
    """[angles rad] -> the same angles made continuous: each one shifted by a multiple of 2 pi to sit
    within pi of the one before (a baked rotation channel; LINEAR keys then never spin the long way)."""
    out = list(values)
    for k in range(1, len(out)):
        out[k] = unwrap_to(out[k], out[k - 1])
    return out


def hash01(i, j):
    """Deterministic integer hash -> [0, 1). Same result in every Python and in JS.

    i, j are integers (any sign; only their low 32 bits matter).
    """
    x = (i * 73856093 ^ j * 19349663 ^ 0x5BD1E995) & 0xFFFFFFFF
    x ^= x >> 16
    x = (x * 0x45D9F3B) & 0xFFFFFFFF
    x ^= x >> 16
    x = (x * 0x45D9F3B) & 0xFFFFFFFF
    x ^= x >> 16
    return x / 4294967296.0


def mulberry32(seed):
    """Seeded RNG. -> next() giving floats in [0, 1). Bit-identical to ease.mjs rng(seed)."""
    s = seed & 0xFFFFFFFF

    def imul(a, b):
        return (a * b) & 0xFFFFFFFF

    def rnd():
        nonlocal s
        s = (s + 0x6D2B79F5) & 0xFFFFFFFF
        t = s
        t = imul(t ^ (t >> 15), t | 1)
        t ^= (t + imul(t ^ (t >> 7), t | 61)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    return rnd


def seed_of(kind, n=0):
    """Stable seed for event kind + occurrence n: zlib.crc32(kind) + n, masked to 32 bits."""
    return (zlib.crc32(kind.encode("utf-8")) + n) & 0xFFFFFFFF
