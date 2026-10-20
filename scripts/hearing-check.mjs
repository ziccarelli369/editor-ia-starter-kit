#!/usr/bin/env node
// The ear: check a final render against its subtitles and its cuts, then write HEARING.md.
// Usage: node scripts/hearing-check.mjs <project-id> [--video renders/final.mp4] [--srt renders/subtitles.srt] [--tolerance 0.35]
// A line the user confirmed by ear goes in video-projects/<id>/VERIFIED.json as ["exact cue text", ...];
// such cues are marked VERIFIED and never MISMATCH, since the ear outranks the transcriber.
//   Paths are relative to video-projects/<project-id>/.
//   Needs ffmpeg on PATH and local Whisper (HYPERFRAMES_WHISPER_PATH passes through to `npm run transcribe`).
//   Writes video-projects/<id>/HEARING.md, prints the summary, exits 1 on FAIL.
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { analyze, nearestOnset, levelAt as bandLevel } from './lib/onsets.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : d; };
const id = args.find((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--')));
if (!id) { console.error('Usage: node scripts/hearing-check.mjs <project-id> [--video renders/final.mp4] [--srt renders/subtitles.srt] [--tolerance 0.35]'); process.exit(2); }
const proj = join(root, 'video-projects', id);
const video = join(proj, opt('video', 'renders/final.mp4'));
const srtPath = join(proj, opt('srt', 'renders/subtitles.srt'));
const tol = Number(opt('tolerance', '0.35'));
for (const p of [video, srtPath]) if (!existsSync(p)) { console.error(`Missing ${p}`); process.exit(2); }

function run(cmd, a, o = {}) {
  const r = spawnSync(cmd, a, { encoding: 'utf8', maxBuffer: 256 * 1024 * 1024, ...o });
  if (r.error) throw r.error;
  return r;
}

const wavFile = join(proj, 'work', 'hearing', 'hearing.wav');
function transcribe() {
  const dir = join(proj, 'work', 'hearing');
  mkdirSync(dir, { recursive: true });
  const wav = wavFile, raw = join(dir, 'hearing.wav.raw.json');
  const ff = run('ffmpeg', ['-y', '-v', 'error', '-i', video, '-vn', '-ac', '1', '-ar', '16000', wav]);
  if (ff.status !== 0) throw new Error(`ffmpeg audio extract failed: ${ff.stderr}`);
  const win = process.platform === 'win32';
  const q = s => (win ? `"${s}"` : s);
  const r = run(win ? 'npm.cmd' : 'npm', ['run', 'transcribe', '--', q(wav), '--out', q(raw)],
    { cwd: root, shell: win, stdio: ['ignore', 'inherit', 'inherit'], env: process.env });
  if (r.status !== 0 || !existsSync(raw)) throw new Error('transcribe failed');
  return JSON.parse(readFileSync(raw, 'utf8')).words.filter(w => w.text?.trim());
}

const toSec = t => { const [h, m, s] = t.replace(',', '.').split(':'); return +h * 3600 + +m * 60 + +s; };
function parseSrt(text) {
  return text.replace(/\r/g, '').trim().split(/\n\s*\n/).map(b => {
    const lines = b.split('\n'); const ti = lines.findIndex(l => l.includes('-->'));
    if (ti < 0) return null;
    const [a, z] = lines[ti].split('-->').map(s => toSec(s.trim().split(' ')[0]));
    return { index: +lines[0] || ti, start: a, end: z, text: lines.slice(ti + 1).join(' ').trim() };
  }).filter(Boolean);
}

const norm = s => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^\p{L}\p{N}\s]/gu, ' ').split(/\s+/).filter(Boolean);
// Character-level Levenshtein ratio on the normalized text: 1 - edits / max(len).
function similarity(a, b) {
  const x = norm(a).join(' '), y = norm(b).join(' ');
  if (!x.length && !y.length) return 1;
  let prev = Array.from({ length: y.length + 1 }, (_, j) => j);
  for (let i = 1; i <= x.length; i++) {
    const cur = [i];
    for (let j = 1; j <= y.length; j++) cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x[i - 1] === y[j - 1] ? 0 : 1));
    prev = cur;
  }
  return 1 - prev[y.length] / Math.max(x.length, y.length);
}

