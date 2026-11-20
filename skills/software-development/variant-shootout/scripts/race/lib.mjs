// Pure helpers for race.mjs: no I/O, so they can be unit-tested with node --test.
export const MAX_ROWS = 12;
export const HEADLINE_HOLD_MS = 3000;

export const LABELS = {
  en: {
    title: 'variant-shootout', results: 'Results', noData: 'no timing data', more: 'more rows',
    columns: ['Test', 'Variant', 'Median', 'Delta', 'Time', 'Stability'],
    tests: 'tests', steps: 'steps', done: 'done', vs: 'vs', deltaMedian: 'Δ median', moreTests: 'more tests',
  },
  ru: {
    title: 'variant-shootout', results: 'Результаты', noData: 'нет данных о времени', more: 'строк скрыто',
    columns: ['Тест', 'Вариант', 'Медиана', 'Δ', 'Время', 'Стабильность'],
    tests: 'тесты', steps: 'шаги', done: 'готово', vs: 'против', deltaMedian: 'Δ медианы', moreTests: 'ещё тестов',
  },
};

export function isTimed(r) {
  return Number.isFinite(r.start_ms) && Number.isFinite(r.stop_ms);
}

// Per variant, the seq whose selection wall time is the (lower) median; untimed runs are skipped.
export function pickRuns(runs, variants) {
  const picked = {};
  for (const v of variants) {
    const bySeq = new Map();
    for (const r of runs) if (r.variant === v) {
      if (!bySeq.has(r.seq)) bySeq.set(r.seq, []);
      bySeq.get(r.seq).push(r);
    }
    const walls = [];
    for (const [seq, recs] of bySeq) {
      const t = recs.filter(isTimed);
      if (t.length) walls.push({ seq, wall: Math.max(...t.map((r) => r.stop_ms)) - Math.min(...t.map((r) => r.start_ms)) });
    }
    walls.sort((a, b) => a.wall - b.wall || a.seq - b.seq);
    picked[v] = walls.length ? walls[Math.floor((walls.length - 1) / 2)].seq : null;
  }
  return picked;
}

export function buildLane(runs, variant, seq) {
  if (seq == null) return { variant, seq: null, tests: [], steps: [], span: 0 };
  const recs = runs.filter((r) => r.variant === variant && r.seq === seq && isTimed(r));
  if (!recs.length) return { variant, seq: null, tests: [], steps: [], span: 0 };
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

export function buildTable(report) {
  const all = report.tests.filter((t) => t.variant !== report.baseline);
  const rows = (all.length ? all : report.tests).map((t) => ({
    test: t.test_id, variant: t.variant, median_ms: t.median_ms, delta_ms: t.delta_ms,
    time_verdict: t.time_verdict, stability_verdict: t.stability_verdict,
  }));
  return { rows: rows.slice(0, MAX_ROWS), more: Math.max(0, rows.length - MAX_ROWS) };
}

export function formatDelta(ms) {
  if (ms == null) return 'n/a';
  const s = (Math.abs(ms) / 1000).toFixed(1);
  return `${ms < 0 ? '−' : '+'}${s} s`;
}

// One line per candidate: its first test entry (sorted by test_id), values copied from the report.
export function buildHeadlines(report, labels = LABELS.en) {
  const lines = [];
  for (const v of report.variants.filter((x) => x !== report.baseline)) {
    const entries = report.tests.filter((t) => t.variant === v)
      .sort((a, b) => (a.test_id < b.test_id ? -1 : a.test_id > b.test_id ? 1 : 0));
    if (!entries.length) continue;
    const e = entries[0];
    let line = `${v} ${labels.vs} ${report.baseline}: ${e.time_verdict ?? 'n/a'}, ${labels.deltaMedian} ${formatDelta(e.delta_ms)}`;
    if (entries.length > 1) line += ` (+${entries.length - 1} ${labels.moreTests})`;
    lines.push(line);
  }
  return lines;
}

export function tableHoldMs(rowCount) {
  return Math.max(4000, 1200 * rowCount);
}
