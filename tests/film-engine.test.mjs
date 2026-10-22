// film-engine: pure Node checks of the engine's JS (no Chrome, no Blender; runs in CI on 3 OSes).
import test from 'node:test';
import assert from 'node:assert/strict';
import { writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { rng } from '../.claude/skills/film-engine/scripts/ease.mjs';
import {
  box, grow, shift, union, inFrame, margin, pad4, timecode, typeOnPrefixes, makeRibbon,
} from '../.claude/skills/film-engine/scripts/comp-kit.mjs';
import * as ui from '../.claude/skills/film-engine/scripts/ui-render.mjs';
import * as fr from '../.claude/skills/film-engine/scripts/frames-render.mjs';
import { chromeCandidates, findChrome } from '../.claude/skills/film-engine/scripts/tool-paths.mjs';
import { findPython, filmDoctor } from '../scripts/lib/film-doctor.mjs';

const root = resolve(import.meta.dirname, '..');
const engine = join(root, '.claude/skills/film-engine/scripts');
const python = findPython();
const noPython = !python && 'no Python 3.10+ on this machine';

function pyJson(code, env = {}) {
  const r = spawnSync(python[0], [...python.slice(1), '-B', '-c', code], {
    cwd: engine, encoding: 'utf8', windowsHide: true, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1', ...env },
  });
  assert.equal(r.status, 0, r.stderr);
  return JSON.parse(r.stdout.trim().split(/\r?\n/).pop());
}

// Five draws per seed from filmkit.ease.mulberry32 (python -B, repr()); the JS twin must match bit for bit.
const PY_RNG = {
  0: [0.26642920868471265, 0.0003297457005828619, 0.2232720274478197, 0.1462021479383111, 0.46732782293111086],
  7: [0.011704753153026104, 0.06195825757458806, 0.97690763277933, 0.6990287057124078, 0.5214452685322613],
  2026: [0.45540769933722913, 0.30849614599719644, 0.6611574492417276, 0.6184752183035016, 0.15228010178543627],
  4294967295: [0.8964226141106337, 0.189478256739676, 0.7156526781618595, 0.9440599093213677, 0.8452364315744489],
  2147483648: [0.8205775609239936, 0.4481089550536126, 0.7836112855002284, 0.5120457962621003, 0.8388098266441375],
};

test('rng(seed) matches the Python mulberry32 vectors', () => {
  for (const [seed, want] of Object.entries(PY_RNG)) {
    const r = rng(Number(seed));
    assert.deepEqual(Array.from({ length: 5 }, () => r()), want, `seed ${seed}`);
  }
});

test('box helpers: grow, shift, union with null, inFrame and margin', () => {
  const b = box(10, 20, 30, 40);
  assert.deepEqual(grow(b, 2), box(8, 18, 32, 42));
  assert.deepEqual(shift(b, 5, -5), box(15, 15, 35, 35));
  assert.deepEqual(union(null, b), b);
  assert.deepEqual(union(b, null), b);
  assert.equal(union(null, null), null);
  assert.deepEqual(union(b, box(0, 25, 12, 50)), box(0, 20, 30, 50));
  assert.equal(inFrame(b, 30, 40), true);
  assert.equal(inFrame(b, 29, 40), false);
  assert.equal(margin(b, 100, 100), 10);
  assert.equal(margin(box(-1, 0, 5, 5), 10, 10), -1);
});

test('timecode and pad4 follow the half-up frame rule', () => {
  assert.equal(timecode(0, 30), '0:00:00:00');
  assert.equal(timecode(4.0, 30), '0:00:04:00');
  assert.equal(timecode(1 / 30 * 29, 30), '0:00:00:29');
  assert.equal(timecode(4.95, 30), '0:00:04:29');       // 148.5 -> 149 frames (floor(x + 0.5)), not banker's 148
  assert.equal(timecode(3661.5, 30), '1:01:01:15');
  assert.equal(timecode(-1, 30), '0:00:00:00');
  assert.equal(pad4(7), '0007');
  assert.equal(pad4(360), '0360');
});

/** Fake 2D context: every glyph is 10 px wide plus the letter spacing; ink 1 px inside the advance. */
function fakeCtx() {
  return {
    font: '', letterSpacing: '0px',
    measureText(s) {
      const track = parseFloat(this.letterSpacing) || 0;
      const n = s.length, width = n * (10 + track);
      return { width, actualBoundingBoxLeft: n ? -1 : 0, actualBoundingBoxRight: n ? width - track - 1 : 0,
        actualBoundingBoxAscent: 8, actualBoundingBoxDescent: 2 };
    },
  };
}

test('typeOnPrefixes centres the full ink on the anchor and grows one glyph per prefix', () => {
  const ctx = fakeCtx();
  const r = typeOnPrefixes(ctx, '900 10px Fake', -1, 'ABCD', [100, 50], 20);
  assert.equal(ctx.font, '900 10px Fake');
  assert.equal(ctx.letterSpacing, '0px', 'letter spacing restored after measuring');
  assert.equal(r.prefixes.length, 5);
  assert.equal(r.prefixes[0].ink, null);
  // full ink: left -1 .. right 34 relative to the pen -> 35 wide, centred on x 100
  const full = r.prefixes[4].ink;
  assert.ok(Math.abs((full.l + full.r) / 2 - 100) < 1e-9);
  assert.equal(full.r - full.l, 35);
  assert.equal(full.t, 50 + 20 - 8);
  assert.equal(full.b, 50 + 20 + 2);
  // each prefix adds one 9 px advance (10 - 1 tracking) to the right edge; top and bottom never move
  for (let k = 1; k < 4; k++) {
    assert.ok(Math.abs(r.prefixes[k + 1].ink.r - r.prefixes[k].ink.r - 9) < 1e-9, `prefix ${k}`);
    assert.equal(r.prefixes[k].ink.t, full.t);
    assert.equal(r.prefixes[k].ink.l, full.l);
  }
  assert.equal(r.prefixes[0].caretX, r.pen[0]);
  assert.ok(Math.abs(r.prefixes[2].caretX - (r.pen[0] + 19)) < 1e-9, 'caret = pen + advance(2 glyphs, 18) - tracking(-1)');
  assert.equal(r.ascent, 8);
  assert.equal(r.descent, 2);
});

test('makeRibbon: straight path length, trimmed box, quarter-circle arc length', () => {
  const line = makeRibbon([{ p: [0, 0] }, { p: [100, 0] }], () => 10, 50);
  assert.ok(Math.abs(line.length - 100) < 1e-9);
  assert.deepEqual(line.box(0, 0, 100), box(-5, -5, 105, 5));
  assert.deepEqual(line.box(3, 4, 40), box(-2, -1, 48, 9));
  const p = line.pointAt(25);
  assert.ok(Math.abs(p.x - 25) < 1e-9 && Math.abs(p.y) < 1e-9);
  assert.ok(Math.abs(Math.abs(p.ny) - 1) < 1e-9, 'normal is perpendicular to the line');
  const c = line.centre(1, 1, 30);
  assert.deepEqual(c[0], [1, 1]);
  assert.ok(Math.abs(c[c.length - 1][0] - 31) < 1e-9);
  // quarter circle of radius 100 with the usual 0.5523 handles: arc length pi/2 * 100 within 0.1 %
  const k = 0.5523 * 100;
  const arc = makeRibbon([{ p: [100, 0], o: [100, k] }, { p: [0, 100], i: [k, 100] }], (s) => 4 + 4 * s, 240);
  assert.ok(Math.abs(arc.length - Math.PI * 50) < Math.PI * 50 * 1e-3, `arc length ${arc.length}`);
  assert.ok(Math.abs(arc.pointAt(arc.length).w - 8) < 1e-9, 'width follows the share along the path');
  assert.throws(() => makeRibbon([{ p: [0, 0] }], () => 1));
});

test('ui-render parseArgs: defaults, mode pairs with empty classes, flat overrides', () => {
  const o = ui.parseArgs(['--html', 'a.html', '--timeline', 't.json', '--out', 'b']);
  assert.deepEqual(o.modes, [['ui.png', ''], ['ui_base.png', 'base'], ['ui_check.png', 'check']]);
  assert.equal(o.sprites, null);
  assert.equal(o.scale, null);
  const p = ui.parseArgs(['--html', 'a', '--timeline', 't', '--out', 'b', '--modes', 'x.png:,y.png:base',
    '--sprites', 'chip.png:chip', '--scale', '2', '--flat', 'comp:#000000,tc:#232323', '--font', 'Segoe UI']);
  assert.deepEqual(p.modes, [['x.png', ''], ['y.png', 'base']]);
  assert.deepEqual(p.sprites, [['chip.png', 'chip']]);
  assert.deepEqual(p.flat, { comp: '#000000', tc: '#232323' });
  assert.equal(p.scale, 2);
  assert.equal(p.font, 'Segoe UI');
  assert.throws(() => ui.parseArgs(['--html', 'a']), /--timeline is required/);
  assert.throws(() => ui.parseArgs(['--html', 'a', '--timeline', 't', '--out', 'b', '--bogus', '1']), /unknown option/);
});

test('ui-render pngSize reads the IHDR and rejects a non-PNG', () => {
  const dir = mkdtempSync(join(tmpdir(), 'film-engine-test-'));
  const png = Buffer.alloc(33);
  png.writeUInt32BE(0x89504e47, 0); png.writeUInt32BE(0x0d0a1a0a, 4);
  png.writeUInt32BE(13, 8); png.write('IHDR', 12); png.writeUInt32BE(3840, 16); png.writeUInt32BE(2160, 20);
  writeFileSync(join(dir, 'a.png'), png);
  assert.deepEqual(ui.pngSize(join(dir, 'a.png')), [3840, 2160]);
  writeFileSync(join(dir, 'b.png'), 'not a png at all, just text');
  assert.throws(() => ui.pngSize(join(dir, 'b.png')), /not a PNG/);
});

test('frames-render parseArgs: frames list, pages, contact options', () => {
  const o = fr.parseArgs(['--page', 'c.html', '--timeline', 't.json', '--out', 'b', '--frames', '1,31,61', '--pages', '2',
    '--contact', 'sheet.png', '--contact-every', '15', '--cols', '5', '--api', 'Comp']);
  assert.deepEqual(o.frames, [1, 31, 61]);
  assert.equal(o.pages, 2);
  assert.equal(o.api, 'Comp');
  assert.equal(o.contactEvery, 15);
  assert.equal(fr.parseArgs(['--page', 'c', '--timeline', 't', '--out', 'b']).pages, 4);
  assert.throws(() => fr.parseArgs(['--page', 'c', '--timeline', 't', '--out', 'b', '--frames', '0,1']), /1-based/);
  assert.throws(() => fr.parseArgs(['--page', 'c', '--timeline', 't']), /--out is required/);
});

test('frames-render missingFrames names the sequence and the requested frames it lacks', () => {
  const frames = [1, 31, 61];                    // a --frames run: the gap check uses this list, not 1..61
  const t = (seq, f) => [join('out', seq, pad4(f) + '.png.part'), join('out', seq, pad4(f) + '.png')];
  const whole = ['main', 'tc'].flatMap((seq) => frames.map((f) => t(seq, f)));
  assert.deepEqual(fr.missingFrames(['main', 'tc'], whole, frames, 'out'), {});
  const gap = whole.filter(([, fin]) => fin !== join('out', 'tc', '0031.png'));
  assert.deepEqual(fr.missingFrames(['main', 'tc'], gap, frames, 'out'), { tc: [31] });
});

test('engineBundle turns ease.mjs + comp-kit.mjs into one classic script with both globals', () => {
  const bundle = fr.engineBundle(engine);
  assert.ok(!/^\s*(import|export)\s/m.test(bundle), 'no import/export left');
  const g = fr.checkBundle(bundle);
  const r = g.FilmEase.rng(2026);
  assert.deepEqual([r(), r()], PY_RNG[2026].slice(0, 2));
  assert.equal(typeof g.FilmKit.typeOnPrefixes, 'function');
  assert.equal(g.FilmKit.timecode(4.95, 30), '0:00:04:29');
  // a foreign import in an engine file is refused, not silently dropped
  const dir = mkdtempSync(join(tmpdir(), 'film-engine-test-'));
  writeFileSync(join(dir, 'ease.mjs'), 'export const x = 1;\nglobalThis.FilmEase = { x };\n');
  writeFileSync(join(dir, 'comp-kit.mjs'), "import { y } from './other.mjs';\nglobalThis.FilmKit = { y };\n");
  assert.throws(() => fr.engineBundle(dir), /not an engine module/);
});

test('writeDataURL refuses anything but a PNG data URL', () => {
  const dir = mkdtempSync(join(tmpdir(), 'film-engine-test-'));
  assert.throws(() => fr.writeDataURL(join(dir, 'x.png'), 'data:text/plain;base64,aGk='), /not a PNG data URL/);
  fr.writeDataURL(join(dir, 'y.png'), 'data:image/png;base64,iVBORw0KGgo=');
  assert.deepEqual([...Buffer.from('iVBORw0KGgo=', 'base64')], [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
});

test('tool-paths: CHROME wins, then the install folders of the platform, then PATH', () => {
  assert.equal(findChrome({ CHROME: 'q' }), 'q');
  assert.deepEqual(chromeCandidates('win32', { ProgramFiles: 'C:\\PF', 'ProgramFiles(x86)': 'C:\\PF86', LOCALAPPDATA: 'C:\\LA' }),
    ['C:\\PF\\Google\\Chrome\\Application\\chrome.exe', 'C:\\PF86\\Google\\Chrome\\Application\\chrome.exe', 'C:\\LA\\Google\\Chrome\\Application\\chrome.exe']);
  assert.equal(chromeCandidates('darwin', {})[0], '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome');
  assert.deepEqual(chromeCandidates('linux', { PATH: '' }), ['google-chrome']);
  const dir = mkdtempSync(join(tmpdir(), 'film-engine-test-'));
  writeFileSync(join(dir, 'chromium'), '');
  assert.deepEqual(chromeCandidates('linux', { PATH: dir }), [join(dir, 'chromium')]);
  assert.equal(findChrome({ PATH: dir }, 'linux'), join(dir, 'chromium'));
  assert.equal(findChrome({ PATH: '' }, 'linux'), 'google-chrome', 'nothing found: the first place looked at');
  assert.equal(chromeCandidates('darwin', { PATH: dir }).at(-1), join(dir, 'chromium'), 'macOS falls back to PATH');
  writeFileSync(join(dir, 'chrome.exe'), '');
  assert.deepEqual(chromeCandidates('win32', { ProgramFiles: 'C:\\PF', PATH: dir }),
    ['C:\\PF\\Google\\Chrome\\Application\\chrome.exe', join(dir, 'chrome.exe')], 'Windows falls back to PATH');
});

test('build.tool_paths honours BLENDER and CHROME', { skip: noPython }, () => {
  const t = pyJson('import json, build; print(json.dumps(build.tool_paths()))', { BLENDER: 'x/blender', CHROME: 'y/chrome' });
  assert.equal(t.blender, 'x/blender');
  assert.equal(t.chrome, 'y/chrome');
  assert.ok(t.python && t.node && t.engine);
});

test('filmkit.tools: newest Blender 5.x by numeric version, per-platform Chrome and Blender places', { skip: noPython }, () => {
  const t = pyJson(`
import json, os, tempfile
from filmkit import tools
tmp = tempfile.mkdtemp(prefix='film_tools_')
for v in ('5.2', '5.10', '4.9'):
    d = os.path.join(tmp, 'Blender Foundation', 'Blender ' + v)
    os.makedirs(d)
    open(os.path.join(d, 'blender.exe'), 'w').close()
none = lambda n: None
print(json.dumps({
 'win': [p.replace(os.sep, '/') for p in tools.blender_candidates('win32', {'ProgramFiles': tmp}, none)],
 'win_empty': [p.replace(os.sep, '/') for p in tools.blender_candidates('win32', {'ProgramFiles': os.path.join(tmp, 'none')}, none)],
 'mac': tools.blender_candidates('darwin', {'HOME': '/h'}, none),
 'lin': tools.blender_candidates('linux', {}, lambda n: '/usr/bin/' + n),
 'lin_none': tools.blender_candidates('linux', {}, none),
 'chrome_win': [p.replace(os.sep, '/') for p in tools.chrome_candidates('win32', {'ProgramFiles': 'P', 'LOCALAPPDATA': 'L'}, none)],
 'chrome_lin': tools.chrome_candidates('linux', {}, none),
 'chrome_mac_path': tools.chrome_candidates('darwin', {}, lambda n: '/opt/homebrew/bin/' + n),
 'chrome_win_path': tools.chrome_candidates('win32', {'ProgramFiles': 'P'}, lambda n: 'C:/shims/' + n),
 'env': [tools.find_blender({'BLENDER': 'z'}), tools.find_chrome({'CHROME': 'c'})],
}))`);
  assert.equal(t.win.length, 2, 'Blender 4.9 is left out');
  assert.ok(t.win[0].endsWith('/Blender 5.10/blender.exe') && t.win[1].endsWith('/Blender 5.2/blender.exe'), `${t.win}`);
  assert.ok(t.win_empty[0].endsWith('/Blender Foundation/Blender 5.x/blender.exe'), 'nothing found: names where it looked');
  assert.deepEqual(t.mac, ['/Applications/Blender.app/Contents/MacOS/Blender', '/h/Applications/Blender.app/Contents/MacOS/Blender']);
  assert.deepEqual(t.lin, ['/usr/bin/blender', '/snap/bin/blender']);
  assert.deepEqual(t.lin_none, ['/snap/bin/blender']);
  assert.deepEqual(t.chrome_win, ['P/Google/Chrome/Application/chrome.exe', 'L/Google/Chrome/Application/chrome.exe']);
  assert.deepEqual(t.chrome_lin, ['google-chrome']);
  assert.deepEqual(t.chrome_mac_path.slice(2), ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'].map((n) => '/opt/homebrew/bin/' + n), 'macOS falls back to PATH');
  assert.deepEqual(t.chrome_win_path.slice(1), ['C:/shims/chrome', 'C:/shims/chromium'], 'Windows falls back to PATH');
  assert.deepEqual(t.env, ['z', 'c']);
});

test('filmkit.outpath: under refuses an escape, an outside path, a root base and a rooted no-drive path; root_problem flags the drive root', { skip: noPython }, () => {
  const t = pyJson(`
import json, os, tempfile
from filmkit import outpath
base = os.path.join(tempfile.gettempdir(), 'film_outpath_test', 'proj')
root = os.path.splitdrive(base)[0] + os.sep
def err(fn):
    try:
        fn()
        return None
    except ValueError as e:
        return str(e)
print(json.dumps({
 'rel': outpath.under(base, os.path.join('renders', 'x.png')).replace(os.sep, '/'),
 'abs_inside': outpath.under(base, os.path.join(base, 'build', 'a.blend')).replace(os.sep, '/'),
 'cwd_rel': outpath.under(base, 'out', os.path.join(base, 'renders')).replace(os.sep, '/'),
 'seq': outpath.under(base, 'renders/frames/').replace(os.sep, '/'),
 'escape': err(lambda: outpath.under(base, os.path.join('..', 'x.png'))),
 'outside': err(lambda: outpath.under(base, os.path.join(tempfile.gettempdir(), 'elsewhere.png'))),
 'root_base': err(lambda: outpath.under(root, 'x.png')),
 'rel_base': err(lambda: outpath.under('proj', 'x.png')),
 'rooted': err(lambda: outpath.under(base, '/renders')),
 'rp_rel': outpath.root_problem('renders/x.png'),
 'rp_empty': outpath.root_problem(''),
 'rp_root_file': outpath.root_problem(os.path.join(root, 'x.png')),
 'rp_root_seq': outpath.root_problem(root),
 'rp_slash': outpath.root_problem('/renders/x.png'),
 'rp_ok_seq': outpath.root_problem(os.path.join(base, 'renders', 'frames') + os.sep),
 'rp_ok_file': outpath.root_problem(os.path.join(base, 'f.png')),
 'nt': os.name == 'nt',
}))`);
  assert.ok(t.rel.endsWith('/film_outpath_test/proj/renders/x.png'), t.rel);
  assert.ok(t.abs_inside.endsWith('/proj/build/a.blend'));
  assert.ok(t.cwd_rel.endsWith('/proj/renders/out'), 'a relative path is taken from the cwd');
  assert.ok(t.seq.endsWith('/proj/renders/frames/'), `a frame folder keeps its trailing separator: ${t.seq}`);
  for (const k of ['escape', 'outside', 'root_base', 'rel_base', 'rooted']) assert.match(t[k] || '', /^outpath: /, k);
  for (const k of ['rp_rel', 'rp_empty', 'rp_root_file', 'rp_root_seq']) assert.ok(t[k], k);
  if (t.nt) assert.match(t.rp_slash, /no drive/);
  assert.equal(t.rp_ok_seq, null);
  assert.equal(t.rp_ok_file, null);
});

test('doctor.py keeps its line format: ok/FAIL/warn lines, a fix hint on every FAIL, a DOCTOR verdict', { skip: noPython, timeout: 180_000 }, () => {
  const { ok, lines } = filmDoctor(root);
  assert.ok(lines.length >= 9, lines.join('\n'));
  const verdict = lines[lines.length - 1];
  assert.match(verdict, /^DOCTOR: (ok|\d+ failed)$/);
  const failed = lines.filter((l) => l.startsWith('FAIL  '));
  assert.equal(ok, verdict === 'DOCTOR: ok');
  assert.equal(verdict, failed.length ? `DOCTOR: ${failed.length} failed` : 'DOCTOR: ok');
  for (const l of lines.slice(0, -1)) {
    assert.match(l, /^(ok  |FAIL|warn)  [a-z -]+: \S/, l);
    if (l.startsWith('FAIL')) assert.match(l, / → \S/, `no fix hint: ${l}`);
  }
});
