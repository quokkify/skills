---
name: skill-promotion-queue
description: Use when a repository owner has explicitly authorized completed, public-safe skill improvements to be accumulated automatically in a rolling draft pull request without per-change review or automatic merge.
---

# Skill Promotion Queue

Use this workflow only after the repository owner has explicitly opted into automatic draft-PR publication for a named repository and agent lane. It turns completed skill improvements into a reviewable batch without publishing runtime-local state or merging automatically.

## Contract

A queue lane owns one branch and at most one open draft pull request:

```text
automation/skill-improvements/<lane>
```

Use a different lane for each device or independently running agent. A lane may collect several related skill improvements. The repository owner reviews and merges the batch later.

The opt-in authorizes branch push and draft-PR creation or update. It does **not** authorize:

- direct writes or pushes to the default branch;
- automatic merge or conversion from draft to ready;
- force-push, history replacement, or conflict guessing;
- publication of local skills merely because they changed;
- bypassing privacy, portability, repository validation, or secret scanning.

## Trigger

Queue an improvement at the end of a task when all of these are true:

1. A reusable skill, support file, adapter, validation rule, or associated documentation was actually improved.
2. The implementation and deterministic checks succeeded.
3. The repository owner has a durable opt-in for this repository and lane, with no task-level opt-out such as “local only” or “do not publish.”
4. The diff is appropriate for the public repository after a privacy and portability audit.
5. The change already lives in the lane worktree, not in the stable default-branch checkout or a runtime-local skill directory.

Do not trigger for exploratory drafts, failed experiments, raw transcripts, memory, user profiles, client or private-project conventions, credentials, account data, private URLs, machine-specific paths, or evidence that has not been generalized.

## Workflow

### 1. Enter the lane worktree

Use a persistent isolated worktree for the lane. Fetch the default branch before editing. If the remote lane already exists, fast-forward the local lane from it before making changes. If the default branch moved, merge it without rewriting the lane; stop for real conflicts.

Never reuse one lane concurrently on two machines. Device-specific lanes avoid cross-machine force-pushes and lock ambiguity.

### 2. Apply the smallest reusable change

Search the catalog before creating a skill. Prefer patching the existing class-level owner over creating a micro-skill. Keep examples fictional and portable. Add tests for executable helpers and regression-prone rules.

Do not copy a runtime-local skill tree wholesale. Recreate only the generalized public artifact in the lane worktree.

### 3. Validate before publication

At minimum:

- inspect tracked and untracked changes;
- run the repository's CI-equivalent validator and tests;
- verify the exact clean commit that will be pushed;
- run the repository's configured secret-scanning gate locally when available and always leave CI secret scanning enabled.

Independent model review may be deferred by the opt-in policy. Deterministic validation and the public/private boundary may not be deferred.

### 4. Commit and publish the queue

Create a Conventional Commit and leave the worktree clean. Run the bundled helper from the repository root:

```bash
python3 skills/skill-management/skill-promotion-queue/scripts/publish_queue.py \
  --repository <owner/repository> \
  --lane <device-or-agent-lane> \
  --title "feat(skills): queue reusable skill improvements"
```

The helper fails closed unless the current branch matches the lane, the tree is clean, the branch is ahead of the fetched default branch, changed paths stay inside the public skill-library boundary, validation succeeds against an unchanged `HEAD`, and any existing remote lane is an ancestor. It never force-pushes or merges.

If a draft PR for the lane exists, the helper updates it. Otherwise it creates one. Do not wait for or perform independent review unless the user requests it; report the draft PR URL and current CI state.

### 5. Resolve exceptional states explicitly

Stop rather than guessing when:

- the user opts out for the current task;
- the candidate contains private or project-specific material;
- the lane is active on another machine;
- the remote lane is not an ancestor of local `HEAD`;
- validation fails or `HEAD` changes during validation;
- the existing pull request is no longer a draft;
- the default branch or queue has merge conflicts;
- credentials are unavailable or repository identity is uncertain.

## Harness Guidance

A completion hook may enforce this workflow by returning a continuation instruction when a queue worktree is dirty or has unpushed commits. The hook should not publish by itself: lifecycle hooks do not understand whether content is reusable or public-safe, and hook failures are observer failures rather than transaction failures.

Keep the semantic decision in the agent workflow and the mechanical publication in the deterministic helper. This separates intent classification from credentials and Git side effects.

