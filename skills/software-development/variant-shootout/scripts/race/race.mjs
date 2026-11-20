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

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WIDTH = 1280;
const HEIGHT = 720;
const HOLD_MS = 2500;
const MAX_ROWS = 12;

const LABELS = {
  en: {
    title: 'variant-shootout', results: 'Results', noData: 'no timing data', more: 'more rows',
    columns: ['Test', 'Variant', 'Median', 'Delta', 'Time', 'Stability'],
  },
  ru: {
    title: 'variant-shootout', results: 'Результаты', noData: 'нет данных о времени', more: 'строк скрыто',
    columns: ['Тест', 'Вариант', 'Медиана', 'Δ', 'Время', 'Стабильность'],
  },
};

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

function timed(r) {
  return Number.isFinite(r.start_ms) && Number.isFinite(r.stop_ms);
}

// Per variant, the seq whose selection wall time is the (lower) median; untimed runs are skipped.
function pickRuns(runs, variants) {
  const picked = {};
  for (const v of variants) {
    const bySeq = new Map();
    for (const r of runs) if (r.variant === v) {
      if (!bySeq.has(r.seq)) bySeq.set(r.seq, []);
      bySeq.get(r.seq).push(r);
    }
    const walls = [];
    for (const [seq, recs] of bySeq) {
      const t = recs.filter(timed);
      if (t.length) walls.push({ seq, wall: Math.max(...t.map((r) => r.stop_ms)) - Math.min(...t.map((r) => r.start_ms)) });
    }
    walls.sort((a, b) => a.wall - b.wall || a.seq - b.seq);
    picked[v] = walls.length ? walls[Math.floor((walls.length - 1) / 2)].seq : null;
  }
  return picked;
}

function buildLane(runs, variant, seq) {
  if (seq == null) return { variant, seq: null, tests: [], steps: [], span: 0 };
  const recs = runs.filter((r) => r.variant === variant && r.seq === seq && timed(r));
  const t0 = Math.min(...recs.map((r) => r.start_ms));
  const tests = [], steps = [];
  for (const r of recs.sort((a, b) => a.start_ms - b.start_ms)) {
    tests.push({ name: r.name, status: r.status, start: r.start_ms - t0, end: r.stop_ms - t0 });
    for (const s of r.steps || []) {
      if (Number.isFinite(s.start_ms) && Number.isFinite(s.stop_ms)) {
        steps.push({ name: s.name, status: s.status, start: s.start_ms - t0, end: s.stop_ms - t0 });
      }
    }
  }
  return { variant, seq, tests, steps, span: Math.max(...tests.map((t) => t.end)) };
}

function buildTable(report) {
  const all = report.tests.filter((t) => t.variant !== report.baseline);
  const rows = (all.length ? all : report.tests).map((t) => ({
    test: t.test_id, variant: t.variant, median_ms: t.median_ms, delta_ms: t.delta_ms,
    time_verdict: t.time_verdict, stability_verdict: t.stability_verdict,
  }));
  return { rows: rows.slice(0, MAX_ROWS), more: Math.max(0, rows.length - MAX_ROWS) };
}

async function launch(playwright, extra = {}) {
  const executablePath = process.env.CHROME_BIN || undefined;
  try {
    return await playwright.chromium.launch({ executablePath, ...extra });
  } catch (e) {
    console.error(`cannot launch a browser: ${String(e.message).split('\n')[0]}\n` +
      'Set CHROME_BIN to a Chrome/Chromium binary or run "npx playwright install chromium" in scripts/race.');
    process.exit(1);
  }
}

async function loadPlaywright() {
  try {
    return (await import('playwright')).default ?? (await import('playwright'));
  } catch {
    console.error('playwright is not installed: run "npm install" in scripts/race');
    process.exit(1);
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

  const runs = readFileSync(opts.runs, 'utf8').split('\n').filter((l) => l.trim()).map((l) => JSON.parse(l));
  const report = JSON.parse(readFileSync(opts.report, 'utf8'));
  const variants = report.variants;
  const picked = pickRuns(runs, variants);
  const lanes = variants.map((v) => buildLane(runs, v, picked[v]));
  const span = Math.max(1, ...lanes.map((l) => l.span));
  const lang = LABELS[report.lang] ? report.lang : 'en';
  const data = {
    labels: LABELS[lang], lanes, span, speed: opts.speed, holdMs: HOLD_MS, table: buildTable(report),
  };

  const tmp = mkdtempSync(path.join(os.tmpdir(), 'race-'));
  try {
    const browser = await launch(playwright);
    const context = await browser.newContext({
      viewport: { width: WIDTH, height: HEIGHT },
      deviceScaleFactor: 1,
      recordVideo: { dir: tmp, size: { width: WIDTH, height: HEIGHT } },
    });
    const page = await context.newPage();
    await page.addInitScript((d) => { window.__RACE__ = d; }, data);
    await page.goto(pathToFileURL(path.join(HERE, 'template.html')).href);
    await page.evaluate(() => window.__raceStart());
    const timeout = Math.ceil(span / opts.speed + HOLD_MS + 30000);
    await page.waitForFunction(() => window.__raceDone === true, null, { timeout, polling: 100 });
    await context.close();
    await browser.close();

    const webm = readdirSync(tmp).find((f) => f.endsWith('.webm'));
    if (!webm) { console.error('no video was recorded'); process.exit(1); }
    const raw = path.join(tmp, 'raw.webm');
    renameSync(path.join(tmp, webm), raw);
    const enc = spawnSync('bash', [path.join(HERE, 'encode.sh'), raw, opts.out], { stdio: 'inherit' });
    if (enc.status !== 0) process.exit(1);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
}

main().catch((e) => { console.error(e.stack || String(e)); process.exit(1); });
