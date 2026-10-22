#!/usr/bin/env node
/* ui-render.mjs: screenshot the app page into UI textures and prove the layout contract. Owner: node.
 * puppeteer-core (kit node_modules) + system Chrome (env CHROME). Launch flags:
 * --force-color-profile=srgb --hide-scrollbars --font-render-hinting=none. Viewport = format.ui at
 * deviceScaleFactor = scale. Waits for document.fonts.ready and fails when --font falls back.
 *
 * Modes come from --modes and from the page's sprites (window.UI_SPRITES, or --sprites): each mode
 * sets a class on <html> and writes one PNG. Checks after the screenshots: every [data-in] element
 * inside #ui and, in its own mode, inside each sprite lies inside the rect it names (union of its
 * box, descendant boxes and text range, SVG children skipped, eps 0.01 CSS px); every screen rect
 * (window.UI_EMPTY, colours overridable with --flat) is one flat colour within +-1 per channel;
 * every panel, button and screen rect in the page equals the timeline's (a stale ui.html fails).
 * PNGs are written to temp names and renamed only when every check passes; exit 1 otherwise.
 *
 * node ui-render.mjs --html build/ui.html --timeline build/timeline.json --out build
 *     [--modes ui.png:,ui_base.png:base,ui_check.png:check] [--sprites chip.png:chip]
 *     [--font "Segoe UI"] [--scale 3] [--flat comp:#000000,timecode:#232323]
 * --flat overrides the colours stored in the page's UI_EMPTY; --scale overrides format.ui_scale.
 * Prints the font widths, every PNG's size and the contract line.
 */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL, fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);

export const CHROME_DEFAULT = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
export const CHROME_ARGS = ['--force-color-profile=srgb', '--hide-scrollbars', '--font-render-hinting=none'];
const DEFAULT_MODES = [['ui.png', ''], ['ui_base.png', 'base'], ['ui_check.png', 'check']];

/** 'a.png:cls,b.png:' -> [['a.png', 'cls'], ['b.png', '']] (split on the first colon only). */
function pairs(s) {
  return s.split(',').filter(Boolean).map((item) => {
    const k = item.indexOf(':');
    return k < 0 ? [item, ''] : [item.slice(0, k), item.slice(k + 1)];
  });
}

/** Parse argv -> {html, timeline, out, modes: [[file, cls]], sprites: [[file, name]] | null,
 *  font: string | null, scale: number | null, flat: {screen: '#hex'}}. Throws on a missing
 *  required option or an unknown one. */
export function parseArgs(argv) {
  const o = { html: null, timeline: null, out: null, modes: DEFAULT_MODES, sprites: null, font: null, scale: null, flat: {} };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i], v = argv[i + 1];
    if (v === undefined && a.startsWith('--')) throw new Error(`ui-render: ${a} needs a value`);
    switch (a) {
      case '--html': o.html = v; i++; break;
      case '--timeline': o.timeline = v; i++; break;
      case '--out': o.out = v; i++; break;
      case '--modes': o.modes = pairs(v); i++; break;
      case '--sprites': o.sprites = pairs(v); i++; break;
      case '--font': o.font = v; i++; break;
      case '--scale': o.scale = Number(v); i++; break;
      case '--flat': o.flat = Object.fromEntries(pairs(v)); i++; break;
      default: throw new Error(`ui-render: unknown option ${a}`);
    }
  }
  for (const k of ['html', 'timeline', 'out']) if (!o[k]) throw new Error(`ui-render: --${k} is required`);
  if (o.scale !== null && !(o.scale > 0)) throw new Error('ui-render: --scale must be > 0');
  return o;
}

/** Launch Chrome through puppeteer-core with the fixed flags. -> browser */
export async function launch(chromePath = process.env.CHROME || CHROME_DEFAULT) {
  const puppeteer = require('puppeteer-core');
  if (!fs.existsSync(chromePath)) throw new Error(`Chrome not found at ${chromePath} (set env CHROME)`);
  return puppeteer.launch({ executablePath: chromePath, headless: true, args: CHROME_ARGS });
}

/** Width test of fontName vs serif and monospace at 11 px. -> {font, serif, mono} widths (px);
 *  throws when the named font is within 0.5 px of either fallback (it is not in use). */
export async function proveFont(page, fontName) {
  const w = await page.evaluate((name) => {
    const c = document.createElement('canvas').getContext('2d');
    const width = (f) => { c.font = f; return c.measureText('The quick brown fox jumps over 0123456789').width; };
    return { font: width(`11px "${name}"`), serif: width('11px serif'), mono: width('11px monospace') };
  }, fontName);
  if (Math.abs(w.font - w.serif) < 0.5 || Math.abs(w.font - w.mono) < 0.5) {
    throw new Error(`font "${fontName}" is not available: text would fall back (${JSON.stringify(w)})`);
  }
  return w;
}

