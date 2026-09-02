---
name: harness-health-doctor
description: Diagnose a skill-improvement publishing harness end to end - installation, hook registration, tracked Git hooks, forge provider, lane worktree, and the rolling draft queue - and report what is broken without changing anything. Use when publication silently stops working, a completion gate blocks or fails to block, a machine is set up for the first time, or a GitHub-only harness is running on a GitLab machine.
---

# Harness Health Doctor

Use this skill to prove whether a lane-based skill-improvement publishing harness is actually working on the current machine, and to explain any failure in terms of the step it breaks.

The check is **read-only**. It never writes a file, moves a ref, pushes, or repairs anything. Diagnosis and repair stay separate so a broken harness is never "fixed" by a side effect nobody reviewed.

## What the harness is

A publishing harness has five moving parts, and a fault in any one of them is silent:

| Part | Location | Failure symptom |
| --- | --- | --- |
| Scripts | `~/.claude/skill-harness/` | `publish.sh` not found or not executable |
| Machine config | `config.env` beside the scripts | Hooks become unconditional no-ops |
| Hook registration | `settings.json` under the Claude config directory | The completion gate never runs |
| Tracked Git hooks | `core.hooksPath` in each checkout | Unvalidated commits reach the queue |
| Lane worktree | Path from `config.env`, branch `automation/skill-improvements/<lane>` | Publication refuses to run |

`config.env` is machine-local and never committed. Every path in this skill is derived from it, so nothing here assumes a particular account, home directory, or operating system.

## When to run it

- A new machine was set up as a publishing lane.
- Work finishes but nothing ever reaches the draft queue.
- The completion gate blocks repeatedly and the reason is unclear.
- The completion gate stopped blocking and queued work is going unnoticed.
- A machine that uses GitLab started behaving strangely at the end of tasks.
- Before trusting `publish.sh` after any change to hooks, config, or checkout layout.

## Run the check

```
bash skills/skill-management/harness-health-doctor/scripts/harness_doctor.sh
```

Add `--offline` to skip provider commands that reach the network. Exit status is `0` healthy, `1` warnings, `2` critical.

Read the report top to bottom. The sections follow the publication pipeline, so the first failing section is the one to fix — later sections often fail only as a consequence.

## Interpreting each section

### Installation

`completion_gate.sh`, `publish.sh`, and `skill_cycle.sh` are invoked as programs and must be executable. `publish_queue.py` is run as `python3 publish_queue.py`, so it is a library file: **do not treat a missing executable bit on it as a fault.** Requiring `+x` there is a common false positive.

A missing `config.env` is critical rather than cosmetic. The completion gate sources it and exits early when it is absent, so an uninstalled config does not produce an error - it produces silence, and queued work stops being noticed.

### Hooks

Read every settings file the runtime merges, not just `settings.json` — a hook registered in `settings.local.json` is live, and reporting it as missing sends the operator to re-register a hook that already exists.

A hook event holds a *list of groups*, each with its own `hooks` list. Several unrelated tools commonly register under the same event. Search every command string in every group for the harness script name; checking only the first group reports a correctly registered hook as missing.

- No Stop hook: nothing holds task completion on an unsettled queue. Work accumulates and is never published.
- No SessionStart hook: the maintenance cycle never runs, so upgrade and prune candidates are never staged.
- Invalid JSON: **every** hook silently stops running, not just the harness ones. Treat it as critical.

### Git configuration

`core.hooksPath` must be set in both the main checkout and the lane worktree - a worktree does not inherit it. When it points at a directory that does not exist, every commit and push from that checkout fails outright, which is a harder failure than having no hooks at all.

Check `pre-commit` and `pre-push` for presence *and* the executable bit. A present-but-non-executable hook is skipped by Git without an error, so validation silently disappears.

### Provider detection

The harness is GitHub-only: the publisher drives `gh`, and the completion gate asks `gh` whether a draft PR exists. Distinguish four states, because they need different remedies:

