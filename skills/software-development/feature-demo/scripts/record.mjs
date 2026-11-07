#!/usr/bin/env node
import { parseArgs } from 'node:util';
import { chromium } from 'playwright';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { resolveChrome } from './lib/browser.mjs';
import { createKit } from './demo-kit.mjs';

const EXIT_FAILURE = 1;
const EXIT_USAGE = 64;
const EXIT_SECRET = 4;
const MIN_SECRET_LENGTH = 6;
const SECRET_ENV_KEY = /PASSWORD|TOKEN|SECRET|API_KEY/i;
const ERROR_TEXT_CHARS = 500;

function usage(message) {
  console.error(`${message}\nusage: record.mjs --config <file> --scenario <file> --base-url <url> --out <dir> [--secrets-file <.env>]`);
  process.exit(EXIT_USAGE);
}

let values;
try {
  ({ values } = parseArgs({
    options: {
      config: { type: 'string' },
      scenario: { type: 'string' },
      'base-url': { type: 'string' },
      out: { type: 'string' },
      'secrets-file': { type: 'string' },
    },
  }));
} catch (err) {
  usage(err.message);
}
for (const flag of ['config', 'scenario', 'base-url', 'out']) {
  if (!values[flag]) usage(`missing --${flag}`);
}

const out = path.resolve(values.out);
const baseUrl = values['base-url'];
const importModule = (file) => import(pathToFileURL(path.resolve(file)).href);
const config = (await importModule(values.config)).default;
const scenario = await importModule(values.scenario);

function loadSecrets(file) {
  const fromFile = file
    ? readFileSync(file, 'utf8')
      .split('\n')
      .map((line) => line.match(/^\s*[\w.-]+\s*=\s*(.*?)\s*$/)?.[1]?.replace(/^(['"])(.*)\1$/, '$2') ?? '')
    : [];
  const fromEnv = Object.entries(process.env).filter(([key]) => SECRET_ENV_KEY.test(key)).map(([, value]) => value ?? '');
  return [...fromFile, ...fromEnv].filter((v) => v.length >= MIN_SECRET_LENGTH);
}
const secrets = loadSecrets(values['secrets-file']);

class SecretVisibleError extends Error {}

async function assertNoSecrets(page) {
  if (secrets.length === 0) return;
  const text = await page.evaluate(() => document.body.innerText);
  if (secrets.some((s) => text.includes(s))) throw new SecretVisibleError('secret value visible in page text');
}

mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: resolveChrome() });
const context = await browser.newContext({ viewport: config.viewport });
const page = await context.newPage();
const kit = createKit(page, {
  shotsDir: path.join(out, 'shots'),
  fixturesDir: config.fixtures,
  onShot: () => assertNoSecrets(page),
});
const webm = path.join(out, 'raw.webm');
let exitCode = 0;
let recording = false;

try {
  // Login is not filmed: showActions would draw the typed password as an action title.
  await config.login(page, { baseUrl });
  await page.screencast.start({ path: webm, size: config.viewport });
  recording = true;
  await page.screencast.showActions();
  await kit.chapter(scenario.title);
  await scenario.steps({ page, kit });
  await assertNoSecrets(page);
  writeFileSync(
    path.join(out, 'scenario.json'),
    JSON.stringify({ title: scenario.title, covers: scenario.covers, notShown: scenario.notShown, questions: scenario.questions }, null, 2),
  );
} catch (err) {
  if (err instanceof SecretVisibleError) {
    exitCode = EXIT_SECRET;
    console.error(err.message);
  } else {
    exitCode = EXIT_FAILURE;
    console.error(err.stack ?? String(err));
    await page.screenshot({ path: path.join(out, 'error.png') }).catch(() => {});
    const text = await page.evaluate(() => document.body.innerText).catch(() => '');
    console.error(`page text:\n${text.slice(0, ERROR_TEXT_CHARS)}`);
  }
} finally {
  if (recording) await page.screencast.stop().catch((e) => console.error(`screencast.stop failed: ${e.message}`));
  await browser.close();
}
process.exit(exitCode);
