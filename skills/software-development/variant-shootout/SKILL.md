---
name: variant-shootout
description: Use when someone claims a code change makes tests faster or less flaky than the current code and the claim needs numbers — proving or disproving "variant X is better than what we have" with repeated, interleaved test runs against a mandatory baseline, locally or in CI, ending in a paste-ready evidence block for a merge or pull request. Also use to settle a review dispute about speed or stability with measurements instead of opinions. Not for microbenchmarks of a function or CLI command (use hyperfine or JMH) and not for fixing a single flaky test.
---

# Variant Shootout

Turn "I think X is better" into evidence a sceptical reviewer accepts: the same tests, the same environment, N runs per variant, the current code as the baseline, interleaved runs, statistics computed by bundled scripts (not by the model), and an honest list of what the numbers do and do not prove. The output is `report.md` (paste-ready block) and `report.json`; the skill never posts either.

`<skill-dir>` is the directory holding this file. `<state>` is the session's `state_dir` (see [Profile](#profile)). What each number and verdict means is in [`references/statistics.md`](references/statistics.md); two example profiles are in [`references/profiles.md`](references/profiles.md).

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
| `runner.ci.trigger` | command template that starts one CI run for `{ref}` with variables and prints a run id or URL | none: CI unavailable |
| `runner.ci.status` / `runner.ci.fetch` | templates that poll a run and download its result artifacts into `{results_dir}` | none |
| `runner.force_env` | variables always set: retries off, notifications off, external reporting off | `{}`, and warn that no-retries cannot be guaranteed |
| `results.format` | `junit`, `allure` or `both`, plus path globs inside a run's results | `junit`, `**/TEST-*.xml` |
| `environments` | environments a proof run may spread over (balanced design) | one environment |
| `max_parallel` | runs (pipelines) in flight against one environment | `1` |
| `variant_branch_pattern` | name of pushed variant branches for CI | `shootout/<slug>` |
| `impact` | instructions or a script for the impact estimate | none: section omitted |
| `language` | language of the report (`--lang en` or `ru`) | language of the conversation, else `en` |
| `report_template` | MR/PR template section names the block will be pasted into | generic block |
| `results_label` | Allure label or link kept per test as an external id (`collect.py --label`) | none |
| `upload` | how to attach the video to the MR/PR | none: give the local path |
| `state_dir` | ledger and artifacts | `${XDG_STATE_HOME:-~/.local/state}/variant-shootout/<repo>/<session>` |

## Honesty rules

These are the point of the skill. Breaking one makes the report worthless even if it "works".

- **Baseline is mandatory.** Every comparison includes `baseline_ref` as the first variant. No baseline, no report.
- **Retries off for proof.** Proof mode refuses to start unless `runner.force_env` turns retries off. If the user explicitly overrides, run anyway with `analyze.py --retries unknown`, so the block states that retries may have hidden failures. Never pass `--retries off` unless `force_env` really disables them. A retried-then-passed execution counts as failed.
- **Confirm every outward step, each time.** Ask before each `git push` of a variant branch and before each CI trigger; a yes covers only the push or trigger shown, never later ones. No notifications, test-management runs or report uploads fired N×V times: that is what `force_env` is for.
- **Stop on infrastructure noise.** After every finished run, check `ledger.py <state>/ledger.jsonl status`. When `infra_ratio` is above `0.10`, stop the session, report the counts and the failing runs, and ask how to proceed.
- **Never post the block.** Show it and hand it to the user, `/mr` or `pull-request-authoring`. The skill does not comment, edit descriptions, or upload without the user's yes.
- **Label every claim** per `benchmark-checklist`: *measured* (a number from `report.json`), *inferred* (reasoning on top of measurements, e.g. why it is faster, the impact estimate), *guess* (anything else). Never round a `no measurable difference` into "slightly faster", and never say "not flaky" from a quick run.
- **Quick mode is indicative, not proof.** The analyzer labels it; keep the label when quoting.
- **No contention.** Variants never run in parallel against one shared environment beyond `max_parallel`; that measures interference, not code.

