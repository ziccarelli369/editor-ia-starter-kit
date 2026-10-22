// new-video --kind film: the scaffold copies the film-engine template, not the HyperFrames starter.
// Pure Node (no Blender, no Chrome, no Python); runs in CI on 3 OSes. Every case removes only the
// folders it created: video-projects/<id> and outbox/<id> for its own unique slug.
import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, rmSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { spawnSync } from 'node:child_process';
const root = resolve(import.meta.dirname, '..');
function run(args) { return spawnSync(process.execPath, [join(root, 'scripts/new-video.mjs'), ...args, '--allow-worktree'], { encoding: 'utf8', cwd: root }); }

const TEMPLATE_FILES = ['timeline.py', 'build.py', 'scene.py', 'motion.py', 'shots.py', 'look.py', 'comp.html'];
const STARTER_FILES = ['index.html', 'meta.json', 'hyperframes.json'];

/** Unique slug per case; the id is <today>-<slug>, as new-video.mjs builds it. */
function project(name) {
  const slug = `${name}-${process.pid}`;
  const id = `${new Date().toISOString().slice(0, 10)}-${slug}`;
  return { slug, id, dir: join(root, 'video-projects', id), outbox: join(root, 'outbox', id) };
}
function cleanup(p) {
  rmSync(p.dir, { recursive: true, force: true });
  rmSync(p.outbox, { recursive: true, force: true });
}

test('new-video --kind film scaffolds the film-engine template with the given size and fps', () => {
  const p = project('film-test');
  try {
    const result = run([p.slug, '--kind', 'film', '--brand', 'none', '--size', '1080x1920', '--fps', '30', '--skip-doctor']);
    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, new RegExp(`video-projects/${p.id}`));
    const doc = JSON.parse(readFileSync(join(p.dir, 'project.json'), 'utf8'));
    assert.equal(doc.kind, 'film');
    assert.equal(doc.brand, null);
    assert.equal(doc.width, 1080);
    assert.equal(doc.height, 1920);
    assert.equal(doc.fps, 30);
    assert.deepEqual(doc.deliverables, []);
    // The final renders to renders/<build.json slug>.mp4, the path the deliver step documents.
    assert.equal(JSON.parse(readFileSync(join(p.dir, 'build.json'), 'utf8')).slug, p.slug);
    // The film format also lands in film.json, the build-only file the timeline step stamps (project.json
    // is rewritten by deliver and must not mark the film stale).
    assert.deepEqual(JSON.parse(readFileSync(join(p.dir, 'film.json'), 'utf8')), { width: 1080, height: 1920, fps: 30 });
    for (const f of TEMPLATE_FILES) assert.ok(existsSync(join(p.dir, f)), `template file missing: ${f}`);
    for (const f of STARTER_FILES) assert.ok(!existsSync(join(p.dir, f)), `HyperFrames starter file present: ${f}`);
    assert.ok(existsSync(p.outbox), 'outbox folder created');
  } finally {
    cleanup(p);
  }
});

test('new-video --kind film with an unknown brand fails and creates nothing', () => {
  const p = project('film-nobrand');
  try {
    const result = run([p.slug, '--kind', 'film', '--brand', 'no-such-brand', '--size', '1080x1920', '--fps', '30']);
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /Brand not found/);
    assert.ok(!existsSync(p.dir), 'project folder must not exist');
    assert.ok(!existsSync(p.outbox), 'outbox folder must not exist');
  } finally {
    cleanup(p);
  }
});

test('new-video --kind film refuses a fractional fps or size and creates nothing', () => {
  for (const [name, args] of [['fps', ['--size', '1080x1920', '--fps', '29.97']], ['size', ['--size', '1080.5x1920', '--fps', '30']]]) {
    const p = project(`film-frac-${name}`);
    try {
      const result = run([p.slug, '--kind', 'film', '--brand', 'none', ...args]);
      assert.notEqual(result.status, 0, name);
      assert.match(result.stderr, /whole number/, name);
      assert.ok(!existsSync(p.dir), `${name}: project folder must not exist`);
      assert.ok(!existsSync(p.outbox), `${name}: outbox folder must not exist`);
    } finally {
      cleanup(p);
    }
  }
});

test('new-video --kind banana fails and creates nothing', () => {
  const p = project('film-banana');
  try {
    const result = run([p.slug, '--kind', 'banana', '--brand', 'none']);
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /--kind must be video or film/);
    assert.ok(!existsSync(p.dir), 'project folder must not exist');
    assert.ok(!existsSync(p.outbox), 'outbox folder must not exist');
  } finally {
    cleanup(p);
  }
});
