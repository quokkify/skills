# mr-glab-review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A public, organisation-neutral skill `mr-glab-review` that reviews a GitLab MR with the human reviewer item by item, stages approved comments as draft notes in a light, formatted style, and publishes them in one batch.

**Architecture:** One skill directory in the hub (`skills/repository/mr-glab-review/`): a phased `SKILL.md`, two reference files (GitLab API recipes, comment style), and one stdlib-only Python helper for the fragile parts (MR URL parsing, diff-line mapping, draft-note payloads). A private wrapper skill living outside the hub passes an organisation profile; it is out of scope for hub commits and handled in the last task.

**Tech Stack:** Markdown skill files; Python ≥3.10 stdlib only (`argparse`, `json`, `re`, `dataclasses`, `urllib.parse`); `unittest`; `glab api` at runtime.

**Spec:** `docs/superpowers/specs/2026-11-10-mr-glab-review-design.md`

## Global Constraints

- Skill path: `skills/repository/mr-glab-review/SKILL.md`; frontmatter `name: mr-glab-review`; single-line `description` ≤ 1024 chars.
- Public boundary: no employer names, hosts, trackers, ticket keys, project IDs, people, machine paths (`/Users/`, `/home/`) or real e-mails (only `example.com`). Examples use invented names (`OrderGenerator`, `UserSteps`, `example.gitlab.com`, project `group/app`).
- No new dependencies (`pyproject.toml` `dependencies = []` stays empty).
- All runtime API calls via `glab api`; project ID and `diff_refs` resolved from the MR, never hardcoded.
- Nothing visible to the MR author before Phase 4 and an explicit yes; inline comments only on lines present in the diff.
- Comment checklist: first line stands alone; ≤ ~120 words excluding code and `<details>`; concrete suggestion present; no "wrong"/"bug" without evidence; language per profile (default: MR description language).
- Markers: 🔍/🙂 double-check · 🧹 cleanup · ✂️ simplify · 🔀 mismatch · 💡 idea/non-blocker · 🔄 process.
- `./scripts/validate.sh --full` passes before any push.

## Review Focus

- A comment targeting a line **outside** any hunk (e.g. a constant declared far from changed lines) → helper reports "not in diff" and the skill falls back to a general note naming `file:line`. Test in Task 1 (`test_line_outside_hunks_is_not_in_diff`).
- A **deleted** line or a line in a **renamed** file → mapping uses the new path and never returns a number for removed lines. Tests in Task 1 (`test_removed_line_has_no_new_number`, `test_renamed_file_uses_new_path`).
- **Duplicate line text** in one file (e.g. two identical `.build();`) → mapping by text must refuse to guess and return all candidates. Test in Task 1 (`test_ambiguous_text_returns_all_candidates`).
- **Self-hosted GitLab under a sub-path or with nested groups** (`https://host/a/b/c/-/merge_requests/7`) → URL parser keeps the full project path. Test in Task 1 (`test_nested_group_url`).
- Reviewer **interrupts** mid-loop → existing drafts on the MR are detected in Phase 0 and the loop resumes from the state file instead of duplicating comments. Pinned by the SKILL.md resume section and exercised in Task 4 scenario 3.

---

### Task 1: Helper script `mr_glab.py`

