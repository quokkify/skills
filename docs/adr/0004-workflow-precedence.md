---
title: "ADR-0004: Workflow precedence between companions and the shared base"
---

# ADR-0004: Set one workflow precedence order and give each runtime a single plan-and-execute owner

- Status: accepted
- Date: 2026-10-20

## Context

[ADR-0003](0003-require-omc-and-superpowers-companions.md) made oh-my-claudecode required on Claude Code and superpowers required on Claude Code and Codex CLI. A review afterwards found that the instructions now conflict in three places.

- The shared base says to ask at most one round of clarifying questions and to go straight to the change for small work. Superpowers `brainstorming` asks one question at a time and waits for approval before any design is implemented. Both claim to govern the same turn.
- On Claude Code, oh-my-claudecode and superpowers each ship a full plan-and-execute chain (`plan`/`ralplan`/`execute` against `writing-plans`/`executing-plans`/`subagent-driven-development`), and `orchestrator-workflow` claimed a third "top-level phase structure" that it said MUST be followed exactly. The adapter's only tie-breaker was one sentence saying oh-my-claudecode drives orchestration and superpowers supplies discipline.
- The Codex adapter and the `orchestrator-workflow` role catalog listed role names — `planner`, `backend-developer`, `code-researcher`, `implementation-generalist`, and others — that no shipped configuration defines, so delegations to them could not resolve. `refactor-workflow` duplicated the five-phase orchestration with a refactor slant and added fixed style rules that override project conventions.

## Decision

- The shared base states one precedence order: user and project instructions, then the runtime's orchestration companion workflow (oh-my-claudecode on Claude Code), then superpowers process discipline, then the base defaults.
- The base's interaction and ceremony-sizing defaults apply only when no required companion process skill applies. When superpowers `brainstorming` applies to new feature or design work, its one-question-at-a-time approval flow governs.
- On Claude Code, oh-my-claudecode owns planning and execution. Superpowers contributes `brainstorming` for design exploration and the discipline skills — `test-driven-development`, `systematic-debugging`, `verification-before-completion`, `receiving-code-review`. Its `writing-plans`, `executing-plans`, and `subagent-driven-development` are not used there, and neither is `orchestrator-workflow`.
- On Codex, the superpowers chain owns planning and execution, and superpowers also supplies the dispatch mechanics through `using-superpowers/references/codex-tools.md` and `subagent-driven-development`. The Codex adapter keeps only roles, hooks, and cost policy, and its budget modes map onto superpowers' own: `executing-plans` inline for cheap, `subagent-driven-development` for thorough, never a mode without review. `orchestrator-workflow` is deleted.
- Role catalogs list only roles that exist: the Codex built-ins `default`, `worker`, and `explorer`, the shipped `explorer`, `reviewer`, and `docs_researcher`, and project-local roles from the target repository's `.codex/agents`, which take precedence.
- `refactor-workflow` is deleted. Its useful core — targeted versus exploratory refactors, behavior preservation, tests green before and after — moves into a Refactoring section of the shared base, so it also serves runtimes without a companion. Its style rules and its mandatory plan-approval gate are dropped.

## Alternatives considered

- **Let superpowers own planning on Claude Code as well.** Rejected: oh-my-claudecode's plan and execute workflows are wired to its own agent catalog and model routing, so running superpowers' chain on top would route delegation around the companion that owns it.
- **Keep `orchestrator-workflow` as the top-level phase structure on every runtime.** Rejected: a third phase model on top of two companion chains is exactly the conflict this record resolves, and it adds ceremony without adding a capability either companion lacks.
- **Keep `orchestrator-workflow` as a Codex delegation backend guide.** Rejected: superpowers' Codex tool mapping covers dispatch, briefs, waiting, model selection, and review more precisely, and the rest duplicated the Codex adapter.
- **Keep `refactor-workflow` as a separate skill.** Rejected: it repeated the orchestration phases nearly verbatim, and its only distinct content fits in one short section.
- **Keep the invented role names as illustrative examples.** Rejected: agents read role lists as instructions, and a name that does not resolve produces a failed delegation rather than a hint.

## Consequences

- Each runtime has exactly one owner for planning and execution, and the precedence order resolves the remaining overlaps without per-skill tie-breakers.
- The base's "at most one round of questions" default no longer applies to feature design work on runtimes with superpowers, so those sessions ask more questions before implementation.
- Users of other harnesses lose the bundled fallback role names. They must define roles in the target repository or delegate to whatever the harness exposes.
- Anyone who invoked `refactor-workflow` or `orchestrator-workflow` directly must switch to the Refactoring section of the shared base and the runtime's companion: oh-my-claudecode on Claude Code, superpowers on Codex.
- Harnesses with neither companion lose the bundled orchestration guide and rely on the shared base's delegation rules.
