import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { textGate } from '../scripts/lib/text-gate.mjs';

const root = resolve(import.meta.dirname, '..');
const countdown = `<html><head><title>countdown</title><style>.l{font:700 40px Inter}</style></head>
<body><div id="lab" class="l"></div><script>const LABEL = 'UNTIL TAP'; lab.textContent = LABEL;</script></body></html>`;
const blank = `<html><head><title>plain</title></head><body><div data-composition-id="main"><video src="a.mp4"></video></div></body></html>`;
const options = [
  { id: 'hud', treatment: 'tracking label', text: 'TRIANGLE // LOCKED', source: '.claude/skills/hyperframes/references/typography.md' },
  { id: 'countdown', treatment: 'countdown, no words', text: '0:03', source: '.claude/skills/short-form-edit/references/opening.md' },
  { id: 'serif', treatment: 'editorial serif', text: 'he had three seconds left.', source: '.claude/skills/style-library/SKILL.md' },
];

function project(files) {
  const dir = mkdtempSync(join(tmpdir(), 'text-gate-'));
  const projectDir = join(dir, 'video-projects', 'p');
  mkdirSync(projectDir, { recursive: true });
  writeFileSync(join(projectDir, 'project.json'), '{}');
  for (const [name, body] of Object.entries(files)) {
    mkdirSync(resolve(projectDir, name, '..'), { recursive: true });
    writeFileSync(join(projectDir, name), typeof body === 'string' ? body : JSON.stringify(body));
  }
  return { dir, projectDir };
}
const board = (change = b => b) => ({ 'text-board/board.png': 'png', 'text-board/text-board.json': change({ board: 'board.png', options, pick: 'countdown' }) });
const hook = (input) => spawnSync(process.execPath, [join(root, '.claude/hooks/text-gate.mjs')], { input: JSON.stringify(input), encoding: 'utf8' });

test('text on screen without a text board is blocked; a complete board passes', () => {
  const bare = project({ 'compositions/countdown.html': countdown, 'index.html': blank });
  const done = project({ 'compositions/countdown.html': countdown, ...board() });
  const quiet = project({ 'index.html': blank, 'build.py': 'cmd = ["ffmpeg", "-vf", "eq=contrast=1.1"]' });
  try {
    const result = textGate(bare.projectDir, root);
    assert.equal(result.ok, false);
    assert.deepEqual(result.files, ['compositions/countdown.html']);
    assert.match(result.errors.join('\n'), /text-board\.json is missing/);
    assert.equal(textGate(done.projectDir, root).ok, true);
    assert.equal(textGate(quiet.projectDir, root).ok, true, 'a title tag and ffmpeg without drawtext are not on-screen text');
    writeFileSync(join(bare.projectDir, 'project.json'), '{"kind":"film"}');
    assert.equal(textGate(bare.projectDir, root).ok, true, 'a character film runs its own checks');
  } finally {
    for (const p of [bare, done, quiet]) rmSync(p.dir, { recursive: true, force: true });
  }
});

test('a thin board is rejected: too few options, one treatment twice, an invented source, no pick, no image', () => {
  const cases = [
    [b => ({ ...b, options: options.slice(0, 2) }), /at least 3 options/],
    [b => ({ ...b, options: options.map(o => ({ ...o, treatment: 'big bold word' })) }), /distinct treatment/],
    [b => ({ ...b, options: [...options.slice(0, 2), { ...options[2], source: '.claude/skills/made-up/SKILL.md' }] }), /not a kit skill file/],
    [b => ({ ...b, pick: 'none' }), /pick/],
    [b => ({ ...b, board: 'missing.png' }), /board image/],
  ];
  for (const [change, error] of cases) {
    const p = project({ 'build.py': 'vf = "drawtext=text=\'HOW LONG\'"', ...board(change) });
    try {
      const result = textGate(p.projectDir, root);
      assert.equal(result.ok, false, String(error));
      assert.match(result.errors.join('\n'), error);
    } finally {
      rmSync(p.dir, { recursive: true, force: true });
    }
  }
});

test('the hook blocks the write that first puts text on screen, and lets the board itself through', () => {
  const p = project({ 'index.html': blank });
  try {
    const target = join(p.projectDir, 'compositions', 'hook.html');
    const write = hook({ tool_name: 'Write', tool_input: { file_path: target, content: '<div class="hook">How long would you last?</div>' } });
    assert.equal(write.status, 2);
    assert.match(write.stderr, /typography\.md/);
    const css = hook({ tool_name: 'Edit', tool_input: { file_path: join(p.projectDir, 'index.html'), old_string: '<title>plain</title>', new_string: '<title>plain</title><style>.a{font-size:20px}</style>' } });
    assert.equal(css.status, 0, css.stderr);
    writeFileSync(join(p.projectDir, 'index.html'), blank.replace('<video', '<h1>Your next great edit</h1><video'));
    const retime = hook({ tool_name: 'Edit', tool_input: { file_path: join(p.projectDir, 'index.html'), old_string: 'src="a.mp4"', new_string: 'src="b.mp4" data-start="2"' } });
    assert.equal(retime.status, 0, 'an edit that adds no text passes, even in a file that already has text');
    const reword = hook({ tool_name: 'Edit', tool_input: { file_path: join(p.projectDir, 'index.html'), old_string: 'Your next great edit', new_string: 'How long would you last?' } });
    assert.equal(reword.status, 2);
    const prototype = hook({ tool_name: 'Write', tool_input: { file_path: join(p.projectDir, 'text-board', 'p1.html'), content: '<div>NO EXIT</div>' } });
    assert.equal(prototype.status, 0, prototype.stderr);
    const bash = hook({ tool_name: 'Bash', tool_input: { command: `ffmpeg -i ${p.projectDir}/assets/a.mov -vf "drawtext=text='LAST?'" out.mp4` } });
    assert.equal(bash.status, 2);
    const grep = hook({ tool_name: 'Bash', tool_input: { command: `grep -n drawtext ${p.projectDir}/build.py` } });
    assert.equal(grep.status, 0, 'reading a project for drawtext is not drawing text');
    const elsewhere = hook({ tool_name: 'Write', tool_input: { file_path: join(p.dir, 'notes.html'), content: '<p>hello</p>' } });
    assert.equal(elsewhere.status, 0);
  } finally {
    rmSync(p.dir, { recursive: true, force: true });
  }
});
