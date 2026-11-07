# renovate-adoption-review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a portable hub skill that turns a Renovate update (open PR or a batch of merged ones) into grounded, cited adoption changes in the consumer repository.

**Architecture:** A deterministic POSIX `sh` CLI (`renovate_adoption.sh`) fetches data through `gh` and pipes it into a jq module (`renovate_adoption.jq`) that parses Renovate PR bodies, classifies update types, applies triage and aggregates retro intervals. `SKILL.md` plus `references/` drive the model-side work (sources, grounding, edits, child PR, issue). Python `unittest` tests run the CLI against recorded fixtures through a stub `gh` on `PATH`.

**Tech Stack:** POSIX sh, jq ≥ 1.6, GitHub CLI `gh`, Python 3 `unittest` (hub convention), hub `scripts/validate.sh`.

**Spec:** `docs/superpowers/specs/2026-11-07-renovate-adoption-review-design.md`

## Global Constraints

- Skill directory: `skills/repository/renovate-adoption-review/`; frontmatter `name: renovate-adoption-review`, single-line `description` ≤ 1024 chars.
- Helper is POSIX `sh` (`#!/bin/sh`, no bashisms), depends only on `gh` and `jq`.
- Exit codes: 0 success, 2 usage error, 3 `gh`/network/missing-tool failure with a message on stderr; never print an empty result on failure.
- Allowlist file in the consumer: `.github/renovate-adoption.json`, shape `{"allow": ["<package>", ...]}`; absent file = empty list.
- Child branch prefix `adopt/`; marker `<!-- adoption-base: <sha> -->`; finding touching more than 10 files is proposed, not applied.
- Public repo: no machine paths, employer data, tokens; fixtures are sanitized copies of public quokkify PRs.
- Tests run via `python3 -m unittest discover -s tests -v`; full gate `./scripts/validate.sh --full`.

## Review Focus

- Grouped Renovate PR (several table rows, mixed types): verdict must be `candidate` if any row qualifies, with every row listed.
- Docker-style versions (`21-jdk-alpine` → `25-jdk-alpine`, `3.12-slim`): classify by leading numeric components, ignore the suffix.
- `0.x` versions: a minor bump `0.4 → 0.5` is a major (semver convention).
- PR body without the updates table (manual edits, lock-file maintenance): no crash; `skip` with reason.
- `retro --since` given a tag or SHA, not a date: resolved to that commit's date via `git log -1 --format=%cI`.

Each line has a test in the task that owns the code (Tasks 1 and 2).

---

## File Structure

| File | Responsibility |
|---|---|
| `skills/repository/renovate-adoption-review/scripts/renovate_adoption.sh` | CLI: arg parsing, `gh`/`git` calls, exit codes, invokes jq module |
| `skills/repository/renovate-adoption-review/scripts/renovate_adoption.jq` | Pure functions: parse body, classify, triage, aggregate, owned paths |
| `skills/repository/renovate-adoption-review/SKILL.md` | Trigger, modes, step order, grounding, guardrails, stop conditions |
| `skills/repository/renovate-adoption-review/references/ecosystems/*.md` | Per-ecosystem opportunity checklists |
| `skills/repository/renovate-adoption-review/references/templates.md` | Child PR, parent comment, retro issue, retro PR bodies |
| `skills/repository/renovate-adoption-review/references/stacked-pr.md` | Branch naming, drift, merge order, recovery commands |
| `tests/test_renovate_adoption.py` | CLI tests through stub `gh` |
| `tests/fixtures/renovate_adoption/*.json` | Recorded `gh` outputs |
| `docs/skill-catalog.md` | Catalog entry |

## Shared JSON shapes (produced by Tasks 1–3, consumed by `SKILL.md`)

```json
// update
{"package": "gradle/actions", "sourceUrl": "https://github.com/gradle/actions",
 "from": "v5.1.0", "to": "v6.4.1", "updateType": "major|minor|patch|digest|pin|lockFileMaintenance|unknown",
 "releaseNotesUrls": ["https://github.com/gradle/actions/releases/tag/v6.4.1"]}
// inspect / sweep item
{"pr": 38, "branch": "renovate/gradle-actions-6.x", "headSha": "<sha>",
 "updates": [<update>], "verdict": "candidate|skip", "reason": "<text>"}
// retro item
{"package": "...", "sourceUrl": "...", "from": "<earliest from>", "to": "<latest to>",
 "updateType": "<recomputed on interval>", "prs": [12, 19], "releaseNotesUrls": [...],
 "verdict": "candidate|skip", "reason": "<text>"}
```

