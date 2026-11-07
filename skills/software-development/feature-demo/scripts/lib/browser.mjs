import { existsSync, readdirSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const MACOS_BINARY = 'Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing';
const LINUX_BINARY = 'chrome-linux64/chrome';

function compareVersions(a, b) {
  const pa = a.split('.').map(Number);
  const pb = b.split('.').map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const diff = (pa[i] ?? 0) - (pb[i] ?? 0);
    if (diff !== 0) return diff;
  }
  return 0;
}

export function resolveChrome(env = process.env) {
  if (env.CHROME_BIN) return env.CHROME_BIN;
  const root = path.join(os.homedir(), '.cache', 'selenium', 'chrome');
  if (!existsSync(root)) return undefined;
  const binary = process.platform === 'darwin' ? MACOS_BINARY : LINUX_BINARY;
  const candidates = [];
  for (const platform of readdirSync(root)) {
    const platformDir = path.join(root, platform);
    for (const version of readdirSync(platformDir)) {
      const exe = path.join(platformDir, version, binary);
      if (/^\d+(\.\d+)*$/.test(version) && existsSync(exe)) candidates.push({ version, exe });
    }
  }
  candidates.sort((a, b) => compareVersions(b.version, a.version));
  return candidates[0]?.exe;
}
