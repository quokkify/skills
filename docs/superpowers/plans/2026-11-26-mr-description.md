# mr-description Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A public `mr-description` skill that drafts and rewrites short GitLab MR descriptions, checks them with a rubric and a cold reader, and learns from the author's edits; usable through a private caller that passes a profile.

**Architecture:** Hub skill = SKILL.md (process, profile, modes) + two stdlib Python helpers: `rubric.py` (deterministic checks) and `mr_log.py` (JSONL edit log and retro stats). A private caller (outside the hub) passes a profile table and owns its style rules.

**Tech Stack:** Python ≥3.10 stdlib only, `unittest` (hub runs `python3 -m unittest discover -s tests`), `glab api`, Markdown skills.

**Spec:** `docs/superpowers/specs/2026-11-26-mr-description-design.md`

## Global Constraints

- Work happens on branch `feat/mr-description` from `origin/main`.
- No organisation names, hosts, trackers or machine paths in the skill, fixtures or docs.
- Python stdlib only; no new dependencies.
- Budget default: 120 visible words / 12 visible lines. Bullet warnings: >20 words, >1 backticked identifier, parenthetical aside, >7 bullets.
- Bottleneck tags (fixed): `length`, `main-point-not-first`, `jargon`, `density`, `mechanism-not-outcome`, `noise`, `missing-context`, `no-ask`.
- Default `state_dir`: `${XDG_STATE_HOME:-~/.local/state}/mr-description`. Style-rules cap: 12.
- Hub commits: Conventional Commits, end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Validation before PR: `./scripts/validate.sh --full`.

## Review Focus

1. Original description has a demo block and the draft drops or edits it → rubric must fail (`marker_block_changed`), never silently pass. → Task 2 test.
2. Stop-list term in different case (`Secret` vs `secret`) → fail. → Task 2 test.
3. Invalid regex in `keep_lines` or malformed profile JSON → exit 2 with a message, no traceback. → Task 2 test.
4. Log key such as `../../etc` or `group/proj!12` → file paths stay inside `state_dir`. → Task 3 test.
5. Empty or whitespace-only draft → fail `empty_description`. → Task 2 test.

---

### Task 1: Spec and plan

- [x] Create the branch, add `docs/superpowers/specs/2026-11-26-mr-description-design.md` and this plan; commit `docs: add mr-description design and plan`.

### Task 2: `rubric.py`

**Files:**
- Create: `skills/repository/mr-description/scripts/rubric.py`
- Create: `tests/fixtures/mr_description/{good.md,dense.md,with_demo.md,demo_edited.md,profile.json}` (fictional English content)
- Test: `tests/test_mr_description.py` (class `RubricTests`; import via `importlib.util` as `test_mr_glab_review.py` does)

**Interfaces:**
- Produces CLI: `python3 rubric.py --profile <profile.json> --text <draft.md> [--original <current.md>]`
  - stdout JSON: `{"ok": bool, "failures": [{"code": str, "detail": str}], "warnings": [{"code": str, "detail": str}], "stats": {"visible_words": int, "visible_lines": int, "bullets": int}}`
  - exit 0 = ok, 1 = failures, 2 = usage/profile error (message on stderr).
- Produces function: `check(text: str, profile: dict, original: str | None = None) -> dict` (same shape as stdout).
- Profile JSON keys: `word_budget: {"words": int, "lines": int}`, `headings: [str]`, `keep_lines: [regex str]`, `stop_list: [str]`. Missing keys → defaults (120/12, `["What changed","Verification","Needs from you"]`, `[]`, `[]`).
- Failure codes: `empty_description`, `over_budget_words`, `over_budget_lines`, `stop_list_hit`, `marker_block_changed`, `marker_block_unbalanced`. Warning codes: `bullet_too_long`, `bullet_identifiers`, `bullet_parenthetical`, `too_many_bullets`, `empty_section`, `duplicate_section`.
- Visible = non-blank lines outside foreign blocks (`<!-- name:start -->…<!-- name:end -->`) and `<details>…</details>`, not matching any `keep_lines` regex. Heading lines count toward lines, not words. Words = whitespace-split tokens.

- [ ] **Step 1: Write failing tests**

```python
class RubricTests(unittest.TestCase):
    def test_good_fixture_passes(self):           # ok True, failures []
    def test_over_word_budget_fails(self):        # 130-word body → "over_budget_words" in codes
    def test_keep_lines_and_details_not_counted(self):  # tracker line + 200 words in <details> → ok
    def test_dense_bullet_warns_not_fails(self):  # dense.md → ok True; warnings ⊇ {bullet_too_long, bullet_identifiers, bullet_parenthetical}
    def test_demo_block_dropped_fails(self):      # original=with_demo.md, text without block → "marker_block_changed"
    def test_demo_block_edited_fails(self):       # original=with_demo.md, text=demo_edited.md → "marker_block_changed"
    def test_demo_block_moved_passes(self):       # same block bytes at another position → ok
    def test_unbalanced_marker_fails(self):       # start without end → "marker_block_unbalanced"
    def test_stop_list_case_insensitive(self):    # stop_list ["secret"], text "Secret" → "stop_list_hit"
    def test_empty_description_fails(self):       # "  \n" → "empty_description"
    def test_bad_regex_exit_2(self):              # CLI, keep_lines ["("] → returncode 2, stderr non-empty, no "Traceback"
    def test_bad_profile_json_exit_2(self):       # CLI, profile file "{" → returncode 2
```

