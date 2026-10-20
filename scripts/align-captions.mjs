#!/usr/bin/env node
// Snap every caption to the measured voice onset, frame-exact.
// Usage: node scripts/align-captions.mjs <project-id> --srt <in.srt> [--audio renders/final.mp4] [--out <out.srt>] [--window 0.2] [--fps 30]
// Paths are relative to video-projects/<project-id>/. Writes the aligned SRT and ALIGN.json
// (per cue: old start, onset used, new start, delta) and prints a summary.
// A cue with no onset inside the window (continuous speech, or a soft first word) keeps its time and is
// listed as "kept". With Scribe word times as the base, the window stays small: a wide window drags a
// soft first word onto the next loud syllable.
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { analyze, nearestOnset } from './lib/onsets.mjs';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const id = args[0];
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
if (!id || id.startsWith('--') || !opt('srt')) { console.error('Usage: node scripts/align-captions.mjs <project-id> --srt <in.srt> [--audio renders/final.mp4] [--out <out.srt>] [--window 0.2] [--fps 30]'); process.exit(2); }
const proj = join(root, 'video-projects', id);
const srtPath = join(proj, opt('srt'));
const audio = join(proj, opt('audio', 'renders/final.mp4'));
const out = join(proj, opt('out', opt('srt').replace(/\.srt$/i, '.aligned.srt')));
const window = Number(opt('window', '0.2'));
const fps = Number(opt('fps', '30'));
if (!existsSync(srtPath) || !existsSync(audio)) { console.error('srt or audio not found'); process.exit(2); }

const toS = s => { const m = s.match(/(\d+):(\d+):(\d+)[,.](\d+)/); return +m[1] * 3600 + +m[2] * 60 + +m[3] + +m[4] / 1000; };
const toSrt = t => { const h = Math.floor(t / 3600), m = Math.floor(t % 3600 / 60), s = Math.floor(t % 60), ms = Math.round((t - Math.floor(t)) * 1000); return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')},${String(ms).padStart(3, '0')}`; };
const snap = t => Math.round(t * fps) / fps;

function parseSrt(text) {
  return text.replace(/\r/g, '').trim().split(/\n\n+/).map(b => {
    const [idx, time, ...lines] = b.split('\n');
    const [a, z] = time.split('-->').map(x => toS(x.trim()));
    return { index: +idx, start: a, end: z, text: lines.join('\n') };
  });
}

const cues = parseSrt(readFileSync(srtPath, 'utf8'));
const { onsets } = analyze(audio);
const report = [];
for (let i = 0; i < cues.length; i++) {
  const c = cues[i];
  const onset = nearestOnset(onsets, c.start, window);
  const used = onset != null && !report.some(r => r.onset === onset);
  const newStart = used ? snap(onset) : snap(c.start);
  const dur = c.end - c.start;
  let newEnd = snap(newStart + dur);
  const next = cues[i + 1];
  if (next) {
    const nextOnset = nearestOnset(onsets, next.start, window);
    const nextStart = nextOnset != null ? snap(nextOnset) : snap(next.start);
    newEnd = Math.min(newEnd, nextStart - 1 / fps);
  }
  report.push({ index: c.index, text: c.text, old: +c.start.toFixed(3), onset: used ? onset : null, new: +newStart.toFixed(3), delta: +(newStart - c.start).toFixed(3), status: used ? 'snapped' : 'kept' });
  c.start = newStart; c.end = Math.max(newEnd, newStart + 2 / fps);
}
writeFileSync(out, cues.map(c => `${c.index}\n${toSrt(c.start)} --> ${toSrt(c.end)}\n${c.text}\n`).join('\n') + '\n');
writeFileSync(join(proj, 'ALIGN.json'), JSON.stringify({ audio: opt('audio', 'renders/final.mp4'), srt: opt('srt'), out: opt('out') ?? null, window, fps, onsets, cues: report }, null, 2) + '\n');
const snapped = report.filter(r => r.status === 'snapped');
const abs = snapped.map(r => Math.abs(r.delta));
console.log(`${snapped.length}/${cues.length} cues snapped to a voice onset (window ±${window}s), ${cues.length - snapped.length} kept`);
if (abs.length) console.log(`shift: mean ${(abs.reduce((a, b) => a + b, 0) / abs.length).toFixed(2)}s, max ${Math.max(...abs).toFixed(2)}s`);
for (const r of report) console.log(`${String(r.index).padStart(3)}  ${r.old.toFixed(2).padStart(6)} -> ${r.new.toFixed(2).padStart(6)}  ${r.delta >= 0 ? '+' : ''}${r.delta.toFixed(2)}  ${r.status.padEnd(7)}  ${r.text.replace(/\n/g, ' / ')}`);
console.log(`wrote ${out} and ALIGN.json`);
