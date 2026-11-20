#!/usr/bin/env node
// Replay one representative run per variant side by side and encode it to mp4.
// Usage: race.mjs --runs R --report J --out race.mp4 [--speed 4] [--seq-per-variant median]
//        race.mjs --check        (preflight: exit 0 when the browser launches, 1 otherwise)
// Exit codes: 0 ok, 1 missing tool or browser cannot launch, 64 usage.
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, readdirSync, renameSync, rmSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import {
  HEADLINE_HOLD_MS, LABELS, buildHeadlines, buildLane, buildTable, pickRuns, tableHoldMs,
} from './lib.mjs';

class ExitError extends Error {
  constructor(code, message) { super(message); this.code = code; }
}

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WIDTH = 1280;
const HEIGHT = 720;

function usage(msg) {
  if (msg) console.error(msg);
  console.error('usage: race.mjs --runs runs.jsonl --report report.json --out race.mp4 [--speed 4] [--seq-per-variant median]\n       race.mjs --check');
  process.exit(64);
}

function parseArgs(argv) {
  const opts = { speed: 4, seqMode: 'median' };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--check') opts.check = true;
    else if (['--runs', '--report', '--out', '--speed', '--seq-per-variant'].includes(a)) {
      const v = argv[++i];
      if (v === undefined) usage(`${a} needs a value`);
      if (a === '--runs') opts.runs = v;
      else if (a === '--report') opts.report = v;
      else if (a === '--out') opts.out = v;
      else if (a === '--speed') opts.speed = Number(v);
      else opts.seqMode = v;
    } else usage(`unknown argument: ${a}`);
  }
  if (opts.check) return opts;
  if (!opts.runs || !opts.report || !opts.out) usage('--runs, --report and --out are required');
  if (!Number.isFinite(opts.speed) || opts.speed <= 0) usage('--speed must be a positive number');
  if (opts.seqMode !== 'median') usage('--seq-per-variant supports only "median"');
  return opts;
}

async function launch(playwright, extra = {}) {
  const executablePath = process.env.CHROME_BIN || undefined;
  try {
    return await playwright.chromium.launch({ executablePath, ...extra });
  } catch (e) {
    throw new ExitError(1, `cannot launch a browser: ${String(e.message).split('\n')[0]}\n` +
      'Set CHROME_BIN to a Chrome/Chromium binary or run "npx playwright install chromium" in scripts/race.');
  }
}

async function loadPlaywright() {
  try {
    return (await import('playwright')).default ?? (await import('playwright'));
  } catch {
    throw new ExitError(1, 'playwright is not installed: run "npm install" in scripts/race');
  }
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const playwright = await loadPlaywright();

  if (opts.check) {
    const browser = await launch(playwright);
    await browser.close();
    return;
  }

  if (spawnSync('ffmpeg', ['-version'], { stdio: 'ignore' }).status !== 0) {
    throw new ExitError(1, 'ffmpeg is required to encode the video');
  }

  const runs = readFileSync(opts.runs, 'utf8').split('\n').filter((l) => l.trim()).map((l) => JSON.parse(l));
  const report = JSON.parse(readFileSync(opts.report, 'utf8'));
  const variants = report.variants;
  const picked = pickRuns(runs, variants);
  const lanes = variants.map((v) => buildLane(runs, v, picked[v]));
  const span = Math.max(1, ...lanes.map((l) => l.span));
  const lang = LABELS[report.lang] ? report.lang : 'en';
  const table = buildTable(report, LABELS[lang]);
  const data = {
    labels: LABELS[lang], lanes, span, speed: opts.speed, table,
    headlines: buildHeadlines(report, LABELS[lang]), headlineHoldMs: HEADLINE_HOLD_MS, tableHoldMs: tableHoldMs(table.rows.length),
  };

  const tmp = mkdtempSync(path.join(os.tmpdir(), 'race-'));
  let browser;
  try {
    browser = await launch(playwright);
    const context = await browser.newContext({
      viewport: { width: WIDTH, height: HEIGHT },
      deviceScaleFactor: 1,
      recordVideo: { dir: tmp, size: { width: WIDTH, height: HEIGHT } },
    });
    const page = await context.newPage();
    await page.addInitScript((d) => { window.__RACE__ = d; }, data);
    await page.goto(pathToFileURL(path.join(HERE, 'template.html')).href);
    await page.evaluate(() => window.__raceStart());
    const timeout = Math.ceil(span / opts.speed + HEADLINE_HOLD_MS + data.tableHoldMs + 30000);
    await page.waitForFunction(() => window.__raceDone === true, null, { timeout, polling: 100 });
    await context.close();
    await browser.close();
    browser = undefined;

    const webm = readdirSync(tmp).find((f) => f.endsWith('.webm'));
    if (!webm) throw new ExitError(1, 'no video was recorded');
    const raw = path.join(tmp, 'raw.webm');
    renameSync(path.join(tmp, webm), raw);
    const enc = spawnSync('bash', [path.join(HERE, 'encode.sh'), raw, opts.out], { stdio: 'inherit' });
    if (enc.status !== 0) throw new ExitError(1, 'encoding failed');
  } finally {
    if (browser) await browser.close().catch(() => {});
    rmSync(tmp, { recursive: true, force: true });
  }
}

main().catch((e) => {
  console.error(e instanceof ExitError ? e.message : e.stack || String(e));
  process.exitCode = e instanceof ExitError ? e.code : 1;
});