| `gh` | `glab` | Meaning |
| --- | --- | --- |
| authenticated | - | Normal operation. |
| installed, not authenticated | - | Publication fails at push time. Run `gh auth login`. |
| absent | - | `publish.sh` cannot run at all. |
| not authenticated | authenticated | **Provider conflict - see below.** |

#### Provider conflict: GitLab machine, GitHub harness

When `glab` is the authenticated provider and `gh` is not, but the harness hooks are still registered, the two workflows fight:

- The Stop hook blocks task completion waiting for a GitHub draft PR that can never exist.
- `publish.sh` fails because the publisher has no GitLab path.
- The lane branch is a GitHub-shaped artifact inside a GitLab-centric workflow.

There is no supported GitLab publication path, and no flag that converts the harness. Disable it on that machine, by either route:

1. **Unregister the hooks** - remove the `completion_gate.sh` Stop hook and the `skill_cycle.sh` SessionStart hook from `settings.json`. This is the explicit, readable option.
2. **Remove the machine config** - rename or delete `config.env`. Both hooks then exit early as unconditional no-ops.

Prefer route 1 when the machine should never publish, and route 2 when the harness may be re-enabled later. Do not invent a Git configuration key to suppress this; no such setting exists, and searching for one wastes time on a problem whose real cause is that the machine is on the wrong forge.

When both providers are authenticated there is no conflict - the harness uses GitHub for the lane queue and leaves `glab` alone.

### Lane status

The publisher is fail-closed and refuses to run unless all of these hold. Check each one, because each produces a different remedy:

- The worktree exists and the command runs from the worktree root.
- `HEAD` is a symbolic ref on `automation/skill-improvements/<lane>`, not detached.
- The working tree is clean, including untracked files.
- `origin` is exactly the configured repository. Accept both remote forms - `https://github.com/<owner>/<repo>[.git]` and `[user@]github.com:<owner>/<repo>[.git]` - and compare case-insensitively.
- The remote lane branch, when it exists, is an **ancestor** of local `HEAD`.
- The lane has at least one commit ahead of the default branch.

Check cleanliness *before* and independently of resolving the base branch. A dirty tree is the most common refusal and does not depend on the base at all; nesting it under base resolution means an unresolvable base hides the real problem.

Two Git details cause confident wrong answers here. `git rev-parse <name>` echoes an unresolvable name back on stdout and signals failure only through its exit status, so a deleted remote branch reads as a valid hash unless you pass `--verify --quiet`. And a remote-tracking ref is a local cache: a read-only checker must not fetch, so it can be reporting on a branch that no longer exists. Treat a non-ancestor remote as a *warning* that names both possibilities - a genuinely diverged branch, or a stale ref - and ask for a `git fetch --prune` before acting. Publication itself fetches first, and proceeds normally when the remote branch turns out to be gone.

Distinguish "unpublished" from "diverged". A local head that differs from the remote lane branch has two causes: commits not yet pushed, which `publish.sh` resolves, and a rebased or amended lane whose remote is no longer an ancestor, which `publish.sh` **refuses** because it never force-pushes. Advising a publish for the second case sends the operator into a failure they cannot fix by rerunning.

#### Resolving the base branch

The publisher asks the forge for the live default branch and **ignores** `SKILL_HARNESS_BASE`; only the completion gate honours that override. The two components can therefore disagree. Resolve the base from the forge when authenticated, fall back to the local `origin/HEAD` and then to `origin/main`, and report a configured override that disagrees rather than silently choosing one. Assuming `origin/main` on a repository with a different default reports the queue as empty and skips every downstream check.

When the base ref is not present locally, say the ahead/behind and path checks are *unavailable*. Do not let an unset count read as zero - that turns a lane full of unpublished work into a confident "queue is empty".

#### Queued paths

The publisher accepts only `skills/`, `docs/`, `tests/`, `scripts/`, `adapters/`, and a small set of allowed root files. It additionally rejects any path containing a private component **at any depth** - among them `.env`, `.git`, `.secrets`, `auth.json`, `credentials.json`, `memory.md`, `sessions`, `transcripts`, and `user.md`. Checking only the first path segment passes `skills/<name>/memory.md` and `docs/sessions/notes.md`, which then fail publication after the work is already committed.

