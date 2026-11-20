---
name: variant-shootout
description: Use when someone claims a code change makes tests faster or less flaky than the current code and the claim needs numbers — proving or disproving "variant X is better than what we have" with repeated, interleaved test runs against a mandatory baseline, locally or in CI, ending in a paste-ready evidence block for a merge or pull request. Also use to settle a review dispute about speed or stability with measurements instead of opinions. Not for microbenchmarks of a function or CLI command (use hyperfine or JMH) and not for fixing a single flaky test.
---

# Variant Shootout

Turn "I think X is better" into evidence a sceptical reviewer accepts: the same tests, the same environment, N runs per variant, the current code as the baseline, interleaved runs, statistics computed by bundled scripts (not by the model), and an honest list of what the numbers do and do not prove. The output is `report.md` (paste-ready block) and `report.json`; the skill never posts either.

`<skill-dir>` is the directory holding this file. `<state>` is the session's `state_dir` (see [Profile](#profile)) as an **absolute** path; every `results_dir` is absolute too, because the ledger stores it and `collect.py` reads it from any working directory. What each number and verdict means is in [`references/statistics.md`](references/statistics.md); two example profiles are in [`references/profiles.md`](references/profiles.md).

## When to use

- A change is claimed to make some tests faster, less flaky, or both, and the claim should hold up on an MR/PR.
- Two or more alternative implementations compete and the user wants to know which is better than the current code.
- Not for: timing one function or shell command (hyperfine, JMH); fixing one flaky test; creating or posting the MR/PR (hand the block to the user, `/mr` or `pull-request-authoring`).

## Prerequisites

- `git` and `python3` (stdlib only) for every mode.
- `runner.local` in the profile for local runs; `runner.ci.*` for CI runs.
- Optional race video: `node`, `npm install` (or `npm ci`) once in `<skill-dir>/scripts/race`, a Chromium Playwright can launch (`CHROME_BIN` overrides), and `ffmpeg`. Missing any of them: skip the video and say so.

## Profile

The skill runs with neutral defaults. A caller (usually a private wrapper skill kept outside this repository) may pass a **profile**; every field it sets overrides the default. The public skill holds no organisation data: hosts, CI systems, test frameworks and environment names belong in the profile.

| Field | Meaning | Default |
|---|---|---|
| `baseline_ref` | baseline git ref | remote default branch |
| `tests` | test selection, an opaque string passed to the runner as `{tests}` | ask the user |
| `runner.local` | shell command template with `{worktree}`, `{results_dir}`, `{tests}` | none: local runs unavailable |
| `runner.local_clean` | command run in `{worktree}` before every local attempt, the first included, that removes the runner's intermediate output (e.g. report directories) | none: warn that stale reports in the worktree may leak into `results_dir` |
| `runner.force_env` | variables exported into the environment of `runner.local`: retries off, notifications off, external reporting off | `{}`, and warn that no-retries cannot be guaranteed |
| `runner.expected_minutes` | time of one run (one pipeline), for the wall-time estimate and the CI timeout | none: measured from quick runs, else ask |
| `runner.ci.trigger` | command template that starts one CI run for `{ref}` (also `{tests}`, `{environment}`, `{seq}`); it must itself pass retries off and notifications/reporting off as pipeline variables or inputs | none: CI unavailable |
| `runner.ci.run_id` | how to extract `<run_id>` and `<run_url>` from the trigger's output (a JSON field, a regex, a follow-up command) | none: required with `trigger` |
| `runner.ci.status` | command template for `<run_id>` that prints exactly one of `running`, `success`, `failed`, `canceled`; the profile maps the CI's native states onto these | none: required with `trigger` |
| `runner.ci.fetch` | command template that downloads the result artifacts of `<run_id>` into `{results_dir}` | none: required with `trigger` |
| `runner.ci.cancel` | command template for `<run_id>` that cancels the pipeline, used when a run times out | none: a timed-out run pauses its environment until it stops |
| `runner.ci.find` | command template with `{ref}`, `{seq}`, `{environment}` that prints the run id of this seq's pipeline (found by its run tag or branch), or nothing | none: a `running` row without `run_id` pauses its environment |
| `runner.ci.poll_seconds` | interval between `status` calls | `60` |
| `runner.ci.timeout_minutes` | a run still `running` after this is given up | 3 × the expected run time |
| `results.format` | `junit`, `allure` or `both`; `collect.py` finds `TEST-*.xml` and `*-result.json` anywhere under `results_dir` | `junit` |
| `results_label` | Allure label or link kept per test as an external id (`collect.py --label`) | none |
| `environments` | environments a proof run may spread over (balanced design) | one environment |
| `max_parallel` | runs (pipelines) in flight against one environment | `1` |
| `variant_branch_pattern` | name of pushed variant branches for CI | `shootout/<slug>` |
| `impact` | instructions or a script for the impact estimate | none: section omitted |
| `language` | language of the report | language of the conversation |
| `report_template` | MR/PR template section names the block will be pasted into | generic block |
| `upload` | how to attach the video to the MR/PR | none: give the local path |
| `state_dir` | ledger and artifacts | `${XDG_STATE_HOME:-~/.local/state}/variant-shootout/<repo>/<session>` |