// Align the subtitle tokens to the heard tokens in order (token Levenshtein with backtrace).
// Returns, per cue, the heard word indexes aligned to it. Order-based, so Whisper timing drift
// cannot push words into the wrong cue.
function alignCues(cues, words) {
  const S = cues.flatMap((c, ci) => norm(c.text).map(t => ({ t, ci })));
  const H = words.flatMap((w, wi) => norm(w.text).map(t => ({ t, wi })));
  const D = Array.from({ length: S.length + 1 }, (_, i) => Array.from({ length: H.length + 1 }, (_, j) => (i ? (j ? 0 : i) : j)));
  for (let i = 1; i <= S.length; i++) for (let j = 1; j <= H.length; j++)
    D[i][j] = Math.min(D[i - 1][j] + 1, D[i][j - 1] + 1, D[i - 1][j - 1] + (S[i - 1].t === H[j - 1].t ? 0 : 1));
  const span = cues.map(() => [Infinity, -Infinity]);
  for (let i = S.length, j = H.length; i > 0 && j > 0;) {
    if (D[i][j] === D[i - 1][j - 1] + (S[i - 1].t === H[j - 1].t ? 0 : 1)) {
      const s = span[S[i - 1].ci], w = H[j - 1].wi; s[0] = Math.min(s[0], w); s[1] = Math.max(s[1], w); i--; j--;
    } else if (D[i][j] === D[i - 1][j] + 1) i--; else j--;
  }
  return span.map(([a, b]) => (a <= b ? words.slice(a, b + 1) : []));
}

function checkCues(cues, words) {
  const aligned = alignCues(cues, words);
  return cues.map((c, ci) => {
    const heard = aligned[ci];
    const heardText = heard.map(w => w.text.trim()).join(' ');
    const sim = heard.length ? similarity(c.text, heardText) : 0;
    const delta = heard.length ? heard[0].start - c.start : null;
    const flags = [];
    const isVerified = verified.includes(c.text.replace(/\s+/g, ' ').trim().toLowerCase());
    if (isVerified) flags.push('VERIFIED');
    else if (!heard.length) flags.push('SILENT');
    else if (sim < 0.6) flags.push('MISMATCH');
    return { ...c, heardText, sim, delta, flags };
  }).map(r => {
    // Timing is judged against measured voice onsets (scripts/lib/onsets.mjs), never Whisper times.
    // A cue is on cue when a sustained speech onset sits within `tol` of its start.
    const onset = nearestOnset(audio.onsets, r.start, 0.6);
    r.onset = onset;
    r.delta = onset == null ? null : +(onset - r.start).toFixed(3);
    if (onset == null || r.flags.includes('VERIFIED')) { /* no onset to measure, or the ear already ruled */ }
    else if (r.delta > tol) r.flags.push('LATE');
    else if (r.delta < -tol) r.flags.push('EARLY');
    return r;
  });
}

function detectCuts() {
  const r = run('ffmpeg', ['-hide_banner', '-i', video, '-an', '-vf', "select='gt(scene,0.4)',showinfo", '-f', 'null', '-']);
  return [...r.stderr.matchAll(/Parsed_showinfo.*?pts_time:\s*([\d.]+)/g)].map(m => +m[1]);
}

// Whisper stretches word spans across silence, so a cut inside a word span only counts when the
// speech band (300-3400 Hz) at the cut is as loud as the word itself (within 4 dB of the word's
// midpoint) and above -35 dB. Drones and sub hits fall outside the band; whooshes mostly do.
// A cut is judged on 100 ms around the frame; a 300 ms span would pick up the next word.
function levelAt(t, span = 0.05) { return bandLevel(audio.frames, t, span); }
function checkCuts(cuts, words) {
  return cuts.map(t => {
    const w = words.find(w => w.start < t && t < w.end);
    const level = w ? levelAt(t) : null;
    const wordLevel = w ? levelAt((w.start + w.end) / 2, 0.15) : null;
    // The word itself must be audible where Whisper placed it; a silent span is a stretched estimate.
    const inWord = w && wordLevel > -32 && level > -32 && level >= wordLevel - 4;
    return { t, word: w?.text.trim() ?? '', level, wordLevel, flags: inWord ? ['CUT_IN_WORD'] : [] };
  });
}

function loudness() {
  const r = run('ffmpeg', ['-hide_banner', '-i', video, '-vn', '-af', 'loudnorm=print_format=json', '-f', 'null', '-']);
  const j = r.stderr.match(/\{[^{}]*"input_i"[^{}]*\}/);
  if (!j) return { lufs: null, tp: null };
  const o = JSON.parse(j[0]);
  return { lufs: +o.input_i, tp: +o.input_tp };
}

const fmt = n => (n == null ? '-' : n.toFixed(2));
const cell = s => String(s).replace(/\|/g, '\\|');

