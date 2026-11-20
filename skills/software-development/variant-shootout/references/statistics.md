# Statistics behind the evidence block

What `scripts/analyze.py` computes, what each number means, and when a verdict is earned. Every number comes from the script; the model explains numbers, it never computes or adjusts them.

## Sample unit

- A **sample** is one execution of one test in one run. Verdicts are computed per test and per variant against the baseline.
- Test identity is `classname#name` (Allure: `testClass#testMethod`, else `fullName`, plus parameters), so equal method names in different classes stay separate.
- `skipped` executions are left out of N. `failed` and `broken` count as failures.
- A retried-then-passed execution counts as **failed**: JUnit `flakyFailure`/`flakyError`/`rerunFailure`/`rerunError`, or several Allure results sharing one `historyId` in a run.
- Runs in state `infra_error`, `no_results` or `invalid` contribute no samples.
- **Time** statistics use passed executions only; a failed run often stops early or hangs, which would distort the time.

## Time

| Field | Meaning |
|---|---|
| `median_ms` | middle passed duration; the headline number, robust to one slow outlier |
| `mean_ms` | average passed duration; diverges from the median when there are outliers |
| `min_ms`–`max_ms` | range of passed durations |
| `iqr_ms` | width of the middle half (inclusive quartiles); the typical spread |
| `delta_ms` | pooled median(candidate) − pooled median(baseline); negative is faster |
| `ci_ms` | 95% confidence interval of `delta_ms` from the bootstrap |

### Stratified bootstrap

- 10000 iterations, fixed seed 1234, so a rerun of `analyze.py` on the same data gives the same CI.
- Each iteration resamples executions with replacement **inside each environment**, separately for baseline and candidate, pools the environments, and takes the difference of the pooled medians. The 2.5th and 97.5th percentiles of those differences are the CI.
- Only environments where both baseline and candidate have passed executions take part.
- Stratifying keeps a fast environment from posing as a fast variant: each environment contributes the same mix in every resample.

### Time verdicts

| Verdict | Rule | What you may say |
|---|---|---|
| `faster` | the whole CI is below 0 | "faster by about \|Δ\| s (95% CI a…b)" |
| `slower` | the whole CI is above 0 | "slower by about Δ s (95% CI a…b)" |
| `no measurable difference` | the CI contains 0 | "no difference was measured at this N"; not "same speed", not "slightly faster" |
| `insufficient data` | fewer than 2 passed executions in a variant, or no shared environment | "not enough passed runs to judge time" |

Identical durations give a CI of `[0, 0]` and `no measurable difference`.

### Per environment

`per_environment` holds N, passed, failed, median and Δ median for each environment. When the sign of Δ differs between environments for some variant, the test is listed under `environment_disagreement` and the block says so: the speed-up may depend on the environment.

`selection_wall_ms` in `report.json` is the median, per variant, of one run's wall time (first test start to last test stop). It needs test timestamps (Allure); JUnit gives none, so it is `null`. It is a secondary line, not a verdict.

## Stability

| Field | Meaning |
|---|---|
| `failed` / `n` | K failures out of N executions |
| `fail_rate_ci` | Wilson 95% interval (z = 1.96) for the failure rate K/N |
| `fail_rate_floor` | rule-of-three upper bound 3/N, only when K = 0 and N ≥ 3 |
| `fisher_p` | two-sided Fisher exact test of candidate K/N vs baseline K/N |

### Wilson interval

The plausible range of the true failure rate given K/N. It behaves at 0 and N where the textbook ± interval breaks. Examples: 0/30 → 0–11%; 3/30 → 3–26%; 0/5 → 0–43%. A wide interval is the honest answer to "how flaky is it", not a defect.

### Rule of three

With N runs and 0 failures, the failure rate is below about 3/N with 95% confidence. 0/30 means "below ≈10%", not "never fails". This is the block's `floor_line`.

### Fisher exact test and stability verdicts

| Verdict | Rule |
|---|---|
| `less flaky` / `more flaky` | `fisher_p` < 0.05, direction from the two failure rates |
| `no measurable difference` | `fisher_p` ≥ 0.05 |
| `insufficient data` | baseline or candidate has no executions |

Fisher is exact for small counts but needs a large gap to reach 0.05. Against a baseline with 0/30, a candidate needs about 6/30 failures (p ≈ 0.024) to be called `more flaky`; 5/30 gives p ≈ 0.052. Turned around: proving that a variant fixed a 10% flake takes more than 30 runs per variant. Say so instead of claiming "less flaky" from a gap the test does not support.

## Quick vs proof

| | quick | proof |
|---|---|---|
| N per variant | 3–5 | 30 by default |
| Purpose | the variant runs at all; rough direction | the evidence block |
| Labelling | "indicative, not proof" on the verdict, the findings heading and the not-proven list | none |
| Retries | `--retries unknown` unless `force_env` disables them | must be off, or user override with `--retries unknown` |

A quick-mode `faster` is a reason to run proof mode, not a result. Even in proof mode, a `faster` with a CI near 0 is a small effect; quote the CI, not just the verdict.

## What the numbers never prove

- Causation beyond the tested selection: other tests, other environments, production.
- Stability beyond the floor: 0/30 is "below ≈10%", nothing tighter.
- Anything about runs that are `infra_error`, `no_results` or `invalid`; they are excluded and counted in the ledger.
- The impact estimate: it extrapolates measured per-test deltas and is *inferred*.
