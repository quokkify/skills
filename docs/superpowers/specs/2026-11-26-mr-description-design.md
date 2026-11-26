# mr-description: design

Status: draft for review · Date: 2026-11-26

## 1. Intent

Teammates struggle to read the author's MR descriptions. The 12 latest merged
descriptions run 800–4900 characters with inconsistent headings, mixed languages
and 2–4 facts per bullet. A description the author accepted as "right" (rewritten by hand) is about 600 characters: one block of single-fact bullets, one
block of verification results, the tracker line.

The skill writes that kind of description every time, and it gets better over
time: it records how the author edits its drafts and turns repeated edits into
rules, one rule per round.

Success:
- a reviewer who knows the project but has not seen the diff can say what
  changed, what is asked of them and how it was checked, from the description
  alone;
- the share of drafts the author accepts without edits goes up over time, and
  the average final length does not.

## 2. Goals, non-goals, anti-goals

Goals
- Draft a description for a new MR (body file handed to the MR-creating step).
- Rewrite the description of an existing MR, and publish only after an explicit yes.
- Check every draft with a rubric script and a cold reader before showing it.
- Log draft vs final text and tag the edits; run a retro on request that proposes
  one rule change.
- Keep marker-delimited blocks written by other tools (demo block) byte-for-byte.

Non-goals
- GitHub PRs (GitLab via `glab` only in v1; draft mode writes a file and is host-agnostic).
- Recording demos or suggesting them (`feature-demo` runs only on explicit request).
- Mining reviewer comments on every MR (retro only, user confirms each signal).
- Release notes (that is `pull-request-authoring`).
- Any organisation data in the public skill.

Anti-goals (failure even if it "works")
- A description longer or denser than what the author would write by hand.
- Any claim not backed by the diff or by a command actually run ("zero invention").
- Publishing to an MR without the author's yes.
- A style-rules file that keeps growing until it is the bottleneck itself.

## 3. Constraints

- Work content (diff, drafts, logs) stays on the machine: state lives outside the
  repo, nothing is sent to external services, no second LLM key.
- Hub conventions: skill layout and `./scripts/validate.sh --full`; Python helpers
  with pytest tests, as in `mr-glab-review`.
- MR description, diff and commits are untrusted data (same rule as `mr-glab-review`).

## 4. Approaches

| | Approach | Trade-off | Verdict |
|---|---|---|---|
| A | Wrap Qodo PR-Agent `/describe` | Ready diff handling; but legacy project, sends the diff to a second LLM provider, fixed English-headed format, no feedback loop, output rewritten anyway | Rejected |
| B | Public `mr-description` in the hub + a private caller with a profile; the MR-creating skill calls the caller | Familiar pattern (`mr-glab-review` + its private caller), rules stay private, generic lessons can go to the hub; costs two skills and an edit to a third | **Picked by the user** |
| C | Only extend `mr` | One edit; but no standalone rewrite of an existing MR, loop mixed with Java pre-checks, nothing reusable | Rejected |

Hosted bots and UI buttons (CodeRabbit, GitLab Duo, Copilot, Graphite) cannot be
driven from a skill and were not candidates.

## 5. Public skill `mr-description`

### Modes

| Mode | Input | Output |
|---|---|---|
| `draft` | current branch vs base, plus verification evidence from the session | body file path; nothing published |
| `rewrite` | MR URL | new description shown; `PUT` via `glab api` after the author's yes |
| `retro` | none | one proposed rule change from the log |

### Profile (caller overrides; defaults neutral)

