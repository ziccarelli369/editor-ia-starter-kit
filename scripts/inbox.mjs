#!/usr/bin/env node
// List inbox media, or move chosen files into a project's assets/ folder.
// Usage: node scripts/inbox.mjs                                  -> list
//        node scripts/inbox.mjs <project-id> <file> [<file>...]  -> move
import { readdirSync, statSync, renameSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const inbox = join(root, 'inbox');
const media = /\.(mp4|mov|mkv|webm|m4v|wav|mp3|m4a|aac|flac|png|jpg|jpeg|srt|vtt|txt|md)$/i;
const [id, ...files] = process.argv.slice(2);
if (!id) {
  const list = readdirSync(inbox).filter(f => media.test(f) && f !== 'README.md');
  if (!list.length) { console.log('inbox is empty'); process.exit(0); }
  for (const f of list) console.log(`${(statSync(join(inbox, f)).size / 1e6).toFixed(1).padStart(8)} MB  ${f}`);
  process.exit(0);
}
const dest = join(root, 'video-projects', id, 'assets');
if (!existsSync(dest)) throw new Error(`No project folder: video-projects/${id}/assets`);
const projectFile = join(root, 'video-projects', id, 'project.json');
const project = JSON.parse(readFileSync(projectFile, 'utf8'));
for (const f of files) {
  const from = join(inbox, f);
  if (!existsSync(from)) throw new Error(`Not in inbox: ${f}`);
  renameSync(from, join(dest, f));
  if (!project.sources.includes(`assets/${f}`)) project.sources.push(`assets/${f}`);
  console.log(`moved ${f} -> video-projects/${id}/assets/`);
}
writeFileSync(projectFile, JSON.stringify(project, null, 2) + '\n');