---

### Task 1: `inspect` — parse, classify, triage

**Files:**
- Create: `skills/repository/renovate-adoption-review/scripts/renovate_adoption.sh`
- Create: `skills/repository/renovate-adoption-review/scripts/renovate_adoption.jq`
- Create: `tests/test_renovate_adoption.py`
- Create: `tests/fixtures/renovate_adoption/pr_view_major.json`, `pr_view_minor.json`, `pr_view_digest.json`, `pr_view_grouped.json`, `pr_view_docker.json`, `pr_view_zero_minor.json`, `pr_view_no_table.json`

**Interfaces:**
- Produces: CLI `renovate_adoption.sh inspect <pr> [--mode open|retro]` → one inspect item on stdout. jq defs `parse_updates` (body string → `[update]`), `classify(from; to)` → updateType string, `triage(mode; allow)` (update → `{verdict, reason}`).
- Stub contract (test helper `make_stub(tmp, fixtures, fail=False)`): writes executable `gh` on a temp `PATH` dir; it appends its argv to `$GH_STUB_LOG`, prints `$GH_STUB_DIR/pr_view.json` for `pr view`, `pr_list_open.json` / `pr_list_merged.json` for `pr list` (by `--state`), `api_tree.json` for `api`; exits 1 with stderr text when `GH_STUB_FAIL=1`.

- [ ] **Step 1: Record fixtures.** From public quokkify repos run `gh pr view <n> --json number,title,body,headRefName,headRefOid` for a major action bump, a minor, a digest, and a grouped PR; hand-edit copies for `docker` (`21-jdk-alpine` → `25-jdk-alpine`), `zero_minor` (`0.4.2` → `0.5.0`), `no_table` (body without the table). Strip nothing but job-log URLs.

- [ ] **Step 2: Write failing tests** in `RenovateAdoptionInspectTests`:

```python
def test_major_action_is_candidate(self):
    out = self.inspect("pr_view_major.json")
    self.assertEqual(out["verdict"], "candidate")
    self.assertEqual(out["updates"][0]["updateType"], "major")
    self.assertTrue(out["updates"][0]["sourceUrl"].startswith("https://github.com/"))  # redirect.github.com normalized
def test_digest_is_skipped(self):        # verdict "skip", reason contains "digest"
def test_minor_open_mode_skipped_retro_mode_candidate(self):
def test_allowlisted_minor_is_candidate(self):   # writes .github/renovate-adoption.json in temp repo cwd
def test_grouped_pr_any_major_makes_candidate(self):  # len(updates) == table rows
def test_docker_suffix_classified_by_numeric_prefix(self):  # "major"
def test_zero_major_minor_bump_is_major(self):
def test_body_without_table_is_skip_not_crash(self):  # exit 0, verdict "skip", reason "no updates table"
def test_gh_failure_exits_3_with_stderr(self):
def test_missing_pr_argument_exits_2(self):
```

- [ ] **Step 3: Run** `python3 -m unittest tests.test_renovate_adoption -v` → all FAIL (script missing).

- [ ] **Step 4: Implement the jq module.** `parse_updates`: take table rows between the header line starting `| Package |` and the first blank line; package = link text of column 1, `sourceUrl` = its href with host `redirect.github.com` → `github.com`; `from`/`to` = the two backticked values in column 2 split on `→`. `releaseNotesUrls` = unique `https://(redirect.)?github.com/<o>/<r>/(releases/tag|compare)/...` links anywhere in the body, normalized. Title containing `lock file maintenance` (case-insensitive) → single update of type `lockFileMaintenance`. `classify` algorithm:

```
strip leading "v"; if both match ^[0-9a-f]{7,40}$ → digest
take leading numeric components (split on [.-], stop at first non-numeric)
if from has fewer components and to starts with from's components → pin
no numeric prefix on either side → unknown
first differing index: 0 → major; 1 → (from[0]==0 ? major : minor); else patch
```

`triage`: package in allow → candidate ("allowlisted"); open mode: major → candidate, else skip ("<type> not reviewed in open mode"); retro mode: major|minor → candidate, else skip. A PR is candidate if any update is; reason joins candidate reasons. Empty updates → skip "no updates table".