For another machine or runtime, start with `templates/local-agent-bootstrap.md`. Give every independently operating device a different lane.

### Reference Claude Code harness

`templates/` holds a runtime-generic reference implementation for Claude Code. Every script reads its locations at runtime from a machine-local `config.env` and contains no machine paths or secrets, so the same files install unchanged on every device.

| Script | Hook | Role |
|---|---|---|
| `completion_gate.sh` | Stop | Holds completion while the lane queue is unsettled. Also carries non-blocking advisories. |
| `publish.sh` | — | Thin wrapper around `scripts/publish_queue.py`. `--target primary\|secondary`. |
| `skill_upgrade.sh` | — | Stages an upgrade candidate per skill whose installed `SKILL.md` diverged from the hub. |
| `skill_prune.sh` | — | Verdict report for never-triggered skills. Deletes nothing on its own. |
| `skill_cycle.sh` | SessionStart (async) | Chains the three above on a cadence. Silent, always exits 0. |

Install them on a machine with:

```bash
bash skills/skill-management/skill-promotion-queue/scripts/install-harness.sh \
  --repo <owner/repository> --lane <unique-lowercase-device-lane> \
  --worktree <absolute-path-to-lane-worktree> --main <absolute-path-to-stable-main-checkout>
```

The installer copies the scripts and the canonical publisher into the Claude configuration directory, seeds `config.env` from `templates/config.example.env` without overwriting an existing one, and idempotently registers both hooks in `settings.json`. The per-machine lane and any HTTPS credentials stay local and are never copied between machines, so synchronizing devices means reinstalling the same portable scripts, not sharing local state.

`SKILL_HARNESS_REPO` must equal the worktree's `origin` URL exactly. The publisher compares them as strings and fails closed on any difference — GitHub's legacy redirect for a transferred or renamed repository does not satisfy the check, so a repository move requires updating both the remote and `config.env` together.

### Automated intake

`skill_upgrade.sh` and `skill_prune.sh` are an automated feed into the same review pipeline the `skill-review` skill drives by hand. They only ever *stage* proposals in the private candidate directory; the semantic decision and the approval stay with the agent and the owner.

Both read a machine-local health signal (`state.tsv`: one row per installed skill with its usage count, checksums, hub path, and `in-sync` / `stale` / `local-only` state). That collection layer belongs to the `shared-skill-library-maintenance` skill and is deliberately not shipped here — without it both scripts no-op with an explanatory message instead of failing.

The two checksums cover the **whole skill directory**, not just `SKILL.md`. A skill's behaviour often lives in the files beside its entry point, so a digest over `SKILL.md` alone reports a skill as in-sync while its bundled scripts have diverged — the divergence is real, invisible, and grows. Any collection layer feeding this signal must digest every file in the skill directory, excluding only generated noise such as `.DS_Store` and `__pycache__`. Both write paths follow the same rule: the upgrade candidate carries a recursive diff that names added and deleted files, and `--adopt` replaces the entire directory so a file deleted locally is also dropped from the hub copy.

The usage count has a blind spot that no amount of waiting closes. It records `Skill` tool invocations, so a skill whose working surface is a bundled executable — run directly, never through the tool — stays at zero uses forever. `skill_prune.sh` therefore holds any skill that ships a runnable file — anything executable, `.sh`, or `.py`, in `scripts/`, `templates/`, or anywhere else beside the entry point — at `keep-unobservable-usage`, and never counts its silence as evidence of disuse. Absence of use is evidence only where use would have been observable.

Two write paths exist, and each requires an explicit flag, never a cadence run:

- `skill_upgrade.sh --adopt <skill>` replaces the hub copy of the whole skill directory with the installed one inside the lane worktree and commits it, including files added and deleted locally.
- `skill_prune.sh --apply` removes `prune`-verdict skills from the hub copy inside the lane worktree and commits the removal.

Neither pushes. Both refuse a dirty lane, a lane on the wrong branch, and any path outside the lane worktree. `skill_prune.sh` additionally enforces a hard-coded keep list that `--apply` re-checks, so a core skill cannot be removed even if a verdict is wrong.

## Completion Criteria

- The reusable change is committed on the correct lane branch.
- The exact committed snapshot passes deterministic validation.
- The remote lane equals local `HEAD` after a non-force push.
- Exactly one open draft pull request exists for the lane.
- The PR body records the current head, commits, changed paths, validation, and deferred-review policy.
- No review or merge was performed unless separately requested.
