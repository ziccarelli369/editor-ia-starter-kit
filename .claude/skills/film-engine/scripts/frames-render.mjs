#!/usr/bin/env node
/* frames-render.mjs: render a canvas page into 1-based PNG sequences with N parallel pages. Owner: node.
 * puppeteer-core + system Chrome (env CHROME), flags --force-color-profile=srgb
 * --allow-file-access-from-files --hide-scrollbars --font-render-hinting=none. Before the page's own
 * script runs it injects ease.mjs and comp-kit.mjs as one classic script (window.FilmEase,
 * window.FilmKit; see engineBundle), so a project page never hard-codes the engine path.
 *
 * Page contract (global named by --api, default FilmPage):
 *   async loadFonts()                 proves fonts, throws listing missing faces
 *   init(timeline)                    builds every seeded element once
 *   render(f) -> {seq: {name: dataURL}, bounds: {name: box}, luma: {mean, std}, checks: [string]}
 *                                     one PNG per sequence name; bounds must stay inside the
 *                                     format.comp canvas (leave off-canvas things out of bounds);
 *                                     checks = failed assertions (empty = ok)
 *   bboxes() -> [{f, ...boxes}]       analytic drawn boxes for every frame (no pixels), each a
 *                                     {l,t,r,b}, [l,t,r,b] or null
 *   contact(urls, labels, cols) -> dataURL   (optional; FilmKit.contact is the default)
 * Output: <out>/<seq>/####.png for every sequence (0001 = frame 1 = t 0), <out>/<page>_bbox.json,
 * and with --contact a sheet of every --contact-every frame plus the last (from the first sequence).
 * Every file is written to a temp name and renamed when every check passes; on a failure the temp
 * files are removed and nothing fresh-looking is left behind. Exit 1 on any check, page error,
 * bound or drawn box outside the canvas, or a sequence that misses any requested frame (a page
 * that returns a sequence name on some frames only; see missingFrames).
 *
 * node frames-render.mjs --page comp.html --timeline build/timeline.json --out build [--pages 4]
 *     [--frames 1,31,61] [--api FilmPage] [--contact comp_contact.png --contact-every 15 --cols 5]
 *     [--bbox comp_bbox.json]
 * --frames renders only those frames (a quick check): the bbox file is still whole (layout only),
 * the contact sheet is skipped and no stale frame is pruned.
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { inFrame, margin, pad4 } from './comp-kit.mjs';

const require = createRequire(import.meta.url);
const HERE = path.dirname(fileURLToPath(import.meta.url));

export const CHROME_DEFAULT = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
export const CHROME_ARGS = ['--force-color-profile=srgb', '--allow-file-access-from-files', '--hide-scrollbars', '--font-render-hinting=none'];
/** The engine modules a page gets, in order, and the global each one's import resolves to. */
export const ENGINE_MODULES = [['ease.mjs', 'FilmEase'], ['comp-kit.mjs', 'FilmKit']];

/** Parse argv -> {page, timeline, out, pages 4, frames [int] | null, api 'FilmPage', contact file |
 *  null, contactEvery 15, cols 5, bbox file | null}. Throws on a missing or unknown option. */
export function parseArgs(argv) {
  const o = { page: null, timeline: null, out: null, pages: 4, frames: null, api: 'FilmPage', contact: null, contactEvery: 15, cols: 5, bbox: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i], v = argv[i + 1];
    if (v === undefined && a.startsWith('--')) throw new Error(`frames-render: ${a} needs a value`);
    switch (a) {
      case '--page': o.page = v; i++; break;
      case '--timeline': o.timeline = v; i++; break;
      case '--out': o.out = v; i++; break;
      case '--pages': o.pages = Math.max(1, Number(v) | 0); i++; break;
      case '--frames': o.frames = v.split(',').filter(Boolean).map((s) => Number(s) | 0); i++; break;
      case '--api': o.api = v; i++; break;
      case '--contact': o.contact = v; i++; break;
      case '--contact-every': o.contactEvery = Math.max(1, Number(v) | 0); i++; break;
      case '--cols': o.cols = Math.max(1, Number(v) | 0); i++; break;
      case '--bbox': o.bbox = v; i++; break;
      default: throw new Error(`frames-render: unknown option ${a}`);
    }
  }
  for (const k of ['page', 'timeline', 'out']) if (!o[k]) throw new Error(`frames-render: --${k} is required`);
  if (o.frames && o.frames.some((f) => !(f >= 1))) throw new Error('frames-render: --frames are 1-based integers');
  return o;
}