/** Set the <html> class to cls (the page mode). */
export async function setMode(page, cls) {
  await page.evaluate((c) => { document.documentElement.className = c; }, cls);
}

/** Set the mode and screenshot clip {x, y, width, height} (CSS px) to file as PNG. */
export async function shoot(page, cls, file, clip, omitBackground = false) {
  await setMode(page, cls);
  const buf = await page.screenshot({ clip, omitBackground, encoding: 'binary', type: 'png' });
  fs.writeFileSync(file, buf);
  return file;
}

/** -> [problem strings]: every element matching selector (default '[data-in]') lies inside
 *  rects[data-in] (CSS px, eps). The element box is unioned with its descendants' boxes (flex rows
 *  overflow their parent; SVG children skipped) and with its text range. */
export async function checkContainment(page, rects, eps = 0.01, selector = '[data-in]') {
  return page.evaluate((R, eps, selector) => {
    const out = [];
    for (const el of document.querySelectorAll(selector)) {
      const name = el.dataset.in;
      const r = R[name];
      if (!r) { out.push(`unknown rect ${name}`); continue; }
      const b0 = el.getBoundingClientRect();
      const b = { left: b0.left, right: b0.right, top: b0.top, bottom: b0.bottom };
      if (el.namespaceURI !== 'http://www.w3.org/2000/svg') {
        for (const d of el.querySelectorAll('*')) {
          if (d.closest('svg') && d.tagName.toLowerCase() !== 'svg') continue;
          const db = d.getBoundingClientRect();
          if (!db.width && !db.height) continue;
          b.left = Math.min(b.left, db.left); b.right = Math.max(b.right, db.right);
          b.top = Math.min(b.top, db.top); b.bottom = Math.max(b.bottom, db.bottom);
        }
        if (el.textContent.trim()) {
          const rg = document.createRange();
          rg.selectNodeContents(el);
          const tb = rg.getBoundingClientRect();
          b.left = Math.min(b.left, tb.left); b.right = Math.max(b.right, tb.right);
        }
      }
      if (b.left < r[0] - eps || b.right > r[0] + r[2] + eps || b.top < r[1] - eps || b.bottom > r[1] + r[3] + eps) {
        out.push(`${name}: <${el.tagName.toLowerCase()} "${(el.textContent || '').trim().slice(0, 24)}"> ` +
          `[${b.left.toFixed(2)},${b.top.toFixed(2)} .. ${b.right.toFixed(2)},${b.bottom.toFixed(2)}] outside [${r}]`);
      }
    }
    return out;
  }, rects, eps, selector);
}

/** -> [problem strings]: each screens[name] = [rect, '#hex'] is one flat colour in the current mode
 *  (screenshot of the clip decoded in the page; every pixel within tol per channel). Prints an ok
 *  line per flat rect with its texture size. */
export async function checkFlat(page, screens, scale, tol = 1) {
  const problems = [];
  for (const [name, [r, colour]] of Object.entries(screens)) {
    const want = [1, 3, 5].map((i) => parseInt(colour.slice(i, i + 2), 16));
    if (want.some((v) => Number.isNaN(v))) { problems.push(`${name}: flat colour ${colour} is not #rrggbb`); continue; }
    const b64 = await page.screenshot({ clip: { x: r[0], y: r[1], width: r[2], height: r[3] }, encoding: 'base64', type: 'png' });
    const res = await page.evaluate(async (b64, want, tol) => {
      const img = new Image();
      img.src = 'data:image/png;base64,' + b64;
      await img.decode();
      const c = document.createElement('canvas');
      c.width = img.width; c.height = img.height;
      const g = c.getContext('2d');
      g.drawImage(img, 0, 0);
      const d = g.getImageData(0, 0, c.width, c.height).data;
      let bad = 0;
      for (let i = 0; i < d.length; i += 4) {
        if (Math.abs(d[i] - want[0]) > tol || Math.abs(d[i + 1] - want[1]) > tol || Math.abs(d[i + 2] - want[2]) > tol) bad++;
      }
      return { w: c.width, h: c.height, bad };
    }, b64, want, tol);
    const msg = `${name} ${res.w}x${res.h} px: ${res.bad} px differ from ${colour}`;
    if (res.bad) problems.push(msg); else console.log('ok  ' + msg);
  }
  return problems;
}

/** Read [width, height] from a PNG's IHDR; throws when the file is not a PNG. */
export function pngSize(file) {
  const b = fs.readFileSync(file);
  if (b.length < 24 || b.readUInt32BE(0) !== 0x89504e47) throw new Error(`${file} is not a PNG`);
  return [b.readUInt32BE(16), b.readUInt32BE(20)];
}