**Files:**
- Create: `skills/repository/mr-glab-review/scripts/mr_glab.py`
- Create: `tests/test_mr_glab_review.py`
- Create: `tests/fixtures/mr_glab_review/sample.diff`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class MrRef: host: str; project_path: str; iid: int` and property `encoded_project -> str` (URL-encoded path for `projects/<id>` endpoints).
  - `parse_mr_url(url: str) -> MrRef` — raises `ValueError` on non-MR URLs.
  - `new_line_map(diff_text: str) -> dict[str, dict[int, str]]` — new path → {new line number: line text} for added and context lines only.
  - `find_new_lines(diff_text: str, path: str, text: str) -> list[int]` — all new-line numbers in `path` whose stripped text equals `text.strip()`.
  - `in_diff(diff_text: str, path: str, new_line: int) -> bool`.
  - `draft_note_payload(note: str, diff_refs: dict | None = None, path: str | None = None, new_line: int | None = None) -> dict` — `{"note": note}` for a general note; with position adds `{"position": {"position_type": "text", "base_sha", "head_sha", "start_sha", "new_path": path, "old_path": path, "new_line": new_line}}`; raises `ValueError` if only some of `diff_refs/path/new_line` are given.
  - CLI: `python3 mr_glab.py parse-url <url>` → JSON; `new-line <diff-file> <path> <text>` → JSON list; `in-diff <diff-file> <path> <line>` → exit 0/1; `draft-payload --note-file F [--refs-file R --path P --line N] --out O`.

- [ ] **Step 1: Write the fixture** `sample.diff`: a unified diff (`diff --git` headers as printed by `glab mr diff`) with (a) a modified file `src/OrderGenerator.java` having two hunks, a removed line, and two identical `        .build();` lines; (b) a renamed file `old/UserSteps.java → src/UserSteps.java`; (c) a new file.

- [ ] **Step 2: Write failing tests** in `tests/test_mr_glab_review.py` (unittest, import the script via `importlib.util.spec_from_file_location`):
  - `test_parse_simple_url`: `https://example.gitlab.com/group/app/-/merge_requests/42` → `MrRef("example.gitlab.com", "group/app", 42)`, `encoded_project == "group%2Fapp"`.
  - `test_nested_group_url`: `https://example.gitlab.com/a/b/c/-/merge_requests/7/diffs` → `project_path == "a/b/c"`, `iid == 7`.
  - `test_non_mr_url_raises`: issue URL → `ValueError`.
  - `test_added_and_context_lines_mapped`: known numbers from the fixture's second hunk.
  - `test_removed_line_has_no_new_number`: removed text → `find_new_lines(...) == []`.
  - `test_renamed_file_uses_new_path`: key `src/UserSteps.java` present, `old/UserSteps.java` absent.
  - `test_ambiguous_text_returns_all_candidates`: `.build();` → two numbers.
  - `test_line_outside_hunks_is_not_in_diff`: `in_diff(..., 1)` is `False` for a line before the first hunk.
  - `test_general_payload` / `test_inline_payload` / `test_partial_position_raises`.
  - `test_cli_new_line_outputs_json`: run via `subprocess`, parse stdout.
  - `test_skill_has_no_machine_paths_or_real_emails`: scan all files under the skill dir (same regexes as `tests/test_discussion_card.py`).

- [ ] **Step 3: Run** `python3 -m unittest tests.test_mr_glab_review -v` — Expected: FAIL (module file missing).

- [ ] **Step 4: Implement** `mr_glab.py` with the interfaces above. Hunk parsing: track `new` counter from `@@ -a,b +c,d @@`; `+` and ` ` lines advance it and are recorded; `-` lines are skipped; new path from the `+++ b/<path>` line (`/dev/null` → deleted file, skipped). URL: split on `/-/merge_requests/`, take the iid as the first integer segment after it.

- [ ] **Step 5: Run** the same command — Expected: all tests PASS.

- [ ] **Step 6: Commit**
```bash
git add skills/repository/mr-glab-review/scripts tests/test_mr_glab_review.py tests/fixtures/mr_glab_review
git commit -m "feat(mr-glab-review): add diff-line and draft-note helper"
```

### Task 2: Reference files

**Files:**
- Create: `skills/repository/mr-glab-review/references/gitlab-api.md`
- Create: `skills/repository/mr-glab-review/references/comment-style.md`
- Modify: `tests/test_mr_glab_review.py` (add reference checks)

**Interfaces:**
- Consumes: Task 1 CLI subcommands (named verbatim in the recipes).
- Produces: section anchors `SKILL.md` links to — `gitlab-api.md#resolve-the-mr`, `#draft-notes`, `#publish`, `#edit-a-note`, `#errors`; `comment-style.md#structure`, `#markers`, `#checklist`, `#examples`.

- [ ] **Step 1: Write failing tests**: `test_references_exist_and_have_sections` (each anchor heading above is present); `test_api_recipes_use_documented_endpoints` (file contains `merge_requests/:iid/draft_notes`, `draft_notes/bulk_publish`, `"note"` field, `glab api`); `test_style_examples_count` (`comment-style.md` has exactly three `### Example` headings, each with `Before` and `After` blocks).
- [ ] **Step 2: Run** `python3 -m unittest tests.test_mr_glab_review -v` — Expected: new tests FAIL.
- [ ] **Step 3: Write `gitlab-api.md`**: resolve MR (`glab api projects/<encoded>/merge_requests/<iid>` → `diff_refs`, `glab mr diff <iid> --color=never`); create draft note (POST `projects/:id/merge_requests/:iid/draft_notes` with `--input` JSON from `draft-payload`); list/delete drafts; `bulk_publish`; edit a published note (PUT `.../discussions/:did/notes/:nid`, body field `body`); errors: 429 → back off 60s, 120s, 240s, one request at a time; 401 → `glab api user`, stop and ask to re-login (`glab auth login --hostname <host>`). Placeholders only (`<host>`, `<encoded>`, `<iid>`).
- [ ] **Step 4: Write `comment-style.md`**: structure, tone, markers table, checklist (verbatim from Global Constraints), three anonymised Before/After examples: dead code list (`<details>`), mixed-up constant, test for a removed test case phrased as a double-check request.
- [ ] **Step 5: Run** tests — Expected: PASS.
- [ ] **Step 6: Commit** `git commit -m "docs(mr-glab-review): add GitLab API recipes and comment style guide"`