- [ ] **Step 5: Implement CLI `inspect`.** Check `command -v gh jq` (exit 3 "requires gh and jq"); call `gh pr view "$pr" --json number,title,body,headRefName,headRefOid`; read allowlist from `$(git rev-parse --show-toplevel)/.github/renovate-adoption.json` if present; run `jq -L "$script_dir" 'include "renovate_adoption"; ...'`. Any `gh` non-zero → stderr `gh failed: <cmd>` and exit 3.

- [ ] **Step 6: Run tests** → all PASS. Also `sh -n` the script and, if available, `shellcheck -s sh`.

- [ ] **Step 7: Commit** `feat(renovate-adoption-review): add inspect helper with update classification`.

### Task 2: `sweep` and `retro`

**Files:**
- Modify: `skills/repository/renovate-adoption-review/scripts/renovate_adoption.sh`
- Modify: `skills/repository/renovate-adoption-review/scripts/renovate_adoption.jq`
- Modify: `tests/test_renovate_adoption.py`
- Create: `tests/fixtures/renovate_adoption/pr_list_open.json`, `pr_list_merged.json`

**Interfaces:**
- Consumes: `parse_updates`, `classify`, `triage` from Task 1.
- Produces: `renovate_adoption.sh sweep` → `[inspect item]`; `renovate_adoption.sh retro (--since <date|tag|sha> | --last <N>)` → `[retro item]`; jq def `aggregate` (`[{pr, mergedAt, updates}]` → `[retro item]` without verdict).

- [ ] **Step 1: Write failing tests** in `RenovateAdoptionBatchTests`:

```python
def test_sweep_lists_every_open_pr_with_verdict(self):  # len == fixture count; gh argv has "--state open" and "--author app/renovate"
def test_retro_aggregates_repeated_bumps(self):
    # fixture: setup-java v4.1.0→v4.2.0 (#12, earlier), v4.2.0→v4.5.0 (#19, later)
    item = next(i for i in out if i["package"] == "actions/setup-java")
    self.assertEqual((item["from"], item["to"], item["prs"]), ("v4.1.0", "v4.5.0", [12, 19]))
    self.assertEqual(item["updateType"], "minor"); self.assertEqual(item["verdict"], "candidate")
def test_retro_since_tag_resolves_to_commit_date(self):  # temp git repo with tag; gh argv contains "merged:>=<that ISO date>"
def test_retro_last_n_passes_limit(self):  # argv contains "--limit 5"
def test_retro_requires_exactly_one_range_flag(self):  # neither or both → exit 2
```

- [ ] **Step 2: Run** the new tests → FAIL.

- [ ] **Step 3: Implement.** `sweep`: `gh pr list --author app/renovate --state open --limit 100 --json number,title,body,headRefName,headRefOid`, map items through the Task 1 pipeline in open mode. `retro`: `--since` value matching `^[0-9]{4}-[0-9]{2}-[0-9]{2}` is a date, otherwise `git log -1 --format=%cI <ref>` (failure → exit 2 "unknown ref"); `gh pr list --author app/renovate --state merged --label dependencies --search "merged:>=<date>" --limit <N or 200> --json number,title,body,mergedAt`. `aggregate`: group updates by `package`, order by `mergedAt`, `from` of first, `to` of last, union of URLs, `prs` ascending; recompute `updateType` with `classify`; then `triage("retro"; allow)`.

- [ ] **Step 4: Run all tests** → PASS.

- [ ] **Step 5: Commit** `feat(renovate-adoption-review): add sweep and retro batch helpers`.

### Task 3: `owned-paths`

**Files:**
- Modify: `skills/repository/renovate-adoption-review/scripts/renovate_adoption.sh`, `renovate_adoption.jq`
- Modify: `tests/test_renovate_adoption.py`
- Create: `tests/fixtures/renovate_adoption/api_tree.json`

**Interfaces:**
- Produces: `renovate_adoption.sh owned-paths` → JSON array of path strings (template paths with `.jinja` removed and leading template root dirs kept); consumer path P is owned iff some entry ends with `/P` or equals P. `SKILL.md` uses this rule.

- [ ] **Step 1: Write failing tests:**

```python
def test_owned_paths_from_copier_answers(self):
    # temp repo with .copier-answers.yml (_src_path https://github.com/quokkify/ci-kit.git, _commit v3.9.0)
    # and .copier-answers.java.yml with the same source → gh api called ONCE with repos/quokkify/ci-kit/git/trees/v3.9.0?recursive=1
    self.assertIn("templates/core/.github/workflows/validate.yml", out)  # ".jinja" stripped
def test_owned_paths_without_answers_is_empty_list(self):  # "[]", exit 0, gh not called
def test_owned_paths_non_github_source_is_skipped_with_warning(self):  # stderr warning, exit 0
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement.** Read `_src_path` and `_commit` with `sed` from each `.copier-answers*.yml` at repo root; dedupe `(owner/repo, commit)`; for `https://github.com/<o>/<r>(.git)?` call `gh api "repos/<o>/<r>/git/trees/<commit>?recursive=1"`; keep `type == "blob"` paths, strip trailing `.jinja`, unique sort.