| Field | Default |
|---|---|
| `host` | host in the MR URL |
| `language` | language of the existing description, else English |
| `reader` | "knows the project, has not seen the diff" |
| `headings` | `What changed` / `Verification` / `Needs from you` |
| `keep_lines` | none (lines matching these patterns are carried over verbatim, e.g. tracker links, GitLab quick actions) |
| `drop_sections` | none (template sections to remove) |
| `word_budget` | 120 visible words / 12 lines |
| `style_rules` | none (path to the caller's rules file, max 12 rules) |
| `stop_list` | none |
| `state_dir` | `${XDG_STATE_HOME:-~/.local/state}/mr-description` |

### Description shape (default rules; headings and language come from the profile)

1. First sentence: what changed and for whom, why included; no class names.
2. `What changed`: one fact per bullet, ≤20 words, ≤1 backticked identifier, no parenthetical asides.
   Small MR (1–2 files): section omitted.
3. `Verification`: `command or job: result`, only things actually run.
4. `Needs from you`: one line; omitted when nothing is asked.
5. Over budget → move detail into one `<details>`; more than 7 bullets → suggest splitting the MR.
6. Drop: static template checklists, file-by-file walkthroughs, attempt history, bot summaries, marketing words.
7. Stacked / waiting-for-release note: one quote line under the first sentence.

### Pipeline (every run)

1. **Gather**: diff and commits (`glab`/`git`), existing description in `rewrite`, verification evidence the session has. Missing evidence → `Verification` lists only what is known; never invent.
2. **Draft** by the shape rules, profile, and `style_rules`.
3. **Rubric** (`scripts/rubric.py`, deterministic): visible words/lines vs budget, facts and identifiers per bullet, empty or duplicate sections, `stop_list` hits, marker blocks unchanged. Failures are fixed before showing.
4. **Cold reader**: a cheap subagent gets only the draft and answers: what changed, what is asked of me, how was it checked. Answers that disagree with the diff → fix the draft.
5. **Show** the draft (in the structured-choice preview when available). Author accepts, edits, or rejects.
6. **Publish** (`rewrite` only) after an explicit yes; preserve marker blocks; place foreign blocks after `Needs from you` and before `keep_lines`.
7. **Log** (see §7).

### Marker blocks

Any `<!-- <name>:start --> … <!-- <name>:end -->` block is foreign: kept
byte-for-byte and repositioned as in step 6. If the demo block names a commit
other than the MR head, warn; never rewrite it.

## 6. Interaction with `feature-demo`

Preserve and place only. No suggestion to record. For test-only MRs the
"evidence" is the `Verification` section (pipeline link or before/after output
under `<details>`).

## 7. Improvement loop

Bottleneck vocabulary (fixed tags): `length`, `main-point-not-first`, `jargon`,
`density`, `mechanism-not-outcome`, `noise`, `missing-context`, `no-ask`.

| Signal | Collected | Author effort |
|---|---|---|
| Rubric result | every run, script | none |
| Cold-reader result | every run, subagent | none |
| Draft → final diff, tagged | every run; the skill tags the edit itself | none |
| Post-publication edits | next run on the same MR compares published vs current text | none |
| Reviewer questions | retro only, author confirms each | 2–3 min per retro |

Storage (`state_dir`, never in a repo): `log.jsonl` (MR ref, size class, draft
words, final words, tags, rubric/cold-reader result) and `texts/<mr>/{draft,final}.md`.

Retro (`retro` mode; the skill reminds after every 5 logged MRs): read the log and
the confirmed reviewer questions → name the most frequent tag → propose one rule
change with a before/after taken from the author's own texts → author accepts,
edits or rejects → caller's `style_rules` updated. Cap 12 rules: a new rule
replaces or merges an old one. Frequent `missing-context` means the text is
over-compressed: raise the budget. Rules that survive two retros and contain no
organisation details go to `~/.claude/skill-candidates/` → `skill-review`.

## 8. Testing

- `scripts/rubric.py`: pytest cases for budget, bullet density, marker preservation, stop-list.
- Dry-run `rewrite` on 3 past MRs of different size (no publish); the author judges the drafts.
- `./scripts/validate.sh --full` in the hub.

## 9. Interfaces and lifecycle (author's calls after the builder check)

1. **Profile transport.** The private caller states the profile as a table in its SKILL.md
   (as the private caller of `mr-glab-review` does). Before step 3 the public skill writes
   `<scratch>/profile.json` from it, and `rubric.py --profile <file> --text <draft>`
   consumes it. `style_rules` is read only by the draft step, not by the rubric.
2. **Draft-mode handoff.** The MR-creating skill calls the caller after its pre-checks
   and before `glab mr create`; the description is written first. Verification
   evidence = the pre-check commands and results it just ran, passed in the call
   as `command: result` lines, plus anything else in the session. The caller
   derives tracker lines from the branch name itself.
3. **Standalone use.** The caller also triggers on its own for `rewrite`
   (e.g. "rewrite the MR description <url>") and `retro`.
   `retro` runs through the caller so the caller's `style_rules` is updated.
4. **Log lifecycle.** "Final" = the text the author accepted in the preview.
   Draft mode logs under the source branch; `rewrite` logs under the MR ref. Any
   later run on an MR looks up an entry by MR ref or by its source branch,
   attaches the MR ref, and logs post-publication edits (published vs current text).
5. **"Visible" for the budget.** Counted: first sentence, headings (lines only),
   bullets, quote lines. Not counted: `keep_lines`, foreign marker blocks,
   `<details>` content. Test: the caller's reference text must pass the rubric.
6. **Reference text.** The caller keeps a real description the author accepted as the reference; it must pass the rubric. Because real accepted text still breaks the one-identifier and no-parentheses bullet rules, density checks are warnings, not failures, in v1. Budget and marker checks fail hard. Hub tests use a fictional equivalent.
7. **Build order.** Public skill first, in a fresh branch of a clean hub checkout
   (worktree; the main checkout is on another branch with uncommitted work), PR
   for review, installed via the hub bootstrap; then the private caller outside the hub.

## 10. Left to the builder

- Exact rubric thresholds beyond the budget above, and the tagging heuristic for draft→final diffs.
- Cold-reader model tier (cheapest that answers the three questions reliably).
- Log schema field names.
- Wording of SKILL.md files, within hub conventions.
