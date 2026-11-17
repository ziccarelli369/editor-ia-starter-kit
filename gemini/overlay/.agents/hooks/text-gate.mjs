#!/usr/bin/env node
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { boardErrors, gateMessage, projectOf, screenWords } from '../../scripts/lib/text-gate.mjs';

const kitRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const nodes = value => value && typeof value === 'object' ? [value, ...Object.values(value).flatMap(nodes)] : [];
const field = (node, key, skip) => Object.entries(node).find(([k, v]) => key.test(k) && typeof v === 'string' && v !== skip)?.[1];

function change({ name = '', args = {} }) {
  const all = nodes(args);
  if (/command|bash|shell/i.test(name)) {
    const command = all.map(n => field(n, /command/i)).find(Boolean) || '';
    const path = command.match(/[^\s"'=]*video-projects[\\/][^\s"'\\/]+/)?.[0];
    return path && /\bffmpeg\b/.test(command) ? { path, before: '', after: command } : null;
  }
  const path = all.map(n => field(n, /file|path/i)).find(Boolean);
  if (!path) return null;
  const before = existsSync(path) ? readFileSync(path, 'utf8') : '';
  const edits = all.map(n => [field(n, /target|old/i, path), field(n, /replac|new/i, path), Object.entries(n).some(([k, v]) => /all|multiple/i.test(k) && v === true)]).filter(([from, to]) => from !== undefined && to !== undefined);
  if (edits.length) return { path, before, after: edits.reduce((text, [from, to, every]) => every ? text.split(from).join(to) : text.replace(from, () => to), before) };
  const content = all.map(n => field(n, /content|code/i, path)).find(v => v !== undefined);
  return content === undefined ? null : { path, before, after: content };
}

function blocked(call) {
  const c = change(call);
  if (!c) return null;
  const old = screenWords(c.before, c.path);
  if (![...screenWords(c.after, c.path)].some(w => !old.has(w))) return null;
  const project = projectOf(c.path);
  if (!project || project.inBoard) return null;
  const errors = boardErrors(project.dir, kitRoot);
  return errors.length ? gateMessage(c.path, errors) : null;
}

let payload = {};
let reason = null;
try {
  payload = JSON.parse(readFileSync(0, 'utf8') || '{}');
  reason = blocked(payload.toolCall || { name: payload.tool_name, args: payload.tool_input });
} catch {
  reason = null;
}
if (reason && payload.toolCall) {
  process.stdout.write(JSON.stringify({ decision: 'deny', reason }) + '\n');
} else if (reason) {
  process.stderr.write(reason + '\n');
  process.exit(2);
}
