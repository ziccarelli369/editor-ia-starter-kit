/* comp-kit.mjs: browser canvas helpers for the per-frame result page. Owner: node.
 * Imports ./ease.mjs only. Loaded into the page by frames-render.mjs as window.FilmKit (and also
 * importable in Node for tests). Every function is a pure drawing or measuring helper; colours, fonts,
 * sizes and timings are arguments. Boxes are {l, t, r, b} in canvas px. Nothing here keeps time:
 * the page draws frame f from timeline.frames[f-1] and calls these with that state.
 *
 * Pure (Node-safe, tested in tests/film-engine.test.mjs): box helpers, pad4, timecode, typeOnPrefixes
 * (with any object that has measureText), makeRibbon except shape()/path() (Path2D).
 * Browser-only: makeCanvas, loadFonts, drawGlow, drawSelection, drawPenHandles, lumaStats,
 * drawTimecode, contact.
 */
import { rng, smoothstep, springStep } from './ease.mjs';

export { rng, smoothstep, springStep };

// ---------------------------------------------------------------- boxes and numbers
/** Box in canvas px: l, t inclusive top-left; r, b bottom-right. */
export const box = (l, t, r, b) => ({ l, t, r, b });
/** Box grown by p px on every side (negative shrinks). */
export function grow(b, p) { return box(b.l - p, b.t - p, b.r + p, b.b + p); }
/** Box moved by dx, dy. */
export function shift(b, dx, dy) { return box(b.l + dx, b.t + dy, b.r + dx, b.b + dy); }
/** Smallest box holding a and b; either may be null (null, null -> null). */
export function union(a, b) {
  if (!a) return b || null;
  if (!b) return a;
  return box(Math.min(a.l, b.l), Math.min(a.t, b.t), Math.max(a.r, b.r), Math.max(a.b, b.b));
}
/** True when b lies inside a W x H canvas (edges included). */
export function inFrame(b, W, H) { return b.l >= 0 && b.t >= 0 && b.r <= W && b.b <= H; }
/** Smallest distance (px) from b to a W x H canvas edge; negative when b leaves the frame. */
export function margin(b, W, H) { return Math.min(b.l, b.t, W - b.r, H - b.b); }
/** Frame number as a 4-digit string: 7 -> '0007' (image sequences are 1-based, 0001 = t 0). */
export const pad4 = (n) => String(n).padStart(4, '0');

/** Seconds -> 'H:MM:SS:FF'. Whole frames = floor(seconds * fps + 0.5) (half frames round up,
 *  the same rule as timebase.frame); FF = frames % fps. Negative seconds clamp to 0. */
export function timecode(seconds, fps) {
  const total = Math.max(0, Math.floor(seconds * fps + 0.5));
  const ff = total % fps, s = Math.floor(total / fps);
  const two = (v) => String(v).padStart(2, '0');
  return `${Math.floor(s / 3600)}:${two(Math.floor(s / 60) % 60)}:${two(s % 60)}:${two(ff)}`;
}

// ---------------------------------------------------------------- canvases and fonts
/** Offscreen canvas of w x h px (browser only). */
export function makeCanvas(w, h) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  return c;
}

/** Prove font faces before the first pixel. faces = ['900 100px CompTitle', ...] (CSS font strings
 *  naming families bound by @font-face with local() or url(); a generic family has no FontFace and
 *  counts as missing). Resolves to the faces list when every face loads with status 'loaded';
 *  throws listing the missing faces. Never a silent fallback. */
export async function loadFonts(faces, sample = 'Ag0') {
  const missing = [];
  for (const f of faces) {
    let loaded = [];
    try { loaded = await document.fonts.load(f, sample); } catch (e) { loaded = []; }
    if (!loaded.length || loaded.some((x) => x.status !== 'loaded')) missing.push(f);
  }
  await document.fonts.ready;
  if (missing.length) throw new Error('fonts not available: ' + missing.join(', '));
  return faces;
}

// ---------------------------------------------------------------- type-on text
/** Ink metrics of every prefix of text, the full ink centred on anchor [x, y].
 *  ctx: a 2D context (or any object with font, letterSpacing and measureText returning width,
 *  actualBoundingBoxLeft/Right/Ascent/Descent). font: CSS font string. trackingPx: letter spacing
 *  in px (set on ctx while measuring, restored to '0px' after). baselineOffset: baseline y below
 *  anchor y (px). Ascent and descent are those of the full text, so prefix boxes share one top and
 *  bottom and never jump as letters arrive.
 *  -> {pen: [x, y] (fillText position of every prefix), ascent, descent,
 *      prefixes: [{text, ink: box | null (empty prefix), caretX}] (length text.length + 1)}.
 *  caretX = pen x + advance of the prefix minus the trailing tracking; the page adds its own gap. */
