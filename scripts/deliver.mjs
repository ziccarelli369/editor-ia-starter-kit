#!/usr/bin/env node
// Copy finals into outbox/<project-id>/ and check the delivery contract from kit.config.json.
// Usage: node scripts/deliver.mjs <project-id> --video <mp4> --cover <png> [--caption <txt>] [--srt <srt>] [--name <deliverable-name>]
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve, dirname, join, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { mainCheckoutOf } from './lib/worktree.mjs';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const id = args[0];
const opt = n => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : undefined; };
if (!id || id.startsWith('--')) throw new Error('Usage: node scripts/deliver.mjs <project-id> --video <mp4> --cover <png> [--caption <txt>] [--srt <srt>] [--name <name>] [--allow-worktree]');
const main = mainCheckoutOf(root);
if (main && !args.includes('--allow-worktree')) {
  console.error([
    'Refused: this kit is a git worktree. video-projects/ and outbox/ are git-ignored, so removing the worktree deletes the delivery.',
    `Run deliver from the main checkout: ${main}`,
    '--allow-worktree delivers here anyway.',
  ].join('\n'));
  process.exit(1);
}
const config = JSON.parse(readFileSync(join(root, 'kit.config.json'), 'utf8'));
const projectFile = join(root, 'video-projects', id, 'project.json');
if (!existsSync(projectFile)) throw new Error(`No project: ${id}`);
const project = JSON.parse(readFileSync(projectFile, 'utf8'));
const name = opt('name') || project.slug;
const out = join(root, 'outbox', id);
mkdirSync(out, { recursive: true });
const missing = config.outbox.required.filter(k => !opt(k));
if (missing.length) throw new Error(`Delivery blocked. Required: ${config.outbox.required.join(', ')}. Missing: ${missing.join(', ')}`);
const delivered = {};
for (const k of [...config.outbox.required, ...config.outbox.extras]) {
  const src = opt(k);
  if (!src) continue;
  if (!existsSync(src)) throw new Error(`File not found for --${k}: ${src}`);
  const file = `${name}-${k}${extname(src)}`;
  copyFileSync(src, join(out, file));
  delivered[k] = file;
}
project.deliverables = project.deliverables.filter(d => d.name !== name);
project.deliverables.push({ name, delivered: new Date().toISOString().slice(0, 10), files: delivered });
project.status = 'delivered';
writeFileSync(projectFile, JSON.stringify(project, null, 2) + '\n');
const skipped = config.outbox.extras.filter(k => !opt(k));
console.log(`Delivered to outbox/${id}/: ${Object.values(delivered).join(', ')}`);
if (skipped.length) console.log(`Not delivered (optional): ${skipped.join(', ')}`);
