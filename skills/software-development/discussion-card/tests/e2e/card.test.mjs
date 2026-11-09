// Browser tests for the discussion-card engine: build the fictional sample, open it from file://.
import { after, before, describe, test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const SKILL = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
// playwright is installed under scripts/ (see scripts/package.json), not next to this file.
const { chromium } = createRequire(path.join(SKILL, 'scripts', 'package.json'))('playwright');
const LAUNCHER = path.join(SKILL, 'scripts', 'discuss.sh');
const SAMPLE = path.join(SKILL, 'tests', 'fixtures', 'sample.md');
const PLAN = path.join(SKILL, 'tests', 'fixtures', 'sample.card.yaml');
const MAC_CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const KEY = 'discussion-card:sample:v1';
const WIDE = { width: 1280, height: 600 };
const NARROW = { width: 900, height: 800 };
const PHONE = { width: 390, height: 844 };
const BUILD_TIMEOUT_MS = 300_000;

let tmp, staticUrl, runtimeUrl, browser;

function build(out, env = {}) {
  execFileSync('sh', [LAUNCHER, SAMPLE, '--plan', PLAN, '-o', out], {
    env: { ...process.env, ...env },
    stdio: 'pipe',
    timeout: BUILD_TIMEOUT_MS,
  });
  return pathToFileURL(out).href;
}

async function launch() {
  try {
    return await chromium.launch();
  } catch (err) {
    const exe = process.env.CHROME_BIN || (existsSync(MAC_CHROME) ? MAC_CHROME : null);
    if (!exe) throw err;
    return chromium.launch({ executablePath: exe });
  }
}

async function open(viewport = NARROW, opts = {}) {
  const context = await browser.newContext({ viewport, acceptDownloads: true, ...opts.context });
  if (opts.init) await context.addInitScript(opts.init);
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto((opts.url || staticUrl) + (opts.hash || ''));
  await page.waitForFunction(() => document.documentElement.classList.contains('dc-ready'));
  return { context, page, errors };
}

const stored = (page) => page.evaluate((k) => JSON.parse(localStorage.getItem(k) || 'null'), KEY);
const firstSpot = (page, chapter) =>
  page.evaluate((c) => document.querySelector(`#${c} [data-spot]`).dataset.spot, chapter);
const spot = (page, id) => page.locator(`[data-spot="${id}"]`);

before(async () => {
  tmp = mkdtempSync(path.join(os.tmpdir(), 'discussion-card-e2e-'));
  staticUrl = build(path.join(tmp, 'card.html'));
  runtimeUrl = build(path.join(tmp, 'runtime.html'), { DISCUSS_NO_CHROME: '1', CHROME_BIN: '/nonexistent' });
  browser = await launch();
});

after(async () => {
  await browser?.close();
  if (tmp) rmSync(tmp, { recursive: true, force: true });
});

describe('discussion card engine', () => {
  test('spot mark and comment persist across reload', async () => {
    const { context, page, errors } = await open();
    const id = await firstSpot(page, 'problem');
    await spot(page, id).click();
    await assert.doesNotReject(page.locator('#dc-drawer').waitFor({ state: 'visible' }));
    await page.click('.dc-st[data-s="change"]');
    await page.fill('#dc-c-who', 'Ana');
    await page.fill('#dc-c-text', 'Needs a rollback plan');
    await page.click('#dc-c-add');
    assert.equal(await spot(page, id).getAttribute('data-heat'), 'change');

    await page.reload();
    await page.waitForFunction(() => document.documentElement.classList.contains('dc-ready'));
    assert.equal(await spot(page, id).getAttribute('data-heat'), 'change');
    const s = await stored(page);
    assert.deepEqual(Object.keys(s).sort(), ['actions', 'questions', 'spots', 'vote']);
    assert.equal(s.spots[id].status, 'change');
    assert.equal(s.spots[id].comments[0].text, 'Needs a rollback plan');
    await spot(page, id).click();
    assert.match(await page.locator('#dc-comments').innerText(), /Needs a rollback plan/);
    assert.match(await page.locator('#dc-comments').innerText(), /Ana/);
    assert.deepEqual(errors, []);
    await context.close();
  });

  test('vote question action item persist', async () => {
    const { context, page, errors } = await open();
    await page.click('[data-vote="for"][data-d="1"]');
    await page.click('[data-vote="for"][data-d="1"]');
    await page.click('[data-vote="against"][data-d="1"]');
    await page.fill('#dc-v-for-names', 'Ana, Bo');
    await page.click('.dc-opt[data-q="q1"][data-opt="Yes"]');
    await page.fill('[data-dec="q1"]', 'Pilot on one service first');
    await page.fill('#dc-act-text', 'Write the threshold doc');
    await page.fill('#dc-act-owner', 'Bo');
    await page.click('#dc-act-add');
    await page.locator('#dc-act-list input[type="checkbox"]').first().check();
    await page.waitForTimeout(500);

    await page.reload();
    await page.waitForFunction(() => document.documentElement.classList.contains('dc-ready'));
    assert.equal(await page.locator('#dc-v-for').innerText(), '2');
    assert.equal(await page.locator('#dc-v-against').innerText(), '1');
    assert.equal(await page.inputValue('#dc-v-for-names'), 'Ana, Bo');
    assert.equal(await page.getAttribute('.dc-opt[data-q="q1"][data-opt="Yes"]', 'aria-pressed'), 'true');
    assert.equal(await page.inputValue('[data-dec="q1"]'), 'Pilot on one service first');
    assert.match(await page.locator('#dc-act-list').innerText(), /Write the threshold doc/);
    assert.equal(await page.locator('#dc-act-list input[type="checkbox"]').first().isChecked(), true);
    const s = await stored(page);
    assert.deepEqual(s.vote, { for: 2, against: 1, forNames: 'Ana, Bo', againstNames: '' });
    assert.deepEqual(s.questions.q1, { pick: 'Yes', decision: 'Pilot on one service first' });
    assert.deepEqual(Object.keys(s.actions[0]).sort(), ['done', 'id', 'owner', 'text']);
    assert.equal(s.actions[0].done, true);
    assert.deepEqual(errors, []);
    await context.close();
  });

  test('hot chip jumps to slide and opens drawer', async () => {
    const { context, page } = await open(WIDE);
    assert.equal(await page.evaluate(() => location.hash), '#problem');
    const id = await firstSpot(page, 'rules');
    await page.evaluate(([k, sid]) => {
      localStorage.setItem(k, JSON.stringify({ spots: { [sid]: { status: 'discuss', comments: [] } } }));
    }, [KEY, id]);
    await page.reload();
    await page.waitForFunction(() => document.documentElement.classList.contains('dc-ready'));
    const chip = page.locator(`#dc-hot [data-goto="${id}"]`);
    assert.equal(await chip.count(), 1);
    await chip.click();
    assert.equal(await page.evaluate(() => location.hash), '#rules');
    assert.equal(await spot(page, id).isVisible(), true);
    await page.locator('#dc-drawer').waitFor({ state: 'visible' });
    assert.ok((await page.locator('#dc-dr-title').innerText()).includes('Small'));
    await context.close();
  });

  test('presenter keys and hash', async () => {
    const { context, page } = await open(WIDE);
    const hash = () => page.evaluate(() => location.hash);
    assert.ok(await page.evaluate(() => document.documentElement.classList.contains('dc-present')));
    assert.equal(await page.locator('#dc-dots button').count(), 9);
    assert.equal(await hash(), '#problem');
    await page.keyboard.press('ArrowRight');
    assert.equal(await hash(), '#how-it-works');
    await page.keyboard.press('ArrowLeft');
    assert.equal(await hash(), '#problem');
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('ArrowRight');
    assert.equal(await hash(), '#pipeline-path');
    assert.equal(await page.evaluate(() => window.scrollY), 0);

    await page.keyboard.press('PageDown');
    await page.waitForTimeout(100);
    assert.ok((await page.evaluate(() => window.scrollY)) > 0, 'first PageDown scrolls the tall slide');
    assert.equal(await hash(), '#pipeline-path');
    for (let i = 0; i < 10 && (await hash()) === '#pipeline-path'; i++) {
      await page.keyboard.press('PageDown');
      await page.waitForTimeout(50);
    }
    assert.equal(await hash(), '#pipeline-path-d1-1');

    await page.keyboard.press('End');
    assert.equal(await hash(), '#open-questions');
    await page.keyboard.press('Home');
    assert.equal(await hash(), '#problem');
    await page.click('#dc-pnext');
    assert.equal(await hash(), '#how-it-works');

    const id = await firstSpot(page, 'problem');
    await page.keyboard.press('Home');
    await spot(page, id).click();
    await page.click('.dc-st[data-s="change"]');
    await page.focus('#dc-c-text');
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('p');
    assert.equal(await hash(), '#problem', 'keys are ignored while typing');
    assert.ok(await page.evaluate(() => document.documentElement.classList.contains('dc-present')));
    const dot = page.locator('#dc-dots button').first();
    assert.match(await dot.getAttribute('class'), /change/);
    assert.match(await dot.getAttribute('title'), /1/);

    await page.goto(staticUrl + '#rules');
    await page.waitForFunction(() => document.documentElement.classList.contains('dc-ready'));
    assert.equal(await page.locator('#rules').isVisible(), true);
    assert.equal(await page.locator('#problem').isVisible(), false);
    await context.close();
  });

  test('P toggles mode and is remembered', async () => {
    const { context, page } = await open(WIDE);
    const present = () => page.evaluate(() => document.documentElement.classList.contains('dc-present'));
    assert.equal(await present(), true, 'presenter is the default at >= 1000px');
    await page.keyboard.press('p');
    assert.equal(await present(), false);
    await page.reload();
    await page.waitForFunction(() => document.documentElement.classList.contains('dc-ready'));
    assert.equal(await present(), false);
    assert.ok(await page.evaluate((k) => localStorage.getItem(k + ':mode') !== null, KEY));
    await page.keyboard.press('P');
    assert.equal(await present(), true);
    await context.close();

    const narrow = await open(NARROW);
    assert.equal(await narrow.page.evaluate(() => document.documentElement.classList.contains('dc-present')), false);
    await narrow.context.close();
  });

  test('markdown export contains comment and verdict', async () => {
    const { context, page } = await open();
    const id = await firstSpot(page, 'situations');
    await spot(page, id).click();
    await page.click('.dc-st[data-s="discuss"]');
    await page.fill('#dc-c-text', 'Friday freeze is unclear');
    await page.click('#dc-c-add');
    await page.keyboard.press('Escape');
    await page.click('[data-vote="for"][data-d="1"]');
    await page.fill('#dc-act-text', 'Draft freeze rules');
    await page.click('#dc-act-add');
    await page.click('#dc-menu-btn');
    const [download] = await Promise.all([page.waitForEvent('download'), page.click('#dc-export-md')]);
    assert.match(download.suggestedFilename(), /\.md$/);
    const md = readFileSync(await download.path(), 'utf8');
    assert.match(md, /## Verdict/);
    assert.match(md, /For: 1/);
    assert.match(md, /Friday freeze is unclear/);
    assert.match(md, /Discuss/);
    assert.match(md, /### Situations/);
    assert.match(md, /- \[ \] Draft freeze rules/);
    await context.close();
  });

  test('phone 390 has no horizontal page scroll', async () => {
    const { context, page } = await open(PHONE);
    const width = () => page.evaluate(() => document.documentElement.scrollWidth);
    assert.ok((await width()) <= 390, `scrollWidth ${await width()}`);
    assert.equal(await page.evaluate(() => document.documentElement.classList.contains('dc-present')), false);
    await spot(page, await firstSpot(page, 'problem')).click();
    assert.ok((await width()) <= 390, `scrollWidth with drawer ${await width()}`);
    await context.close();
  });

  test('dark theme tokens apply', async () => {
    const lum = (page) =>
      page.evaluate(() => {
        const m = getComputedStyle(document.body).backgroundColor.match(/\d+(\.\d+)?/g).map(Number);
        return (0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]) / 255;
      });
    const dark = await open(NARROW, { context: { colorScheme: 'dark' } });
    assert.ok((await lum(dark.page)) < 0.3, 'system dark scheme gives a dark page');
    await dark.context.close();

    const light = await open(NARROW, { context: { colorScheme: 'light' } });
    assert.ok((await lum(light.page)) > 0.7, 'light by default');
    await light.page.click('#dc-menu-btn');
    await light.page.click('#dc-theme');
    assert.equal(await light.page.evaluate(() => document.documentElement.dataset.theme), 'dark');
    assert.ok((await lum(light.page)) < 0.3, 'theme toggle forces dark');
    await light.context.close();
  });

  test('storage unavailable still works', async () => {
    const init = () => {
      const boom = () => {
        throw new DOMException('denied', 'SecurityError');
      };
      Storage.prototype.getItem = boom;
      Storage.prototype.setItem = boom;
    };
    const { context, page, errors } = await open(NARROW, { init });
    const id = await firstSpot(page, 'problem');
    await spot(page, id).click();
    await page.click('.dc-st[data-s="ok"]');
    assert.equal(await spot(page, id).getAttribute('data-heat'), 'ok');
    await page.locator('#dc-toast').waitFor({ state: 'visible' });
    assert.ok((await page.locator('#dc-toast').innerText()).length > 0);
    assert.deepEqual(errors, []);
    await context.close();
  });

  test('import sanitises junk', async () => {
    const { context, page } = await open();
    const id = await firstSpot(page, 'problem');
    const junk = {
      vote: { for: -5, against: 'x', forNames: 'a'.repeat(1000), againstNames: 7 },
      spots: {
        [id]: { status: 'bogus', comments: [{ text: 'c'.repeat(10000), who: 'w'.repeat(200) }, 'nope', { text: 3 }] },
        'not-a-spot': { status: 'ok', comments: [] },
        '<img src=x onerror=alert(1)>': { status: 'change' },
      },
      questions: { q1: { pick: 'Maybe', decision: 7 }, zz: { pick: 'Yes', decision: 'x' } },
      actions: [{ text: 't', owner: 'o'.repeat(200), done: 'yes' }, 5, null, { owner: 'no text' }],
      extra: { evil: true },
    };
    const file = path.join(tmp, 'junk.json');
    writeFileSync(file, JSON.stringify(junk));
    await page.click('#dc-menu-btn');
    await page.setInputFiles('#dc-load-json', file);
    await page.waitForFunction((k) => localStorage.getItem(k) !== null, KEY);
    const s = await stored(page);
    assert.deepEqual(Object.keys(s).sort(), ['actions', 'questions', 'spots', 'vote']);
    assert.deepEqual(s.vote, { for: 0, against: 0, forNames: 'a'.repeat(500), againstNames: '' });
    assert.deepEqual(Object.keys(s.spots), [id]);
    assert.equal(s.spots[id].status, null);
    assert.equal(s.spots[id].comments.length, 1);
    assert.equal(s.spots[id].comments[0].text.length, 4000);
    assert.equal(s.spots[id].comments[0].who.length, 80);
    assert.deepEqual(Object.keys(s.questions), ['q1']);
    assert.deepEqual(s.questions.q1, { pick: null, decision: '' });
    assert.equal(s.actions.length, 1);
    assert.equal(s.actions[0].owner.length, 80);
    assert.equal(s.actions[0].done, false);
    assert.equal(await page.locator('img').count(), 0);
    await context.close();
  });

  test('runtime diagrams become clickable spots with the static ids', async () => {
    const nodeIds = (page) =>
      page.evaluate(() => [...document.querySelectorAll('svg g.node[data-spot]')].map((g) => g.dataset.spot).sort());
    const st = await open(NARROW);
    const want = await nodeIds(st.page);
    await st.context.close();
    assert.ok(want.length >= 9, `static node spots: ${want}`);

    const { context, page, errors } = await open(NARROW, { url: runtimeUrl });
    assert.equal(await page.locator('pre.mermaid-runtime').count(), 0, 'runtime blocks are rendered');
    assert.deepEqual(await nodeIds(page), want);
    const node = page.locator(`g.node[data-spot="${want[0]}"]`);
    assert.equal(await node.getAttribute('tabindex'), '0');
    assert.equal(await node.getAttribute('role'), 'button');
    await node.click();
    await page.locator('#dc-drawer').waitFor({ state: 'visible' });
    await page.click('.dc-st[data-s="change"]');
    assert.equal(await node.getAttribute('data-heat'), 'change');
    assert.deepEqual(errors, []);
    await context.close();
  });
});
