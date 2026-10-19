#!/usr/bin/env node
// Convert the bare word array from `npx hyperframes transcribe` into the kit's
// transcript shape used by cut-silences and cut-mistakes.
// Usage: node scripts/whisper-to-kit.mjs <transcript.json> <out.json> [--duration <secs>]
import { readFileSync, writeFileSync } from 'node:fs';
const args = process.argv.slice(2);
const [input, output] = args.filter((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--')));
if (!input || !output) { console.error('Usage: node scripts/whisper-to-kit.mjs <transcript.json> <out.json> [--duration <secs>]'); process.exit(1); }
const di = args.indexOf('--duration');
const raw = JSON.parse(readFileSync(input, 'utf8'));
const list = Array.isArray(raw) ? raw : Array.isArray(raw.words) ? raw.words : null;
if (!list) throw new Error('Input is neither a word array nor { words: [...] }');
const words = list
  .filter(w => typeof w.text === 'string' && Number.isFinite(w.start) && Number.isFinite(w.end))
  .map(w => ({ text: w.text, start: w.start, end: w.end, type: 'word' }));
if (!words.length) throw new Error('No timed words found');
const duration = di >= 0 ? Number(args[di + 1]) : Math.round((words.at(-1).end + 0.5) * 100) / 100;
const out = { language_code: raw.language ?? 'auto', audio_duration_secs: duration, text: words.map(w => w.text).join(' '), words };
writeFileSync(output, JSON.stringify(out, null, 2) + '\n');
console.log(`${words.length} words -> ${output} (${duration}s)`);
