---
name: skill-review
description: Review reusable lessons and propose safe skill changes.
---

# Skill Review

Use this skill after significant work to decide whether a reusable lesson belongs in the shared skill library. The output is a reviewed candidate, not an automatic publication.

## When to run

Run a review when at least one condition is true:

- A non-trivial workflow succeeded and would save time in future tasks.
- An error required multiple attempts, investigation, or a workaround worth preserving.
- The user corrected the approach and the correction generalizes beyond the current task.
- An existing skill was used but its instructions were missing, stale, or misleading.
- Several tasks exposed the same repeatable pattern.

Skip the review for routine edits, obvious commands, one-off facts, temporary task state, generated logs, or results that will become stale quickly.

A candidate may also arrive already staged, from tooling rather than from a live conversation — the `skill-promotion-queue` harness stages one when an installed skill has diverged from its hub revision, and again when a never-triggered skill accumulates enough evidence to be questioned. Review those exactly like a hand-written candidate: a staged file is not a decision, and its pre-filled sections are a starting point to verify, not findings to accept. Machine-staged candidates carry the diff that triggered them, so classify each hunk before proposing anything — a genuine improvement worth promoting, a machine-local or task-specific edit that must never reach the hub, or drift to revert.

## Non-negotiable boundaries

- Never publish directly to `main`.
- Never turn a transcript, memory, user profile, or project-specific rule into a public skill.
- Never copy a locally generated skill into this repository without review and redaction.
- Never include credentials, identities, account data, private URLs, infrastructure addresses, client context, or machine-specific paths.
- Never treat scanner success as proof that content is safe to publish.
- Never mutate a shared external skill directory as a shortcut. In Hermes, `external_dirs` are writable when filesystem permissions allow it; use a Git branch or worktree for shared changes instead of editing through `skill_manage`.
- Never create a branch, push, open a pull request, or merge solely because a review was triggered. Obtain task-specific approval before promotion unless the repository owner has already declared a durable, repository-scoped opt-in policy. A durable opt-in may authorize a draft queue, but never direct-to-main publication or automatic merge.

Follow the repository's `SECURITY.md` whenever the candidate may enter a public repository.

## Review flow

### 1. Classify the lesson

Decide where the knowledge belongs:

- User preference or stable personal fact -> private memory, not a skill.
- Project-specific convention -> the relevant project repository, not this shared library.
- Temporary progress or completed-task record -> session history or task tracking, not a skill.
- Reusable procedure with clear triggers, steps, pitfalls, and verification -> skill candidate.

Stop when the lesson does not qualify as a reusable procedure.

### 2. Search before proposing

Inspect the available skill index and the shared repository before writing anything. Use the environment's native discovery tools, such as a skill list, skill view, or repository file search.

Choose one outcome:

- `patch-existing` when an installed skill already owns the workflow;
- `create-new` when the workflow is reusable and no suitable owner exists;
- `no-change` when the lesson is too narrow, duplicated, private, or temporary.

Prefer extending a broad existing skill over creating a micro-skill for one incident.

### 3. Build a private candidate

Use `templates/candidate.md` as the review structure. Keep the candidate outside the shared repository until it is approved for promotion. If the environment has no private staging area, present the candidate inline instead of writing it into the repository.

A candidate must contain:

- the reusable trigger;
- the generalized procedure or exact patch intent;
- pitfalls and failure modes;
- verification steps;
- the proposed target skill or new skill name;
- a privacy and portability audit;
- evidence summarized without raw transcripts or sensitive source material.

Use placeholders such as `<repository>`, `<project-root>`, and `<secret-file>` rather than real values.

### 4. Review the candidate

Check all of the following before recommending promotion:

1. The trigger describes a class of tasks, not one completed task.
2. The procedure is reproducible and does not invent commands or tools.
3. Existing skill instructions are not duplicated or contradicted.
4. Examples are fictional, portable, and free of private context.
5. Required tools, prerequisites, pitfalls, and verification are explicit.
6. The candidate is small enough to review and maintain.
7. The candidate satisfies `SECURITY.md` and the target repository's contribution rules.

If any check fails, revise the private candidate or choose `no-change`.

### 5. Present the decision

Report only the information needed for a decision:

- outcome: `patch-existing`, `create-new`, or `no-change`;
- target skill and why it is the correct owner;
- reusable lesson captured;
- sensitive details removed or generalized;
- proposed files and validation;
- any remaining uncertainty.

Ask the user whether to promote the candidate unless a durable repository-scoped opt-in already authorizes the applicable draft queue. Do not imply that the change was published when it was only drafted.

### 6. Promote through Git review

After task-specific approval, or after verifying an applicable durable opt-in:

1. Update from the current shared `main`.
2. Create an isolated branch or worktree.
3. Apply only the approved skill and documentation changes.
4. Review the complete diff, including untracked files.
5. Validate frontmatter, links, referenced files, and any bundled scripts.
6. Run repository checks and full-history secret scanning.
7. Commit with a Conventional Commit message.
8. Push the branch and open a focused pull request with the security checklist completed.
9. Leave merge to the repository's normal review policy.

When the opt-in selects a rolling draft queue, load `skill-promotion-queue`, use the lane worktree, and stop after the draft PR is created or updated. The opt-in may defer independent review, but it does not waive privacy, portability, deterministic validation, or secret scanning.

If validation exposes private data, remove it from the candidate and branch before pushing. If a real credential was committed, rotate it and follow `SECURITY.md`; deleting the latest file is not sufficient.

## Environment notes

### Claude Code

Use installed skill discovery and file tools for the review. Keep the candidate local until approval, then use the target repository's branch and pull-request workflow.

### Codex

Follow project-local `AGENTS.md` instructions first. Keep the default review compact: targeted skill search, one candidate, validation, and a decision request.

### Hermes

Use `skills_list` and `skill_view` to discover existing skills. New private candidates may be created in the local Hermes skill area only after the normal user confirmation required by Hermes skill management. Shared repository updates must use a Git branch or worktree; do not patch a writable `external_dirs` checkout in place.

## Completion criteria

A review is complete when it ends in one of these states:

- `no-change` with a short reason;
- an approved private candidate awaiting promotion;
- a validated branch and pull request awaiting normal review.

A direct write to public `main` is never a completion state.