export function typeOnPrefixes(ctx, font, trackingPx, text, anchor, baselineOffset = 0) {
  ctx.font = font;
  ctx.letterSpacing = trackingPx + 'px';
  const m = ctx.measureText(text);
  const ink = m.actualBoundingBoxLeft + m.actualBoundingBoxRight;
  const penX = anchor[0] - ink / 2 + m.actualBoundingBoxLeft;
  const penY = anchor[1] + baselineOffset;
  const ascent = m.actualBoundingBoxAscent, descent = m.actualBoundingBoxDescent;
  const prefixes = [];
  for (let k = 0; k <= text.length; k++) {
    const s = text.slice(0, k);
    const mk = ctx.measureText(s);
    prefixes.push({
      text: s,
      ink: k === 0 ? null : box(penX - mk.actualBoundingBoxLeft, penY - ascent, penX + mk.actualBoundingBoxRight, penY + descent),
      caretX: penX + (k === 0 ? 0 : mk.width - trackingPx),
    });
  }
  ctx.letterSpacing = '0px';
  return { pen: [penX, penY], ascent, descent, prefixes };
}

// ---------------------------------------------------------------- trim-path ribbon
const lerp2 = (a, b, u) => a + (b - a) * u;

/** Brush ribbon along a cubic Bezier path, drawn trimmed to an arc length (an AE trim path).
 *  anchors: [{p: [x, y], i?: [x, y], o?: [x, y]}] in canvas px; i/o are the in/out handles
 *  (missing handle = the anchor itself, a straight join). widthFn(share, arc) -> brush width px at
 *  share 0..1 of the length. n: sample points over the whole path (>= 2 per segment).
 *  -> {points: [{x, y, s, nx, ny, w}], length,
 *      pointAt(upTo) -> {x, y, nx, ny, w} on the centre line at arc length upTo (clamped),
 *      centre(dx, dy, upTo) -> [[x, y], ...] centre polyline up to upTo, moved by dx, dy,
 *      outline(dx, dy, upTo) -> {left: [[x, y]], right: [[x, y]], start, end} ribbon edges,
 *      box(dx, dy, upTo) -> box of the ribbon drawn to upTo, caps included,
 *      shape(dx, dy, upTo) -> [Path2D ribbon, Path2D capStart, Path2D capEnd] (fill each one
 *        on its own, so windings never cancel),
 *      path(dx, dy, upTo) -> {path: Path2D centre line, tip: [x, y]}}.
 *  Everything but shape() and path() is pure math (no Path2D), so Node can test it. */