/** Turn the engine ESM files into one classic script that sets globalThis.FilmEase and FilmKit.
 *  Each file is wrapped in its own function scope; `import { a, b } from './ease.mjs'` becomes
 *  `const { a, b } = globalThis.FilmEase`; `export` keywords are dropped. Any other import form
 *  throws (the engine files keep to named exports and one-line named imports). */
export function engineBundle(dir = HERE, modules = ENGINE_MODULES) {
  const globals = Object.fromEntries(modules.map(([f, g]) => [`./${f}`, g]));
  return modules.map(([file]) => {
    let src = fs.readFileSync(path.join(dir, file), 'utf8');
    src = src.replace(/^import\s*\{([^}]*)\}\s*from\s*['"]([^'"]+)['"];?[ \t]*$/mg, (m, names, from) => {
      if (!globals[from]) throw new Error(`engineBundle: ${file} imports ${from}, which is not an engine module`);
      return `const {${names}} = globalThis.${globals[from]};`;
    });
    const left = src.match(/^import\s.*$/m);
    if (left) throw new Error(`engineBundle: unsupported import in ${file}: ${left[0]}`);
    src = src.replace(/^export\s+default\s+[^;\n]+;?[ \t]*$/mg, '');
    src = src.replace(/^export\s*\{[^}]*\};?[ \t]*$/mg, '');
    src = src.replace(/^export\s+(?=(?:async\s+)?function\b|const\b|let\b|class\b)/mg, '');
    return `/* ${file} */\n(function () {\n${src}\n})();`;
  }).join('\n');
}

/** Run the bundle in a bare VM context and return the globals it defines; throws when FilmEase or
 *  FilmKit is missing (a transform failure is caught before Chrome starts). */
export function checkBundle(bundle = engineBundle()) {
  const g = vm.runInNewContext(`${bundle}\n;({ FilmEase: globalThis.FilmEase, FilmKit: globalThis.FilmKit })`, {});
  if (!g.FilmEase || typeof g.FilmEase.rng !== 'function') throw new Error('engineBundle: FilmEase missing after the bundle ran');
  if (!g.FilmKit || typeof g.FilmKit.makeRibbon !== 'function') throw new Error('engineBundle: FilmKit missing after the bundle ran');
  return g;
}

/** Launch Chrome with the fixed flags. -> browser */
export async function launch(chromePath = process.env.CHROME || CHROME_DEFAULT) {
  const puppeteer = require('puppeteer-core');
  if (!fs.existsSync(chromePath)) throw new Error(`Chrome not found at ${chromePath} (set env CHROME)`);
  return puppeteer.launch({ executablePath: chromePath, headless: true, args: CHROME_ARGS });
}

/** Open the page with the engine bundle injected before its own script, prove fonts, init with the
 *  timeline. -> page; page.errors collects page errors and console errors as they happen. */
export async function openPage(browser, pageFile, timeline, api = 'FilmPage', bundle = engineBundle()) {
  const page = await browser.newPage();
  page.errors = [];
  page.on('pageerror', (e) => page.errors.push(`page error: ${e.message}`));
  page.on('console', (m) => { if (m.type() === 'error') page.errors.push(`console error: ${m.text()}`); });
  await page.evaluateOnNewDocument(bundle);
  await page.goto(pathToFileURL(path.resolve(pageFile)).href, { waitUntil: 'load' });
  const ok = await page.evaluate((api) => !!(window[api] && typeof window[api].render === 'function'), api);
  if (!ok) throw new Error(`${pageFile} exposes no window.${api} with render(f)` + (page.errors.length ? `: ${page.errors.join('; ')}` : ''));
  await page.evaluate((api) => window[api].loadFonts(), api);
  await page.evaluate((api, tl) => { window[api].init(tl); }, api, timeline);
  return page;
}

/** Write a PNG data URL to file; throws on any other payload. */
export function writeDataURL(file, url) {
  if (typeof url !== 'string' || !url.startsWith('data:image/png;base64,')) throw new Error(`${file}: not a PNG data URL`);
  fs.writeFileSync(file, Buffer.from(url.slice(url.indexOf(',') + 1), 'base64'));
}

/** Shared work queue over pages: render every frame, write each sequence frame to
 *  <outDir>/<seq>/####.png.part, collect failures, bounds and luma.
 *  -> {failures: [string], temps: [[tmp, final]], seqs: [name], luma: {f: {mean, std}},
 *      worst: {m, f, k} tightest bound margin}. canvas = [W, H] for the bounds rule (null skips). */
