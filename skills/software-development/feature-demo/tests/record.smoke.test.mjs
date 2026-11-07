import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { spawn, spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdtempSync, existsSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { captionHtml } from '../scripts/demo-kit.mjs';

const RECORD = fileURLToPath(new URL('../scripts/record.mjs', import.meta.url));
const FIXTURES = fileURLToPath(new URL('./fixtures/', import.meta.url));
const CONFIG = path.join(FIXTURES, 'demo.config.mjs');
const LOGIN_ORDER_CONFIG = path.join(FIXTURES, 'demo.config.login-order.mjs');
const EXIT_SECRET = 4;
const MIN_DURATION_S = 3;
const ERROR_TEXT_CHARS = 500;
const hasFfprobe = spawnSync('ffprobe', ['-version']).status === 0;

let server;
let baseUrl;

before(async () => {
  server = http.createServer((req, res) => {
    const file = path.join(FIXTURES, path.basename(req.url));
    if (!existsSync(file)) return res.writeHead(404).end();
    res.writeHead(200, { 'content-type': 'text/html' }).end(readFileSync(file));
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  baseUrl = `http://127.0.0.1:${server.address().port}`;
});
after(() => server.close());

// Async spawn: the fixture server lives in this process, so a blocking spawn would deadlock it.
function record(scenario, extra = [], { config = CONFIG, env = {} } = {}) {
  const out = mkdtempSync(path.join(tmpdir(), 'feature-demo-'));
  const args = [RECORD, '--config', config, '--scenario', path.join(FIXTURES, scenario), '--base-url', baseUrl, '--out', out, ...extra];
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, args, { env: { ...process.env, ...env } });
    let stderr = '';
    child.stderr.on('data', (d) => (stderr += d));
    child.on('error', reject);
    child.on('close', (status) => resolve({ out, status, stderr }));
  });
}

test('records webm with captions', { skip: hasFfprobe ? false : 'ffprobe not installed' }, async () => {
  const r = await record('scenario.mjs');
  assert.equal(r.status, 0, r.stderr);
  const probe = spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path.join(r.out, 'raw.webm')], { encoding: 'utf8' });
  assert.ok(Number(probe.stdout) >= MIN_DURATION_S, `duration ${probe.stdout}`);
  assert.equal(JSON.parse(readFileSync(path.join(r.out, 'scenario.json'), 'utf8')).title, 'Fixture walkthrough');
  assert.ok(readdirSync(path.join(r.out, 'shots')).includes('end.png'));
});

// Overlay content from screencast.showOverlay is not reachable via the page DOM,
// so literal-text behaviour is asserted on the HTML handed to showOverlay.
test('caption is literal text', () => {
  const html = captionHtml('<b>Привет</b> "мир" & \'x\'');
  assert.ok(html.includes('data-demo-caption'));
  assert.ok(html.includes('&lt;b&gt;Привет&lt;/b&gt; &quot;мир&quot; &amp; &#39;x&#39;'), html);
  assert.ok(!html.includes('<b>'), html);
});

test('fails on secret in page text', async () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'feature-demo-secrets-'));
  const secrets = path.join(dir, '.env');
  writeFileSync(secrets, 'DEMO_SECRET=s3cr3t-value\n');
  const r = await record('scenario-secret.mjs', ['--secrets-file', secrets]);
  assert.equal(r.status, EXIT_SECRET);
  assert.match(r.stderr, /secret value visible/);
});

// Regression guard: Playwright draws `Fill "<value>"` titles, so login (which types the password) must not be filmed.
test('login runs before the recording starts', async () => {
  const r = await record('scenario-login-order.mjs', [], { config: LOGIN_ORDER_CONFIG });
  assert.equal(r.status, 0, r.stderr);
});

test('fails on secret from a password-like environment variable', async () => {
  const r = await record('scenario-env-secret.mjs', [], { env: { DEMO_TEST_PASSWORD: 's3cr3t-env' } });
  assert.equal(r.status, EXIT_SECRET, r.stderr);
  assert.match(r.stderr, /secret value visible/);
});

test('missing locator reports context', async () => {
  const r = await record('scenario-missing.mjs');
  assert.notEqual(r.status, 0);
  assert.ok(existsSync(path.join(r.out, 'error.png')));
  const pageText = r.stderr.split('page text:\n')[1];
  assert.ok(pageText?.startsWith('Acme demo'), r.stderr);
  assert.ok(pageText.length <= ERROR_TEXT_CHARS + 1);
});
