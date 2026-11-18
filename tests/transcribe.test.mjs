import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
const root = resolve(import.meta.dirname, '..');
const transcribe = (...args) => spawnSync(process.execPath, [join(root, 'scripts/transcribe.mjs'), ...args], { encoding: 'utf8', cwd: root });
const config = JSON.parse(readFileSync(join(root, 'kit.config.json'), 'utf8'));

test('with provider elevenlabs and no --via, transcribe stops and names both routes instead of charging', { skip: config.transcription.provider !== 'elevenlabs' || config.elevenlabs?.access === 'api' }, () => {
  const r = transcribe(join(root, 'package.json'));
  assert.equal(r.status, 2);
  assert.match(r.stderr, /--from/);
  assert.match(r.stderr, /--via api/);
});

test('--from writes the kit transcript from MCP words and rejects out-of-order times', () => {
  const dir = mkdtempSync(join(tmpdir(), 'transcribe-'));
  try {
    const words = join(dir, 'words.json');
    const out = join(dir, 'raw.json');
    writeFileSync(words, JSON.stringify({ audio_duration_secs: 2, words: [{ word: 'Hola', start: 0.2, end: 0.6, type: 'word' }, { text: ' ', start: 0.6, end: 0.7, type: 'spacing' }, { text: 'mundo', start: 0.7, end: 1.2, type: 'word' }] }));
    const ok = transcribe(words, '--from', words, '--out', out);
    assert.equal(ok.status, 0, ok.stderr);
    const raw = JSON.parse(readFileSync(out, 'utf8'));
    assert.equal(raw.text, 'Hola mundo');
    assert.equal(raw.audio_duration_secs, 2);
    assert.deepEqual(raw.words.map(w => w.text), ['Hola', ' ', 'mundo']);
    writeFileSync(words, JSON.stringify({ words: [{ text: 'b', start: 1, end: 1.2 }, { text: 'a', start: 0.5, end: 0.8 }] }));
    const bad = transcribe(words, '--from', words, '--out', out);
    assert.equal(bad.status, 1);
    assert.match(bad.stderr, /out-of-order/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
