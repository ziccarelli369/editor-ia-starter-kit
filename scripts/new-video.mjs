#!/usr/bin/env node
// Create a project folder: video-projects/<yyyy-mm-dd>-<slug>/ with project.json.
// Usage: npm run new-video -- <slug> [--brand <brand-slug>] [--mode guided|freeform]
import { cpSync, mkdirSync, existsSync, readFileSync, writeFileSync, copyFileSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const opt = (name, def) => { const i = args.indexOf(`--${name}`); return i >= 0 ? args[i + 1] : def; };
const slug = args.find((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--')));
if (!slug || slug === '--help') {
  console.log('Usage: npm run new-video -- <lowercase-slug> [--brand <brand>] [--mode guided|freeform]');
  process.exit(slug ? 0 : 1);
}
if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) throw new Error('Use a lowercase kebab-case slug, not a path.');
const config = JSON.parse(readFileSync(join(root, 'kit.config.json'), 'utf8'));
const brand = opt('brand', config.defaults.brand);
const mode = opt('mode', 'guided');
if (!['guided', 'freeform'].includes(mode)) throw new Error('--mode must be guided or freeform');
if (!existsSync(join(root, 'brands', brand, 'DESIGN.md'))) throw new Error(`Brand not found: brands/${brand}/DESIGN.md`);
const date = new Date().toISOString().slice(0, 10);
const id = `${date}-${slug}`;
const dest = join(root, 'video-projects', id);
if (existsSync(dest)) throw new Error(`Project already exists: ${id}.`);
const gsap = join(root, 'node_modules/gsap/dist/gsap.min.js');
if (!existsSync(gsap)) throw new Error('Run npm install in the kit root first.');
cpSync(join(root, 'examples/starter'), dest, { recursive: true, errorOnExist: true });
for (const d of ['assets', 'compositions', 'renders', 'raw']) mkdirSync(join(dest, d), { recursive: true });
copyFileSync(gsap, join(dest, 'assets/gsap.min.js'));
copyFileSync(join(root, 'brands', brand, 'tokens.css'), join(dest, 'assets/brand-tokens.css'));
const meta = JSON.parse(readFileSync(join(dest, 'meta.json'), 'utf8'));
Object.assign(meta, { id, name: slug, width: config.defaults.width, height: config.defaults.height, fps: config.defaults.fps });
writeFileSync(join(dest, 'meta.json'), JSON.stringify(meta, null, 2) + '\n');
const project = {
  id, slug, created: date, brand, mode,
  status: 'new',
  style: null,
  sources: [],
  deliverables: [],
  notes: ''
};
writeFileSync(join(dest, 'project.json'), JSON.stringify(project, null, 2) + '\n');
mkdirSync(join(root, 'outbox', id), { recursive: true });
console.log(`Created video-projects/${id} (brand: ${brand}, mode: ${mode}) and outbox/${id}.`);