### Task 3: `SKILL.md` and catalog entry

**Files:**
- Create: `skills/repository/mr-glab-review/SKILL.md`
- Modify: `docs/skill-catalog.md` (under `## repository`)
- Modify: `tests/test_mr_glab_review.py`

**Interfaces:**
- Consumes: Task 1 CLI, Task 2 anchors.

- [ ] **Step 1: Write failing tests**: `test_skill_frontmatter` (`name: mr-glab-review`, one-line description); `test_skill_has_all_phases` (headings `Phase 0` … `Phase 4`, `Profile`, `Resume`); `test_skill_links_resolve` (every `references/...#anchor` link points to an existing heading); `test_catalog_lists_skill`.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Write `SKILL.md`** following the spec's Process and Cross-cutting rules sections, with: *When to use* / not-for list; requirements (`glab` authenticated, `python3`); **Profile** section (fields: host, language, requirements source, extra conventions, leak stop-list; caller profile overrides defaults); Phases 0–4 each ending in a ✅ check; approval loop answered via the runtime's structured-choice prompt with options Yes / Edit / Brainstorm / Skip / Back to N; **Resume** section with the state file schema `{"mr": "<url>", "diff_refs": {...}, "items": [{"id", "severity", "target": {"path", "new_line"} | null, "status": "pending|drafted|skipped", "draft_id", "text"}]}` stored in the scratch directory; rule "never publish without an explicit yes".
  Description line: `Review a GitLab merge request together with the human reviewer: verify findings, approve each comment one by one, stage approved ones as draft notes in a light, friendly format, and publish them in one batch.`
- [ ] **Step 4: Add catalog line**: ``- [`mr-glab-review`](../skills/repository/mr-glab-review/SKILL.md) — review a GitLab MR with the reviewer item by item and publish approved, friendly comments in one batch.``
- [ ] **Step 5: Run** `python3 -m unittest tests.test_mr_glab_review -v && ./scripts/validate.sh --full` — Expected: PASS.
- [ ] **Step 6: Commit** `git commit -m "feat(mr-glab-review): add skill entry point and catalog entry"`

### Task 4: Scenario checks (writing-skills)

**Files:** none in the hub (results go into the PR description as a test plan).

- [ ] **Step 1: Baseline.** Dispatch a fresh subagent *without* the skill: "Review MR <url> and leave comments." Record failures (publishes unasked / wall of text / wrong line). Use a disposable test MR in a personal GitLab project, or drafts-only on a real MR with publishing forbidden in the prompt.
- [ ] **Step 2: Install for testing:** copy the skill dir into the local skills directory (temporary build-output copy; replaced by the normal sync after merge).
- [ ] **Step 3: With the skill, drafts only** (stop before Phase 4). Check: (1) no published note appears (`glab api .../notes` unchanged); (2) each draft's `position.new_line` matches the intended line in the GitLab UI; (3) every text passes the checklist; (4) interrupt after two items, start a new session, confirm resume from state file and existing drafts without duplicates.
- [ ] **Step 4: Clean up** the test drafts (DELETE each `draft_notes/:id`) and record results for the PR test plan.

### Task 5: Private wrapper `aqa-mr-glab-review` (outside the hub)

**Files:**
- Create: `<local skills dir>/aqa-mr-glab-review/SKILL.md` — **never added to the hub repo or any public place.**

- [ ] **Step 1: Write the wrapper**: when to use (work MRs); the profile block (host, language, requirements source and how to read it, extra conventions taken from the reviewer's saved preferences, leak stop-list); "invoke `mr-glab-review` with this profile".
- [ ] **Step 2: Leak gate before the hub PR:** `grep -rniE '<stop-list>' skills/repository/mr-glab-review docs/superpowers tests/test_mr_glab_review.py tests/fixtures/mr_glab_review` → Expected: no output. Then `./scripts/validate.sh --full` → PASS.
- [ ] **Step 3: Smoke run** on one real work MR via the wrapper, drafts only, then delete the drafts.
- [ ] **Step 4: Hub PR** (after the reviewer's explicit approval): push `feat/mr-glab-review`, open a PR with the scenario results as the test plan; the reviewer reads the PR diff once more for leaks before marking it ready.
