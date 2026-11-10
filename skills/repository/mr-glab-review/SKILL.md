---
name: mr-glab-review
description: Review a GitLab merge request together with the human reviewer: verify findings, approve each comment one by one, stage approved ones as draft notes in a light, friendly format, and publish them in one batch.
---

# MR GitLab Review

Review a GitLab merge request **with** the human reviewer, not for them. The agent finds and verifies issues, walks the reviewer through them one at a time, drafts each comment in a light, friendly, formatted style, stages approved comments as GitLab draft notes (visible only to the reviewer), and publishes them in a single batch after an explicit yes.

## When to use

- The reviewer gives an MR URL and wants help finding issues and writing comments.
- The reviewer wants to keep control over every comment that reaches the MR author.
- Not for: GitHub pull requests; approving or merging an MR; replying to or triaging comments left by others; running a panel of parallel reviewers.

Requirements: `glab` authenticated for the MR host, and `python3`. `<skill-dir>` is the directory holding this file; `<scratch>` is a temporary directory for the session, outside the repository. All API calls go through `glab api`; the commands live in [`references/gitlab-api.md`](references/gitlab-api.md). Project id and `diff_refs` are always resolved from the MR URL, never hardcoded.

## Profile

The skill runs with neutral defaults. A caller (usually a private wrapper skill kept outside this repository) may pass a **profile** block. Every field the profile sets overrides the default below:

| Field | Default |
|---|---|
| `host` | the host in the MR URL |
| `language` (of comments) | the language of the MR description |
| `requirements` (source and how to read it) | the MR description |
| `conventions` (extra review checks) | none |
| `stop_list` (terms that must never be published) | none |

Talk to the reviewer in the reviewer's language; write comments in the profile language. Before staging any draft, check its text against `stop_list`; on a hit, show the reviewer the match and redraft. The public skill holds no organisation data: hosts, trackers, team conventions and stop-lists belong in the caller's profile.

## Rules

