import fs from 'node:fs';
import path from 'node:path';

export const CHROME_NAMES = ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'];

export function onPath(name, env = process.env) {
  for (const dir of (env.PATH || '').split(path.delimiter)) {
    if (dir && fs.existsSync(path.join(dir, name))) return path.join(dir, name);
  }
  return null;
}

const allOnPath = (names, env) => names.map((n) => onPath(n, env)).filter(Boolean);

export function chromeCandidates(platform = process.platform, env = process.env) {
  if (platform === 'win32') {
    const roots = [env.ProgramFiles, env['ProgramFiles(x86)'], env.LOCALAPPDATA].filter(Boolean);
    const found = (roots.length ? roots : ['C:\\Program Files']).map((r) => path.win32.join(r, 'Google', 'Chrome', 'Application', 'chrome.exe'));
    return found.concat(allOnPath(['chrome.exe', 'chromium.exe'], env));
  }
  if (platform === 'darwin') {
    const apps = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Chromium.app/Contents/MacOS/Chromium'];
    return apps.concat(allOnPath(CHROME_NAMES, env));
  }
  const found = allOnPath(CHROME_NAMES, env);
  return found.length ? found : [CHROME_NAMES[0]];
}

export function findChrome(env = process.env, platform = process.platform) {
  if (env.CHROME) return env.CHROME;
  const c = chromeCandidates(platform, env);
  return c.find((p) => fs.existsSync(p)) || c[0];
}
