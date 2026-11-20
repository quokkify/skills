import test from 'node:test';
import assert from 'node:assert/strict';
import { pickRuns, buildLane, buildTable, buildHeadlines, buildResultsTitle, tableHoldMs, LABELS, MAX_ROWS } from '../scripts/race/lib.mjs';

const rec = (seq, variant, start, stop, extra = {}) => ({
  seq, variant, test_id: 't', name: 't', status: 'passed', start_ms: start, stop_ms: stop, steps: [], ...extra,
});

test('pickRuns picks the median wall time run', () => {
  const runs = [rec(1, 'a', 0, 300), rec(2, 'a', 0, 100), rec(3, 'a', 0, 200)];
  assert.deepEqual(pickRuns(runs, ['a']), { a: 3 });
});

test('pickRuns takes the lower median on an even count', () => {
  const runs = [rec(1, 'a', 0, 400), rec(2, 'a', 0, 100), rec(3, 'a', 0, 300), rec(4, 'a', 0, 200)];
  assert.deepEqual(pickRuns(runs, ['a']), { a: 4 });
});

test('pickRuns skips untimed runs and returns null without any timed run', () => {
  const runs = [rec(1, 'a', null, null), rec(2, 'a', 0, 50), rec(1, 'b', null, null)];
  assert.deepEqual(pickRuns(runs, ['a', 'b']), { a: 2, b: null });
});

test('buildLane aligns to first start and collects steps; no timing data gives empty lane', () => {
  const lane = buildLane([rec(1, 'a', 1000, 1500, { steps: [{ name: 's', start_ms: 1100, stop_ms: 1200, status: 'passed' }, { name: 'x', start_ms: null, stop_ms: null }] })], 'a', 1);
  assert.equal(lane.span, 500);
  assert.deepEqual(lane.steps, [{ name: 's', status: 'passed', start: 100, end: 200 }]);
  assert.deepEqual(buildLane([], 'b', null), { variant: 'b', seq: null, tests: [], steps: [], span: 0 });
});

const entry = (test_id, variant, extra = {}) => ({
  test_id, variant, median_ms: 1000, delta_ms: -30200, time_verdict: 'faster', stability_verdict: 'no measurable difference', ...extra,
});

test('buildHeadlines uses first test by id, appends extra count, copies values', () => {
  const report = {
    baseline: 'base', variants: ['base', 'A'],
    tests: [entry('t2', 'A', { delta_ms: 5 }), entry('t1', 'A'), entry('t1', 'base', { delta_ms: null })],
  };
  assert.deepEqual(buildHeadlines(report), ['A vs base · t1: faster, Δ median −30.2 s (+1 more tests)']);
});

test('buildTable lists candidate rows and caps at MAX_ROWS', () => {
  const tests = Array.from({ length: MAX_ROWS + 3 }, (_, i) => entry(`t${i}`, 'A'));
  const t = buildTable({ baseline: 'base', tests: [entry('t0', 'base'), ...tests] });
  assert.equal(t.rows.length, MAX_ROWS);
  assert.equal(t.more, 3);
  assert.equal(t.rows[0].variant, 'A');
});

test('tableHoldMs is at least 4000 and scales with rows', () => {
  assert.equal(tableHoldMs(1), 4000);
  assert.equal(tableHoldMs(10), 12000);
});

test('buildHeadlines in quick mode carries the indicative label first', () => {
  const report = { baseline: 'base', variants: ['base', 'A'], mode: 'quick', lang: 'en', tests: [entry('t1', 'A')] };
  assert.deepEqual(buildHeadlines(report), [
    'Indicative only (quick mode, not proof):',
    'A vs base · t1: faster, Δ median −30.2 s',
  ]);
  const proof = { ...report, mode: 'proof' };
  assert.deepEqual(buildHeadlines(proof), ['A vs base · t1: faster, Δ median −30.2 s']);
});

test('buildHeadlines translates verdict words via report.lang', () => {
  const report = {
    baseline: 'base', variants: ['base', 'A', 'B'], mode: 'quick', lang: 'ru',
    tests: [entry('t1', 'A'), entry('t1', 'B', { time_verdict: 'no measurable difference' })],
  };
  assert.deepEqual(buildHeadlines(report), [
    'Только ориентировочно (быстрый режим, не доказательство):',
    'A против base · t1: быстрее, Δ медианы −30.2 s',
    'B против base · t1: измеримой разницы нет, Δ медианы −30.2 s',
  ]);
});

test('buildTable translates verdict words via report.lang', () => {
  const t = buildTable({ baseline: 'base', lang: 'ru', tests: [entry('t1', 'A')] });
  assert.equal(t.rows[0].time_verdict, 'быстрее');
  assert.equal(t.rows[0].stability_verdict, 'измеримой разницы нет');
});

test('LABELS verdict tables match strings.py keys', () => {
  for (const lang of ['en', 'ru']) {
    assert.deepEqual(Object.keys(LABELS[lang].verdicts).sort(), [
      'baseline', 'faster', 'insufficient data', 'less flaky', 'more flaky', 'no measurable difference', 'slower',
    ]);
  }
});

test('buildResultsTitle qualifies quick mode and leaves proof mode unchanged', () => {
  assert.deepEqual(buildResultsTitle({ mode: 'quick', lang: 'en' }),
    { title: 'Results', qualifier: 'Indicative only (quick mode, not proof)' });
  assert.deepEqual(buildResultsTitle({ mode: 'quick', lang: 'ru' }),
    { title: 'Результаты', qualifier: 'Только ориентировочно (быстрый режим, не доказательство)' });
  assert.deepEqual(buildResultsTitle({ mode: 'proof', lang: 'en' }), { title: 'Results', qualifier: null });
});
