#!/usr/bin/env node
// Create a project folder: video-projects/<yyyy-mm-dd>-<slug>/ with project.json.
// Usage: npm run new-video -- <slug> [--brand <brand-slug>] [--mode guided|freeform] [--goal personal|sell|grow]
//        [--kind video|film] [--size 1920x1080] [--fps 30]   (film: a Blender character film, see character-film)
import { cpSync, mkdirSync, existsSync, readFileSync, writeFileSync, copyFileSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { filmDoctor } from './lib/film-doctor.mjs';
import { mainCheckoutOf } from './lib/worktree.mjs';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const opt = (name, def) => { const i = args.indexOf(`--${name}`); return i >= 0 ? args[i + 1] : def; };
const flags = ['--skip-doctor', '--allow-worktree'];
const slug = args.find((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--') && !flags.includes(args[i - 1])));
if (!slug || slug === '--help') {
  console.log('Usage: npm run new-video -- <lowercase-slug> [--brand <brand>] [--mode guided|freeform] [--goal personal|sell|grow] [--kind video|film] [--size WxH] [--fps N] [--skip-doctor] [--allow-worktree]');
  process.exit(slug ? 0 : 1);
}
const main = mainCheckoutOf(root);
if (main && !args.includes('--allow-worktree')) {
  console.error([
    'Refused: this kit is a git worktree. video-projects/ and outbox/ are git-ignored, so removing the worktree deletes the project.',
    `Run new-video from the main checkout: ${main}`,
    '--allow-worktree creates it here anyway.',
  ].join('\n'));
  process.exit(1);
}
if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) throw new Error('Use a lowercase kebab-case slug, not a path.');
const config = JSON.parse(readFileSync(join(root, 'kit.config.json'), 'utf8'));
const kind = opt('kind', 'video');
if (!['video', 'film'].includes(kind)) throw new Error('--kind must be video or film');
const brand = opt('brand', config.defaults.brand);
const mode = opt('mode', 'guided');
if (!['guided', 'freeform'].includes(mode)) throw new Error('--mode must be guided or freeform');
const goal = opt('goal', config.defaults.goal ?? '');
if (goal && !['personal', 'sell', 'grow'].includes(goal)) throw new Error('--goal must be personal, sell or grow');
// A film may run without a brand (--brand none): its BRAND block lives in the project DESIGN.md.
const branded = !(kind === 'film' && brand === 'none');
if (branded && !existsSync(join(root, 'brands', brand, 'DESIGN.md'))) throw new Error(`Brand not found: brands/${brand}/DESIGN.md`);
const date = new Date().toISOString().slice(0, 10);
const id = `${date}-${slug}`;
const dest = join(root, 'video-projects', id);
if (existsSync(dest)) throw new Error(`Project already exists: ${id}.`);
const film = {};
if (kind === 'film') {
  // Whole numbers only: the engine's Format rejects a fractional fps (29.97) and libx264 an odd size.
  const [width, height] = opt('size', '1920x1080').split('x').map(Number);
  const fps = Number(opt('fps', 30));
  if (![width, height, fps].every((v) => Number.isInteger(v) && v > 0)) throw new Error('--size must be WxH and --fps a whole number');
  const template = join(root, '.claude/skills/film-engine/templates/project');
  if (!existsSync(template)) throw new Error('Film template missing: .claude/skills/film-engine/templates/project');
  if (!args.includes('--skip-doctor')) {
    const doctor = filmDoctor(root);
    if (!doctor.ok) {
      const fails = doctor.lines.filter(l => l.startsWith('FAIL'));
      console.error([
        'This machine cannot render a film yet:',
        ...(fails.length ? fails : doctor.lines).map(l => `  ${l}`),
        'Install:',
        '  npm run film:install   builds the Python venv',
        '  Blender 5.x            https://www.blender.org/download/ (set BLENDER for a custom folder)',
        'Check again: npm run setup -- --film',
        '--skip-doctor creates the project anyway, but it cannot render until the check passes.',
      ].join('\n'));
      process.exit(1);
    }
    console.log('film doctor: ok');
  }
  cpSync(template, dest, { recursive: true, errorOnExist: true });
  for (const d of ['build', 'renders', 'reviews', 'scratch']) mkdirSync(join(dest, d), { recursive: true });
  // The final renders to renders/<build.json slug>.mp4: name it after the project, not the template.
  const knobs = JSON.parse(readFileSync(join(dest, 'build.json'), 'utf8'));
  writeFileSync(join(dest, 'build.json'), JSON.stringify({ ...knobs, slug }, null, 2) + '\n');
  // The film format lives in film.json, a build-only file the timeline step stamps. project.json is
  // rewritten by deliver (deliverables) and would mark the whole film stale.
  writeFileSync(join(dest, 'film.json'), JSON.stringify({ width, height, fps }, null, 2) + '\n');
  Object.assign(film, { kind, width, height, fps });
} else {
  const gsap = join(root, 'node_modules/gsap/dist/gsap.min.js');
  if (!existsSync(gsap)) throw new Error('Run npm install in the kit root first.');
  cpSync(join(root, 'examples/starter'), dest, { recursive: true, errorOnExist: true });
  for (const d of ['assets', 'compositions', 'renders']) mkdirSync(join(dest, d), { recursive: true });
  copyFileSync(gsap, join(dest, 'assets/gsap.min.js'));
  copyFileSync(join(root, 'brands', brand, 'tokens.css'), join(dest, 'assets/brand-tokens.css'));
  const meta = JSON.parse(readFileSync(join(dest, 'meta.json'), 'utf8'));
  Object.assign(meta, { id, name: slug, width: config.defaults.width, height: config.defaults.height, fps: config.defaults.fps });
  writeFileSync(join(dest, 'meta.json'), JSON.stringify(meta, null, 2) + '\n');
}
const project = {
  id, slug, created: date, brand: branded ? brand : null, mode, goal,
  ...film,
  status: 'new',
  style: null,
  sources: [],
  deliverables: [],
  notes: ''
};
writeFileSync(join(dest, 'project.json'), JSON.stringify(project, null, 2) + '\n');
mkdirSync(join(root, 'outbox', id), { recursive: true });
console.log(`Created video-projects/${id} (brand: ${brand}, mode: ${mode}, goal: ${goal || 'unset'}) and outbox/${id}.`);