- [ ] **Step 2:** `python3 -m unittest tests.test_mr_description -v` → FAIL (module missing).
- [ ] **Step 3:** Implement `check()` and `main()` in `rubric.py` per Interfaces.
- [ ] **Step 4:** Same command → all `RubricTests` PASS.
- [ ] **Step 5:** `git add skills/repository/mr-description/scripts/rubric.py tests/ && git commit -m "feat(skills): add mr-description rubric"`

### Task 3: `mr_log.py`

**Files:**
- Create: `skills/repository/mr-description/scripts/mr_log.py`
- Test: `tests/test_mr_description.py` (class `LogTests`, temp dirs only)

**Interfaces:**
- CLI subcommands (all take `--state-dir <dir>`; JSON on stdout; exit 2 on usage error):
  - `record --branch B [--mr REF] --size small|medium|large --draft F --final F --tags t1,t2 --rubric ok|fail --cold-reader ok|fixed` → appends to `<state>/log.jsonl` `{"ts","branch","mr","size","draft_words","final_words","edited": draft!=final,"tags":[...],"rubric","cold_reader"}`; copies texts to `<state>/texts/<slug>/{draft,final}.md`. Unknown tag → exit 2.
  - `find (--mr REF | --branch B)` → latest matching entry; none → exit 3.
  - `attach --branch B --mr REF` → sets `mr` on entries of B with `mr` null; prints count.
  - `stats [--last N]` → `{"count","tag_counts","accepted_unedited_share","avg_final_words","since_last_retro"}`.
  - `mark-retro` → appends `{"ts","type":"retro"}`; `since_last_retro` counts entries after the last one.
- `slug(key: str) -> str`: `re.sub(r"[^A-Za-z0-9._-]", "_", key)`, leading dots stripped; result never empty.

- [ ] **Step 1: Write failing tests**

```python
class LogTests(unittest.TestCase):
    def test_record_then_find_by_branch(self):
    def test_attach_then_find_by_mr(self):
    def test_unknown_tag_rejected(self):            # --tags "vibes" → returncode 2
    def test_edited_flag_and_words(self):           # draft != final → edited True, final_words correct
    def test_stats_share_and_tag_counts(self):      # 2 edited (density, length), 1 unedited → share 1/3, density 1
    def test_since_last_retro(self):                # 2 records, mark-retro, 1 record → 1
    def test_slug_stays_inside_state_dir(self):     # branch "../../etc", mr "group/proj!12" → all written paths under state dir
    def test_find_missing_exit_3(self):
```

- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5:** `git commit -m "feat(skills): add mr-description edit log"`

### Task 4: SKILL.md, references, catalog, boundary test, PR

**Files:**
- Create: `skills/repository/mr-description/SKILL.md`
- Create: `skills/repository/mr-description/references/description-shape.md` (spec §5 shape rules + two fictional examples: small and medium-with-demo)
- Create: `skills/repository/mr-description/references/gitlab-api.md` (`glab api` read MR, read diff/commits, `PUT projects/:id/merge_requests/:iid` with `description` from file; project id resolved from URL)
- Create: `skills/repository/mr-description/references/retro.md` (tag vocabulary, retro steps, 12-rule cap, `missing-context` → raise budget, promotion via `skill-review`)
- Modify: `docs/skill-catalog.md` (one row, same format as `mr-glab-review`)
- Test: `tests/test_mr_description.py` (class `BoundaryTests`)

**Interfaces:**
- Frontmatter `description`: "Write or rewrite a GitLab merge request description that a reviewer can read in a minute — compact, outcome first, checked by a rubric and a cold reader, and improved over time from the author's own edits."
- SKILL.md sections: When to use · Untrusted content (copy the `mr-glab-review` rule set) · Profile (spec §5 table) · Modes (`draft`/`rewrite`/`retro`) · Pipeline steps 1–7 with exact commands for `rubric.py` and `mr_log.py` · Marker blocks · Cold reader prompt (only the draft; three questions: what changed, what is asked of me, how was it checked) · Publish only after explicit yes · Retro (points to `references/retro.md`).
- SKILL.md must also state: (a) on any run for an existing MR, `mr_log.py find`; if the logged final differs from the current GitLab description, `record` it with draft = logged final, final = current text and tags (post-publication edits); (b) after `record`, if `stats.since_last_retro >= 5`, remind the author to run `retro` in one line; (c) if the demo block names a commit other than the MR head, warn and leave the block untouched.

- [ ] **Step 1: Write failing tests**

```python
class BoundaryTests(unittest.TestCase):
    def test_frontmatter_description_exact(self):
    def test_no_machine_paths_or_real_emails(self):   # reuse MACHINE_PATHS / EMAIL_RE pattern from test_mr_glab_review.py
    def test_no_org_terms(self):                      # none of the org terms listed in the test (case-insensitive) in skill dir + fixtures
    def test_skill_md_references_exist(self):          # every references/*.md and scripts/*.py named in SKILL.md exists
    def test_catalog_lists_skill(self):
```

- [ ] **Step 2:** Run → FAIL. **Step 3:** Write the files. **Step 4:** Run → PASS.
- [ ] **Step 5:** `./scripts/validate.sh --full` → exits 0 (docs build ok, gitleaks clean).
- [ ] **Step 6:** Commit `feat(skills): add mr-description skill`, push, open PR (use `pull-request-authoring`; body ends with the Claude Code attribution line). Wait for user review/merge; install via the hub bootstrap.
