---
title: "ADR-0005: superpowers owns the process on Claude Code"
---

# ADR-0005: Let the superpowers chain own the process on Claude Code and keep oh-my-claudecode for agents

- Status: accepted
- Date: 2026-10-21
- Supersedes: the Claude Code decision and the precedence order in [ADR-0004](0004-workflow-precedence.md)

## Context

[ADR-0004](0004-workflow-precedence.md) gave oh-my-claudecode the plan and execute steps on Claude Code and kept only `brainstorming` and the discipline skills from superpowers. In use, that split cuts the superpowers chain at its first handoff:

- `brainstorming` ends by invoking `writing-plans`; that is its only terminal state on the architectural path. The adapter forbade the very next step the skill requires, so every design session hit a conflict between the skill and the adapter and resolved it ad hoc, sometimes one way and sometimes the other.
- ADR-0004 rejected superpowers on Claude Code because oh-my-claudecode's plan and execute workflows are wired to its agent catalog and model routing. `subagent-driven-development` carries its whole task in prompt templates and requires only that each dispatch names a model. Its templates name `general-purpose` as the subagent type, but nothing in the flow depends on that type, so the adapter can route the same templates to oh-my-claudecode agents without bypassing the companion.
- Codex already runs the superpowers chain. Two process owners in one hub means two process descriptions to keep consistent.

## Decision

- On Claude Code, the superpowers chain owns the process: `brainstorming` → `writing-plans` → the execution mode the user picks at its handoff, `subagent-driven-development` or `executing-plans`. Each execution mode runs its own reviews and ends in `finishing-a-development-branch`. The discipline skills — `test-driven-development`, `systematic-debugging`, `requesting-code-review`, `receiving-code-review`, `verification-before-completion` — apply wherever they fit.
- oh-my-claudecode stays required and owns the agent catalog, model routing, and hooks. The adapter overrides the templates' `general-purpose` subagent type: implementers and fixes go to `executor`, reviewers to `code-reviewer`. The skill's prompt template replaces the agent's default task and report format, and the skill's model tiers map to `haiku`, `sonnet`, and `opus`.
- oh-my-claudecode workflows (`plan`, `ralplan`, `deep-interview`, `execute`, `review`, `verify`, `autopilot`, `ralph`, `team`, `ultragoal`) run only when the user types the slash command or asks for one by name; a keyword detected in incidental text does not count. The adapter states that the workflow list in oh-my-claudecode's managed block does not set the process.
- The shared precedence order becomes: user and project instructions, then the superpowers process chain, then the runtime's orchestration layer, then the base defaults. A marker-delimited block that a companion's tooling writes into the user's instruction file ranks as that companion, not as a user instruction.
- The rest of ADR-0004 stands: interaction defaults yield to companion process skills, Codex is unchanged, and `orchestrator-workflow` and `refactor-workflow` stay deleted.

## Alternatives considered

- **Keep oh-my-claudecode as the process owner and allow `writing-plans` as an exception.** Rejected: the chain continues past planning into an execution mode and `finishing-a-development-branch`, so a single exception moves the conflict one step later instead of removing it.
- **Drop oh-my-claudecode on Claude Code.** Rejected: superpowers ships no agent catalog, model routing, or hooks, and the user-invoked autonomous modes have no superpowers equivalent.
- **Let both chains coexist and choose per task.** Rejected: this is the overlap ADR-0004 removed; an agent choosing between two process owners on every turn is the failure being fixed.

## Consequences

- Claude Code and Codex run the same superpowers chain; the adapters differ in dispatch mechanics and agent catalogs.
- Specs land in `docs/superpowers/specs/` and plans in `docs/superpowers/plans/` and are committed to the target repository, unlike oh-my-claudecode's git-ignored `.omc/plans/`.
- oh-my-claudecode reviewer agents carry their own output contracts and cannot write files. Dispatches rely on the superpowers template overriding the contract, and fixes always go to `executor`.
- The oh-my-claudecode managed block still lists its own canonical workflows. Agents must apply the precedence rule for managed blocks to ignore it.
- Users who relied on `plan` or `ralplan` running by default must now invoke them by name.