- Nothing is visible to the MR author before Phase 4 and an explicit yes. **Never publish without an explicit yes.**
- Inline comments only on lines present in the diff (check with `in-diff`); otherwise stage a general note whose first line names `file:line`.
- Send one API request at a time. Handle 429 and 401 as in [`references/gitlab-api.md#errors`](references/gitlab-api.md#errors): back off on 429; on 401 check `glab api user`, and if the token fails, stop and ask the reviewer to log in again.
- Every comment follows [`references/comment-style.md`](references/comment-style.md): [structure](references/comment-style.md#structure), [markers](references/comment-style.md#markers), and it passes the [checklist](references/comment-style.md#checklist) before the reviewer sees it.
- Keep the state file (see [Resume](#resume)) current after every change of an item.
- Start a subagent only when the reviewer asks for one (the Brainstorm option or an explicit request).

## Phase 0 — Prepare

Work silently; report only problems.

1. Run `glab auth status --hostname <host>`. On failure, stop and ask the reviewer to log in.
2. Resolve the MR, save `mr.json`, `refs.json` and `mr.diff` to `<scratch>` as in [`references/gitlab-api.md#resolve-the-mr`](references/gitlab-api.md#resolve-the-mr).
3. List the reviewer's existing drafts on the MR ([`references/gitlab-api.md#draft-notes`](references/gitlab-api.md#draft-notes)). If there are drafts, or a state file for this MR exists in `<scratch>`, offer to resume (see [Resume](#resume)) before starting a new review.
4. Create the state file with `mr` and `diff_refs`.

✅ Check: `mr.diff` is stored, `base_sha`, `head_sha` and `start_sha` are known, and existing drafts are accounted for.

## Phase 1 — Review

1. Read the whole diff and the requirements from the profile source.
2. Look for bugs and contradictions with the requirements, dead code, names that do not match their content, side effects, and violations of the profile `conventions`.
3. Verify every finding with evidence: search the source branch, compare with the target branch, read the requirement. A finding you cannot verify is marked *uncertain*, and its comment asks the author to double-check instead of asserting.
4. For each inline finding, get its new-side line with `new-line` and confirm it with `in-diff`. An empty result means a general note; more than one number means pick by context.
5. Record each finding in the state file as an item with `status: "pending"` and its drafted `text`.

✅ Check: every finding has a `file:line` (or is a deliberate general note) and named evidence.

## Phase 2 — Summary

Show a short list ordered by severity, one line per item:

- 🔴 must fix before merge, 🟠 should fix, 🟡 non-blocker;
- each line tagged *inline* or *general note*;
- then requirement coverage, for example which listed cases have tests and which do not.

The reviewer may drop items here; mark them `skipped`.

✅ Check: the reviewer has seen the full list and the remaining items are numbered in the order they will be walked.

## Phase 3 — Approval loop

Walk the items one at a time. For each, show:

1. the gist in one line and the severity;
2. the target: `file:line` (inline) or *general note*;
3. the ready comment text, already passing the [checklist](references/comment-style.md#checklist) and the `stop_list` check.

Ask through the runtime's structured-choice prompt when one is available (otherwise a short numbered prompt), with one item per question and these options:

- **Yes**: build the payload and create the draft note immediately ([`references/gitlab-api.md#draft-notes`](references/gitlab-api.md#draft-notes)); record its `draft_id` and set `status: "drafted"` in the state file.
- **Edit**: apply the requested change, show the new version, ask again.
- **Brainstorm**: start one subagent with a focused question: the options for this point and a reusable pattern already in the repository, with `file:line`. Redraft from its answer, show it and ask again. Never publish the subagent's output directly.
- **Skip**: set `status: "skipped"`; nothing is staged.
- **Back to N**: return to item N. If it is already drafted and the reviewer changes it, delete that draft and stage a new one (drafts are not edited in place).

Never batch several items into one approval, and never treat silence or a general "looks good" as a yes for the remaining items.

✅ Check: every item is `drafted` or `skipped`, and every `drafted` item has a `draft_id` that appears in the draft list.

## Phase 4 — Publish

1. List the drafts on the MR and compare them with the state file.
2. Summarise for the reviewer: the drafted items (gist and target) and the skipped ones.
3. Ask once: "Publish all drafts now?" Only an explicit yes publishes. Otherwise leave the drafts staged and tell the reviewer they stay private until published.
4. On yes, publish in one batch and confirm the notes are visible ([`references/gitlab-api.md#publish`](references/gitlab-api.md#publish)).
5. Report the links to the new threads.

To change a note after publishing, follow [`references/gitlab-api.md#edit-a-note`](references/gitlab-api.md#edit-a-note), again only after the reviewer approves the new text.

✅ Check: every drafted item is visible as a thread on the MR, and no skipped item was published.

## Resume

The state file `<scratch>/mr-glab-review-<iid>.json` records the session:

```json
{
  "mr": "<url>",
  "diff_refs": {"base_sha": "...", "head_sha": "...", "start_sha": "..."},
  "items": [
    {
      "id": 1,
      "severity": "🔴|🟠|🟡",
      "target": {"path": "src/App.java", "new_line": 12},
      "status": "pending|drafted|skipped",
      "draft_id": null,
      "text": "**Gist** 🧹 ..."
    }
  ]
}
```

`target` is `null` for a general note; `draft_id` is set once the draft exists.

To resume an interrupted session:

1. Re-run Phase 0 steps 1–3. If the MR `head_sha` changed, re-download the diff and re-check every pending inline target with `in-diff`; drafts already staged keep their old position, so tell the reviewer which ones may need restaging.
2. Reconcile the state file with the listed drafts so nothing is duplicated: a `drafted` item whose `draft_id` is missing from the list goes back to `pending`; a listed draft with no matching item is shown to the reviewer, who keeps it (add it as a `drafted` item) or deletes it.
3. Continue Phase 3 from the first `pending` item.

Without a state file but with existing drafts, show the drafts and ask whether to keep them as already-approved items before reviewing again.
