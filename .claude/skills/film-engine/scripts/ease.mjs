/* ease.mjs: JS twins of filmkit/ease.py. Owner: core. No imports.
 * Same names (camelCase), same numbers, same results as the Python module. rng(seed) is mulberry32 and is
 * bit-identical to ease.mulberry32(seed); hash01, seedOf and wrap are bit-identical too. The functions that
 * use sin/cos/exp agree with Python's libm to about 1e-15. Works in Node (import) and in a browser page:
 * when loaded there it also sets globalThis.FilmEase (frames-render.mjs injects it before the page's script).
 * No number here is taste: every shape parameter is an argument the project passes.
 */
const TAU = 2 * Math.PI;

/** Mix a scalar or an array value per component. */
const mix = (a, b, u) => Array.isArray(a) ? a.map((x, i) => x + (b[i] - x) * u) : a + (b - a) * u;
const sub = (a, b) => Array.isArray(a) ? a.map((x, i) => x - b[i]) : a - b;
const scale = (a, s) => Array.isArray(a) ? a.map((x) => x * s) : a * s;

/** x limited to [a, b]. */
export function clamp(x, a = 0, b = 1) { return x < a ? a : x > b ? b : x; }
/** a + (b - a) * u, no clamp. */
export function lerp(a, b, u) { return a + (b - a) * u; }
/** 0..1 -> 3u^2 - 2u^3, clamped (AE Easy Ease at 33 % influence). */
export function smoothstep(u) { u = clamp(u); return u * u * (3 - 2 * u); }
/** 0..1 -> 6u^5 - 15u^4 + 10u^3, clamped. */
export function smootherstep(u) { u = clamp(u); return u * u * u * (u * (6 * u - 15) + 10); }
/** 0..1 -> 1 - (1-u)^3, clamped. */
export function outCubic(u) { u = clamp(u); return 1 - (1 - u) ** 3; }
/** 0..1 -> 0.5 - 0.5 cos(pi u), clamped. */
export function inOutCos(u) { u = clamp(u); return 0.5 - 0.5 * Math.cos(Math.PI * u); }

/** 0..1 with a trapezoid speed: smooth ramps over the first and last share r, cruise between. r <= 0: linear. */
export function trap(u, r = 0.25) {
  u = clamp(u);
  if (r <= 0) return u;
  let d;
  if (u < r) { const x = u / r; d = r * (x ** 3 - x ** 4 / 2); }
  else if (u <= 1 - r) { d = r / 2 + (u - r); }
  else { const x = (1 - u) / r; d = 1 - r - r * (x ** 3 - x ** 4 / 2); }
  return d / (1 - r);
}

/** 0 before a, 1 after b, linear between (a == b: a step at b). */
export function win(t, a, b) {
  if (b <= a) return t >= b ? 1 : 0;
  return clamp((t - a) / (b - a));
}

/** 0 outside [a, b], sin^2 bump of height 1 centred in the middle. */
export function bell(t, a, b) {
  if (t <= a || t >= b) return 0;
  return Math.sin(Math.PI * (t - a) / (b - a)) ** 2;
}

/** Hit envelope: 0 at tau <= 0, 1 at tau = tp, then (1 + x/decay) e^(-x/decay), ringing at period if > 0. Seconds. */
export function impulse(tau, tp = 0.04, decay = 0.07, period = 0) {
  if (tau <= 0) return 0;
  if (tau < tp) return Math.sin(0.5 * Math.PI * tau / tp);
  const x = tau - tp;
  let v = (1 + x / decay) * Math.exp(-x / decay);
  if (period) v *= Math.cos(TAU * x / period);
  return v;
}

/** Underdamped spring from start to 1 whose first peak is `peak` at tau = peakT (s). start for tau <= 0. */
export function spring(tau, start, peakT, peak) {
  if (tau <= 0) return start;
  const a0 = 1 - start;
  if (a0 === 0) return 1;
  const q = (peak - 1) / a0;
  if (q <= 0) throw new Error('spring: peak must overshoot 1 away from start');
  const k = -Math.log(q) / peakT;
  return 1 - a0 * Math.exp(-k * tau) * Math.cos(Math.PI * tau / peakT);
}

