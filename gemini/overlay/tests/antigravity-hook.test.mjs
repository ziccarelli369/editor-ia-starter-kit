import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { spawnSync } from 'node:child_process';

const root = resolve(import.meta.dirname, '..');
const blank = `<html><head><title>plain</title><style>.a{color:red}</style></head><body><video src="a.mp4"></video></body></html>`;
const hook = (name, args) => {
  const run = spawnSync(process.execPath, [join(root, '.agents/hooks/text-gate.mjs')], { input: JSON.stringify({ toolCall: { name, args } }), encoding: 'utf8' });
  return { status: run.status, decision: run.stdout ? JSON.parse(run.stdout).decision : 'allow' };
};

test('an Antigravity tool call that adds on-screen text is denied; other calls pass', () => {
  const dir = mkdtempSync(join(tmpdir(), 'antigravity-hook-'));
  const projectDir = join(dir, 'video-projects', 'p');
  mkdirSync(projectDir, { recursive: true });
  writeFileSync(join(projectDir, 'project.json'), '{}');
  const index = join(projectDir, 'index.html');
  writeFileSync(index, blank);
  try {
    const cases = [
      ['write_to_file', { TargetFile: join(projectDir, 'hook.html'), CodeContent: '<div>How long would you last?</div>', Description: 'hook card' }, 'deny'],
      ['replace_file_content', { TargetFile: index, ReplacementChunks: [{ TargetContent: '<video src="a.mp4">', ReplacementContent: '<h1>NO EXIT</h1><video src="a.mp4">', AllowMultiple: false }] }, 'deny'],
      ['replace_file_content', { TargetFile: index, ReplacementChunks: [{ TargetContent: '.a{color:red}', ReplacementContent: '.a{color:blue;font-size:20px}' }] }, 'allow'],
      ['write_to_file', { TargetFile: join(projectDir, 'text-board', 'p1.html'), CodeContent: '<div>NO EXIT</div>' }, 'allow'],
      ['run_command', { CommandLine: `ffmpeg -i ${projectDir}/a.mov -vf "drawtext=text='LAST?'" out.mp4`, Cwd: dir }, 'deny'],
      ['run_command', { CommandLine: `ffmpeg -i ${projectDir}/a.mov -vf scale=1080:-2 out.mp4`, Cwd: dir }, 'allow'],
      ['some_future_tool', { shape: ['nobody', 'knows'] }, 'allow'],
    ];
    for (const [name, args, decision] of cases) {
      const result = hook(name, args);
      assert.equal(result.status, 0, name);
      assert.equal(result.decision, decision, `${name} ${JSON.stringify(args).slice(0, 80)}`);
    }
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
