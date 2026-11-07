import { test } from 'node:test';
import assert from 'node:assert/strict';
import { chmodSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const PUBLISH = fileURLToPath(new URL('../scripts/publish.sh', import.meta.url));
const ORIGIN_URL = 'https://github.com/acme/app.git';
const START = '<!-- demo:start -->';
const END = '<!-- demo:end -->';

function git(cwd, ...args) {
  const r = spawnSync('git', args, { cwd, encoding: 'utf8' });
  assert.equal(r.status, 0, `git ${args.join(' ')}: ${r.stderr}`);
  return r.stdout.trim();
}

function setup(t) {
  const root = mkdtempSync(path.join(tmpdir(), 'publish-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const bare = path.join(root, 'origin.git');
  const repo = path.join(root, 'repo');
  const dir = path.join(root, 'out');
  git(root, 'init', '-q', '--bare', bare);
  git(root, 'init', '-q', '-b', 'main', repo);
  git(repo, 'config', 'user.name', 'Demo Bot');
  git(repo, 'config', 'user.email', 'demo@example.com');
  git(repo, 'config', `url.${bare}.insteadOf`, ORIGIN_URL);
  git(repo, 'remote', 'add', 'origin', ORIGIN_URL);
  writeFileSync(path.join(repo, 'README.md'), 'app\n');
  git(repo, 'add', 'README.md');
  git(repo, 'commit', '-q', '-m', 'init');
  git(repo, 'push', '-q', 'origin', 'main');
  mkdirSync(dir);
  writeFileSync(path.join(dir, 'demo.mp4'), 'fake video v1');
  writeFileSync(path.join(dir, 'scenario.mjs'), "export const title = 'Demo';\n");
  writeFileSync(path.join(dir, 'scenario.json'), JSON.stringify({ title: 'Demo', covers: { 'AC-1': 'shown' }, notShown: [], questions: [] }));
  const sha = git(repo, 'rev-parse', 'HEAD');
  return { bare, repo, dir, sha, sha12: sha.slice(0, 12), root };
}

function publish({ repo, dir, sha }, extra = [], env = {}, mr = '7') {
  return spawnSync('bash', [PUBLISH, '--repo', repo, '--mr', mr, '--sha', sha, '--dir', dir, '--duration', '12.5', ...extra], {
    encoding: 'utf8',
    env: { ...process.env, DEMO_SKIP_FORGE: '1', ...env },
  });
}

const hasLocalBranch = (repo, name) => spawnSync('git', ['rev-parse', '--verify', '-q', `refs/heads/${name}`], { cwd: repo }).status === 0;

// REST-only gh stub: PR 7 exists; any other call fails with gh's own exit code 4.
function ghStub({ root }, { failEdit = false } = {}) {
  const bin = path.join(root, 'bin');
  const log = path.join(root, 'gh.log');
  mkdirSync(bin);
  writeFileSync(path.join(bin, 'gh'), `#!/bin/sh
echo "$*" >> "${log}"
case "$1 $2 $3 $4" in
  "api repos/acme/app/pulls/7 --jq "*) printf 'Intro\\n\\n${START}\\nold\\n${END}\\n' ;;
  "api -X PATCH repos/acme/app/pulls/7") ${failEdit ? 'exit 4' : `cat "\${6#body=@}" > "${log}.body"`} ;;
  "api -X POST repos/acme/app/issues/7/comments") cat "\${6#body=@}" >> "${log}.comments" ;;
  *) echo "HTTP 404: Not Found" >&2; exit 4 ;;
esac
`);
  chmodSync(path.join(bin, 'gh'), 0o755);
  return { log, env: { DEMO_SKIP_FORGE: '', PATH: `${bin}:${process.env.PATH}` } };
}

test('publish creates orphan demos branch', (t) => {
  const ctx = setup(t);
  const r = publish(ctx);
  assert.equal(r.status, 0, r.stderr);
  const files = git(ctx.bare, 'ls-tree', '-r', '--name-only', 'demos').split('\n');
  assert.ok(files.includes(`demos/7/${ctx.sha12}/demo.mp4`));
  assert.ok(files.includes(`demos/7/${ctx.sha12}/summary.md`));
  assert.ok(files.includes(`demos/7/${ctx.sha12}/scenario.mjs`));
  assert.ok(files.includes(`demos/7/${ctx.sha12}/scenario.json`));
  const mb = spawnSync('git', ['merge-base', 'main', 'demos'], { cwd: ctx.bare });
  assert.equal(mb.status, 1, 'demos must not share history with main');
  assert.equal(git(ctx.bare, 'log', '-1', '--format=%s', 'demos'), `docs(demo): MR !7 at ${ctx.sha12}`);
  const summary = git(ctx.bare, 'show', `demos:demos/7/${ctx.sha12}/summary.md`);
  assert.match(summary, new RegExp(`https://github.com/acme/app/blob/demos/demos/7/${ctx.sha12}/demo.mp4`));
  assert.match(r.stdout, /blob\/demos\/demos\/7\//);
  assert.equal(git(ctx.repo, 'worktree', 'list', '--porcelain').split('\n').filter((l) => l.startsWith('worktree ')).length, 1);
  assert.ok(!hasLocalBranch(ctx.repo, 'demos'), 'publish must not leave a local demos branch');
});

test('publish twice same sha overwrites', (t) => {
  const ctx = setup(t);
  assert.equal(publish(ctx).status, 0);
  writeFileSync(path.join(ctx.dir, 'demo.mp4'), 'fake video v2');
  const r = publish(ctx);
  assert.equal(r.status, 0, r.stderr);
  const files = git(ctx.bare, 'ls-tree', '-r', '--name-only', 'demos').split('\n');
  assert.equal(files.length, 4);
  assert.ok(files.every((f) => f.startsWith(`demos/7/${ctx.sha12}/`)));
  assert.equal(git(ctx.bare, 'rev-list', '--count', 'demos'), '2');
  assert.equal(git(ctx.bare, 'show', `demos:demos/7/${ctx.sha12}/demo.mp4`), 'fake video v2');
});

test('publish dry-run prints replaced body', (t) => {
  const ctx = setup(t);
  const body = path.join(ctx.root, 'body.md');
  writeFileSync(body, `Описание\n\n${START}\nстарое\n${END}\n\nконец\n`);
  const r = publish(ctx, ['--dry-run', '--body-file', body]);
  assert.equal(r.status, 0, r.stderr);
  assert.equal(r.stdout.split(START).length - 1, 1);
  assert.equal(r.stdout.split(END).length - 1, 1);
  assert.match(r.stdout, /blob\/demos\/demos\/7\//);
  assert.match(r.stdout, new RegExp(`demos/7/${ctx.sha12}/summary\\.md`));
  assert.doesNotMatch(r.stdout, /старое/);
  assert.notEqual(spawnSync('git', ['rev-parse', '--verify', 'demos'], { cwd: ctx.bare }).status, 0);
});

test('publish rejects dir without demo.mp4', (t) => {
  const ctx = setup(t);
  rmSync(path.join(ctx.dir, 'demo.mp4'));
  const r = publish(ctx);
  assert.equal(r.status, 64);
  assert.match(r.stderr, /demo\.mp4/);
});

test('publish stops with exit 5 when push is rejected', (t) => {
  const ctx = setup(t);
  const hook = path.join(ctx.bare, 'hooks', 'pre-receive');
  writeFileSync(hook, '#!/bin/sh\nexit 1\n');
  chmodSync(hook, 0o755);
  git(ctx.bare, 'config', 'core.hooksPath', path.dirname(hook));
  const r = publish(ctx);
  assert.equal(r.status, 5);
  assert.match(r.stderr, /push of demos to origin failed/);
  assert.doesNotMatch(r.stderr, /another publish may have landed/);
  assert.equal(git(ctx.repo, 'worktree', 'list', '--porcelain').split('\n').filter((l) => l.startsWith('worktree ')).length, 1);
});

// Regression guard: a failed first push used to leave a local `demos` branch that blocked every re-run.
test('publish succeeds on re-run after a failed first push', (t) => {
  const ctx = setup(t);
  const hooks = path.join(ctx.root, 'hooks');
  mkdirSync(hooks);
  writeFileSync(path.join(hooks, 'pre-receive'), '#!/bin/sh\nexit 1\n');
  chmodSync(path.join(hooks, 'pre-receive'), 0o755);
  git(ctx.bare, 'config', 'core.hooksPath', hooks);
  assert.equal(publish(ctx).status, 5);
  assert.ok(!hasLocalBranch(ctx.repo, 'demos'));
  git(ctx.bare, 'config', '--unset', 'core.hooksPath');
  const r = publish(ctx);
  assert.equal(r.status, 0, r.stderr);
  assert.ok(git(ctx.bare, 'ls-tree', '-r', '--name-only', 'demos').includes(`demos/7/${ctx.sha12}/demo.mp4`));
});

// Regression guard: the MR is confirmed before anything is pushed.
test('publish to a missing MR exits 1 and pushes nothing', (t) => {
  const ctx = setup(t);
  const { env } = ghStub(ctx);
  const r = publish(ctx, [], env, '8');
  assert.equal(r.status, 1, r.stderr);
  assert.match(r.stderr, /!8/);
  assert.notEqual(spawnSync('git', ['rev-parse', '--verify', '-q', 'demos'], { cwd: ctx.bare }).status, 0);
  assert.ok(!hasLocalBranch(ctx.repo, 'demos'));
});

test('publish maps an unexpected tool failure to exit 1', (t) => {
  const ctx = setup(t);
  const { env } = ghStub(ctx, { failEdit: true });
  const r = publish(ctx, [], env);
  assert.equal(r.status, 1, r.stderr);
});

test('publish updates GitHub PR body and comments on replace', (t) => {
  const ctx = setup(t);
  const { log, env } = ghStub(ctx);
  const r = publish(ctx, [], env);
  assert.equal(r.status, 0, r.stderr);
  const calls = readFileSync(log, 'utf8');
  assert.match(calls, /^api repos\/acme\/app\/pulls\/7 --jq /m);
  assert.match(calls, /^api -X PATCH repos\/acme\/app\/pulls\/7 -F body=@/m);
  assert.match(calls, /^api -X POST repos\/acme\/app\/issues\/7\/comments -F body=@/m);
  assert.doesNotMatch(calls, /^pr /m);
  assert.equal(readFileSync(`${log}.comments`, 'utf8').trim(), `Demo updated: https://github.com/acme/app/blob/demos/demos/7/${ctx.sha12}/demo.mp4`);
  const body = readFileSync(`${log}.body`, 'utf8');
  assert.ok(body.startsWith('Intro\n\n'));
  assert.equal(body.split(START).length - 1, 1);
  assert.doesNotMatch(body, /old/);
});

test('publish skips comment when identical re-publish pushes nothing', (t) => {
  const ctx = setup(t);
  const { log, env } = ghStub(ctx);
  assert.equal(publish(ctx, [], env).status, 0);
  const r = publish(ctx, [], env);
  assert.equal(r.status, 0, r.stderr);
  assert.equal(git(ctx.bare, 'rev-list', '--count', 'demos'), '1');
  const calls = readFileSync(log, 'utf8');
  assert.equal(calls.match(/^api -X PATCH /gm).length, 2);
  assert.equal(calls.match(/^api -X POST /gm).length, 1);
});

test('publish comments and summarizes in Russian with --lang ru', (t) => {
  const ctx = setup(t);
  const { log, env } = ghStub(ctx);
  const r = publish(ctx, ['--lang', 'ru'], env);
  assert.equal(r.status, 0, r.stderr);
  assert.match(readFileSync(`${log}.comments`, 'utf8'), /^Демо обновлено: https:/m);
  assert.match(readFileSync(`${log}.body`, 'utf8'), /^Видео: https:/m);
  assert.match(git(ctx.bare, 'show', `demos:demos/7/${ctx.sha12}/summary.md`), /^Коммит: /m);
});

test('publish rejects unknown --lang', (t) => {
  const ctx = setup(t);
  const r = publish(ctx, ['--lang', 'de']);
  assert.equal(r.status, 64);
  assert.match(r.stderr, /--lang/);
  assert.notEqual(spawnSync('git', ['rev-parse', '--verify', 'demos'], { cwd: ctx.bare }).status, 0);
});

test('publish dry-run shows --note in the block', (t) => {
  const ctx = setup(t);
  const body = path.join(ctx.root, 'body.md');
  writeFileSync(body, 'Intro\n');
  const note = 'Recorded at 0123456789ab; MR head is now ba9876543210';
  const r = publish(ctx, ['--dry-run', '--body-file', body, '--note', note]);
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, new RegExp(`^Duration: 0:12\\n${note}$`, 'm'));
});

test('publish fails loudly when origin is unreachable', (t) => {
  const ctx = setup(t);
  const missingUrl = 'https://github.com/acme/missing.git';
  git(ctx.repo, 'remote', 'set-url', 'origin', missingUrl);
  git(ctx.repo, 'config', `url.${path.join(ctx.root, 'missing.git')}.insteadOf`, missingUrl);
  const r = publish(ctx);
  assert.equal(r.status, 1, r.stderr);
  assert.match(r.stderr, /cannot read origin/);
  assert.match(r.stderr, /missing\.git/);
  assert.notEqual(spawnSync('git', ['rev-parse', '--verify', '-q', 'demos'], { cwd: ctx.repo }).status, 0);
});

// Regression guard: credentials embedded in remote.origin.url must never leak into output or published files.
test('publish keeps origin credentials out of output', (t) => {
  const ctx = setup(t);
  for (const bad of ['https://u:SECRET@github.com', 'https://u:SECRET/x@github.com/acme/app.git', 'git@github.com:acme:SECRET']) {
    git(ctx.repo, 'remote', 'set-url', 'origin', bad);
    const r = publish(ctx);
    assert.equal(r.status, 64, `${bad}: ${r.stderr}`);
    assert.doesNotMatch(r.stdout + r.stderr, /SECRET/, bad);
    assert.match(r.stderr, /origin URL/);
  }
  const withToken = 'https://u:SE@CRET@github.com/acme/app.git';
  git(ctx.repo, 'remote', 'set-url', 'origin', withToken);
  git(ctx.repo, 'config', `url.${ctx.bare}.insteadOf`, withToken);
  const r = publish(ctx);
  assert.equal(r.status, 0, r.stderr);
  const summary = git(ctx.bare, 'show', `demos:demos/7/${ctx.sha12}/summary.md`);
  for (const out of [r.stdout, r.stderr, summary]) {
    assert.doesNotMatch(out, /CRET|SE@/);
  }
  assert.match(r.stdout, new RegExp(`^https://github.com/acme/app/blob/demos/demos/7/${ctx.sha12}/demo.mp4$`, 'm'));
});