## Flow

### 0. Frame

1. Restate the claim as a testable sentence: "variant `A` is faster than `baseline` on tests `T` without being flakier".
2. Fix the variants: a short name and a git ref each; the baseline is first. Resolve each ref to a SHA (`git rev-parse <ref>^{commit}`); the variant **is** that pinned SHA.
3. Pick the mode:
   - **quick**: local, N = 3–5 per variant; checks that each variant works and shows a rough delta.
   - **proof**: N = 30 per variant by default, local or CI; needs retries off (see Honesty rules).
4. Check N against the environments: `runs per variant` must be divisible by the number of environments (balanced design). `schedule.py` refuses otherwise; pick the next multiple.
5. Show the plan: variants with SHAs, tests, mode, N, environments, `force_env`, and the expected wall time `= runs per variant × variants × time per run (pipeline) ÷ environments` (÷ `max_parallel` when above 1). Get an explicit yes before anything runs.

### 1. Prepare

1. Create `<state>` and one git worktree per variant at its SHA: `git worktree add --detach <state>/worktrees/<variant> <sha>`.
2. Build the interleaved schedule and plan it in the ledger:

```
python3 <skill-dir>/scripts/schedule.py --variants baseline,a,b --environments env1,env2 --runs 30 > <state>/schedule.json
python3 <skill-dir>/scripts/ledger.py <state>/ledger.jsonl plan --schedule <state>/schedule.json --shas baseline=<sha>,a=<sha>,b=<sha>
```

   `--variants`: comma list, the first is the baseline. `--runs`: runs per variant. Each item has `seq`, `variant`, `environment`; the `seq` order is the trigger order. Planning is idempotent: already planned `seq`s are kept.
3. CI mode only: for each variant, show the branch name from `variant_branch_pattern` and the SHA, get a yes, then push exactly that SHA (`git push origin <sha>:refs/heads/<branch>`). A refused push stops the session.

### 2. Run

Walk the ledger in `seq` order. Environments run in parallel; inside one environment at most `max_parallel` runs are in flight, and the next run starts only when a slot frees (with `1`, wait for the pipeline to finish). For each run:

1. `ledger.py <state>/ledger.jsonl update --seq N --state running --results-dir <state>/runs/<N>` (sets `started_at`).
2. Start it with `force_env` applied:
   - local: render `runner.local` with `{worktree}`, `{results_dir}`, `{tests}` and run it;
   - CI: render `runner.ci.trigger` with `{ref}` = the variant branch, show it, run it after the user's yes, record the URL (`--ci-url`), poll with `runner.ci.status`, then `runner.ci.fetch` into `{results_dir}`.
3. Make the result files flat in `results_dir`: `collect.py` reads `*.xml` (JUnit) and `*-result.json` (Allure) directly inside it, not in subdirectories. Copy files matching the profile globs there if the runner nests them.
4. Record the outcome (sets `finished_at`):
   - result files present: `--state done`, plus `--observed-sha <sha the run reports>` when the runner or CI reports one; a mismatch with the pin turns the row `invalid` automatically (not counted, offered for re-run);
   - the run ended without results: `--state infra_error` (kept out of the flake rate);
   - CI artifacts expired or missing: `--state no_results` (stays pending, offered for re-run).
5. Check `status`; stop above `infra_ratio` 0.10.

**Resume** after a crash or compaction: read `<state>/ledger.jsonl` (append-only; the last row per `seq` is its current state) and run only the `planned`, `running` and `no_results` rows. A `running` row whose CI URL is recorded is polled, not re-triggered. To re-run an `invalid` row after the user agrees: `update --seq N --state planned --observed-sha <pinned sha>`.

### 3. Collect

```
python3 <skill-dir>/scripts/collect.py --ledger <state>/ledger.jsonl --format junit|allure|both --out <state>/runs.jsonl [--label <results_label>]
```

