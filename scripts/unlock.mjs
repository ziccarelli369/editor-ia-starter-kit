#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve, dirname, join, basename } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const win = process.platform === 'win32';
const args = process.argv.slice(2);
const target = args.find(a => !a.startsWith('--'));
if (!target) {
  console.log('Usage: npm run unlock -- <project-id|path> [--stop]');
  process.exit(1);
}
const dir = existsSync(target) ? resolve(target) : join(root, 'video-projects', target);
if (!existsSync(dir)) throw new Error(`No project folder: ${target}`);
const fold = s => win ? s.toLowerCase() : s;
const needles = [dir, dir.replace(/\\/g, '/'), dir.replace(/\//g, '\\')];
if (dirname(dir) === join(root, 'video-projects')) needles.push(`video-projects/${basename(dir)}`, `video-projects\\${basename(dir)}`);
const names = [...new Set(needles.map(fold))];
const mentions = cmd => names.some(n => {
  for (let i = cmd.indexOf(n); i >= 0; i = cmd.indexOf(n, i + 1)) if (!/[\w.-]/.test(cmd[i + n.length] ?? '')) return true;
  return false;
});

function processes() {
  if (win) {
    const r = spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command',
      '[Console]::OutputEncoding = [Text.Encoding]::UTF8; Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress'],
      { encoding: 'utf8', windowsHide: true, maxBuffer: 256 * 1024 * 1024 });
    return [JSON.parse(r.stdout)].flat().map(p => ({ pid: p.ProcessId, ppid: p.ParentProcessId, name: p.Name, cmd: p.CommandLine || '' }));
  }
  const r = spawnSync('ps', ['-axo', 'pid=,ppid=,command='], { encoding: 'utf8', maxBuffer: 256 * 1024 * 1024 });
  return r.stdout.split('\n').map(l => l.match(/^\s*(\d+)\s+(\d+)\s+(.*)$/)).filter(Boolean)
    .map(([, pid, ppid, cmd]) => ({ pid: Number(pid), ppid: Number(ppid), name: basename(cmd.split(' ')[0]), cmd }));
}

function holders() {
  const all = processes();
  const parent = new Map(all.map(p => [p.pid, p.ppid]));
  const self = new Set();
  for (let pid = process.pid; pid && !self.has(pid); pid = parent.get(pid)) self.add(pid);
  return all.filter(p => !self.has(p.pid) && !/unlock\.mjs|npm(\.cmd)?"?\s+run(-script)?\s+unlock\b/i.test(p.cmd) && mentions(fold(p.cmd)));
}

function show(list) {
  if (!list.length) return console.log(`No process names ${dir}.`);
  console.log(`${list.length} process(es) name ${dir}:`);
  for (const p of list) console.log(`  ${p.pid}  ${p.name}  ${p.cmd.length > 120 ? `${p.cmd.slice(0, 117)}...` : p.cmd}`);
}

const found = holders();
show(found);
if (!args.includes('--stop') || !found.length) process.exit(0);
for (const p of found) {
  if (win) spawnSync('taskkill', ['/PID', String(p.pid), '/T', '/F'], { stdio: 'ignore', windowsHide: true });
  else try { process.kill(p.pid, 'SIGTERM'); } catch {}
}
Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 1000);
console.log(`Stopped ${found.length}. Again:`);
const left = holders();
show(left);
process.exit(left.length ? 1 : 0);
