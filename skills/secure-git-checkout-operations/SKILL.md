---
name: secure-git-checkout-operations
description: "Safely synchronize and update long-lived Git checkouts consumed directly by agents, services, configuration loaders, or automation."
---

# Secure Git Checkout Operations

## Overview

Use this skill for long-lived Git checkouts whose files are consumed directly by another process: shared agent skills, plugins, configuration repositories, deployment checkouts, documentation sources, or automation bundles. The core rule is that a fetched tree may be an approved update target without being safe to execute during synchronization.

Keep repository publication/review policy separate from consumer synchronization. Protected-branch CI may execute candidate tests and builds in its isolated environment; a local updater should perform only trusted, non-executable validation and exact fail-closed branch movement.

## When to Use

- A checkout is a source of truth for multiple tools or sessions.
- An agent/service reads files directly from a mutable `main` checkout.
- The user wants `fetch` + `ff-only` automation without overwriting local state.
- A sync helper validates fetched content before exposing it to consumers.
- Git hooks or fetched validation scripts could create a supply-chain execution path.
- Post-merge cleanup must preserve a stable consumer checkout while removing feature worktrees safely.

## Safety Model

1. Treat the configured upstream/default branch as an administratively trusted source only after repository review and CI policy are established.
2. Still treat the fetched tree as **non-executable data** during local synchronization.
3. Require a clean expected branch; reject detached, dirty, ahead, and diverged states.
4. Pin every decision to exact commit OIDs. Never validate one ref and move to a later mutable ref.
5. Preserve the current trusted validator before fetching or moving the branch.
6. Reassert the expected branch, original OID, and clean state immediately before movement; after movement require `HEAD` to equal the exact validated remote OID.
7. Disable Git hooks for controlled branch movement.
8. Repeat the exact-OID/branch/clean assertion after post-update validation before reporting success.
9. Keep active consumer reload semantics truthful; do not invent a hot-reload command.

## Standard Workflow

### 1. Establish a trusted publication path

Before automating consumer sync, require small reviewable PRs, current-head checks, privacy/secret scanning, and protected default-branch policy. Sync safety cannot compensate for an unreviewed or writable-by-everyone upstream.

### 2. Guard local state

- Resolve and verify the repository root.
- Require the expected default branch.
- Require an empty `git status --porcelain --untracked-files=normal`.
- Record the exact current commit.
- Refuse to stash, reset, or delete user work automatically.

### 3. Preserve trusted validation

Copy the current dependency-free structural/privacy validator to a private temporary directory. Use that same preserved file for current-tree, candidate-tree, and post-update validation. Running the fetched validator after branch movement is not equivalent: its behavior is controlled by the candidate.

### 4. Fetch and fence exact history

Fetch only the intended branch into its remote-tracking ref, resolve the exact commit, and require the local commit to be an ancestor. Equality is a no-op; local-ahead or divergence fails closed.

### 5. Inspect without execution

Export the exact fetched commit with `git archive` into a private temporary directory and run only the preserved trusted validator against it. Do not run fetched tests, shell scripts, package managers, build hooks, or documentation tooling on the host.

### 6. Fence and move without hooks

Immediately before movement, reassert the symbolic branch, original `CURRENT_OID`, and clean state. This closes the validation-window race where another process changes `main` while the candidate is inspected.

After candidate validation succeeds, perform the exact fast-forward with hooks disabled, for example:

```bash
git -c core.hooksPath=/dev/null merge --ff-only "$REMOTE_OID"
```

This prevents a fetched executable `post-merge` hook from running after the worktree changes.

### 7. Verify and hand off

Immediately require the expected branch, a clean checkout, and `HEAD == REMOTE_OID`. Run the preserved validator against the updated checkout, then repeat that exact-state assertion before reporting success. This matters because if another process moves `main` to a descendant of the fetched commit, `merge --ff-only "$REMOTE_OID"` can report “Already up to date” even though the checkout is not the validated exact revision.

Concurrent changes should produce failure, not an automatic destructive rollback of another process's work. Remove temporary data, print the exact SHA, and tell consumers to start a new session/process when authoritative documentation does not guarantee external-directory hot reload.

## Executable Candidate Validation

A temporary directory or detached worktree is not a sandbox. Candidate code executed there still inherits host credentials, network access, and writable mounts.

If executable candidate validation is mandatory, use a disposable sandbox with:

- no host credentials or secret environment;
- no writable host mounts;
- bounded CPU, memory, disk, and time;
- controlled/no network as appropriate;
- read-only candidate input and disposable output.

Prefer repository CI for tests, builds, linters, and full-history secret scanning. Keep the local sync helper non-executable whenever possible.

## Regression Requirements

Test with temporary bare remotes and clones, not mocked Git commands:

- successful exact fast-forward and updated remote-tracking ref;
- dirty and detached checkout rejection;
- local-ahead/diverged rejection;
- invalid candidate rejection before `HEAD` moves;
- concurrent movement after candidate validation to a descendant of the fetched commit: synchronization fails and never prints success;
- fetched script sentinel cannot write to the host;
- fetched executable `post-merge` hook cannot run even when `core.hooksPath` points at the tracked hook directory;
- final local `HEAD`, expected remote OID, and remote-tracking ref match;
- post-update trusted validation runs and temporary artifacts are cleaned.

## Post-Merge Feature Cleanup

For reviewed feature PRs merged by squash:

1. Re-read PR state and merge commit after the merge side effect.
2. Verify the reviewed head and squash-merge commit have identical trees.
3. Fast-forward the stable consumer checkout only if it is clean.
4. Re-run safe validation from the stable checkout.
5. Delete the remote feature branch, remove the temporary worktree, and force-delete the local feature ref only after merge/tree-equivalence/cleanliness are proven.

## Common Pitfalls

- Running candidate `validate.sh` because its name sounds trustworthy.
- Treating `mktemp`, `git archive`, or `git worktree` as process isolation.
- Using ordinary `git merge --ff-only` while tracked hooks can be replaced by the fetched commit.
- Validating a mutable branch name and then merging whatever it points to later.
- Checking the original OID only before candidate validation; a concurrent descendant can make `merge --ff-only` say “Already up to date” at an unvalidated `HEAD`.
- Updating the branch before candidate validation and attempting an automatic destructive rollback.
- Claiming `/reload-skills` or another reload command covers external directories without checking current authoritative documentation.
- Assuming green CI means every review surface is clear; inspect top-level comments, submitted review bodies, inline comments, and review threads on the exact head.

## Detailed Reference

See `references/fail-closed-shared-checkout-sync.md` for the command sequence, threat model, adversarial fixtures, and review lessons.

## Verification Checklist

- [ ] Expected repository, remote, branch, and root verified.
- [ ] Checkout clean, attached, and neither ahead nor diverged.
- [ ] Current trusted validator preserved before fetch/movement.
- [ ] Candidate exported and validated by exact OID without executing fetched code.
- [ ] Expected branch, original OID, and clean state rechecked immediately before movement.
- [ ] Fast-forward pinned to the same OID with hooks disabled.
- [ ] Exact remote OID, branch, and clean state asserted immediately after movement and after preserved-validator execution.
- [ ] Fetched-script, fetched-hook, and concurrent-ref-movement regressions pass.
- [ ] Resulting SHA and remote-tracking ref verified.
- [ ] Consumer reload/new-session guidance matches authoritative docs.
- [ ] Temporary worktrees/files and credentials cleaned safely.