"Behind the base branch" is informational, not a fault: rebase before queueing new work.

### Validation toolchain

The tracked `pre-push` hook runs the repository's *full* validation and the publisher runs its CI equivalent. Both are fail-closed: when a pinned tool is missing they refuse to run rather than skipping the check. The practical effect is that a missing tool blocks every push and every publication from that checkout, with an error that names the tool rather than the harness.

Confirm `python3` for structural validation, `zensical` or `uvx` for the documentation build, and `gitleaks` (or a `GITLEAKS_BIN` override) for the secret scan. This is the check most often missed on a freshly provisioned machine, because every other section can be green while nothing can be pushed.

### Forge status

With the forge authenticated, confirm the repository is reachable and that the lane has **exactly one** open pull request, that it is still a draft, and that it targets the default branch.

Query *all* open pull requests for the head, not only drafts. Filtering to drafts before counting hides two real refusals: one draft alongside one non-draft reads as a healthy single draft, and a lone pull request that left draft reads as "no PR", producing advice to publish that fails with "no longer a draft".

| Observed | Meaning |
| --- | --- |
| No open PR, queue empty | Expected. Not a fault. |
| No open PR, queue has commits | The work is unpublished. |
| One draft, default base | Healthy. |
| One PR, no longer draft | Publication refuses to update it. |
| One draft, non-default base | Publication refuses to update it. |
| More than one open PR | Breaks the rolling-queue contract; reduce to one by hand. |

Never convert the queue PR out of draft and never merge it as part of a health check.

## Known failure mode: validation that passes by hand and fails on push

When the tracked `pre-push` hook runs the repository's test suite, that suite inherits Git's hook environment - `GIT_DIR`, `GIT_INDEX_FILE`, and the author/committer variables are all exported. Any test that creates a throwaway repository and commits into it then operates against the *pushing* repository instead of its own fixture, and fails.

The signature is unmistakable and easy to misread:

- `scripts/validate.sh` and the test suite pass when run by hand from the same checkout.
- The identical suite fails during `git push` with errors inside fixture setup, typically a non-zero `git commit` in a temporary directory.
- Publication stops at `failed to push some refs`, so the queue never reaches the draft PR.

This is a defect in the hook, not in the harness, the lane, or the change being pushed. Confirm it by re-running the suite with `GIT_DIR` set to the checkout's git directory - if it now fails the same way, the diagnosis is settled. The fix belongs in the hook: clear the inherited Git environment (`unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE`, and the author/committer overrides) before invoking validation, so the suite runs in the same environment a developer does.

Never work around this by pushing with `--no-verify`. That skips the full validation and secret scan the public repository depends on, to route around a bug that takes one line to fix.

## Safety requirements

- Diagnose only. Any repair is a separate, explicitly approved action.
- Redact the home directory from printed paths so a report can be pasted into an issue or chat.
- Never source `config.env` into the reporting scope. It is arbitrary shell, and a key that collides with the checker's own state - its status level, its accumulated warnings, its output symbols - silently rewrites the report and the exit code. Read it in a subshell and import only the harness keys.
- Treat every `config.env` key as optional when reading it. A strict-mode expansion of a missing key aborts the check, and inside a Stop hook that turns a diagnostic into a broken session.
- Do not report a healthy harness because no check failed. An absent config or absent hooks produce silence, which is exactly what a working system looks like from the outside.
- Run provider queries against the lane checkout explicitly. A forge CLI invoked without a repository argument resolves whatever project the operator's shell happens to be sitting in, and reports on the wrong repository with full confidence.
- Never suppress a provider conflict by disabling validation gates that protect the public repository.

## Related

- `skill-promotion-queue` - the publication workflow this skill diagnoses.
- `skill-review` - deciding what belongs in the queue in the first place.
- `repository-quality-gates` - the tracked hooks and validators the lane must satisfy.
