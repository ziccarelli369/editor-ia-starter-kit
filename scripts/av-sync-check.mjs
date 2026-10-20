#!/usr/bin/env node
// Does the render show the picture and play the sound the edit list says, at the same time?
// For each probe "reelTime:sourceTime", the script finds where in the source the render's sound
// comes from (audio cross-correlation over the whole source) and where its picture comes from
// (crop-aware frame match within ±2 s of the expected time), and reports both offsets.
// Usage: node scripts/av-sync-check.mjs <project-id> --source <source video> [--video renders/final.mp4] --probes 1.0:58.75,5.0:62.75,...
// Pass one probe per shot, a second or two after each cut. Tolerance 0.12 s (about 3 frames at 30 fps).
import { spawnSync } from 'node:child_process';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { writeFileSync } from 'node:fs';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const id = args[0];
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
if (!id || id.startsWith('--') || !opt('source') || !opt('probes')) { console.error('Usage: node scripts/av-sync-check.mjs <project-id> --source <video> [--video renders/final.mp4] --probes t:s,t:s,...'); process.exit(2); }
const proj = join(root, 'video-projects', id);
const final = join(proj, opt('video', 'renders/final.mp4'));
const source = resolve(root, opt('source'));
const tol = Number(opt('tolerance', '0.12'));
const probes = opt('probes').split(',').map(p => p.split(':').map(Number));
const FPS = 30, SR = 8000, HH = 48, FW = 27, SW = 85;
const run = a => { const r = spawnSync('ffmpeg', ['-v', 'error', ...a], { maxBuffer: 2e9 }); if (r.status !== 0) throw new Error(r.stderr.toString()); return r.stdout; };
const pcm = f => { const b = run(['-i', f, '-vn', '-ac', '1', '-ar', String(SR), '-af', 'highpass=f=300,lowpass=f=3400', '-f', 's16le', '-']); return new Int16Array(b.buffer, b.byteOffset, b.length >> 1); };
function normF(a) { let mu = 0; for (const v of a) mu += v; mu /= a.length; let s = 0; for (const v of a) s += (v - mu) ** 2; s = Math.sqrt(s / a.length) || 1; return Float32Array.from(a, v => (v - mu) / s); }
function soundAt(finA, srcA, t) {
  const win = SR, a = normF(finA.subarray(Math.round(t * SR), Math.round(t * SR) + win));
  let best = 0, bestC = -Infinity;
  for (let s = 0; s + win <= srcA.length; s += 2) { let c = 0; for (let i = 0; i < win; i += 2) c += a[i] * srcA[s + i]; if (c > bestC) { bestC = c; best = s; } }
  return { t: best / SR, r: bestC / (win / 2) };
}
const normU = a => { let mu = 0; for (const v of a) mu += v; mu /= a.length; return Uint8Array.from(a, v => Math.max(0, Math.min(255, v - mu + 128))); };
function pictureAt(t, s) {
  const a = normU(run(['-ss', String(t), '-i', final, '-frames:v', '1', '-vf', `scale=${FW}:${HH},format=gray`, '-f', 'rawvideo', '-']));
  const span = 2, start = Math.max(0, s - span);
  const buf = run(['-ss', String(start), '-t', String(2 * span), '-i', source, '-vf', `fps=${FPS},scale=${SW}:${HH},format=gray`, '-f', 'rawvideo', '-']);
  const n = Math.floor(buf.length / (SW * HH));
  let best = { d: Infinity, k: 0 };
  for (let k = 0; k < n; k++) {
    const fr = normU(buf.subarray(k * SW * HH, (k + 1) * SW * HH));
    for (let x = 0; x <= SW - FW; x += 2) {
      let d = 0;
      for (let y = 0; y < HH && d < best.d; y++) for (let i = 0; i < FW; i++) { const v = a[y * FW + i] - fr[y * SW + x + i]; d += v * v; }
      if (d < best.d) best = { d, k };
    }
  }
  return start + best.k / FPS;
}
const finA = pcm(final), srcA = normF(pcm(source));
const rows = [];
for (const [t, s] of probes) {
  const snd = soundAt(finA, srcA, t), pic = pictureAt(t, s);
  const dS = snd.t - s, dP = pic - s, av = snd.t - pic;
  const flags = [];
  if (Math.abs(dS) > tol) flags.push('SOUND_OFF_EDL');
  if (Math.abs(dP) > tol) flags.push('PICTURE_OFF_EDL');
  if (Math.abs(av) > tol) flags.push('AV_OFFSET');
  rows.push({ t, s, sound: +snd.t.toFixed(2), picture: +pic.toFixed(2), av: +av.toFixed(2), flags });
  console.log(`reel ${t.toFixed(2)}s  edl ${s.toFixed(2)}s  sound ${snd.t.toFixed(2)} (${dS >= 0 ? '+' : ''}${dS.toFixed(2)})  picture ${pic.toFixed(2)} (${dP >= 0 ? '+' : ''}${dP.toFixed(2)})  sound-picture ${av >= 0 ? '+' : ''}${av.toFixed(2)}  ${flags.join(' ')}`);
}
const bad = rows.filter(r => r.flags.length);
const verdict = bad.length ? 'FAIL' : 'PASS';
const md = [`# AV sync check: ${verdict}`, '', `Render \`${opt('video', 'renders/final.mp4')}\` against \`${opt('source')}\`, tolerance ${tol}s.`, '',
  '| reel (s) | edl source (s) | sound from (s) | picture from (s) | sound-picture (s) | flags |', '|---|---|---|---|---|---|',
  ...rows.map(r => `| ${r.t} | ${r.s} | ${r.sound} | ${r.picture} | ${r.av} | ${r.flags.join(' ')} |`), ''].join('\n');
writeFileSync(join(proj, 'AVSYNC.md'), md);
console.log(`Verdict: ${verdict} — ${rows.length} probes, ${bad.length} flagged. Wrote AVSYNC.md`);
process.exitCode = bad.length ? 1 : 0;