## Honesty rules

These are the point of the skill. Breaking one makes the report worthless even if it "works".

- **Baseline is mandatory.** Every comparison includes `baseline_ref` as the first variant. No baseline, no report.
- **Retries off for proof.** Proof mode refuses to start unless retries are off where the runs happen: for local runs, `runner.force_env` turns them off; for CI runs, the rendered `runner.ci.trigger` itself passes retries off (shell variables never reach a pipeline, so `force_env` alone proves nothing there). If the user explicitly overrides, run anyway with `analyze.py --retries unknown`, so the block states that retries may have hidden failures. Never pass `--retries off` unless retries really are off. A retried-then-passed execution counts as failed.
- **Confirm outward steps by batch.** Before any `git push` or CI trigger, show the batch: each push (variant, SHA, branch) and the triggers (variant, environment, count, branch, variables). One explicit yes covers exactly that list. Anything outside it needs a new yes: re-runs, extra runs, changed variables, another branch. Notifications, test-management runs and report uploads must stay off; the trigger and `force_env` carry those switches.
- **Stop on infrastructure noise.** After every finished run, check `ledger.py <state>/ledger.jsonl status`. When `infra_ratio` is above `0.10`, stop the session, report the counts and the failing runs, and ask how to proceed.
- **Never post the block.** Show it and hand it to the user, `/mr` or `pull-request-authoring`. The skill does not comment, edit descriptions, or upload without the user's yes.
- **Label every claim** per `benchmark-checklist`: *measured* (a number from `report.json`), *inferred* (reasoning on top of measurements, e.g. why it is faster, the impact estimate), *guess* (anything else). Never round a `no measurable difference` into "slightly faster", and never say "not flaky" from a quick run.
- **Quick mode is indicative, not proof.** The analyzer labels it; keep the label when quoting.
- **Small proof runs are flagged.** Proof mode with N < 10 per variant: warn before starting, and the report states it (see [Hand-off](#6-hand-off)).
- **No contention.** Variants never run in parallel against one shared environment beyond `max_parallel`; that measures interference, not code.

## Flow

### 0. Frame

1. Restate the claim as a testable sentence: "variant `A` is faster than `baseline` on tests `T` without being flakier".
2. Fix the variants: a short name (letters, digits, `-`) and a git ref each; the baseline is first. Resolve each ref to a SHA (`git rev-parse <ref>^{commit}`); the variant **is** that pinned SHA. The names must be identical in `schedule.py --variants`, `ledger.py --shas` and `analyze.py --baseline` (the first name).
3. Pick the mode:
   - **quick**: local, N = 3–5 per variant; checks that each variant works and shows a rough delta.
   - **proof**: N = 30 per variant by default, local or CI; needs retries off (see Honesty rules). N < 10 gets a warning.
4. Check N against the environments: `runs per variant` must be divisible by the number of environments (balanced design). `schedule.py` refuses otherwise; pick the next multiple.
5. Estimate the time per run, in this order: the median of `finished_at − started_at` over `done` rows of an earlier quick run of the same tests, if one exists; else `runner.expected_minutes`; else ask the user. Say which source you used.
6. Show the plan: variants with SHAs, tests, mode, N, environments, the retries-off switch (in `force_env` or in the trigger), and the expected wall time `= runs per variant × variants × time per run ÷ environments` (÷ `max_parallel` when above 1). Quick mode shows the estimate too. Get an explicit yes before anything runs.

### 1. Prepare

1. Create `<state>` (absolute) and one git worktree per variant at its SHA: `git worktree add --detach <state>/worktrees/<variant> <sha>`.
2. Build the interleaved schedule and plan it in the ledger:

```
python3 <skill-dir>/scripts/schedule.py --variants baseline,a,b --environments env1,env2 --runs 30 > <state>/schedule.json
python3 <skill-dir>/scripts/ledger.py <state>/ledger.jsonl plan --schedule <state>/schedule.json --shas baseline=<sha>,a=<sha>,b=<sha>
```

   `--variants`: comma list, the first is the baseline. `--runs`: runs per variant. Each item has `seq`, `variant`, `environment`; the `seq` order is the trigger order. Planning is idempotent: already planned `seq`s are kept. Re-planning a `seq` with a different variant, environment or SHA is refused with `error: seq N is already planned as ...` (exit 2): start a new `<state>` instead. Local quick runs use one environment, e.g. `local`.
3. CI mode only: show the batch (see Honesty rules) with the branch names from `variant_branch_pattern`, get a yes, then push exactly each pinned SHA (`git push origin <sha>:refs/heads/<branch>`). A refused push stops the session.

### 2. Run

Walk the ledger in `seq` order. Environments run in parallel; inside one environment at most `max_parallel` runs are in flight, and the next run starts only when a slot frees (with `1`, wait for the pipeline to finish). For each run:

1. Reserve the attempt directory before any runner starts: `ledger.py <state>/ledger.jsonl next-attempt --seq N` creates `<state>/runs/<N>/attempt-<k>`, records it as `results_dir` on the row and prints its absolute path. `<k>` is one above the highest attempt ever recorded for that seq in the ledger history or present on disk, so a directory is never reused, even an empty one whose runner had not created anything yet. Then `ledger.py <state>/ledger.jsonl update --seq N --state running` (sets `started_at`), and only then start the runner, pointing it at the reserved directory.
2. Start it:
   - **local**: first run `runner.local_clean` in `{worktree}` (when set), then render `runner.local` with `{worktree}`, `{results_dir}`, `{tests}` and run it with every `force_env` variable exported into its environment;
   - **CI**: render `runner.ci.trigger` with `{ref}` = the variant branch, `{environment}`, `{tests}` and `{seq}` (within the confirmed batch), run it, extract `<run_id>` and `<run_url>` as `runner.ci.run_id` says, and record both at once: `update --seq N --ci-url <run_url> --run-id <run_id>`. Then call `runner.ci.status` every `poll_seconds` (default 60) until it prints `success`, `failed` or `canceled`, or until `timeout_minutes` (default 3 × the expected run time) passes. When it ended `success` or `failed`, run `runner.ci.fetch` into `{results_dir}`.
   - **CI timeout**: a timed-out pipeline still holds its slot in the environment. With `runner.ci.cancel`, run it for `<run_id>`, then keep polling `status` until it prints `canceled`, `failed` or `success`; only then record `infra_error` and free the slot. Without `runner.ci.cancel`, record nothing yet: pause that environment (start nothing new there) and keep polling until the status leaves `running`, then record `infra_error`. If cancel or polling never reaches a terminal state, the pipeline is not confirmed stopped: handle the row as an unconfirmed previous attempt (see Resume).
3. Record the outcome (sets `finished_at`). "Results" means at least one `TEST-*.xml` or `*-result.json` anywhere under `results_dir`.

| What happened | State |
|---|---|
| local: results present (whatever the runner's exit code) | `done` |
| local: no results | `infra_error` |
| CI: `success` or `failed`, results fetched | `done` |
| CI: `success` or `failed`, artifacts missing or expired | `no_results` (pending; offered for re-run) |
| CI: `canceled`, timed out, or the pipeline died before tests ran (failed early, no test results at all) | `infra_error` |

   With `done`, also pass `--observed-sha <sha the run reports>` when the runner or CI reports one; a mismatch with the pin turns the row `invalid` automatically (not counted, offered for re-run). `infra_error` runs are kept out of the flake rate.
4. Check `status`; stop above `infra_ratio` 0.10.

**Resume** after a crash or compaction: `python3 <skill-dir>/scripts/ledger.py <state>/ledger.jsonl pending` prints the rows still to run (`planned`, `running`, `no_results`) as JSON lines, in `seq` order. A `running` row with a `run_id` is polled with `runner.ci.status` for that `run_id`, not re-triggered. A CI `running` row without `run_id` may still have a live pipeline (the session died between trigger and record): run `runner.ci.find` first; when it prints an id, record it with `update --seq N --run-id <id>` and treat the row as above, including the timeout rule. When it prints nothing or the profile has no `find`, the previous attempt is unconfirmed (an orphan pipeline may be running). A local runner process started by a crashed session may survive it and keep writing into the shared per-variant worktree, so a local `running` row is unconfirmed too, until you have checked that no process of the runner command is left (or the user confirms it).

Before re-running any row, reset it with `update --seq N --state planned`: the reset clears `ci_url`, `run_id`, `results_dir`, `observed_sha`, `started_at` and `finished_at`, so the re-run never polls the old pipeline and stale results cannot mix in. The re-run reserves a new attempt with `next-attempt`; never reuse or delete a previous attempt's directory, because a surviving old process may still write into it, and `collect.py` reads only the `results_dir` on the current ledger row, so it cannot contaminate the new attempt.

If the previous CI attempt is unconfirmed (no run id found, or cancel/polling did not reach a terminal state), ask the user before re-using the environment: either confirm that the prior run has stopped (checked in the CI UI), or explicitly accept the contention risk. A local re-run has no accept-risk path: the previous runner must be confirmed stopped (no process of the runner command left, checked by you or confirmed by the user) before `runner.local_clean` runs and the row is re-run; when it cannot be confirmed, do not re-run locally on that worktree. Waiting `runner.ci.timeout_minutes` is only a fallback pause and does not prove that the pipeline has stopped. If the user accepts the risk, record `update --seq N --overlap-risk yes` after the reset; the report's "what is not proven" then says that run seq N may have overlapped an orphaned run. Re-runs of `no_results` or `invalid` rows are outside the confirmed batch and need a new yes.

### 3. Collect

```
python3 <skill-dir>/scripts/collect.py --ledger <state>/ledger.jsonl --format junit|allure|both --out <state>/runs.jsonl [--label <results_label>]
```

Searches each `done` run's `results_dir` recursively for `TEST-*.xml` (JUnit) and `*-result.json` (Allure), so multi-module layouts work as fetched. Writes one line per test execution with variant, environment, status, retried flag, duration, failure message, and steps with timestamps when Allure has them. Test identity is `classname#name` (Allure: `testClass#testMethod`, else `fullName`, plus parameters); with `both`, an Allure `a.b.C.m` matches a JUnit `a.b.C#m` and Allure wins. Only retry markers make a retry (JUnit `flaky*`/`rerun*` elements, Allure results with distinct `uuid`s sharing a `historyId`; copies with the same `uuid` are one attempt, and results without `historyId` are never grouped); byte-identical JUnit files in one run are read once, and any other duplicate `test_id` in one run keeps the latest result with `warning: duplicate test_id <id> in seq <n>; kept one` on stderr: mention such warnings in the hand-off. It prints the number of executions; zero means the results are not where the runner put them or not named `TEST-*.xml`. A parse error ends in a traceback and a non-zero exit: report the file it names.

### 4. Analyze

```
python3 <skill-dir>/scripts/analyze.py --runs <state>/runs.jsonl --ledger <state>/ledger.jsonl --baseline <first variant name> --mode quick|proof --retries off|unknown --lang en|ru --out <state>/report
```

`--lang`: the profile `language` or the conversation language mapped to `en` or `ru`; any other language becomes `en`. `--retries` defaults to `unknown`. Writes `<state>/report/report.json` and `<state>/report/report.md`. Per test and variant: median, mean, min–max, IQR, Δ median vs baseline (environment-weighted median difference) with a stratified bootstrap 95% CI, K/N failures with a Wilson interval, Fisher exact test vs baseline, the rule-of-three floor, a per-environment breakdown (a table in `report.md` when there is more than one environment), the top 3 failure messages per variant and test, the selection wall time per variant as a secondary line, tests missing from some variants, runs excluded per variant (`infra_error`, `invalid`, `no_results`, from the ledger), the number of comparisons tested at α = 0.05, and CI links (excluded runs marked with their state). Read [`references/statistics.md`](references/statistics.md) before explaining any number.

### 5. Extras (optional)

- **Race video**: one representative run per variant replayed side by side on a shared time axis from real test timestamps.

```
node <skill-dir>/scripts/race/race.mjs --check
node <skill-dir>/scripts/race/race.mjs --runs <state>/runs.jsonl --report <state>/report/report.json --out <state>/report/race.mp4 [--speed 4]
```

  `--check` exits 0 when a browser launches. Exit 1 means a missing tool (Playwright, browser, `ffmpeg`): skip the video and say why. Exit 64 is a usage error: fix the call. Runs without test timestamps show "no timing data". Attach via `upload` only after the user's yes; otherwise give the local path.
- **Impact estimate**: only when the profile has `impact`. Run its instructions or script against `report.json` (it may use per-test `external_id`). State plainly which part is measured (per-test deltas) and which is extrapolated (how many suites use the changed code, serial vs parallel execution); the extrapolation is *inferred*, never *measured*.

### 6. Hand-off

1. In proof mode with N < 10 per variant, add one item to the "What is not proven" list of `report.md`: "Only N runs per variant; proof mode expects at least 10, the default is 30." Change nothing else in the block.
2. Show `report.md`. If `report_template` names MR/PR sections, say which block section goes where; do not reword verdicts.
3. Under it, list in plain words what is **not** proven: every `no measurable difference` and `insufficient data` line, quick-mode labelling, unknown retries, environment disagreement, missing tests, excluded runs, and how many "proven" lines could be chance across the comparisons tested.
4. Label any extra sentence you add as measured / inferred / guess.
5. Hand the block to the user, `/mr` or `pull-request-authoring`. Clean up worktrees (`git worktree remove`) and, after asking, the pushed variant branches.

## Exit codes

| Script | Exit | Meaning | Action |
|---|---|---|---|
| `schedule.py` | 0 | schedule JSON on stdout | plan it |
| | 2 | `error: ...`: no variants or environments, `--runs` < 1, or not divisible by the number of environments; or bad arguments | fix N or the lists |
| `ledger.py` | 0 | done; `status` prints `counts` per state and `infra_ratio`; `pending` prints JSON lines | continue |
| | 2 | `error: ...`: missing SHA for a variant, a re-plan that conflicts with a planned `seq`, unknown `seq`, field or state, corrupt ledger line; or bad arguments | fix the call; never hand-edit past rows |
| `collect.py` | 0 | prints the execution count; `warning: duplicate test_id ...` lines on stderr | check it is not 0; report the warnings |
| | non-zero | traceback on an unreadable result file; 2 on bad arguments | report the file |
| `analyze.py` | 0 | `report.json` and `report.md` written | hand-off |
| | 1 | `error: ...`: baseline has no executions, unreadable input | check the baseline name and collection |
| | 2 | bad arguments | fix the call |
| `race.mjs` | 0 / 1 / 64 | ok / missing tool or browser / usage | skip the video on 1 |
| `encode.sh` | 0 / 1 / 64 | ok / no `ffmpeg` / usage or missing input | called by `race.mjs` |

## Ledger states

`planned` → `running` → `done` | `infra_error` | `no_results` | `invalid`. `update --state planned` resets a row for a re-run and clears its run fields. Finished runs for `infra_ratio` are `done` and `infra_error`; pending runs are `planned`, `running` and `no_results`.
