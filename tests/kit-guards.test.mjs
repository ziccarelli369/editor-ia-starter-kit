import test from 'node:test';
import assert from 'node:assert/strict';
import { cpSync, existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { mainCheckoutOf } from '../scripts/lib/worktree.mjs';
const root = resolve(import.meta.dirname, '..');
const node = (script, args, env = process.env) => spawnSync(process.execPath, [script, ...args], { encoding: 'utf8', cwd: root, env });
const slashed = p => resolve(p).replace(/\\/g, '/');

test('mainCheckoutOf names the main checkout only for a linked worktree', () => {
  const dir = mkdtempSync(join(tmpdir(), 'kit-guards-'));
  try {
    const main = join(dir, 'main');
    for (const [name, gitdir, want] of [['worktree', join(main, '.git', 'worktrees', 'wt'), slashed(main)], ['submodule', '../.git/modules/sub', null]]) {
      mkdirSync(join(dir, name));
      writeFileSync(join(dir, name, '.git'), `gitdir: ${gitdir}\n`);
      assert.equal(mainCheckoutOf(join(dir, name)), want, name);
    }
    mkdirSync(join(dir, 'repo', '.git'), { recursive: true });
    assert.equal(mainCheckoutOf(join(dir, 'repo')), null, '.git directory');
    assert.equal(mainCheckoutOf(dir), null, 'no .git');
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('new-video and deliver refuse inside a linked worktree, name the main checkout and create nothing', () => {
  const kit = mkdtempSync(join(tmpdir(), 'kit-guards-'));
  try {
    for (const f of ['new-video.mjs', 'deliver.mjs', 'lib']) cpSync(join(root, 'scripts', f), join(kit, 'scripts', f), { recursive: true });
    writeFileSync(join(kit, '.git'), `gitdir: ${join(kit, 'main', '.git', 'worktrees', 'wt')}\n`);
    for (const [script, ...args] of [['new-video.mjs', 'guard-test'], ['deliver.mjs', 'guard-test', '--video', 'v.mp4', '--cover', 'c.png']]) {
      const r = node(join(kit, 'scripts', script), args);
      assert.equal(r.status, 1, script);
      assert.ok(r.stderr.includes(slashed(join(kit, 'main'))), r.stderr);
      assert.match(r.stderr, /--allow-worktree/);
      assert.ok(!existsSync(join(kit, 'video-projects')) && !existsSync(join(kit, 'outbox')), script);
    }
  } finally {
    rmSync(kit, { recursive: true, force: true });
  }
});

test('new-video --kind film refuses when the film doctor fails and creates nothing', () => {
  const slug = `guard-film-${process.pid}`;
  const id = `${new Date().toISOString().slice(0, 10)}-${slug}`;
  const created = [join(root, 'video-projects', id), join(root, 'outbox', id)];
  try {
    const blender = join(tmpdir(), `no-blender-${process.pid}`, 'blender');
    const r = node(join(root, 'scripts/new-video.mjs'), [slug, '--kind', 'film', '--brand', 'none', '--allow-worktree'], { ...process.env, BLENDER: blender });
    assert.equal(r.status, 1, r.stdout + r.stderr);
    assert.match(r.stderr, /FAIL\s+(blender|python)/);
    assert.match(r.stderr, /npm run film:install/);
    for (const d of created) assert.ok(!existsSync(d), `must not exist: ${d}`);
  } finally {
    for (const d of created) rmSync(d, { recursive: true, force: true });
  }
});

test('unlock lists and stops a process that names a project folder but not its own caller, then the folder can be removed', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'kit-guards-'));
  const idle = (arg, cwd) => spawn(process.execPath, ['-e', 'setInterval(() => {}, 1e6)', arg], { cwd, stdio: 'ignore' });
  const child = idle(dir, dir);
  const caller = idle(`npm run unlock -- ${dir} --stop`, root);
  const exited = [child, caller].map(p => new Promise(r => p.once('exit', r)));
  const listed = pid => new RegExp(`^\\s+${pid}\\s`, 'm');
  try {
    await Promise.all([child, caller].map(p => new Promise(r => p.once('spawn', r))));
    const list = node(join(root, 'scripts/unlock.mjs'), [dir]);
    assert.equal(list.status, 0, list.stderr);
    assert.match(list.stdout, listed(child.pid));
    assert.doesNotMatch(list.stdout, listed(caller.pid));
    const stop = node(join(root, 'scripts/unlock.mjs'), [dir, '--stop']);
    assert.equal(stop.status, 0, stop.stdout + stop.stderr);
    assert.doesNotMatch(stop.stdout, listed(caller.pid));
    await exited[0];
    assert.doesNotThrow(() => process.kill(caller.pid, 0));
    rmSync(dir, { recursive: true });
    assert.ok(!existsSync(dir));
  } finally {
    child.kill();
    caller.kill();
    await Promise.all(exited);
    rmSync(dir, { recursive: true, force: true });
  }
});
