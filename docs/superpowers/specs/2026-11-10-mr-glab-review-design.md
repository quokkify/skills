# mr-glab-review — design

Status: draft for review · Date: 2026-11-10

## Problem

AI-assisted merge request reviews tend to fail the human reviewer in two ways.
Either the agent publishes findings on its own (no chance to drop a wrong or
unwanted point), or it produces technically correct comments that read as a dense,
intimidating wall of text that the MR author struggles to act on. Publishing many
comments one by one also triggers one notification per comment and runs into API
rate limits.

## Goal

A portable skill that reviews a GitLab merge request **together with the human
reviewer**: the agent finds and verifies issues, then walks the reviewer through
them one at a time, drafts each comment in a light, friendly, well-formatted
style, and publishes only what the reviewer approved — in a single batch.

Success: on a real MR, nothing reaches the MR author without an explicit "yes"
from the reviewer; every published inline comment lands on the intended diff line;
every comment passes the style checklist; and an interrupted session resumes from
where it stopped.

## Non-goals

- GitHub pull requests (GitLab only in v1).
- Approving or merging the MR automatically.
- Replying to or triaging comments left by others (covered by `get-pr-comments`).
- Running a panel of parallel reviewers by default.
- Any organisation-specific context (hosts, trackers, team conventions) — that
  belongs in a private caller (see Extension point).

## Prior art

No existing skill combines "agent finds issues → per-comment human approval →
inline threads → single batch publish" for GitLab (web search, 2026-11; negative
result, not proof). Closest, and ideas taken from each:

- A community `gitlab-mr-code-review` skill: analyse → user approval with
  Edit/Cancel → inline comments; inline comments only on lines present in the
  diff. *Taken:* the approval options and the diff-line rule.
- A community `glab-cli` skill: inline threads via a position object, separate
  resolvable threads for conceptual remarks. *Taken:* inline vs. general-note split.
- `gitlab-reviewer-cli` (TUI): accept / edit / reject each suggested comment before
  publishing. *Taken:* per-item verdicts.
- GitLab draft notes as an unpublished staging area for AI findings, published by
  the human. *Taken:* drafts + `bulk_publish`.
- Claude Code's built-in `/code-review --comment` posts a single note on GitLab,
  with no per-item approval — not a fit, but complementary.

## Design

### Components

| Part | Content |
|---|---|
| `SKILL.md` | The phased process below; each phase ends in a check. |
| `references/comment-style.md` | Comment style guide, marker vocabulary, checklist, three anonymised before/after pairs. |
| `references/gitlab-api.md` | Recipes: draft note with position, general note, `bulk_publish`, editing a note, computing `new_line` from a diff, handling 429/401. |
| `scripts/` | Small Python helper: maps a diff line to its new-file line number; builds draft-note payloads and positions; glab performs the calls. Covered by unittest on a stored diff fixture. |

All API calls go through `glab api` (no extra dependency). Project ID and
`diff_refs` are resolved from the MR URL, never hardcoded.

### Extension point: caller-supplied profile

The skill runs with neutral defaults. A private wrapper skill (kept outside this
repository) may invoke it with a **profile** block that overrides defaults:

- GitLab host;
- comment language (default: the language of the MR description);
- where requirements come from (default: the MR description; a profile may name a
  test-case tracker or ticket system and how to read it);
- extra review conventions to check;
- a leak-guard stop-list used by the wrapper before anything is published to a
  public place.

Rule in `SKILL.md`: a profile passed by the caller takes precedence over defaults.

### Process

**Phase 0 — Prepare (silent).** Resolve project, MR and `diff_refs`
(base/head/start SHA); download the diff to the scratch directory; verify
`glab auth`; detect the reviewer's existing unpublished drafts on the MR and offer
to resume from them. *Check:* diff stored, SHAs known.

**Phase 1 — Review.** Read the whole diff and the requirements (per profile).
Look for: bugs and contradictions with requirements, dead code, names that do not
match content, side effects, convention violations from the profile. Verify every
finding with evidence (search the branch, compare with the target branch, read the
requirement). Unverified findings are marked *uncertain* and their comment is
phrased as a request to double-check. A subagent is started only when the reviewer
asks for it (brainstorm / template search). *Check:* every finding has a
`file:line` and evidence.

**Phase 2 — Summary.** A short list ordered by severity (🔴 / 🟠 / 🟡), one line
per item, each tagged *inline* or *general note*, plus requirement coverage
(e.g. which listed test cases have tests). The reviewer may drop items here.

**Phase 3 — Approval loop (one item at a time).** For each item show the gist,
the target (`file:line` or general note) and the ready comment text. The reviewer
answers through a structured choice:

- **Yes** → create a draft note (invisible to the author);
- **Edit** → apply the requested change, show the new version, ask again;
- **Brainstorm** → start a subagent for options and a reusable in-repo pattern,
  then redraft;
- **Skip** → not published;
- **Back to item N**.

**Phase 4 — Publish.** Summarise drafts and skipped items; ask once
"publish all drafts now?"; on yes, call `bulk_publish`; report links to the
threads.

### Cross-cutting rules

- Nothing is visible to the MR author before Phase 4 and an explicit yes.
- Inline comments only on lines present in the diff; otherwise a general note
  that names `file:line`.
- **429**: back off with increasing delay, no request bursts. **401**: check
  `glab api user`; if the token fails, stop and ask the reviewer to re-login.
- Session state (findings, texts, verdicts, draft IDs) is written to a state file
  in the scratch directory so an interrupted session can resume.

### Comment style

Structure: bold one-line gist + marker → "What I noticed" (1–3 bullets, one fact
each) → "Suggestion" (a concrete action; two options joined by "or") → optional
short code block and a pointer to an existing in-repo example.

Tone: acknowledge what is right first; mark non-blockers explicitly; phrase
uncertain points as questions; no reviewer jargon, caps or exclamation marks;
lists longer than five items go under `<details>`.

Markers: 🔍/🙂 please double-check · 🧹 cleanup · ✂️ simplify · 🔀 mismatch ·
💡 idea / non-blocker · 🔄 process (rebase, branch).

Checklist applied to every draft before it is shown: the first line stands on its
own; ≤ ~120 words excluding code and `<details>`; a concrete suggestion is
present; no "wrong"/"bug" without evidence; language per profile.

## Testing

Following `writing-skills`:

1. **Baseline without the skill:** ask an agent to "review this MR and publish
   comments"; record the failures (publishes unasked, wall of text, wrong
   position).
2. **With the skill on a real MR, drafts only:** drafts are created and then
   deleted. Verify: nothing published without a yes; `new_line` correct; texts
   pass the checklist; interruption → resume from the state file.
3. **Helper script:** unittest on a stored diff fixture (line mapping, draft payload
   shape), run by `validate.sh --full`.
4. **Leak guard:** the hub's validation plus a manual review of the PR diff.

## Open questions

None at the time of writing.