/** Step response 0 -> 1 of a damped spring (zeta damping ratio, wn rad/s); overshoots when zeta < 1. 0 for tau <= 0. */
export function springStep(tau, zeta, wn) {
  if (tau <= 0) return 0;
  if (zeta < 1) {
    const wd = wn * Math.sqrt(1 - zeta * zeta), z = zeta * wn;
    return 1 - Math.exp(-z * tau) * (Math.cos(wd * tau) + (z / wd) * Math.sin(wd * tau));
  }
  if (zeta === 1) return 1 - Math.exp(-wn * tau) * (1 + wn * tau);
  const s = wn * Math.sqrt(zeta * zeta - 1), r1 = -zeta * wn + s, r2 = -zeta * wn - s;
  return 1 - (r2 * Math.exp(r1 * tau) - r1 * Math.exp(r2 * tau)) / (r2 - r1);
}

/** keys: [[t, value]] sorted. Value at t, eased (default smoothstep) between keys, held outside. Value scalar or array. */
export function keyed(keys, t, ease = smoothstep) {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 0; i + 1 < keys.length; i++) {
    const [ta, va] = keys[i], [tb, vb] = keys[i + 1];
    if (t < tb) return mix(va, vb, tb > ta ? ease((t - ta) / (tb - ta)) : 1);
  }
  return keys[keys.length - 1][1];
}

/** keys: [[t, value]] sorted, value scalar or array. Catmull-Rom (C1) with one-sided end tangents, held outside. */
export function catmull(keys, t) {
  const ts = keys.map((k) => k[0]), ps = keys.map((k) => k[1]), n = ts.length;
  if (t <= ts[0]) return ps[0];
  if (t >= ts[n - 1]) return ps[n - 1];
  let i = 0;
  for (let j = 0; j < n - 1; j++) if (ts[j] <= t) i = j;
  const tan = (j) => { const a = Math.max(0, j - 1), b = Math.min(n - 1, j + 1); return scale(sub(ps[b], ps[a]), 1 / (ts[b] - ts[a])); };
  const h = ts[i + 1] - ts[i], u = (t - ts[i]) / h;
  const c0 = 2 * u ** 3 - 3 * u ** 2 + 1, c1 = (u ** 3 - 2 * u ** 2 + u) * h;
  const c2 = -2 * u ** 3 + 3 * u ** 2, c3 = (u ** 3 - u ** 2) * h;
  const m0 = tan(i), m1 = tan(i + 1);
  if (Array.isArray(ps[i])) return ps[i].map((p, k) => c0 * p + c1 * m0[k] + c2 * ps[i + 1][k] + c3 * m1[k]);
  return c0 * ps[i] + c1 * m0 + c2 * ps[i + 1] + c3 * m1;
}

/** Angle -> (-pi, pi]. */
export function wrap(a) { return a - TAU * Math.ceil((a - Math.PI) / TAU); }
/** The angle equal to target mod 2pi that is nearest current. */
export function unwrapTo(target, current) { return current + wrap(target - current); }

/** Deterministic integer hash -> [0, 1). i, j integers (low 32 bits matter). Identical to filmkit.ease.hash01. */
export function hash01(i, j) {
  let x = (Math.imul(i, 73856093) ^ Math.imul(j, 19349663) ^ 0x5BD1E995) >>> 0;
  x = (x ^ (x >>> 16)) >>> 0;
  x = Math.imul(x, 0x45D9F3B) >>> 0;
  x = (x ^ (x >>> 16)) >>> 0;
  x = Math.imul(x, 0x45D9F3B) >>> 0;
  x = (x ^ (x >>> 16)) >>> 0;
  return x / 4294967296;
}

/** Seeded RNG, mulberry32: next() -> [0, 1). Identical to filmkit.ease.mulberry32. */
export function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6D2B79F5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const CRC_TABLE = (() => {
  const table = new Int32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c;
  }
  return table;
})();

/** IEEE CRC-32 of the UTF-8 bytes of s, as zlib.crc32 gives it. */
export function crc32(s) {
  const bytes = new TextEncoder().encode(s);
  let c = -1;
  for (const b of bytes) c = CRC_TABLE[(c ^ b) & 0xFF] ^ (c >>> 8);
  return (c ^ -1) >>> 0;
}

/** crc32(kind) + n, masked to 32 bits: the same seed filmkit.ease.seed_of gives. */
export function seedOf(kind, n = 0) { return (crc32(kind) + n) >>> 0; }

export const FilmEase = { TAU, clamp, lerp, smoothstep, smootherstep, outCubic, inOutCos, trap, win, bell,
  impulse, spring, springStep, keyed, catmull, wrap, unwrapTo, hash01, rng, crc32, seedOf };
if (typeof globalThis !== 'undefined') globalThis.FilmEase = FilmEase;
export default FilmEase;