const same = (a, b) => a && b && a.length === 4 && a.every((v, i) => Math.abs(v - b[i]) < 1e-6);

export async function main(argv = process.argv.slice(2)) {
  const o = parseArgs(argv);
  const tl = JSON.parse(fs.readFileSync(o.timeline, 'utf8'));
  const [W, H] = tl.format.ui;
  const S = o.scale ?? tl.format.ui_scale;
  const L = tl.layout || {};
  fs.mkdirSync(o.out, { recursive: true });
  const problems = [];
  const temps = [];                       // [tmp, final]
  let fontWidths = null;
  const browser = await launch();
  try {
    const page = await browser.newPage();
    page.on('pageerror', (e) => problems.push(`page error: ${e.message}`));
    await page.setViewport({ width: W, height: H, deviceScaleFactor: S });
    await page.goto(pathToFileURL(path.resolve(o.html)).href, { waitUntil: 'load' });
    await page.evaluate(async () => { await document.fonts.ready; });
    if (o.font) fontWidths = await proveFont(page, o.font);

    const reg = await page.evaluate(() => ({
      rects: window.UI_RECTS || null, empty: window.UI_EMPTY || {}, sprites: window.UI_SPRITES || {}, size: window.UI_SIZE || null,
    }));
    if (!reg.rects) throw new Error('the page has no window.UI_RECTS (build it with filmkit.ui_html.Page)');
    if (reg.size && !same([...reg.size, 0, 0], [W, H, 0, 0])) problems.push(`page size ${reg.size} differs from format.ui ${[W, H]}`);
    for (const [kind, table] of [['panel', L.panels || {}], ['button', L.buttons || {}]]) {
      for (const [name, r] of Object.entries(table)) {
        if (!same(reg.rects[name], r)) problems.push(`${kind} ${name}: page rect ${reg.rects[name]} differs from timeline ${r} (rebuild ui.html)`);
      }
    }
    for (const [name, [r]] of Object.entries(L.screens || {})) {
      if (!same(reg.rects[name], r)) problems.push(`screen ${name}: page rect ${reg.rects[name]} differs from timeline ${r} (rebuild ui.html)`);
    }
    const screens = {};
    for (const [name, [r, hex]] of Object.entries(reg.empty)) screens[name] = [r, o.flat[name] || hex];
    for (const name of Object.keys(o.flat)) if (!screens[name]) problems.push(`--flat names unknown screen ${name}`);
    const sprites = o.sprites ?? Object.keys(reg.sprites).map((n) => [`${n}.png`, n]);

    const tmpOf = (file) => { const t = path.join(o.out, file + '.part'); temps.push([t, path.join(o.out, file)]); return t; };
    for (const [file, cls] of o.modes) await shoot(page, cls, tmpOf(file), { x: 0, y: 0, width: W, height: H });
    for (const [file, name] of sprites) {
      const size = reg.sprites[name];
      if (!size) { problems.push(`sprite ${name} is not in the page's UI_SPRITES`); continue; }
      await shoot(page, name, tmpOf(file), { x: 0, y: 0, width: size[0], height: size[1] }, true);
    }

    await setMode(page, '');
    problems.push(...await checkContainment(page, reg.rects, 0.01, '#ui [data-in]'));
    for (const [, name] of sprites) {
      if (!reg.sprites[name]) continue;
      await setMode(page, name);
      problems.push(...await checkContainment(page, reg.rects, 0.01, `#sprite-${name} [data-in]`));
    }
    await setMode(page, '');
    problems.push(...await checkFlat(page, screens, S));
    const n = await page.evaluate(() => document.querySelectorAll('[data-in]').length);
    console.log(`elements: ${n} data-in checked (eps 0.01 CSS px); screens: ${Object.keys(screens).length}; sprites: ${sprites.length}`);
  } finally {
    await browser.close();
  }
  if (fontWidths) console.log(`fonts: ${o.font} ${fontWidths.font.toFixed(1)} px vs serif ${fontWidths.serif.toFixed(1)} px, monospace ${fontWidths.mono.toFixed(1)} px`);
  else console.log('fonts: none named (--font), not proven');
  for (const [tmp, final] of temps) {
    if (!fs.existsSync(tmp)) continue;
    const [w, h] = pngSize(tmp);
    console.log(`${path.basename(final)}: ${w}x${h}`);
  }
  if (problems.length) {
    for (const [tmp] of temps) fs.rmSync(tmp, { force: true });
    console.error(`${problems.length} contract problem(s):`);
    for (const p of problems) console.error('  ' + p);
    process.exit(1);
  }
  for (const [tmp, final] of temps) fs.renameSync(tmp, final);
  console.log('contract: every element inside its rect; every screen rect flat; page rects match the timeline');
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((e) => { console.error(e.stack || e); process.exit(1); });
}