export function makeRibbon(anchors, widthFn, n = 240) {
  if (!anchors || anchors.length < 2) throw new Error('makeRibbon: at least two anchors');
  const segs = [];
  for (let k = 0; k < anchors.length - 1; k++) {
    const a = anchors[k], b = anchors[k + 1];
    segs.push([a.p, a.o || a.p, b.i || b.p, b.p]);
  }
  const perSeg = Math.max(2, Math.ceil(n / segs.length));
  const pts = [{ x: segs[0][0][0], y: segs[0][0][1], s: 0 }];
  for (const [p0, c1, c2, p1] of segs) {
    for (let j = 1; j <= perSeg; j++) {
      const u = j / perSeg, v = 1 - u;
      const x = v * v * v * p0[0] + 3 * v * v * u * c1[0] + 3 * v * u * u * c2[0] + u * u * u * p1[0];
      const y = v * v * v * p0[1] + 3 * v * v * u * c1[1] + 3 * v * u * u * c2[1] + u * u * u * p1[1];
      const last = pts[pts.length - 1];
      pts.push({ x, y, s: last.s + Math.hypot(x - last.x, y - last.y) });
    }
  }
  const length = pts[pts.length - 1].s;
  const width = (arc) => widthFn(length ? arc / length : 0, arc);
  for (let i = 0; i < pts.length; i++) {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
    const tx = b.x - a.x, ty = b.y - a.y, len = Math.hypot(tx, ty) || 1;
    pts[i].nx = -ty / len; pts[i].ny = tx / len;
    pts[i].w = width(pts[i].s);
  }

  function pointAt(upTo) {
    upTo = Math.max(0, Math.min(length, upTo));
    let i = 1;
    while (i < pts.length - 1 && pts[i].s < upTo) i++;
    const a = pts[i - 1], b = pts[i], u = (upTo - a.s) / (b.s - a.s || 1);
    return { x: lerp2(a.x, b.x, u), y: lerp2(a.y, b.y, u), nx: a.nx, ny: a.ny, w: width(upTo) };
  }
  /** Sample points with s < upTo, then the interpolated end point. */
  function trimmed(upTo) {
    upTo = Math.max(0, Math.min(length, upTo));
    const out = [];
    for (const p of pts) { if (p.s >= upTo) break; out.push(p); }
    out.push(pointAt(upTo));
    return out;
  }
  function centre(dx, dy, upTo) { return trimmed(upTo).map((p) => [p.x + dx, p.y + dy]); }
  function outline(dx, dy, upTo) {
    const L = trimmed(upTo);
    const left = L.map((p) => [p.x + p.nx * p.w / 2 + dx, p.y + p.ny * p.w / 2 + dy]);
    const right = L.map((p) => [p.x - p.nx * p.w / 2 + dx, p.y - p.ny * p.w / 2 + dy]);
    return { left, right, start: L[0], end: L[L.length - 1] };
  }
  function bbox(dx, dy, upTo) {
    let b = null;
    for (const p of trimmed(upTo)) b = union(b, box(p.x - p.w / 2 + dx, p.y - p.w / 2 + dy, p.x + p.w / 2 + dx, p.y + p.w / 2 + dy));
    return b;
  }
  function shape(dx, dy, upTo) {
    const o = outline(dx, dy, upTo);
    const path = new Path2D();
    o.left.forEach(([x, y], i) => (i ? path.lineTo(x, y) : path.moveTo(x, y)));
    for (let i = o.right.length - 1; i >= 0; i--) path.lineTo(o.right[i][0], o.right[i][1]);
    path.closePath();
    const cap = (p) => { const c = new Path2D(); c.arc(p.x + dx, p.y + dy, p.w / 2, 0, Math.PI * 2); return c; };
    return [path, cap(o.start), cap(o.end)];
  }
  function path(dx, dy, upTo) {
    const c = centre(dx, dy, upTo), p = new Path2D();
    c.forEach(([x, y], i) => (i ? p.lineTo(x, y) : p.moveTo(x, y)));
    return { path: p, tip: c[c.length - 1] };
  }
  return { points: pts, length, pointAt, centre, outline, box: bbox, shape, path };
}

// ---------------------------------------------------------------- glow
const glowCache = new WeakMap();

/** Multi-resolution glow of srcCanvas added onto ctx with 'lighter': a tight blur of the layer's
 *  own colours at half resolution plus a wide blur at quarter resolution, tinted when opts.tint is a
 *  colour (source-in). k scales every alpha (0 = nothing). opts (every value a placeholder the page
 *  sets): tightPx 3.5, widePx 14, tint null, tightAlpha 0.5, wideAlphas [0.75, 0.55] (the wide
 *  halo is drawn once per entry). Work canvases are cached per srcCanvas. Browser only. */
export function drawGlow(ctx, srcCanvas, k, opts = {}) {
  if (!(k > 0)) return;
  const o = { tightPx: 3.5, widePx: 14, tint: null, tightAlpha: 0.5, wideAlphas: [0.75, 0.55], ...opts };
  const W = srcCanvas.width, H = srcCanvas.height;
  let c = glowCache.get(srcCanvas);
  if (!c || c.W !== W || c.H !== H) {
    c = { W, H, half: makeCanvas(W / 2, H / 2), q1: makeCanvas(W / 4, H / 4), q2: makeCanvas(W / 4, H / 4) };
    glowCache.set(srcCanvas, c);
  }
  const h = c.half.getContext('2d'), q1 = c.q1.getContext('2d'), q2 = c.q2.getContext('2d');
  h.clearRect(0, 0, W / 2, H / 2);
  h.filter = `blur(${o.tightPx}px)`;
  h.drawImage(srcCanvas, 0, 0, W / 2, H / 2);
  h.filter = 'none';
  q1.clearRect(0, 0, W / 4, H / 4);
  q1.globalCompositeOperation = 'source-over';
  q1.drawImage(srcCanvas, 0, 0, W / 4, H / 4);
  if (o.tint) {
    q1.globalCompositeOperation = 'source-in';
    q1.fillStyle = o.tint;
    q1.fillRect(0, 0, W / 4, H / 4);
    q1.globalCompositeOperation = 'source-over';
  }
  q2.clearRect(0, 0, W / 4, H / 4);
  q2.filter = `blur(${o.widePx}px)`;
  q2.drawImage(c.q1, 0, 0);
  q2.filter = 'none';
  ctx.save();
  ctx.globalCompositeOperation = 'lighter';
  ctx.imageSmoothingQuality = 'high';
  for (const a of o.wideAlphas) {
    ctx.globalAlpha = Math.min(1, Math.max(0, a * k));
    ctx.drawImage(c.q2, 0, 0, W, H);
  }
  ctx.globalAlpha = Math.min(1, Math.max(0, o.tightAlpha * k));
  ctx.drawImage(c.half, 0, 0, W, H);
  ctx.restore();
}

