import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const RENDER = fileURLToPath(new URL('../scripts/render.sh', import.meta.url));
const hasFfmpeg = ['ffmpeg', 'ffprobe'].every((b) => spawnSync(b, ['-version']).status === 0);
const skip = hasFfmpeg ? false : 'ffmpeg/ffprobe not installed';

function makeWebm(dir) {
  const raw = path.join(dir, 'raw.webm');
  const r = spawnSync('ffmpeg', ['-v', 'error', '-f', 'lavfi', '-i', 'testsrc=duration=4:size=640x400:rate=25', '-c:v', 'libvpx', '-b:v', '1M', raw]);
  assert.equal(r.status, 0, r.stderr.toString());
  return raw;
}

function probe(file) {
  const r = spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'stream=codec_name,pix_fmt:format=duration', '-of', 'json', file]);
  assert.equal(r.status, 0, r.stderr.toString());
  return JSON.parse(r.stdout);
}

function lastJson(stdout) {
  const lines = stdout.toString().trim().split('\n');
  return JSON.parse(lines.at(-1));
}

test('render converts webm to h264 yuv420p', { skip }, (t) => {
  const dir = mkdtempSync(path.join(tmpdir(), 'render-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const out = path.join(dir, 'demo.mp4');
  const r = spawnSync('bash', [RENDER, makeWebm(dir), out]);
  assert.equal(r.status, 0, r.stderr.toString());
  const info = probe(out);
  assert.equal(info.streams[0].codec_name, 'h264');
  assert.equal(info.streams[0].pix_fmt, 'yuv420p');
  assert.ok(Math.abs(Number(info.format.duration) - 4) < 0.5);
  const res = lastJson(r.stdout);
  assert.equal(res.crf, 22);
  assert.equal(res.scaled, false);
  assert.ok(Math.abs(res.durationSec - 4) < 0.5);
  assert.ok(res.bytes > 0);
});

test('render falls back then fails', { skip }, (t) => {
  const dir = mkdtempSync(path.join(tmpdir(), 'render-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const r = spawnSync('bash', [RENDER, makeWebm(dir), path.join(dir, 'demo.mp4')], {
    env: { ...process.env, DEMO_MAX_BYTES: '1000' },
  });
  assert.equal(r.status, 3, r.stderr.toString());
  const lines = r.stdout.toString().trim().split('\n').map((l) => JSON.parse(l));
  assert.deepEqual(lines.map((l) => [l.crf, l.scaled]), [[22, false], [28, false], [28, true]]);
  assert.match(r.stderr.toString(), /size/i);
});

test('render fails immediately when duration is over limit', { skip }, (t) => {
  const dir = mkdtempSync(path.join(tmpdir(), 'render-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const r = spawnSync('bash', [RENDER, makeWebm(dir), path.join(dir, 'demo.mp4')], {
    env: { ...process.env, DEMO_MAX_SEC: '2' },
  });
  assert.equal(r.status, 3);
  assert.equal(r.stdout.toString().trim().split('\n').length, 1);
  assert.match(r.stderr.toString(), /duration/i);
});

test('render rejects missing arguments', () => {
  const r = spawnSync('bash', [RENDER]);
  assert.equal(r.status, 64);
});
