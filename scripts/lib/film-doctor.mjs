import { spawnSync } from 'node:child_process';
import { join } from 'node:path';

const CANDIDATES = process.platform === 'win32'
  ? [['py', '-3'], ['python'], ['python3']]
  : [['python3'], ['python']];

export function findPython() {
  for (const [cmd, ...pre] of CANDIDATES) {
    const r = spawnSync(cmd, [...pre, '-c', 'import sys; print(sys.version_info >= (3, 10))'], { encoding: 'utf8', windowsHide: true });
    if (!r.error && r.status === 0 && r.stdout.trim() === 'True') return [cmd, ...pre];
  }
  return null;
}

export function filmDoctor(root) {
  const python = findPython();
  if (!python) return { ok: false, python: null, lines: ['FAIL  python: Python 3.10+ not found → https://www.python.org/downloads/'] };
  const r = spawnSync(python[0], [...python.slice(1), '-B', join(root, '.claude/skills/film-engine/scripts/doctor.py')], {
    cwd: root, encoding: 'utf8', windowsHide: true, timeout: 300_000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
  });
  const lines = `${r.stdout || ''}${r.stderr || ''}`.split(/\r?\n/).filter(l => l.trim());
  return { ok: r.status === 0, python, lines };
}