One line per test execution of every `done` run, with variant, environment, status, retried flag, duration, failure message, and steps with timestamps when Allure has them. Test identity is `classname#name` (Allure: `testClass#testMethod`, else `fullName`, plus parameters). It prints the number of executions; zero means the result paths are wrong. A parse error ends in a traceback and a non-zero exit: report the file it names.

### 4. Analyze

```
python3 <skill-dir>/scripts/analyze.py --runs <state>/runs.jsonl --ledger <state>/ledger.jsonl --baseline baseline --mode quick|proof --retries off|unknown --lang en|ru --out <state>/report
```

Writes `<state>/report/report.json` and `<state>/report/report.md`. `--retries` defaults to `unknown`; `--lang` to `en`. Per test and variant: median, mean, min–max, IQR, Δ median vs baseline with a stratified bootstrap 95% CI, K/N failures with a Wilson interval, Fisher exact test vs baseline, the rule-of-three floor, a per-environment breakdown, tests missing from some variants, and CI links. Read [`references/statistics.md`](references/statistics.md) before explaining any number.

### 5. Extras (optional)

- **Race video**: one representative run per variant replayed side by side on a shared time axis from real test timestamps.

```
node <skill-dir>/scripts/race/race.mjs --check
node <skill-dir>/scripts/race/race.mjs --runs <state>/runs.jsonl --report <state>/report/report.json --out <state>/report/race.mp4 [--speed 4]
```

  `--check` exits 0 when a browser launches. Exit 1 means a missing tool (Playwright, browser, `ffmpeg`): skip the video and say why. Exit 64 is a usage error: fix the call. Runs without test timestamps show "no timing data". Attach via `upload` only after the user's yes; otherwise give the local path.
- **Impact estimate**: only when the profile has `impact`. Run its instructions or script against `report.json` (it may use per-test `external_id`). State plainly which part is measured (per-test deltas) and which is extrapolated (how many suites use the changed code, serial vs parallel execution); the extrapolation is *inferred*, never *measured*.

### 6. Hand-off

1. Show `report.md` as is. If `report_template` names MR/PR sections, say which block section goes where; do not reword verdicts.
2. Under it, list in plain words what is **not** proven: every `no measurable difference` and `insufficient data` line, quick-mode labelling, unknown retries, environment disagreement, missing tests.
3. Label any extra sentence you add as measured / inferred / guess.
4. Hand the block to the user, `/mr` or `pull-request-authoring`. Clean up worktrees (`git worktree remove`) and, after asking, the pushed variant branches.

## Exit codes

| Script | Exit | Meaning | Action |
|---|---|---|---|
| `schedule.py` | 0 | schedule JSON on stdout | plan it |
| | 2 | `error: ...`: no variants or environments, `--runs` < 1, or not divisible by the number of environments; or bad arguments | fix N or the lists |
| `ledger.py` | 0 | done; `status` prints `counts` per state and `infra_ratio` | continue |
| | 2 | `error: ...`: missing SHA for a variant, unknown `seq`, field or state, corrupt ledger line; or bad arguments | fix the call; never hand-edit past rows |
| `collect.py` | 0 | prints the execution count | check it is not 0 |
| | non-zero | traceback on an unreadable result file; 2 on bad arguments | report the file |
| `analyze.py` | 0 | `report.json` and `report.md` written | hand-off |
| | 1 | `error: ...`: baseline has no executions, unreadable input | check the baseline name and collection |
| | 2 | bad arguments | fix the call |
| `race.mjs` | 0 / 1 / 64 | ok / missing tool or browser / usage | skip the video on 1 |
| `encode.sh` | 0 / 1 / 64 | ok / no `ffmpeg` / usage or missing input | called by `race.mjs` |

## Ledger states

`planned` → `running` → `done` | `infra_error` | `no_results` | `invalid`. Finished runs for `infra_ratio` are `done` and `infra_error`; pending runs are `planned`, `running` and `no_results`.