function report(cueRes, cutRes, loud) {
  const counts = {};
  for (const r of [...cueRes, ...cutRes]) for (const f of r.flags) counts[f] = (counts[f] ?? 0) + 1;
  const timing = (counts.LATE ?? 0) + (counts.EARLY ?? 0);
  const measured = cueRes.filter(r => r.delta != null).length;
  // Whisper word times are unreliable under a music bed (it spreads words evenly). When the
  // steady offset is above 1 s, timing is reported but not judged.
  const timingJudged = true;
  const pass = !counts.MISMATCH && !counts.CUT_IN_WORD && timing <= 0.1 * cueRes.length;
  const problems = [
    ...cueRes.filter(r => r.flags.length).map(r => `cue ${r.index} @${fmt(r.start)}s ${r.flags.join('+')}: "${r.text}" heard "${r.heardText}"`),
    ...cutRes.filter(r => r.flags.length).map(r => `cut @${fmt(r.t)}s CUT_IN_WORD "${r.word}" (speech band ${fmt(r.level)} dB at cut, ${fmt(r.wordLevel)} dB in word)`),
  ];
  const countStr = ['MISMATCH', 'LATE', 'EARLY', 'SILENT', 'CUT_IN_WORD'].map(k => `${k} ${counts[k] ?? 0}`).join(' · ');
  const summary = [
    `Verdict: ${pass ? 'PASS' : 'FAIL'} — ${cueRes.length} cues, ${cutRes.length} cuts · ${countStr} · timing ${timing}/${cueRes.length} (limit 10%, ${measured} cues measured against voice onsets)`,
    `Timing source: ${audio.onsets.length} voice onsets measured from the waveform; a flagged cue is off by more than ${tol}s. Fix with: node scripts/align-captions.mjs ${id} --srt <srt>`,
    `Loudness: integrated ${fmt(loud.lufs)} LUFS, true peak ${fmt(loud.tp)} dBTP`,
    ...(pass ? [] : problems.slice(0, 3).map(p => `- ${p}`)),
  ].join('\n');
  const md = [
    `# HEARING — ${id}`, '',
    `Video \`${opt('video', 'renders/final.mp4')}\` · subtitles \`${opt('srt', 'renders/subtitles.srt')}\` · tolerance ${tol}s · checked ${new Date().toISOString()}`, '',
    '## Summary', '', '```', summary, '```', '',
    '## Cues', '', '| # | start | cue text | heard text | similarity | delta (s) | flags |', '|---|---|---|---|---|---|---|',
    ...cueRes.map(r => `| ${r.index} | ${fmt(r.start)} | ${cell(r.text)} | ${cell(r.heardText)} | ${fmt(r.sim)} | ${fmt(r.delta)} | ${r.flags.join(' ')} |`), '',
    '## Cuts', '', '| time (s) | word spanning the cut | speech band at cut (dB) | in word (dB) | flags |', '|---|---|---|',
    ...(cutRes.length ? cutRes.map(r => `| ${fmt(r.t)} | ${cell(r.word)} | ${fmt(r.level)} | ${fmt(r.wordLevel)} | ${r.flags.join(' ')} |`) : ['| - | no hard cuts found | | | |']), '',
    '## Loudness', '', `- Integrated: ${fmt(loud.lufs)} LUFS`, `- True peak: ${fmt(loud.tp)} dBTP`, '',
  ].join('\n');
  return { pass, summary, md };
}

// Whisper invents these over silence or room tone. They are never in the footage.
const HALLUCINATED = /suscr[ií]b|canal!|amara\.org|subt[ií]tulos|gracias por ver|thank you for watching|subscribe/i;
const dropHallucinations = ws => {
  // An invented phrase is appended after real speech. Keep any real text glued before the
  // first "¡" in the matching token, then drop every following word until a 1 s gap.
  const out = [];
  for (let i = 0; i < ws.length; i++) {
    const w = ws[i];
    if (!HALLUCINATED.test(w.text)) { out.push(w); continue; }
    const head = w.text.split(/[¡¿]/)[0].trim();
    if (head && !HALLUCINATED.test(head)) out.push({ ...w, text: head, end: Math.min(w.end, w.start + 0.6) });
    while (i + 1 < ws.length && ws[i + 1].start - ws[i].end < 1.0) i++;
  }
  return out;
};
try { for (const line of readFileSync(join(root, '.env'), 'utf8').split(/\r?\n/)) { const m = line.match(/^([A-Z_]+)=(.*)$/); if (m && !process.env[m[1]] && m[2]) process.env[m[1]] = m[2].trim(); } } catch {}
const verifiedPath = join(proj, 'VERIFIED.json');
const verified = existsSync(verifiedPath) ? JSON.parse(readFileSync(verifiedPath, 'utf8')).map(t => t.replace(/\s+/g, ' ').trim().toLowerCase()) : [];
const words = dropHallucinations(transcribe());
const audio = analyze(wavFile);
const cueRes = checkCues(parseSrt(readFileSync(srtPath, 'utf8')), words);
const cutRes = checkCuts(detectCuts(), words);
const { pass, summary, md } = report(cueRes, cutRes, loudness());
writeFileSync(join(proj, 'HEARING.md'), md);
console.log(summary);
process.exit(pass ? 0 : 1);
