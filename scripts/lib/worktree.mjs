import { readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';

export function mainCheckoutOf(root) {
  let text;
  try {
    if (!statSync(join(root, '.git')).isFile()) return null;
    text = readFileSync(join(root, '.git'), 'utf8');
  } catch {
    return null;
  }
  const m = text.match(/^gitdir:\s*(.+?)\s*$/m);
  if (!m) return null;
  const gitdir = resolve(root, m[1]).replace(/\\/g, '/');
  const i = gitdir.lastIndexOf('/.git/worktrees/');
  return i < 0 ? null : gitdir.slice(0, i);
}
