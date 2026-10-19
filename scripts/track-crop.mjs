#!/usr/bin/env node
// track-crop.mjs - propose 9:16 crop keyframes that follow the action in landscape footage.
// Usage: node scripts/track-crop.mjs <video> --out <keyframes.json> [--start <s>] [--end <s>]
//        [--step 0.5] [--aspect 9:16] [--smooth 3]
// Method: 1) decode a 160px-wide grayscale stream at 2 samples per step; 2) per sample pair, take the
// per-pixel absolute difference and the motion mass per column; 3) the target center is the
// motion-weighted mean column (static shot: keep the previous center; first sample: brightness subject);
// 4) smooth with a moving median then a moving average, clamp the window inside the frame, emit JSON + ffmpeg crop.
import { spawnSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import path from 'node:path';

const NOISE = 8;        // per-pixel difference below this is compression noise
const MIN_MOTION = 0.3; // mean motion per pixel below this counts as a static shot
const SMALL_W = 160;

function parseArgs(argv) {
  const opts = { start: 0, end: null, step: 0.5, aspect: '9:16', smooth: 3, out: null, video: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) opts[a.slice(2)] = argv[++i];
    else opts.video = a;
  }
  if (!opts.video || !opts.out) {
    console.error('Usage: node scripts/track-crop.mjs <video> --out <keyframes.json> [--start s] [--end s] [--step 0.5] [--aspect 9:16] [--smooth 3]');
    process.exit(1);
  }
  for (const k of ['start', 'step', 'smooth']) opts[k] = Number(opts[k]);
  if (opts.end !== null) opts.end = Number(opts.end);
  return opts;
}

function probe(video) {
  const r = spawnSync('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_entries',
    'stream=width,height,r_frame_rate:format=duration', '-of', 'json', video], { encoding: 'utf8' });
  if (r.status !== 0) throw new Error(`ffprobe failed: ${r.stderr}`);
  const j = JSON.parse(r.stdout);
  const s = j.streams[0];
  const [num, den] = s.r_frame_rate.split('/').map(Number);
  return { width: s.width, height: s.height, fps: num / (den || 1), duration: Number(j.format.duration) };
}

function decodeGray(video, start, end, rate, w, h) {
  const r = spawnSync('ffmpeg', ['-v', 'error', '-ss', String(start), '-t', String(end - start), '-i', video,
    '-vf', `fps=${rate},scale=${w}:${h},format=gray`, '-f', 'rawvideo', '-'],
    { maxBuffer: 1 << 30 });
  if (r.status !== 0) throw new Error(`ffmpeg decode failed: ${r.stderr}`);
  const size = w * h, frames = [];
  for (let o = 0; o + size <= r.stdout.length; o += size) frames.push(r.stdout.subarray(o, o + size));
  return frames;
}

// Motion mass per column between two frames; returns { center, motion } in small-frame columns.
function motionCenter(a, b, w, h) {
  const cols = new Float64Array(w);
  let total = 0;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const d = Math.abs(a[y * w + x] - b[y * w + x]) - NOISE;
      if (d > 0) { cols[x] += d; total += d; }
    }
  }
  let sw = 0, sx = 0;
  for (let x = 0; x < w; x++) { const m = cols[x] * cols[x]; sw += m; sx += m * (x + 0.5); }
  return { center: sw > 0 ? sx / sw : null, motion: total / (w * h) };
}

// Brightness subject: columns whose mean brightness differs most from the frame median.
function subjectCenter(f, w, h) {
  const median = Array.from(f).sort((p, q) => p - q)[f.length >> 1];
  let sw = 0, sx = 0;
  for (let x = 0; x < w; x++) {
    let s = 0;
    for (let y = 0; y < h; y++) s += f[y * w + x];
    const dev = Math.abs(s / h - median) ** 2;
    sw += dev; sx += dev * (x + 0.5);
  }
  return sw > 0 ? sx / sw : w / 2;
}

function movingMedian(v, n) {
  const r = Math.floor(n / 2);
  return v.map((_, i) => {
    const win = v.slice(Math.max(0, i - r), i + r + 1).sort((p, q) => p - q);
    return win[win.length >> 1];
  });
}

function movingAverage(v, n) {
  const r = Math.floor(n / 2);
  return v.map((_, i) => {
    const win = v.slice(Math.max(0, i - r), i + r + 1);
    return win.reduce((s, x) => s + x, 0) / win.length;
  });
}

// Piecewise linear x(t) as nested ffmpeg if() expressions; t is relative to the clip start.
function cropExpression(kfs, t0) {
  const pts = kfs.map((k) => [+(k.t - t0).toFixed(3), k.x]);
  let expr = String(pts[pts.length - 1][1]);
  for (let i = pts.length - 2; i >= 0; i--) {
    const [t1, x1] = pts[i], [t2, x2] = pts[i + 1];
    expr = `if(lt(t,${t2}),${x1}+(${x2 - x1})*(t-${t1})/${+(t2 - t1).toFixed(3)},${expr})`;
  }
  return `if(lt(t,${pts[0][0]}),${pts[0][1]},${expr})`;
}

function main() {
  const o = parseArgs(process.argv.slice(2));
  const info = probe(o.video);
  const end = Math.min(o.end ?? info.duration, info.duration);
  const sw = SMALL_W, sh = 2 * Math.round((SMALL_W * info.height) / info.width / 2);
  const frames = decodeGray(o.video, o.start, end, 2 / o.step, sw, sh);

  // Pair sample 2k with 2k+1 (half a step apart); one keyframe per step.
  const raw = [];
  let prev = null;
  for (let k = 0; 2 * k + 1 < frames.length; k++) {
    const a = frames[2 * k], b = frames[2 * k + 1];
    const m = motionCenter(a, b, sw, sh);
    let c = m.motion >= MIN_MOTION && m.center !== null ? m.center : prev;
    if (c === null) c = subjectCenter(a, sw, sh);
    prev = c;
    raw.push({ t: o.start + k * o.step, c, motion: +m.motion.toFixed(3) });
  }
  if (!raw.length) throw new Error('No frames decoded in the requested range.');

  const n = Math.max(1, o.smooth);
  const smooth = movingAverage(movingMedian(raw.map((r) => r.c), n), n);
  const [aw, ah] = o.aspect.split(':').map(Number);
  const cropH = info.height;
  const cropW = 2 * Math.round((cropH * aw) / ah / 2);
  const scale = info.width / sw;
  const keyframes = raw.map((r, i) => {
    const x = Math.round(Math.min(Math.max(smooth[i] * scale - cropW / 2, 0), info.width - cropW));
    return { t: +r.t.toFixed(3), x, y: 0, motion: r.motion };
  });

  const result = { source: path.resolve(o.video), width: info.width, height: info.height, fps: +info.fps.toFixed(3),
    crop: { w: cropW, h: cropH }, step: o.step, keyframes };
  writeFileSync(o.out, JSON.stringify(result, null, 2));

  console.log(`keyframes: ${keyframes.length} -> ${o.out}`);
  if (keyframes.length <= 60) {
    console.log(`filter (t relative to --start ${o.start}; render with -ss ${o.start} before -i):`);
    console.log(`crop=${cropW}:${cropH}:x='${cropExpression(keyframes, o.start)}':y=0`);
  } else {
    console.log('More than 60 keyframes: use the JSON and render in segments (one crop expression per segment).');
  }
}

main();