export async function renderFrames(pages, frames, outDir, api = 'FilmPage', canvas = null) {
  const failures = [], temps = [], luma = {}, seqs = new Set();
  let next = 0, worst = { m: Infinity, f: null, k: null };
  const fmt = (b) => `[${b.l.toFixed(1)},${b.t.toFixed(1)} - ${b.r.toFixed(1)},${b.b.toFixed(1)}]`;
  await Promise.all(pages.map(async (page) => {
    while (next < frames.length) {
      const f = frames[next++];
      let r;
      try {
        r = await page.evaluate((api, n) => window[api].render(n), api, f);
      } catch (e) {
        failures.push(`frame ${f}: render threw: ${e.message}`);
        continue;
      }
      if (!r || !r.seq || !Object.keys(r.seq).length) { failures.push(`frame ${f}: render returned no seq`); continue; }
      for (const [name, url] of Object.entries(r.seq)) {
        seqs.add(name);
        const dir = path.join(outDir, name);
        fs.mkdirSync(dir, { recursive: true });
        const tmp = path.join(dir, pad4(f) + '.png.part');
        try { writeDataURL(tmp, url); } catch (e) { failures.push(`frame ${f}: ${e.message}`); continue; }
        temps.push([tmp, path.join(dir, pad4(f) + '.png')]);
      }
      for (const c of r.checks || []) failures.push(`frame ${f}: ${c}`);
      if (canvas) {
        for (const [k, b] of Object.entries(r.bounds || {})) {
          if (!b) continue;
          if (!inFrame(b, canvas[0], canvas[1])) failures.push(`frame ${f}: ${k} leaves the frame ${fmt(b)}`);
          const m = margin(b, canvas[0], canvas[1]);
          if (m < worst.m) worst = { m, f, k };
        }
      }
      if (r.luma) luma[f] = r.luma;
    }
  }));
  return { failures, temps, seqs: [...seqs], luma, worst };
}

/** Gaps per sequence: the requested frames with no temp file in renderFrames' temps
 *  ([[tmp, <outDir>/<seq>/####.png]]). frames is the requested list (all of 1..n, or --frames).
 *  -> {seq: [f...]} with only the sequences that miss a frame; {} when every sequence is whole. */
export function missingFrames(seqs, temps, frames, outDir) {
  const have = new Set(temps.map(([, fin]) => path.resolve(fin)));
  const gaps = {};
  for (const seq of seqs) {
    const miss = frames.filter((f) => !have.has(path.resolve(outDir, seq, pad4(f) + '.png')));
    if (miss.length) gaps[seq] = miss;
  }
  return gaps;
}

const asBox = (b) => (Array.isArray(b) ? { l: b[0], t: b[1], r: b[2], b: b[3] } : b);
const round1 = (v) => Math.round(v * 10) / 10;

/** Ask one page for bboxes() and write outFile (temp name outFile + '.part') with an 'about' line,
 *  the canvas size and the frame list; every box becomes [l, t, r, b] rounded to 0.1 px.
 *  -> {frames: [{f, ...}], failures: [string] (boxes outside the canvas), tmp}. */
