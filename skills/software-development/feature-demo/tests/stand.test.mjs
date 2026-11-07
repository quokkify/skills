import { test } from 'node:test';
import assert from 'node:assert/strict';
import net from 'node:net';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { findFreePorts } from '../scripts/lib/ports.mjs';

const STAND = fileURLToPath(new URL('../scripts/stand.mjs', import.meta.url));
const FIXTURE = fileURLToPath(new URL('./fixtures/demo.config.mjs', import.meta.url));

function listen(port, host = '127.0.0.1') {
  return new Promise((resolve, reject) => {
    const s = net.createServer();
    s.once('error', reject);
    s.listen(port, host, () => resolve(s));
  });
}
const close = (s) => new Promise((r) => s.close(r));

// Probe one bind at a time: Linux rejects binding 127.0.0.1:p while 0.0.0.0:p is held, so holding
// both at once makes every candidate look busy there (macOS allows it).
async function bindsAlone(port, host) {
  try {
    await close(await listen(port, host));
    return true;
  } catch {
    return false;
  }
}

async function freeBase() {
  for (let p = 41000; p < 60000; p += 100) {
    let free = true;
    for (const off of [0, 1, 10, 11]) {
      for (const host of ['0.0.0.0', '127.0.0.1']) {
        if (!(await bindsAlone(p + off, host))) free = false;
      }
    }
    if (free) return { A: p, B: p + 1 };
  }
  throw new Error('no free test ports');
}

test('findFreePorts returns base when free', async () => {
  const base = await freeBase();
  assert.deepEqual(await findFreePorts(base), base);
});

test('findFreePorts shifts whole set when one port busy', async () => {
  const base = await freeBase();
  const busy = await listen(base.B);
  try {
    assert.deepEqual(await findFreePorts(base), { A: base.A + 10, B: base.B + 10 });
  } finally {
    await close(busy);
  }
});

// Regression guard: Docker publishes on all interfaces; a port held on 0.0.0.0 must not count as free.
test('findFreePorts shifts when a port is held on 0.0.0.0', async () => {
  const base = await freeBase();
  const busy = await listen(base.A, '0.0.0.0');
  try {
    assert.deepEqual(await findFreePorts(base), { A: base.A + 10, B: base.B + 10 });
  } finally {
    await close(busy);
  }
});

test('findFreePorts throws after maxShift', async () => {
  const base = await freeBase();
  const busy = await listen(base.B);
  try {
    await assert.rejects(findFreePorts(base, { maxShift: 0 }), /no free port set/);
  } finally {
    await close(busy);
  }
});

test('up --dry-run prints plan', () => {
  const r = spawnSync(process.execPath, [
    STAND, 'up', '--dry-run', '--config', FIXTURE, '--worktree', '/nonexistent-worktree', '--project', 'demo-x',
  ], { encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
  const plan = JSON.parse(r.stdout);
  assert.equal(plan.project, 'demo-x');
  assert.equal(plan.baseUrl, `http://localhost:${plan.ports.FRONTEND_PORT}`);
  assert.deepEqual(Object.keys(plan.ports), ['FRONTEND_PORT', 'BACKEND_PORT', 'DB_PORT']);
});

// Regression guard: seed/reset scripts come from the adapter checkout, not from the MR worktree.
test('seed --dry-run resolves script relative to the config directory', () => {
  const worktree = '/nonexistent-worktree';
  const r = spawnSync(process.execPath, [
    STAND, 'seed', '--dry-run', '--config', FIXTURE, '--worktree', worktree, '--project', 'demo-x',
  ], { encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
  const plan = JSON.parse(r.stdout);
  assert.equal(plan.stdin, path.join(path.dirname(FIXTURE), 'seed.py'));
  assert.ok(!plan.stdin.startsWith(worktree), plan.stdin);
});

test('missing required flag exits 64', () => {
  const r = spawnSync(process.execPath, [STAND, 'up'], { encoding: 'utf8' });
  assert.equal(r.status, 64);
});
