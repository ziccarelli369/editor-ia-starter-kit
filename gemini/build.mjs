#!/usr/bin/env node
import { cpSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

const here = dirname(fileURLToPath(import.meta.url));
const source = resolve(here, '..');
const out = resolve(process.argv[2] || join(source, '..', 'editor-ia-starter-kit-gemini'));
const git = (cwd, ...args) => execFileSync('git', ['-C', cwd, ...args], { encoding: 'utf8', maxBuffer: 1 << 28 });

const DROP = [/^gemini\//, /^CLAUDE\.md$/, /^README\.md$/, /^\.claude\/(settings\.json|launch\.json|hooks\/)/];
const VERBATIM = [
  /^LICENSE$/, /^licenses\//, /^THIRD_PARTY_NOTICES\.md$/, /NOTICE\.txt$/, /^package-lock\.json$/, /\.workflow$/,
  /motion-showreel\/references\/reference-breakdown\.md$/,
  /short-form-edit\/references\/(curiosity-and-entertainment|quality-gates|visual-world)\.md$/,
];
const PATHS = [[/\.claude\//g, '.agents/'], [/(['"])\.claude\1/g, '$1.agents$1'], [/CLAUDE\.md/g, 'AGENTS.md']];
const PHRASES = [
  [/an AI agent \(Claude Code\)/g, 'an AI agent'],
  [/the Claude desktop browser pane/g, 'the Antigravity browser'],
  [/the built-in browser pane of the Claude desktop app/g, 'the Antigravity browser subagent'],
  [/ \((?:tools )?`mcp__Claude_Browser__\*`(?: tools)?\)/g, ''],
  [/`mcp__claude_ai_HeyGen__text_to_speech`/g, 'the `text_to_speech` tool of a HeyGen MCP server'],
  [/ per `AskUserQuestion` call/g, ' per message'],
  [/ via `AskUserQuestion`/g, ' in chat'],
  [/Coste por video: unos 10 a 15 USD en tokens de Opus, más céntimos de ElevenLabs\./g, 'Coste por video: gasta cuota de tu plan de Gemini. ElevenLabs es opcional.'],
  [/and about 10 to 15 USD of Opus tokens per video\./g, 'and each video spends quota from your Gemini plan.'],
  [/Claude\s+Code/g, 'Antigravity'],
  [/Claude (Opus|Haiku) 5\.5/g, (_, m) => m === 'Opus' ? 'the pro model' : 'flash-tier'],
  [/you \(Opus\)/g, 'you'],
  [/Opus writes/g, 'You write'],
  [/Opus 5\.5/g, 'the pro model'],
  [/Haiku(?: 5\.5)?(\s+)subagents/g, 'Flash-tier$1subagents'],
  [/the Edit tool/g, 'your file-edit tool'],
  [/browser pane/g, 'browser'],
];
const NAMES_SOURCE = [/^README\.md$/, /^docs\/EXPERTO\.md$/, /^MIRROR\.txt$/, /\.py$/];
const LEFTOVER = /claude|anthropic|haiku|(?<![.\w])opus\b|fable[- ]5|AskUserQuestion/i;

const isText = buf => !buf.includes(0);
const hit = (list, rel) => list.some(re => re.test(rel));
const apply = (text, table) => table.reduce((t, [re, to]) => t.replace(re, to), text);

function section(guide, heading, body) {
  const re = new RegExp(`(^## ${heading}\\n)[\\s\\S]*?(?=^## )`, 'm');
  if (!re.test(guide)) throw new Error(`CLAUDE.md has no section "## ${heading}"`);
  return guide.replace(re, `$1\n${body.trim()}\n\n`);
}

if (existsSync(join(out, '.git'))) {
  for (const f of git(out, 'ls-files', '-z').split('\0').filter(Boolean)) rmSync(join(out, f), { force: true });
} else if (existsSync(out) && readdirSync(out).length) {
  throw new Error(`${out} is not empty and not a git repo`);
}
mkdirSync(out, { recursive: true });

const sha = git(source, 'rev-parse', '--short', 'HEAD').trim();
const files = git(source, 'ls-files', '-z').split('\0').filter(f => f && !hit(DROP, f));
for (const rel of files) {
  const buf = execFileSync('git', ['-C', source, 'show', `HEAD:${rel}`], { maxBuffer: 1 << 28 });
  const target = join(out, rel.replace(/^\.claude\//, '.agents/'));
  mkdirSync(dirname(target), { recursive: true });
  if (!isText(buf)) { writeFileSync(target, buf); continue; }
  const text = apply(buf.toString('utf8'), PATHS);
  writeFileSync(target, hit(VERBATIM, rel) ? text : apply(text, PHRASES));
}

const read = name => readFileSync(join(here, 'sections', name), 'utf8');
let guide = git(source, 'show', 'HEAD:CLAUDE.md');
guide = section(guide, '1\\. Identity', read('identity.md'));
guide = section(guide, '3\\. Models', read('models.md'));
guide = apply(apply(guide, PATHS), PHRASES).trimEnd() + '\n\n' + read('antigravity.md').trim() + '\n';
writeFileSync(join(out, 'AGENTS.md'), guide);

cpSync(join(here, 'overlay'), out, { recursive: true });

const json = (rel, change) => {
  const path = join(out, rel);
  const data = JSON.parse(readFileSync(path, 'utf8'));
  change(data);
  writeFileSync(path, JSON.stringify(data, null, 2) + '\n');
};
json('kit.config.json', c => {
  c.models = {
    profile: 'solo',
    $profiles: {
      solo: 'One agent on the pro model does everything: taste, design, cuts, render.',
      team: 'The pro model orchestrates and makes every design decision. Flash-tier subagents run mechanical, parallel work: transcripts, probes, validators, contact sheets.',
    },
    design: 'pro',
    worker: 'flash',
    engineer: 'pro',
    $engineer: c.models.$engineer,
  };
  c.transcription.provider = 'whisper';
});
const describe = p => { p.name = 'editor-ia-starter-kit-gemini'; if (p.description) p.description = p.description.replace('Claude Code', 'Antigravity'); };
json('package.json', describe);
json('package-lock.json', l => { l.name = 'editor-ia-starter-kit-gemini'; l.packages[''].name = l.name; });
writeFileSync(join(out, 'MIRROR.txt'), `Generated from editor-ia-starter-kit@${sha} by gemini/build.mjs.\nEdit the source kit and rebuild. Hand edits here are overwritten.\n`);

const walk = dir => readdirSync(dir, { withFileTypes: true }).flatMap(e =>
  ['.git', 'node_modules'].includes(e.name) ? [] : e.isDirectory() ? walk(join(dir, e.name)) : [join(dir, e.name)]);
const tracked = new Set([...files.map(f => f.replace(/^\.claude\//, '.agents/')), 'AGENTS.md', 'MIRROR.txt',
  ...walk(join(here, 'overlay')).map(p => p.slice(join(here, 'overlay').length + 1).replaceAll('\\', '/'))]);
const leftovers = [];
for (const rel of tracked) {
  if (hit(VERBATIM, rel.replace(/^\.agents\//, '.claude/')) || hit(NAMES_SOURCE, rel)) continue;
  const path = join(out, rel);
  if (!statSync(path).isFile()) continue;
  const buf = readFileSync(path);
  if (!isText(buf)) continue;
  buf.toString('utf8').split('\n').forEach((line, i) => { if (LEFTOVER.test(line)) leftovers.push(`${rel}:${i + 1}: ${line.trim().slice(0, 140)}`); });
}
if (leftovers.length) {
  console.error(`Claude-only wording left in the mirror (${leftovers.length}):\n${leftovers.join('\n')}`);
  process.exit(1);
}
console.log(`Mirror of ${sha} written to ${out}: ${tracked.size} files.`);
