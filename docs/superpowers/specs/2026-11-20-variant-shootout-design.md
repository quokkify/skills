# variant-shootout — design (public part)

Status: approved.

## Intent and why

The user regularly argues that an alternative implementation is better than the current one
(faster, less flaky) and wants to close such disputes with numbers rather than opinions.
The skill turns "I think X is better" into a paste-ready evidence block for a merge/pull request:
the same tests, the same environment, N runs per variant, the current code as the baseline,
and an honest statement of what the numbers do and do not prove.

Audience of the output: the colleague or reviewer on the MR/PR, who may be sceptical.
The output must survive the obvious objections: "too few runs", "different conditions",
"retries hid the failures", "you only ran it locally".

## Goals

- Compare two or more code variants (git refs) of the same tests against a **mandatory baseline**
  (default: the repository's default branch).
- Two metrics:
  - **Time**: per-run duration of the selected tests; optionally per-step durations when step data exists.
  - **Stability**: failures out of N runs; a retried-then-passed run counts as a failure; failures grouped by reason.
- Two modes:
  - **quick**: local, N = 3–5 per variant. Purpose: the variant works at all, rough delta. The report labels it "indicative, not proof".
  - **proof**: N ≈ 30 per variant (default 30), locally or in CI. Purpose: the evidence block.
- Runs are **interleaved** (baseline, A, B, baseline, A, B, …) so drift of the shared environment hits every variant equally.
- Statistics, computed by a bundled script, not by the model:
  - time: median, mean, min–max, IQR; Δ median vs baseline with a bootstrap 95% CI (fixed seed);
    verdict `faster` / `slower` / `no measurable difference` from whether the CI excludes zero;
  - stability: K/N with a Wilson 95% interval per variant; Fisher exact test vs baseline;
    the explicit floor "with N runs and 0 failures the failure rate is below ≈3/N" (rule of three).
- Report:
  - `report.md`: a paste-ready block with the method, the table, the verdict, what is proven, what is not, and links to runs;
  - `report.json`: machine-readable, same data.
  - Claims are labelled per `benchmark-checklist` (measured / inferred / guess).
- Optional **race video**: the runs replayed on a shared time axis from their real timestamps, rendered to mp4.
- Optional **impact estimate**: an adapter-supplied hook that turns the per-test delta into "what this saves for a whole suite run" (which tests use the changed code, serial vs parallel execution).
- Resumable: a proof run can take hours; a run ledger lets the skill continue after a crash or compaction without re-running finished runs.

## Non-goals

- Fixing flaky tests (that is `flaky-loop`).
- Microbenchmarks of functions or CLI commands (use JMH, hyperfine, etc.).
- Creating or posting the MR/PR itself. The skill hands the block to `/mr`, `pull-request-authoring`, or the user.
- Statistical methods beyond the above: no power analysis UI, no Bayesian models.

## Anti-goals (failure even if it "works")

- A report that overclaims: "30% faster" when the CI crosses zero, or "not flaky" from 5 runs.
- Measuring with retries on, so failures are hidden.
- A comparison without the baseline.
- Spamming people or systems: notifications, test-management runs, report servers fired N×V times.
- Variants run in parallel against one shared environment that they contend for, e.g. rate limits, the same accounts, the same data. That measures interference, not the code.

## Constraints

- Lives in the public skills hub. All organisation specifics come from a **profile** passed by a private wrapper, as `mr-glab-review` does.
- No hardcoded hosts, CI systems, or test frameworks in the public skill.
- Bundled scripts: Python 3 stdlib only for collect/analyze; Node + Playwright + ffmpeg only for the optional video. If they are missing, the video is skipped with a note.
- Outward-facing steps need explicit user confirmation each time: pushing variant branches, triggering CI.

## Approaches considered

1. **Full-cycle public skill + private profile** (chosen). The public skill owns the flow: variants, interleaved runs through a runner adapter, collection, statistics, report, optional video and impact. The private wrapper only supplies the profile.
   Trade-off: the most work, but the hard part (N runs with correct switches, resume) is written once.
2. **Public analysis-only skill.** Inputs are result directories, the output is the report. Rejected: every wrapper would re-implement the N-run orchestration, which is where mistakes happen (retries on, notifications on, no interleaving).
3. **Generalise `flake-runner`.** Rejected: it is Maven- and local-only, single-variant, and stays as is.

User picked 1.

## Profile (contract between public skill and wrapper)

Every field has a neutral default; the profile overrides it.

| Field | Meaning | Default |
|---|---|---|
| `baseline_ref` | baseline git ref | remote default branch |
| `tests` | how to select the tests under comparison (opaque string passed to the runner) | asked from the user |
| `runner.local` | shell command template; placeholders `{worktree}`, `{results_dir}`, `{tests}` | none (quick mode unavailable) |
| `runner.ci.trigger` | command template that starts one CI run for `{ref}` with variables, printing a run id/URL | none (CI unavailable) |
| `runner.ci.status` / `runner.ci.fetch` | templates to poll a run and download its result artifacts into `{results_dir}` | none |
| `runner.force_env` | variables always set: retries off, notifications off, external reporting off | `{}` and the skill warns that it cannot guarantee no retries |
| `results.format` | `junit`, `allure`, or both; plus path globs inside a run's results dir | `junit`, `**/TEST-*.xml` |
| `environments` | environments a proof run may spread over (balanced design) | one environment |
| `max_parallel` | concurrent runs allowed against one environment | `1` |
| `variant_branch_pattern` | how to name pushed variant branches for CI | `shootout/<slug>` |
| `impact` | instructions or a script path for the impact estimate | none (section omitted) |
| `language` | language of the report | language of the conversation |
| `report_template` | where the block will be pasted (MR template section names) | generic block |
| `upload` | how to attach the video to the MR/PR | none (local path given to user) |
| `state_dir` | ledger and artifacts location | `${XDG_STATE_HOME:-~/.local/state}/variant-shootout/<repo>/<session>` |

## Flow

0. **Frame**: restate the claim being tested ("variant A is faster than baseline for tests T without being flakier"), variants, tests, mode, N. Show the run plan and its expected wall time. Get a yes.
1. **Prepare variants**: one git worktree per variant, at pinned SHAs, recorded in the ledger. For CI mode, push variant branches only after confirmation.
2. **Run**: interleaved schedule, `max_parallel` respected, `force_env` applied. Every run is written to the ledger: id, variant, SHA, start/end, status, results path, CI URL. Resume reads the ledger and runs only missing ones.
3. **Collect**: `scripts/collect.py` normalises JUnit/Allure into `runs.jsonl`: one line per test execution, with duration, status, retries, failure message, and optional steps with timestamps.
4. **Analyze**: `scripts/analyze.py` → `report.json` + `report.md`.
5. **Optional extras**: race video (`scripts/race/`), impact estimate from the profile hook.
6. **Hand-off**: show the block, list the claims that are not proven. The skill does not post anything itself.

## Units

- `SKILL.md`: the flow, profile contract, honesty rules, pointers.
- `scripts/collect.py`: parsers for JUnit XML and Allure results (`*-result.json`, including nested steps); tolerant of missing fields.
- `scripts/analyze.py`: statistics (bootstrap, Wilson, Fisher implemented in stdlib), verdict rules, renders `report.md` from a template.
- `scripts/ledger.py`: append, query and resume the run ledger (JSONL).
- `scripts/race/`: data-driven HTML template + Playwright recorder + ffmpeg encode. Reuse from `feature-demo`'s render pipeline where it fits; builder's call.
- `references/statistics.md`: what each number means and the verdict thresholds, for the model and the reader.
- `references/profiles.md`: two fictional example profiles (a GitHub Actions + pytest repo, a GitLab CI + Maven repo).
- `tests/`: fixtures of JUnit and Allure results; unit tests for analyze with known answers; smoke test for the race renderer, skipped without ffmpeg.

## Error handling

- A run that errors before producing results is recorded as `infra_error`, kept out of the flake rate, and listed separately. Too many of them (>10% of runs) stop the session.
- Missing `force_env` for retries: the report states that retries may hide failures.
- CI artifacts expired or missing: the run is marked `no_results`; it is offered for re-run.

## Decisions after the builder check (author's calls, open for correction)

- **Sample unit.** A sample is one execution of one test. Time and stability verdicts are computed per test across runs. Runs are independent, so the bootstrap resamples executions within each variant.
  - Wall time of the whole selection per run is reported as a secondary line.
  - A test failing in a run counts as one failure for that test.
- **Retries.**
  - Proof mode requires `force_env` to turn retries off. Without it, proof mode refuses unless the user explicitly overrides, and the report then carries the warning.
  - `collect.py` also detects retry signals where the format has them:
    - Surefire `flakyFailure` / `rerunFailure` elements;
    - several Allure results sharing one `historyId` within a run.
  - Any retry it detects marks the execution failed.
- **SHA pinning.**
  - A variant is a pinned SHA. The pushed CI branch points exactly at it.
  - Each run's reported SHA is checked against the pin. A mismatch makes the run `invalid`; it is not counted and is offered for re-run.
  - If a push is refused, the session stops.
- **Several environments (user's decision).**
  - Profile field `environments`: the list of environments a proof run may use. Default: one.
  - **Balanced design.** Every environment runs every variant the same number of times, interleaved. Environments run in parallel, `max_parallel` per environment. Example: 30 runs per variant across 3 environments are 10 + 10 + 10.
  - **Analysis is stratified by environment.**
    - The time delta is computed within each environment, then pooled with a stratified bootstrap that resamples inside each environment.
    - Flakes are pooled across environments; per-environment K/N is shown too.
    - The report shows a per-environment breakdown. When environments disagree on the direction of the delta, it flags this.
  - Wall time drops roughly by the number of environments.
- **CI scheduling.** `max_parallel` counts pipelines in flight against one environment. With `1`, the scheduler waits for a pipeline to finish before triggering the next one. Interleaving is the order of triggers.
- **Selector vs results.** `tests` is opaque and only passed to the runner. Analysis covers every test found in the results, grouped by test identity (class + method, or Allure `fullName`). The report flags tests that appear in some variants but not in others.
- **Video timestamps.** The video uses test-level start/stop times from Allure (JUnit as fallback), with each run aligned to its own first test start. It never uses CI job times, which include queueing and build.
- **External IDs.** If the profile names a label, for example an Allure TMS link, `collect.py` keeps it per test. Impact hooks use it.

## Left to the builder

Exact verdict wording, the report layout, file names inside `state_dir`, the CLI flags of the scripts, and the video styling.