- [ ] **Step 4: Run all tests** → PASS.

- [ ] **Step 5: Commit** `feat(renovate-adoption-review): detect template-owned paths`.

### Task 4: `SKILL.md`, references, catalog

**Files:**
- Create: `skills/repository/renovate-adoption-review/SKILL.md`
- Create: `references/ecosystems/github-actions.md`, `docker.md`, `gradle-maven.md`, `npm-typescript.md`, `python.md`
- Create: `references/templates.md`, `references/stacked-pr.md`
- Modify: `docs/skill-catalog.md` (Repository section, after `repository-quality-gates`)

**Interfaces:**
- Consumes: CLI commands and JSON shapes from Tasks 1–3 (`inspect`, `sweep`, `retro`, `owned-paths`).

- [ ] **Step 1: Write `SKILL.md`.** Description (single line): `Review a Renovate update (open PR or a batch of merged updates) and apply grounded, cited opportunities to adopt what the new version brings in the consumer repository, via a child PR or an issue.` Body sections, each pinned to the spec section of the same name: When to use; Modes (`review <pr>`, `sweep`, `retro`, `--apply`); Workflow (preflight clean tree and correct branch → helper → per-dependency sources in spec order → search consumer usages (no source available → report "no sources" and skip that dependency) → findings → apply within guardrails → consumer checks → output); Grounding rules; Guardrails (including the 10-file cap and `owned-paths` rule); Explicit-PR override (verdict `skip` on a PR the user named → report reason, ask before proceeding); Stop conditions (helper exit ≠ 0, dirty tree, failing checks); Outward actions (pushing branches, opening PRs/issues, commenting require the user's go-ahead unless they invoked the mode that implies it).

- [ ] **Step 2: Write `references/stacked-pr.md`** with the exact commands: create `adopt/<branch without renovate/>` from the parent head; open PR `gh pr create --base <renovate-branch>`; comment on parent; drift: read marker, `git rebase --onto <new-head> <old-head>`, checks, `git push --force-with-lease`, update marker via `gh pr edit --body`; parent merged/closed: `gh pr edit --base <default>` + rebase, or new PR linking the closed one; existing `adopt/` branch → reuse through the drift path, never a duplicate. Cite Renovate docs `pruneStaleBranches` and `gitIgnoredAuthors`.

- [ ] **Step 3: Write `references/templates.md`** with the spec's Output formats as fill-in markdown (child PR, parent comment, retro issue titled `Adoption review: <range>`, retro PR with `Closes #<issue>`).

- [ ] **Step 4: Write the five ecosystem checklists**, each: where to look in release notes/diff, which consumer files to grep, which local warning command to run (`gradle --warning-mode all`, `actionlint`, `hadolint`, `ruff check`, `tsc --noEmit`), typical adoptable patterns, typical false positives.

- [ ] **Step 5: Add catalog line** in the Repository list, same format as the `repository-quality-gates` entry, linking `../skills/repository/renovate-adoption-review/SKILL.md`, text: `adopt what a dependency update brings, with cited changes in a child PR or issue.`

- [ ] **Step 6: Run** `./scripts/validate.sh --full` → `Repository validation: ok`, all tests OK, documentation build ok.

- [ ] **Step 7: Commit** `feat(renovate-adoption-review): add skill instructions and references`.

### Task 5: Canary end-to-end (verification, no code)

- [ ] **Step 1:** Install the branch's skill locally (hub `scripts/sync-shared-skills.sh` or symlink per hub docs).
- [ ] **Step 2:** In a quokkify consumer, run `sweep`; pick one open major. Ask the user before running `review <pr>` (it pushes and opens a PR). Record: verdict, findings, citations, checks run, PR link or "nothing to adopt" report.
- [ ] **Step 3:** In a repository consuming GitHub Actions updates, run `retro --last 20` without `--apply`; ask the user before creating the issue. Record the issue link and finding count.
- [ ] **Step 4:** Fix any skill defects found as separate commits with a regression test where the helper is at fault; report results to the user.
