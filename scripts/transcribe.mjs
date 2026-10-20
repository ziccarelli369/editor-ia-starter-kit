#!/usr/bin/env node
// Transcribe with local Whisper using the languages set in kit.config.json, then
// write the kit's transcript shape next to the input.
// Usage: npm run transcribe -- <video-or-audio> [--out <raw.json>] [--language en|es|auto]
//   languages ["en"]        -> model medium.en, --language en
//   languages ["es"]        -> model medium,    --language es
//   languages ["en","es"]   -> model medium,    --language auto (Whisper detects per file)
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { resolve, dirname, join, basename, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const opt = n => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : undefined; };
const input = args.find((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--')));
if (!input || !existsSync(input)) { console.error('Usage: npm run transcribe -- <video-or-audio> [--out <raw.json>] [--language en|es|auto]'); process.exit(1); }
const config = JSON.parse(readFileSync(join(root, 'kit.config.json'), 'utf8'));
const langs = config.transcription.languages ?? ['es'];
const language = opt('language') ?? (langs.length === 1 ? langs[0] : 'auto');
const model = language === 'en' ? (config.transcription.model_en ?? 'medium.en') : (config.transcription.model ?? 'medium');
const dir = dirname(input);
const out = opt('out') ?? join(dir, basename(input, extname(input)) + '.raw.json');
// provider elevenlabs (needs ELEVENLABS_API_KEY in .env): Scribe returns measured word times.
const envFile = join(root, '.env');
const envKey = existsSync(envFile) ? (readFileSync(envFile, 'utf8').match(/^ELEVENLABS_API_KEY=(.+)$/m)?.[1] ?? '').trim() : '';
const hasKey = Boolean(process.env.ELEVENLABS_API_KEY || envKey);
if (config.transcription.provider === 'elevenlabs') {
  if (!hasKey) { console.error('provider is elevenlabs but ELEVENLABS_API_KEY is empty in .env; falling back to whisper'); }
  else {
    const el = spawnSync(process.execPath, [join(root, 'scripts/transcribe-elevenlabs.mjs'), input, '--output', out, ...(language !== 'auto' ? ['--language', language] : [])], { stdio: 'inherit', cwd: root });
    process.exit(el.status ?? 1);
  }
}
const cliArgs = ['hyperframes', 'transcribe', input, '--model', model];
if (language !== 'auto') cliArgs.push('--language', language);
console.log(`whisper model ${model}, language ${language}`);
const r = spawnSync(process.platform === 'win32' ? 'npx.cmd' : 'npx', cliArgs, { stdio: 'inherit', cwd: root, shell: process.platform === 'win32' });
if (r.status !== 0) process.exit(r.status ?? 1);
const produced = join(dir, 'transcript.json');
if (!existsSync(produced)) { console.error(`Expected ${produced} from hyperframes transcribe`); process.exit(1); }
const conv = spawnSync(process.execPath, [join(root, 'scripts/whisper-to-kit.mjs'), produced, out], { stdio: 'inherit' });
process.exit(conv.status ?? 1);
