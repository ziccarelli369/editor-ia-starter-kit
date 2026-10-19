// Voice onsets measured from the waveform: the frames where the speech band (300-3400 Hz)
// jumps at least `rise` dB above the previous 300 ms and sits above `floor` dB.
// This is a measurement; Whisper word times are estimates spread across a chunk.
import { spawnSync } from 'node:child_process';

export const FRAME_S = 0.01;

// Returns { frames: Float32Array of dB per 10 ms, onsets: [seconds], duration }.
export function analyze(audioPath, { rise = 6, floor = -35, refractory = 0.15 } = {}) {
  const r = spawnSync('ffmpeg', ['-v', 'error', '-i', audioPath, '-vn', '-ac', '1', '-ar', '16000',
    '-af', 'highpass=f=300,lowpass=f=3400', '-f', 's16le', '-'], { maxBuffer: 1 << 30 });
  if (r.status !== 0) throw new Error(`ffmpeg decode failed: ${r.stderr}`);
  const pcm = new Int16Array(r.stdout.buffer, r.stdout.byteOffset, Math.floor(r.stdout.length / 2));
  const per = Math.round(16000 * FRAME_S);
  const n = Math.floor(pcm.length / per);
  const frames = new Float32Array(n);
  for (let f = 0; f < n; f++) {
    let acc = 0;
    for (let i = f * per; i < (f + 1) * per; i++) acc += pcm[i] * pcm[i];
    frames[f] = 10 * Math.log10(acc / per / (32768 * 32768) + 1e-12);
  }
  const back = Math.round(0.3 / FRAME_S);
  const onsets = [];
  let last = -Infinity;
  for (let f = back; f < n; f++) {
    let base = 0;
    for (let i = f - back; i < f; i++) base += frames[i];
    base /= back;
    const t = f * FRAME_S;
    if (frames[f] > floor && frames[f] - base >= rise && t - last >= refractory && sustained(frames, f)) { onsets.push(+t.toFixed(2)); last = t; }
  }
  return { frames, onsets, duration: n * FRAME_S };
}

// Speech holds its level for the next 100-250 ms; a cut tick or a click decays at once.
function sustained(frames, f) {
  const a = f + 10, b = Math.min(frames.length, f + 25);
  if (b <= a) return false;
  let acc = 0;
  for (let i = a; i < b; i++) acc += frames[i];
  return acc / (b - a) >= frames[f] - 9;
}

export function levelAt(frames, t, span = 0.15) {
  const a = Math.max(0, Math.round((t - span) / FRAME_S)), b = Math.min(frames.length, Math.round((t + span) / FRAME_S));
  if (b <= a) return -99;
  let acc = 0;
  for (let i = a; i < b; i++) acc += Math.pow(10, frames[i] / 10);
  return 10 * Math.log10(acc / (b - a) + 1e-12);
}

export function nearestOnset(onsets, t, window) {
  let best = null;
  for (const o of onsets) if (Math.abs(o - t) <= window && (best === null || Math.abs(o - t) < Math.abs(best - t))) best = o;
  return best;
}
