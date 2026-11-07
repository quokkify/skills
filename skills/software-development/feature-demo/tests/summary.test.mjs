import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildSummary, buildDemoBlock, replaceDemoBlock } from '../scripts/summary.mjs';

const base = {
  title: 'Фильтр заказов',
  covers: { 'AC-1': 'Фильтр по статусу', 'AC-2': 'Сброс фильтра' },
  notShown: ['Экспорт в CSV'],
  questions: ['Нужен ли фильтр по дате?'],
  sha: 'abc123def456',
  durationSec: 169.5,
  videoUrl: 'https://example.com/demo.mp4',
};
const START = '<!-- demo:start -->';
const END = '<!-- demo:end -->';

test('formats duration', () => {
  const md = buildSummary(base);
  assert.match(md, /Длительность: 2:49/);
  assert.match(md, /Видео: https:\/\/example\.com\/demo\.mp4/);
  assert.match(md, /`abc123def456`/);
  assert.match(md, /- AC-1: Фильтр по статусу/);
  assert.match(md, /^# Фильтр заказов/);
});

test('omits empty sections', () => {
  const md = buildSummary({ ...base, notShown: [], questions: [] });
  assert.doesNotMatch(md, /Не показано/);
  assert.doesNotMatch(md, /Вопросы к клиентке/);
  assert.match(md, /Показано/);
});

test('block wraps summary without title', () => {
  const block = buildDemoBlock(base);
  assert.ok(block.startsWith(`${START}\n## Demo\n`));
  assert.ok(block.endsWith(END));
  assert.doesNotMatch(block, /^# /m);
  assert.match(block, /Длительность: 2:49/);
});

test('appends block to body without markers', () => {
  const block = buildDemoBlock(base);
  const r = replaceDemoBlock('Описание MR', block);
  assert.equal(r.replaced, false);
  assert.equal(r.body, `Описание MR\n\n${block}`);
});

test('replaces existing block once', () => {
  const block = buildDemoBlock(base);
  const body = `до\n\n${START}\nстарое\n${END}\n\nпосле`;
  const r = replaceDemoBlock(body, block);
  assert.equal(r.replaced, true);
  assert.ok(r.body.startsWith('до\n\n'));
  assert.ok(r.body.endsWith('\n\nпосле'));
  assert.equal(r.body.split(START).length - 1, 1);
  assert.equal(r.body.split(END).length - 1, 1);
  assert.doesNotMatch(r.body, /старое/);
});

test('handles CRLF body', () => {
  const block = buildDemoBlock(base);
  const body = `до\r\n${START}\r\nстарое\r\n${END}\r\nпосле\r\n`;
  const r = replaceDemoBlock(body, block);
  assert.equal(r.replaced, true);
  assert.doesNotMatch(r.body, /\r/);
  assert.match(r.body, /до\n<!-- demo:start -->/);
});

test('handles empty body', () => {
  const block = buildDemoBlock(base);
  assert.deepEqual(replaceDemoBlock('', block), { body: block, replaced: false });
});
