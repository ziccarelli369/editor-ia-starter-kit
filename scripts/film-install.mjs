#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { findPython, filmDoctor } from './lib/film-doctor.mjs';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const os = { win32: 'windows', darwin: 'macos' }[process.platform] ?? 'linux';
const requirements = '.claude/skills/film-engine/requirements.txt';
const run = (cmd, args) => spawnSync(cmd, args, { cwd: root, stdio: 'inherit', windowsHide: true }).status === 0;
const venvPython = () => ['Scripts/python.exe', 'bin/python'].map(p => join(root, '.venv', p)).find(p => existsSync(p));
const pipOk = () => !!venvPython() && spawnSync(venvPython(), ['-m', 'pip', '--version'], { stdio: 'ignore', windowsHide: true }).status === 0;

console.log('editor-ia-starter-kit · instalación de la película 3D / film install\n');
const python = findPython();
if (!python) {
  console.log('  FALTA Python 3.10+ → https://www.python.org/downloads/');
  console.log({
    windows: '        Windows: el instalador de python.org (marca "Add python.exe to PATH"), o: winget install Python.Python.3.12',
    macos: '        macOS: el instalador de python.org, o: brew install python@3.12',
    linux: '        Linux: sudo apt install python3 python3-venv (o el paquete python3 de tu distribución)',
  }[os]);
  process.exit(1);
}

if (!pipOk()) {
  console.log(`  ${venvPython() ? 'repara' : 'nuevo '} .venv con ${python.join(' ')} -m venv .venv`);
  if (!run(python[0], [...python.slice(1), '-m', 'venv', '.venv']) || !pipOk()) {
    console.log('  FALTA no se pudo crear .venv' + (os === 'linux' ? ' (Debian/Ubuntu: sudo apt install python3-venv)' : ''));
    process.exit(1);
  }
}

const packages = readFileSync(join(root, requirements), 'utf8').split(/\r?\n/).filter(l => l.trim()).join(', ');
console.log(`  pip    instala en .venv: ${packages}`);
console.log('         descarga aprox. 35-65 MB la primera vez (wheels de PyPI, oct. 2026), unos 230 MB en disco\n');
run(venvPython(), ['-m', 'pip', 'install', '--disable-pip-version-check', '-r', requirements]);

console.log('\npelícula 3D (character-film) · film doctor\n');
const doctor = filmDoctor(root);
for (const line of doctor.lines) console.log(`  ${line}`);
if (doctor.lines.some(l => /^FAIL\s+blender:/.test(l))) {
  console.log('\n  Blender 5.x lo instalas tú; este script no lo instala (descarga aprox. 350-400 MB, unos 900 MB instalado):');
  console.log({
    windows: '  Windows: el instalador .msi de https://www.blender.org/download/',
    macos: '  macOS: el instalador .dmg de https://www.blender.org/download/',
    linux: '  Linux: el .tar.xz de https://www.blender.org/download/, o: sudo snap install blender --classic',
  }[os]);
  console.log('  Si Blender está en otra carpeta, pon la ruta del ejecutable en la variable BLENDER.');
}
console.log('');
console.log(doctor.ok ? 'Película 3D lista. Siguiente: npm run setup -- --film' : 'Arregla las líneas FAIL y vuelve a correr: npm run film:install');
process.exitCode = doctor.ok ? 0 : 1;
