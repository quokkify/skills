---
name: shared-skill-library-maintenance
description: "Structure, migrate, review, and maintain a shared cross-agent skill repository with portable skills and thin tool adapters."
---

# Shared Skill Library Maintenance

## Overview

Maintain one canonical portable skill library without turning tool-specific discovery paths, global agent state, or project configuration into competing sources of truth.

## When to Use

- Reorganizing a skill repository into `skills/`, adapters, docs, and tooling.
- Deciding whether `.claude`, `.agents`, `.codex`, or Hermes-specific files belong in source control.
- Migrating existing skills or configuration while preserving discovery and safe update behavior.
- Reviewing a public shared library for project-specific assumptions or duplicated agent personas.

## Ownership Classification

Classify content before moving it:

1. **Portable workflow** → canonical `skills/<category>/<name>/SKILL.md` with support files inside that skill.
2. **Thin integration** → `adapters/<tool>/` only when a tool requires configuration that cannot be expressed as a portable skill.
3. **User-owned state** → global personas, model routing, status lines, output styles, and personal commands stay outside the shared repository.
4. **Project-owned state** → stack, modules, package names, domain paths, and repository-specific instructions stay in the project that owns them.

Tool-specific syntax alone does not justify publishing an adapter. Do not create equivalent Claude, Codex, and Hermes copies merely for symmetry.

## Workflow

1. Inventory tracked files, install scripts, discovery paths, docs, validators, and tests.
2. Inspect content—not only directory names—for frontmatter tools/models, installer targets, hard-coded stacks, modules, packages, and private context.
3. Choose one canonical skill directory and document official consumer discovery paths separately.
4. Move only portable skills and genuinely thin adapters. Delete or leave out legacy global/project-owned bundles rather than blessing them through a mechanical rename.
5. Update validators to enforce the canonical layout and reject legacy skill roots, nested grouping drift, symlinks, and public-boundary violations.
6. Update install scripts and tests so they exercise only adapters that still exist.
7. Search the full tree for retired installer names, old paths, project identifiers, and stale migration claims. Also audit semantic capability claims: documentation must not say an adapter prompts, routes, installs, or auto-runs behavior that the surviving adapter does not implement.
8. Trace dependency closure through every canonical `SKILL.md` and support file: removed personas, global directories, model tiers, and tool names must not remain mandatory. Express delegation by capability and provide a bounded direct fallback when a supported backend lacks native subagents.
9. Verify current tool and API terminology against authoritative documentation. Use the current name in instructions and mention a legacy alias only when it remains relevant for compatibility.
10. Verify real discovery with each available agent CLI or a documented equivalent, then run repository tests, docs build, shell checks, and secret scans.
11. Review the final exact commit and treat automated findings on content-identical moves as pre-existing unless the migration changes ownership or exposure. Fix newly exposed privacy/portability problems instead of hiding behind rename equivalence. After a finding-driven patch, re-review the new exact head for dependency leftovers rather than assuming the targeted edit closed the class of issue.

See [`references/adapter-boundary-checklist.md`](references/adapter-boundary-checklist.md) for the detailed classification and migration checklist. After merge, follow [`references/post-merge-discovery-migration.md`](references/post-merge-discovery-migration.md) to synchronize the stable checkout, preserve typed consumer configuration, verify discovery from a fresh process, and clean temporary branches safely.

## Migration Rules

- Preserve safe-sync trust properties: validate an exact fetched revision with trusted code, do not execute fetched scripts, disable hooks during ref movement, and detect races.
- Verify whether existing discovery roots scan recursively before declaring a mandatory configuration migration.
- Use release semantics that surface user-visible path changes; for pre-1.0 libraries, a feature/minor release can carry a breaking layout migration when that is the documented policy.
- Keep README concise: purpose → canonical structure → setup per agent → safe sync → contribution/security. Put detailed rationale in guides.

## Library Health And Selection

A capture-and-promote loop grows a library; keeping it useful over time needs a selection signal and a recurring consolidation pass, not just more entries.

- Use a lightweight usage signal as a maintenance input: whether a skill was triggered and whether the task it supported succeeded. Collect this in the consuming runtime, never in the shared repository.
- Classify each skill periodically: frequently useful → keep; never triggered or low value → prune candidate; overlapping or narrow → merge into a broader umbrella skill. Prune on low value plus duplication, not on raw frequency alone, and require review before removal so a rarely used but critical skill is not lost.
- Run a scheduled library-health pass (for example weekly or per sprint) together with `repository-quality-gates`: dedupe, merge micro-skills, retire stale entries, and re-verify frontmatter, links, and referenced files.
- Keep signal collection and scheduling in each runtime's own configuration. Only the decision procedure and cadence are portable; telemetry wiring, cron or scheduler definitions, and concrete paths must stay out of the shared repository.

### Signal shape and automated intake

Give the local collector a machine-readable output beside its human report, so the maintenance pass reads a contract instead of re-deriving state or scraping markdown. One row per installed skill is enough: name, usage count, checksum of the installed skill file, resolved upstream path, upstream checksum, and a state of `in-sync`, `stale`, or `local-only`.

That signal turns two of the classifications above into scripted intake, which the `skill-promotion-queue` harness implements as `skill_upgrade.sh` (stale → upgrade candidate) and `skill_prune.sh` (never triggered → prune verdict with evidence). Both only stage proposals; every removal or promotion still needs explicit approval.

Two guards matter more than the heuristics, because an absent signal is not evidence of disuse:

- Compare against the signal's own history, not just the current date. A usage log that has only existed for two weeks cannot support a "unused for 30+ days" claim about anything.
- Compare against how long the skill has actually been installed. A skill synced yesterday has had no chance to be triggered.

When either guard fails, the correct verdict is "keep, insufficient evidence" — not "prune". Report duplication with the evidence that produced it (which skill it overlaps and by how much) so a reviewer can disagree with the measurement rather than only with the conclusion.

Compare checksums against the upstream revision you actually intend to match. Comparing against a local checkout that has drifted behind its remote reports "in sync" when it means "matches my stale copy"; state the checkout's position in the report so the number is interpretable.

## Pitfalls

- Mechanically moving every legacy tool directory into `adapters/`.
- Treating role personas as portable skills.
- Publishing global configuration that overwrites a user's existing setup.
- Preserving private project assumptions because they were already public.
- Adding dot-directories as duplicate sources of truth instead of consumer-side discovery targets.
- Claiming an integration breaks without checking the current implementation's recursive discovery behavior.
- Updating tests to validate a legacy installer that should have been removed.
- Deleting personas or adapters without removing mandatory role, model, tool, and fallback-directory references from canonical skills.
- Calling a workflow portable while it requires one harness's delegation primitive or has no bounded fallback when delegation is unavailable.
- Committing usage telemetry, scheduler definitions, or runtime-specific paths into the shared repository instead of keeping them in the consuming runtime.

## Verification

- Exactly one canonical copy of each skill exists.
- Every skill is discovered from the repository's canonical root.
- Adapters contain no duplicate skill bodies or project-specific state.
- Retired paths, installer names, persona names, and dependent workflow references have zero mandatory occurrences.
- Portable workflows select roles by capability, use only active-backend tools, and remain executable through a bounded fallback when delegation is absent.
- Public/privacy scans find no machine paths, credentials, private modules, package namespaces, fixed stack ownership paths, domain-document assumptions, or client context.
- Validator, unit tests, docs build, shell checks, secret scans, and current-head review pass.
- Library-health guidance keeps usage-signal collection and scheduling in the consuming runtime; the shared repository contains only the portable selection procedure and cadence.
