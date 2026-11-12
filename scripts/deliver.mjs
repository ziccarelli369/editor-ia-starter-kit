#!/usr/bin/env node
// Two steps. --stage copies a review version into staging/<project-id>/ as <name>-v<N>-<kind>.
// --promote <N> copies staged version N into outbox/<project-id>/ as <name>-<kind>, replacing the previous
// final of that deliverable, and checks the delivery contract from kit.config.json.
// Usage: node scripts/deliver.mjs <project-id> --stage --video <mp4> [--cover <png>] [--caption <txt>] [--srt <srt>] [--name <name>]
//        node scripts/deliver.mjs <project-id> --promote <N> [--name <name>]
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve, dirname, join, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { mainCheckoutOf } from './lib/worktree.mjs';
import { trash } from './lib/trash.mjs';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const id = args[0];
const opt = n => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : undefined; };
const usage = 'Usage: node scripts/deliver.mjs <project-id> --stage --video <mp4> [--cover <png>] [--caption <txt>] [--srt <srt>] [--name <name>] [--allow-worktree]\n       node scripts/deliver.mjs <project-id> --promote <N> [--name <name>] [--allow-worktree]';
if (!id || id.startsWith('--')) throw new Error(usage);
const main = mainCheckoutOf(root);
if (main && !args.includes('--allow-worktree')) {
  console.error([
    'Refused: this kit is a git worktree. video-projects/, staging/ and outbox/ are git-ignored, so removing the worktree deletes the delivery.',
    `Run deliver from the main checkout: ${main}`,
    '--allow-worktree delivers here anyway.',
  ].join('\n'));
  process.exit(1);
}
const stage = args.includes('--stage');
const promote = opt('promote');
if (stage === args.includes('--promote') || (promote !== undefined && !/^\d+$/.test(promote))) throw new Error(usage);
const config = JSON.parse(readFileSync(join(root, 'kit.config.json'), 'utf8'));
const kinds = [...config.outbox.required, ...config.outbox.extras];
const projectFile = join(root, 'video-projects', id, 'project.json');
if (!existsSync(projectFile)) throw new Error(`No project: ${id}`);
const project = JSON.parse(readFileSync(projectFile, 'utf8'));
const name = opt('name') || project.slug;
const staging = join(root, 'staging', id);
const staged = existsSync(staging) ? readdirSync(staging) : [];
const prefix = v => `${name}-v${v}-`;

if (stage) {
  const given = kinds.filter(k => opt(k));
  if (!given.length) throw new Error(`Nothing to stage. Give at least one of: ${kinds.map(k => `--${k}`).join(', ')}`);
  for (const k of given) if (!existsSync(opt(k))) throw new Error(`File not found for --${k}: ${opt(k)}`);
  const re = new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}-v(\\d+)-`);
  const version = 1 + Math.max(0, ...staged.map(f => Number(f.match(re)?.[1] ?? 0)));
  mkdirSync(staging, { recursive: true });
  const files = given.map(k => {
    const file = `${prefix(version)}${k}${extname(opt(k))}`;
    copyFileSync(opt(k), join(staging, file));
    return file;
  });
  console.log(`Staged ${name} v${version} in staging/${id}/: ${files.join(', ')}`);
  console.log(`Promote it after the user approves: node scripts/deliver.mjs ${id} --promote ${version}${opt('name') ? ` --name ${name}` : ''}`);
  process.exit(0);
}

const pick = {};
for (const k of kinds) {
  const file = staged.find(f => f.startsWith(`${prefix(promote)}${k}.`));
  if (file) pick[k] = file;
}
const missing = config.outbox.required.filter(k => !pick[k]);
if (missing.length) throw new Error(`Promote blocked. Required: ${config.outbox.required.join(', ')}. Missing in staging/${id}/ for ${name} v${promote}: ${missing.join(', ')}`);
const out = join(root, 'outbox', id);
mkdirSync(out, { recursive: true });
const previous = project.deliverables.find(d => d.name === name);
const replaced = trash(Object.values(previous?.files ?? {}).map(f => join(out, f)).filter(p => existsSync(p)));
const delivered = {};
for (const [k, src] of Object.entries(pick)) {
  const file = `${name}-${k}${extname(src)}`;
  copyFileSync(join(staging, src), join(out, file));
  delivered[k] = file;
}
project.deliverables = project.deliverables.filter(d => d.name !== name);
project.deliverables.push({ name, version: Number(promote), delivered: new Date().toISOString().slice(0, 10), files: delivered });
project.status = 'delivered';
writeFileSync(projectFile, JSON.stringify(project, null, 2) + '\n');
const skipped = config.outbox.extras.filter(k => !pick[k]);
console.log(`Promoted ${name} v${promote} to outbox/${id}/: ${Object.values(delivered).join(', ')}`);
if (previous) console.log(`Replaced the previous final (v${previous.version ?? '?'}); its files went to: ${replaced}`);
if (skipped.length) console.log(`Not delivered (optional): ${skipped.join(', ')}`);