export async function writeBboxes(page, outFile, api = 'FilmPage', about = '', canvas = null) {
  const raw = await page.evaluate((api) => window[api].bboxes(), api);
  if (!Array.isArray(raw)) throw new Error('bboxes() must return a list');
  const failures = [];
  const frames = raw.map((o) => {
    const row = { f: o.f };
    for (const [k, v] of Object.entries(o)) {
      if (k === 'f') continue;
      if (v === null || v === undefined) { row[k] = null; continue; }
      const b = asBox(v);
      row[k] = [b.l, b.t, b.r, b.b].map(round1);
      if (canvas && !inFrame(b, canvas[0], canvas[1])) failures.push(`frame ${o.f}: drawn ${k} leaves the frame ${row[k]}`);
    }
    return row;
  });
  const doc = { about: about || 'Drawn boxes in canvas px, [left, top, right, bottom], per film frame (f 1 = t 0). null = nothing drawn.',
    canvas, frames };
  const tmp = outFile + '.part';
  fs.writeFileSync(tmp, JSON.stringify(doc, null, 0).replace(/\{"f"/g, '\n{"f"') + '\n');
  return { frames, failures, tmp };
}

/** Build the contact sheet from PNGs on disk through the page's contact() (or FilmKit.contact) and
 *  write it to outFile. labels: one string per png. */
export async function contactSheet(page, pngs, labels, cols, outFile, api = 'FilmPage') {
  const urls = pngs.map((p) => 'data:image/png;base64,' + fs.readFileSync(p).toString('base64'));
  const sheet = await page.evaluate((api, u, l, c) => {
    const fn = (window[api] && window[api].contact) || window.FilmKit.contact;
    return fn(u, l, c);
  }, api, urls, labels, cols);
  writeDataURL(outFile, sheet);
  return outFile;
}

export async function main(argv = process.argv.slice(2)) {
  const o = parseArgs(argv);
  const tl = JSON.parse(fs.readFileSync(o.timeline, 'utf8'));
  const N = tl.format.frames, fps = tl.format.fps, canvas = tl.format.comp || null;
  const frames = o.frames || Array.from({ length: N }, (_, i) => i + 1);
  const bundle = engineBundle();
  checkBundle(bundle);
  fs.mkdirSync(o.out, { recursive: true });
  const pageBase = path.basename(o.page).replace(/\.[^.]+$/, '');
  const bboxFile = path.join(o.out, o.bbox || `${pageBase}_bbox.json`);
  const failures = [], temps = [];
  let res = null, sheet = null;
  const t0 = Date.now();
  const browser = await launch();
  try {
    const first = await openPage(browser, o.page, tl, o.api, bundle);
    const bb = await writeBboxes(first, bboxFile, o.api, '', canvas);
    temps.push([bb.tmp, bboxFile]);
    failures.push(...bb.failures);
    const nonNull = Object.keys(bb.frames[0] || {}).filter((k) => k !== 'f');
    console.log(`${path.basename(bboxFile)}: ${bb.frames.length} frames, keys ${nonNull.join(', ') || '(none)'}`);
    if (bb.frames.length !== N) failures.push(`bboxes() returned ${bb.frames.length} frames, format.frames is ${N}`);

    const workers = [first];
    for (let i = 1; i < Math.min(o.pages, frames.length); i++) workers.push(await openPage(browser, o.page, tl, o.api, bundle));
    res = await renderFrames(workers, frames, o.out, o.api, canvas);
    failures.push(...res.failures);
    temps.push(...res.temps);
    for (const [seq, miss] of Object.entries(missingFrames(res.seqs, res.temps, frames, o.out))) {
      const list = miss.slice(0, 20).join(', ') + (miss.length > 20 ? ', ...' : '');
      failures.push(`sequence ${seq}: ${miss.length} of ${frames.length} requested frames missing: ${list}`);
    }
    for (const w of workers) failures.push(...w.errors);

    if (o.contact && !o.frames && !failures.length) {
      const seq = res.seqs[0];
      const pick = [];
      for (let f = 1; f <= N; f += o.contactEvery) pick.push(f);
      if (pick[pick.length - 1] !== N) pick.push(N);
      const pngs = pick.map((f) => path.join(o.out, seq, pad4(f) + '.png.part'));
      const labels = pick.map((f) => `f${pad4(f)}  ${((f - 1) / fps).toFixed(2)} s`);
      sheet = path.join(o.out, o.contact);
      await contactSheet(first, pngs, labels, o.cols, sheet + '.part', o.api);
      temps.push([sheet + '.part', sheet]);
      console.log(`${o.contact}: ${pick.length} frames of ${seq}, every ${o.contactEvery}`);
    }
  } finally {
    await browser.close();
  }
  if (res) {
    const stds = Object.entries(res.luma).map(([f, l]) => [Number(f), l.std]).sort((a, b) => a[1] - b[1]);
    const lo = stds[0], hi = stds[stds.length - 1];
    console.log(`${frames.length} frames in ${((Date.now() - t0) / 1000).toFixed(1)} s on ${Math.min(o.pages, frames.length)} page(s); sequences ${res.seqs.join(', ')}` +
      (res.worst.f !== null ? `; tightest margin ${res.worst.m.toFixed(1)} px (${res.worst.k}, frame ${res.worst.f})` : '') +
      (lo ? `; luma std ${lo[1].toFixed(1)} (f${lo[0]}) .. ${hi[1].toFixed(1)} (f${hi[0]})` : ''));
  }
  if (failures.length) {
    for (const [tmp] of temps) fs.rmSync(tmp, { force: true });
    console.error(`FAILED ${failures.length} check(s):\n  ` + failures.slice(0, 40).join('\n  '));
    process.exit(1);
  }
  for (const [tmp, final] of temps) fs.renameSync(tmp, final);
  if (!o.frames && res) {
    const keep = new Set(frames.map((f) => pad4(f) + '.png'));
    for (const seq of res.seqs) {
      for (const name of fs.readdirSync(path.join(o.out, seq))) {
        if (/^\d{4}\.png$/.test(name) && !keep.has(name)) fs.rmSync(path.join(o.out, seq, name));
      }
    }
  }
  console.log('all checks passed');
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((e) => { console.error(e.stack || e); process.exit(1); });
}
