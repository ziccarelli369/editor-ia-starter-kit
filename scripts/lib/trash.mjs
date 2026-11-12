import { existsSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

const recycleBin = "Add-Type -AssemblyName Microsoft.VisualBasic; $env:KIT_TRASH_PATHS -split \"`n\" | ForEach-Object { [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($_, 'OnlyErrorDialogs', 'SendToRecycleBin') }";

function tryTrash(paths) {
  if (process.platform === 'win32') {
    const r = spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', recycleBin], { env: { ...process.env, KIT_TRASH_PATHS: paths.join('\n') }, encoding: 'utf8' });
    return r.status === 0 ? 'Recycle Bin' : null;
  }
  if (spawnSync('trash', paths).status === 0) return 'trash';
  if (process.platform === 'linux' && spawnSync('gio', ['trash', ...paths]).status === 0) return 'trash';
  return null;
}

export function trash(paths) {
  if (!paths.length) return 'nothing';
  const method = tryTrash(paths);
  const left = paths.filter(p => existsSync(p));
  for (const p of left) rmSync(p, { force: true });
  return left.length ? 'deleted' : method ?? 'deleted';
}