// ---------------------------------------------------------------- app overlays
/** Selection box with 8 handles and an optional anchor crosshair, in an app's overlay style.
 *  b: box; color: CSS colour; alpha 0..1; anchor: [x, y] or null. Sizes are given in display px
 *  (what the viewer shows) and divided by displayScale (shown px per canvas px, e.g. 0.3 for a
 *  viewer at 30 %): sizes = {line 1, handle 5, anchorR 3.5, cross 7, edge 'rgba(0,0,0,0.6)'}. */
export function drawSelection(ctx, b, color, alpha, anchor = null, displayScale = 1, sizes = {}) {
  if (!(alpha > 0)) return;
  const z = { line: 1, handle: 5, anchorR: 3.5, cross: 7, edge: 'rgba(0,0,0,0.6)', ...sizes };
  const k = 1 / displayScale, line = z.line * k, h = z.handle * k;
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = color;
  ctx.lineWidth = line;
  ctx.strokeRect(b.l, b.t, b.r - b.l, b.b - b.t);
  const mx = (b.l + b.r) / 2, my = (b.t + b.b) / 2;
  for (const [x, y] of [[b.l, b.t], [mx, b.t], [b.r, b.t], [b.r, my], [b.r, b.b], [mx, b.b], [b.l, b.b], [b.l, my]]) {
    ctx.fillStyle = color;
    ctx.fillRect(x - h / 2, y - h / 2, h, h);
    ctx.strokeStyle = z.edge;
    ctx.lineWidth = line / 2;
    ctx.strokeRect(x - h / 2, y - h / 2, h, h);
  }
  if (anchor) {
    const [x, y] = anchor, r = z.anchorR * k, c = z.cross * k;
    const cross = () => {
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.moveTo(x - c, y); ctx.lineTo(x + c, y);
      ctx.moveTo(x, y - c); ctx.lineTo(x, y + c);
      ctx.stroke();
    };
    ctx.strokeStyle = z.edge; ctx.lineWidth = line * 2; cross();
    ctx.strokeStyle = color; ctx.lineWidth = line * 0.8; cross();
  }
  ctx.restore();
}

/** Pen path overlay: the whole path thin, tangent handles, square anchors filled up to progress
 *  (0..1 share of the anchors reached) and hollow ahead. anchors: [{p, i?, o?}] in canvas px (shift
 *  them yourself); path: Path2D of the full centre line (ribbon.path(dx, dy, ribbon.length).path).
 *  Sizes in display px over displayScale: {line 1, handleLine 0.8, handleR 2.3, anchor 5,
 *  hollow null (fill colour of unreached anchors; null = no fill)}. */
export function drawPenHandles(ctx, anchors, path, alpha, progress, color, displayScale = 1, sizes = {}) {
  if (!(alpha > 0)) return;
  const z = { line: 1, handleLine: 0.8, handleR: 2.3, anchor: 5, hollow: null, ...sizes };
  const k = 1 / displayScale;
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = color;
  ctx.lineWidth = z.line * k;
  ctx.stroke(path);
  for (const a of anchors) {
    for (const h of [a.i, a.o]) {
      if (!h) continue;
      ctx.strokeStyle = color; ctx.lineWidth = z.handleLine * k;
      ctx.beginPath(); ctx.moveTo(a.p[0], a.p[1]); ctx.lineTo(h[0], h[1]); ctx.stroke();
      ctx.fillStyle = color;
      ctx.beginPath(); ctx.arc(h[0], h[1], z.handleR * k, 0, Math.PI * 2); ctx.fill();
    }
  }
  const last = Math.max(1, anchors.length - 1), s = z.anchor * k;
  anchors.forEach((a, i) => {
    const reached = i / last <= progress + 1e-6;
    const x = a.p[0] - s / 2, y = a.p[1] - s / 2;
    if (reached || z.hollow) { ctx.fillStyle = reached ? color : z.hollow; ctx.fillRect(x, y, s, s); }
    ctx.strokeStyle = color; ctx.lineWidth = z.line * k;
    ctx.strokeRect(x, y, s, s);
  });
  ctx.restore();
}

