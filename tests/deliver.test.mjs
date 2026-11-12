import test from 'node:test';
import assert from 'node:assert/strict';
import { cpSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { spawnSync } from 'node:child_process';
const root = resolve(import.meta.dirname, '..');

test('stage keeps every round; promote leaves one unversioned final per deliverable; clean empties staging only', () => {
  const kit = mkdtempSync(join(tmpdir(), 'kit-deliver-'));
  try {
    for (const f of ['deliver.mjs', 'clean-staging.mjs', 'lib']) cpSync(join(root, 'scripts', f), join(kit, 'scripts', f), { recursive: true });
    cpSync(join(root, 'kit.config.json'), join(kit, 'kit.config.json'));
    const id = '2026-01-01-demo';
    const project = join(kit, 'video-projects', id);
    mkdirSync(join(project, 'renders'), { recursive: true });
    writeFileSync(join(project, 'project.json'), JSON.stringify({ id, slug: 'demo', status: 'editing', deliverables: [] }));
    const render = (f, text) => { writeFileSync(join(project, 'renders', f), text); return join(project, 'renders', f); };
    const run = (script, ...args) => spawnSync(process.execPath, [join(kit, 'scripts', script), ...args], { encoding: 'utf8' });
    const ok = r => { assert.equal(r.status, 0, r.stdout + r.stderr); return r.stdout; };
    const outbox = () => readdirSync(join(kit, 'outbox', id)).sort();
    const read = f => readFileSync(join(kit, 'outbox', id, f), 'utf8');

    ok(run('deliver.mjs', id, '--stage', '--video', render('a.mp4', 'v1'), '--cover', render('a.png', 'c1'), '--srt', render('a.srt', 's1')));
    assert.match(ok(run('deliver.mjs', id, '--stage', '--video', render('b.mp4', 'v2'), '--cover', render('b.png', 'c2'))), /demo v2/);
    assert.deepEqual(readdirSync(join(kit, 'staging', id)).sort(), ['demo-v1-cover.png', 'demo-v1-srt.srt', 'demo-v1-video.mp4', 'demo-v2-cover.png', 'demo-v2-video.mp4']);
    assert.ok(!existsSync(join(kit, 'outbox')), 'stage writes nothing to outbox');

    ok(run('deliver.mjs', id, '--stage', '--video', render('c.mp4', 'v3')));
    assert.match(run('deliver.mjs', id, '--promote', '3').stderr, /Promote blocked.*Missing.*cover/);

    ok(run('deliver.mjs', id, '--promote', '1'));
    assert.deepEqual(outbox(), ['demo-cover.png', 'demo-srt.srt', 'demo-video.mp4']);
    assert.equal(read('demo-video.mp4'), 'v1');
    ok(run('deliver.mjs', id, '--promote', '2'));
    assert.deepEqual(outbox(), ['demo-cover.png', 'demo-video.mp4']);
    assert.equal(read('demo-video.mp4'), 'v2');
    const doc = JSON.parse(readFileSync(join(project, 'project.json'), 'utf8'));
    assert.deepEqual(doc.deliverables.map(d => [d.name, d.version, d.files]), [['demo', 2, { video: 'demo-video.mp4', cover: 'demo-cover.png' }]]);
    assert.equal(doc.status, 'delivered');

    assert.match(ok(run('clean-staging.mjs', id, '--older-than', '1')), /Nothing to clean/);
    assert.match(ok(run('clean-staging.mjs')), /Removed 6 staged file/);
    assert.deepEqual(readdirSync(join(kit, 'staging')), []);
    assert.deepEqual(outbox(), ['demo-cover.png', 'demo-video.mp4']);
    assert.equal(readdirSync(join(project, 'renders')).length, 6);
  } finally {
    rmSync(kit, { recursive: true, force: true });
  }
});
