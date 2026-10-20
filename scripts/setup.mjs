#!/usr/bin/env node
// First-run check. Prints what is installed, what is missing, and the next step. Changes nothing
// except creating .env from .env.example when it does not exist.
import { spawnSync } from 'node:child_process';
import { existsSync, copyFileSync, readFileSync, readdirSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const win = process.platform === 'win32';
let missing = 0;
const ok = m => console.log(`  ok    ${m}`);
const bad = m => { console.log(`  FALTA ${m}`); missing++; };
const has = (cmd, args) => { const r = spawnSync(cmd, args, { encoding: 'utf8', windowsHide: true, shell: win }); return !r.error && r.status === 0 ? (r.stdout || r.stderr).split(/\r?\n/)[0] : null; };

console.log('editor-ia-starter-kit · comprobación de instalación / install check\n');
const node = Number(process.versions.node.split('.')[0]);
node >= 22 ? ok(`Node ${process.versions.node}`) : bad(`Node 22+ (tienes ${process.versions.node}) → https://nodejs.org`);
has('ffmpeg', ['-version']) ? ok('ffmpeg') : bad('ffmpeg en el PATH → https://ffmpeg.org/download.html');
has('ffprobe', ['-version']) ? ok('ffprobe') : bad('ffprobe (viene con ffmpeg)');
existsSync(join(root, 'node_modules', 'hyperframes')) ? ok('HyperFrames (npm install hecho)') : bad('npm install (HyperFrames no está en node_modules)');

if (!existsSync(join(root, '.env'))) { copyFileSync(join(root, '.env.example'), join(root, '.env')); console.log('  nuevo  .env creado desde .env.example'); }
const env = Object.fromEntries(readFileSync(join(root, '.env'), 'utf8').split(/\r?\n/).map(l => l.match(/^([A-Z_]+)=(.*)$/)).filter(Boolean).map(m => [m[1], m[2].trim()]));
const config = JSON.parse(readFileSync(join(root, 'kit.config.json'), 'utf8'));

const whisperPath = env.HYPERFRAMES_WHISPER_PATH || process.env.HYPERFRAMES_WHISPER_PATH;
const whisper = (whisperPath && existsSync(whisperPath)) || has('whisper-cli', ['--help']);
const eleven = Boolean(env.ELEVENLABS_API_KEY);
if (eleven) ok('ElevenLabs key en .env (transcripción medida por palabra)');
if (whisper) ok('whisper.cpp (transcripción local gratis)');
if (!eleven && !whisper) bad('transcripción: pon ELEVENLABS_API_KEY en .env, o instala whisper.cpp y pon HYPERFRAMES_WHISPER_PATH en .env (docs/SETUP.md paso 3)');
if (config.transcription.provider === 'elevenlabs' && !eleven && whisper) console.log('  aviso  kit.config.json pide elevenlabs sin clave: se usará whisper local');
env.KIE_API_KEY ? ok('Kie.ai key (música y clips generados)') : console.log('  opc.   sin KIE_API_KEY: la música y el B-roll serán gráficos del agente');

ok(`idioma del agente: ${config.language} · idioma del metraje: ${config.transcription.languages.join(', ')} (cámbialo en kit.config.json)`);
const brands = readdirSync(join(root, 'brands'), { withFileTypes: true }).filter(d => d.isDirectory() && d.name !== '_template').map(d => d.name);
brands.length ? ok(`marcas: ${brands.join(', ')}`) : console.log('  opc.   sin marcas todavía: el agente crea la primera en tu primer /new-video');

console.log('');
if (missing) { console.log(`${missing} cosa(s) por instalar. Luego: npx hyperframes doctor`); process.exitCode = 1; }
else console.log('Todo listo. Siguiente: npx hyperframes doctor, luego deja un video en inbox/ y escribe /new-video');
