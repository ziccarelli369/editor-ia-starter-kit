#!/usr/bin/env node
// Remove review versions from staging/. Never touches outbox/, inbox/ or video-projects/.
// Usage: node scripts/clean-staging.mjs [<project-id>] [--older-than <days>]
import { existsSync, readdirSync, rmdirSync, statSync } from 'node:fs';
import { resolve, dirname, join, basename } from 'node:path';
import { fileURLToPath } from 'node:url';
import { trash } from './lib/trash.mjs';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const i = args.indexOf('--older-than');
const days = i >= 0 ? Number(args[i + 1]) : 0;
const id = args.find((a, j) => !a.startsWith('--') && (i < 0 || j !== i + 1));
if (i >= 0 && !(days >= 0)) throw new Error('Usage: node scripts/clean-staging.mjs [<project-id>] [--older-than <days>]');
const staging = join(root, 'staging');
if (id && (basename(id) !== id || !existsSync(join(staging, id)))) throw new Error(`No staging folder: staging/${id}`);
const dirs = (id ? [id] : existsSync(staging) ? readdirSync(staging, { withFileTypes: true }).filter(e => e.isDirectory()).map(e => e.name) : []);
const cutoff = Date.now() - days * 86400000;
const old = dirs.flatMap(d => readdirSync(join(staging, d)).map(f => join(staging, d, f)))
  .filter(p => statSync(p).isFile() && statSync(p).mtimeMs <= cutoff);
const method = trash(old);
for (const d of dirs) if (!readdirSync(join(staging, d)).length) rmdirSync(join(staging, d));
console.log(old.length ? `Removed ${old.length} staged file(s) from staging/ (${method}).` : 'Nothing to clean in staging/.');
