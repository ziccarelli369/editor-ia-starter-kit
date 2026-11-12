import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';

export const TEXT_SKILLS = [
  '.claude/skills/hyperframes/references/typography.md',
  '.claude/skills/hyperframes/references/captions.md',
  '.claude/skills/short-form-edit/references/opening.md',
  '.claude/skills/short-form-edit/references/text-board.md',
  '.claude/skills/style-library/SKILL.md',
];
const SOURCE_ROOTS = ['.claude/skills/', 'style-library/', 'styles/'];
const SOURCE_FILE = /\.(html?|m?js|cjs|py|sh|ps1)$/i;
const SKIP_DIRS = new Set(['assets', 'audio', 'renders', 'work', 'node_modules', 'text-board']);
const TEXT_CALL = /\bdrawtext\b|\bsubtitles=|\.(?:textContent|innerText|innerHTML)\s*=|\bfillText\s*\(/;

export function screenWords(source, file) {
  const calls = source.split('\n').filter(line => TEXT_CALL.test(line));
  const visible = /\.html?$/i.test(file) ? source
    .replace(/<(head|script|style|template)\b[\s\S]*?<\/\1>/gi, ' ')
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/<[^>]*>/g, ' ')
    .replace(/&[a-z0-9#]+;/gi, ' ') : '';
  return new Set([...calls, visible].join(' ').match(/[\p{L}\p{N}]+/gu));
}

export const drawsText = (source, file) => screenWords(source, file).size > 0;

const isFilm = dir => JSON.parse(readFileSync(join(dir, 'project.json'), 'utf8')).kind === 'film';

export function projectOf(path) {
  const m = resolve(path).split(sep).join('/').match(/^(.*\/video-projects\/[^/]+)(\/.*)?$/);
  if (!m || !existsSync(join(m[1], 'project.json')) || isFilm(m[1])) return null;
  return { dir: m[1], inBoard: (m[2] || '').startsWith('/text-board/') };
}

function sourceFiles(dir, base = dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap(e => {
    if (e.isDirectory()) return SKIP_DIRS.has(e.name) ? [] : sourceFiles(join(dir, e.name), base);
    return SOURCE_FILE.test(e.name) ? [relative(base, join(dir, e.name)).split(sep).join('/')] : [];
  });
}

export function boardErrors(projectDir, kitRoot) {
  const file = join(projectDir, 'text-board', 'text-board.json');
  if (!existsSync(file)) return ['text-board/text-board.json is missing'];
  let b;
  try { b = JSON.parse(readFileSync(file, 'utf8')); } catch (e) { return [`text-board.json is not JSON: ${e.message}`]; }
  const options = Array.isArray(b.options) ? b.options : [];
  const errors = [];
  if (options.length < 3) errors.push(`the board needs at least 3 options, it has ${options.length}`);
  for (const key of ['id', 'treatment']) {
    const values = options.map(o => String(o[key] || '').trim().toLowerCase());
    if (values.some(v => !v) || new Set(values).size !== values.length) errors.push(`every option needs its own ${key === 'id' ? 'id' : 'distinct treatment'}`);
  }
  for (const o of options) {
    if (!String(o.text || '').trim()) errors.push(`option ${o.id} has no text`);
    const src = String(o.source || '').replace(/\\/g, '/');
    if (!SOURCE_ROOTS.some(r => src.startsWith(r)) || !existsSync(join(kitRoot, src))) errors.push(`option ${o.id} source "${src}" is not a kit skill file`);
  }
  if (!b.board || !existsSync(join(projectDir, 'text-board', b.board))) errors.push('the board image (text-board/<board>) is missing');
  if (!options.some(o => o.id === b.pick)) errors.push('pick must name the option the user chose');
  return errors;
}

export function textGate(projectDir, kitRoot) {
  if (isFilm(projectDir)) return { ok: true, files: [], errors: [] };
  const files = sourceFiles(projectDir).filter(f => drawsText(readFileSync(join(projectDir, f), 'utf8'), f));
  const errors = files.length ? boardErrors(projectDir, kitRoot) : [];
  return { ok: errors.length === 0, files, errors };
}

export function gateMessage(where, errors) {
  return [
    `Text gate: ${where} puts text on screen, but the text board is not done:`,
    ...errors.map(e => `  - ${e}`),
    'On-screen text is a design choice, not a placeholder. Before you write it:',
    ...TEXT_SKILLS.map(s => `  read ${s}`),
    'Then build at least 3 distinct treatments on the real frame into text-board/, show the board, and record the pick.',
    'Format: .claude/skills/short-form-edit/references/text-board.md',
  ].join('\n');
}
