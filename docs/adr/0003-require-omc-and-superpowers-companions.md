---
title: "ADR-0003: Require oh-my-claudecode and superpowers companions"
---

# ADR-0003: Require oh-my-claudecode on Claude Code and superpowers on every runtime

- Status: accepted
- Date: 2026-10-20

## Context

The adapters assumed one orchestration layer but never named it. `orchestrator-workflow` deferred to Everything Claude Code (ECC) whenever a target repository used it, and the shared base carried ECC-derived defaults: an 80 percent coverage target, fixed function and file size limits, immutability as a default, and a Java-specific nullability rule. On a machine where oh-my-claudecode supplies the agents, ECC role names such as `tdd-guide`, `doc-updater`, and `docs-lookup` do not resolve, so the guidance pointed at roles that did not exist and competed with the catalog that did.

Superpowers supplies process discipline — brainstorming, test-driven development, systematic debugging, verification before completion — on both Claude Code and Codex CLI. Nothing checked that it was installed, so a missing plugin failed silently: the agent reconstructed the workflows from memory or skipped them.

## Decision

- Claude Code requires oh-my-claudecode. It owns the agent catalog, model routing, and the plan, execute, review, and verify workflows on that runtime.
- Every runtime requires superpowers. Its skills are the discipline applied inside each orchestration step; when both companions offer a workflow for the same step, oh-my-claudecode drives orchestration and superpowers supplies discipline.
- A shared `SessionStart` hook, `sessionstart-prerequisites.sh`, checks the companions for its runtime and tells the agent to stop and report a missing one before substantive work. `scripts/bootstrap.sh` prints the same result as non-fatal warnings.
- ECC is no longer a role or rule source. The skills adapted from ECC stay, with attribution, because they are standalone and do not depend on an ECC installation.

## Alternatives considered

- **Keep ECC as the preferred role catalog.** Rejected: two catalogs with overlapping role names produce unresolvable delegations, and ECC's coding-style defaults override project conventions.
- **Fail the installer when a companion is missing.** Rejected: companions are installed through each runtime's own plugin flow, which may happen after the hub is installed. The session hook enforces the requirement where the agent actually works.
- **State the requirement in prose only.** Rejected: the requirement is mechanically checkable, and the repository's rule is that checkable rules become hooks.

## Consequences

- The public adapters are now opinionated about two third-party companions. A reader who does not use them must opt out with `SKILLS_HUB_SKIP_HOOKS=prerequisites` and override the instruction in a private overlay.
- Detection relies on installation markers — the oh-my-claudecode `CLAUDE.md` block, enabled plugin entries, the `omc` CLI, a superpowers skill directory. A companion installed some other way reads as missing until the hook learns that marker.
- Removing the ECC-derived defaults means coverage targets and size limits now come from each project rather than the global base.
