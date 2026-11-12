#!/usr/bin/env node
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { boardErrors, gateMessage, projectOf, screenWords } from '../../scripts/lib/text-gate.mjs';

const kitRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const { tool_name: tool, tool_input: input = {} } = JSON.parse(readFileSync(0, 'utf8') || '{}');

function change() {
  if (tool === 'Bash') {
    const path = (input.command || '').match(/[^\s"'=]*video-projects[\\/][^\s"'\\/]+/)?.[0];
    return path && /\bffmpeg\b/.test(input.command) && { path, before: '', after: input.command };
  }
  if (tool !== 'Write' && tool !== 'Edit') return null;
  const before = existsSync(input.file_path) ? readFileSync(input.file_path, 'utf8') : '';
  if (tool === 'Write') return { path: input.file_path, before, after: input.content || '' };
  const after = input.replace_all ? before.split(input.old_string).join(input.new_string) : before.replace(input.old_string, () => input.new_string);
  return { path: input.file_path, before, after };
}

function check() {
  const c = change();
  if (!c) return null;
  const old = screenWords(c.before, c.path);
  return [...screenWords(c.after, c.path)].some(w => !old.has(w)) ? c : null;
}

const hit = check();
const project = hit && projectOf(hit.path);
if (project && !project.inBoard) {
  const errors = boardErrors(project.dir, kitRoot);
  if (errors.length) {
    process.stderr.write(gateMessage(hit.path, errors) + '\n');
    process.exit(2);
  }
}
