import { test } from 'node:test';
import assert from 'node:assert/strict';
import net from 'node:net';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { findFreePorts } from '../scripts/lib/ports.mjs';

const STAND = fileURLToPath(new URL('../scripts/stand.mjs', import.meta.url));
const FIXTURE = fileURLToPath(new URL('./fixtures/demo.config.mjs', import.meta.url));

function listen(port) {
  return new Promise((resolve, reject) => {
    const s = net.createServer();
    s.once('error', reject);
    s.listen(port, '127.0.0.1', () => resolve(s));
  });
}
const close = (s) => new Promise((r) => s.close(r));

async function freeBase() {
  for (let p = 41000; p < 60000; p += 100) {
    const held = [];
    try {
      for (const off of [0, 1, 10, 11]) held.push(await listen(p + off));
      await Promise.all(held.map(close));
      return { A: p, B: p + 1 };
    } catch {
      await Promise.all(held.map(close));
    }
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

test('missing required flag exits 64', () => {
  const r = spawnSync(process.execPath, [STAND, 'up'], { encoding: 'utf8' });
  assert.equal(r.status, 64);
});