// ---------------------------------------------------------------- measurement
/** Rec.709 luminance mean and standard deviation (0..255) of ctx's canvas. step 1 reads every
 *  pixel; step s reads every s-th column of every s-th row (faster, approximate). */
export function lumaStats(ctx, step = 1) {
  const W = ctx.canvas.width, H = ctx.canvas.height;
  const d = ctx.getImageData(0, 0, W, H).data;
  let s = 0, s2 = 0, n = 0;
  for (let y = 0; y < H; y += step) {
    for (let x = 0; x < W; x += step) {
      const i = (y * W + x) * 4;
      const l = 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
      s += l; s2 += l * l; n++;
    }
  }
  const mean = n ? s / n : 0;
  return { mean, std: Math.sqrt(Math.max(0, (n ? s2 / n : 0) - mean * mean)) };
}

// ---------------------------------------------------------------- timecode texture
const tcCache = new Map();

/** Draw text into a w x h texture with the baseline fixed by a reference string, so digits never
 *  jitter vertically from frame to frame. spec: {w, h, font, color, bg, pad (left px, 0), ref
 *  ('0:00:00:00')}. bg must equal the flat colour the UI texture leaves under the rect, so the
 *  per-frame plane blends in. -> PNG data URL. The canvas is cached per w x h. */
export function drawTimecode(spec, text) {
  const key = `${spec.w}x${spec.h}`;
  let c = tcCache.get(key);
  if (!c) { c = makeCanvas(spec.w, spec.h); tcCache.set(key, c); }
  const g = c.getContext('2d');
  g.fillStyle = spec.bg;
  g.fillRect(0, 0, spec.w, spec.h);
  g.font = spec.font;
  g.fillStyle = spec.color;
  g.textBaseline = 'alphabetic';
  const m = g.measureText(spec.ref || '0:00:00:00');
  const y = spec.h / 2 + (m.actualBoundingBoxAscent - m.actualBoundingBoxDescent) / 2;
  g.fillText(text, spec.pad || 0, Math.round(y));
  return c.toDataURL('image/png');
}

// ---------------------------------------------------------------- contact sheet
/** Tile image data URLs cols wide, each cell x cell with a label strip below. Review-only greys.
 *  -> PNG data URL of the sheet. Browser only. */
export async function contact(urls, labels, cols = 5, cell = [384, 216], labelH = 30, gap = 4, font = '14px sans-serif') {
  const imgs = await Promise.all(urls.map((u) => new Promise((res, rej) => {
    const im = new Image();
    im.onload = () => res(im);
    im.onerror = () => rej(new Error('contact: image failed to load'));
    im.src = u;
  })));
  const [cw, ch] = cell, rows = Math.ceil(imgs.length / cols);
  const c = makeCanvas(cols * (cw + gap) + gap, rows * (ch + labelH + gap) + gap), g = c.getContext('2d');
  g.fillStyle = '#0c0c0c';
  g.fillRect(0, 0, c.width, c.height);
  imgs.forEach((im, i) => {
    const x = gap + (i % cols) * (cw + gap), y = gap + Math.floor(i / cols) * (ch + labelH + gap);
    g.imageSmoothingQuality = 'high';
    g.drawImage(im, x, y, cw, ch);
    g.fillStyle = '#1d1d1d';
    g.fillRect(x, y + ch, cw, labelH);
    g.font = font;
    g.fillStyle = '#d8d8d8';
    g.textBaseline = 'middle';
    g.fillText(labels[i] || '', x + 8, y + ch + labelH / 2);
  });
  return c.toDataURL('image/png');
}

export const FilmKit = { box, grow, shift, union, inFrame, margin, pad4, timecode, makeCanvas, loadFonts,
  typeOnPrefixes, makeRibbon, drawGlow, drawSelection, drawPenHandles, lumaStats, drawTimecode, contact,
  rng, smoothstep, springStep };
if (typeof globalThis !== 'undefined') globalThis.FilmKit = FilmKit;
export default FilmKit;
