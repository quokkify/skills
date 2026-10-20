---
name: orchestrator-workflow
description: FOR MAIN ORCHESTRATOR ONLY. Delegation backend guide for runtimes without an orchestration companion (Codex, other harnesses) - backend resolution, handoff packets, cost-aware selection, execution policy, validation, and a refactor mode. Not used on Claude Code, where oh-my-claudecode replaces it. Sub-agents should NOT use this skill.
---

# Orchestrator Workflow

You are the main orchestrator. This skill is a delegation backend guide: it tells you how to resolve, brief, run, and validate sub-agents on a runtime that has no orchestration companion of its own, such as Codex CLI or another harness.

It does not own the top-level workflow. Where a process companion is required — superpowers on Codex — that companion's chain owns planning and execution, and this skill supplies only the delegation mechanics inside it. On Claude Code, oh-my-claudecode replaces this skill entirely; do not use it there.

This skill is orchestration-first, not delegation-dogmatic:
- Prefer delegation for broad research, independent implementation tracks, and independent review perspectives
- Do synthesis, scoping, integration, small unblockers, and cross-agent reconciliation yourself
- Do not stall the work just because a perfect sub-agent mapping is unavailable

Default tempo matters. Prefer a fast execution loop over ceremony:
- Plan quickly from targeted evidence
- Delegate execution when file ownership is clear
- Build a compact handoff packet before each delegated task
- Validate after the implementation group completes
- Do not turn research into a mandatory long-form session

Sub-agents should NOT use this skill. It is for the parent orchestrator only.

## Role Resolution Priority

When choosing sub-agent instructions, prefer sources in this order:

1. Project-local role and configuration metadata such as `AGENTS.md`, `.codex/agents/`, `.codex/config.toml`, or the active environment's supported role registry
2. The runtime's built-in and shipped roles listed in `references/subagents.md`

If the target project already defines stack-specific roles, use those roles as the source of truth for delegation. Never invent a role name the active backend does not expose.

## Delegation Backend Resolution

Resolve the backend before research or multi-agent execution:

1. Detect which harness you are running in and which native sub-agent mechanism it exposes
2. Detect whether the target repo provides project-local agent roles, skills, or orchestration conventions
3. Choose the strongest native backend first
4. When native sub-agents are missing, use separate git worktrees for independent parallel writers

Then explicitly decide:

1. Which project-local roles exist
2. Which tasks actually benefit from delegation
3. Which tasks should stay on the orchestrator critical path

Use this decision rule:

- Delegate when the work is parallelizable, independent, or benefits from an isolated review or research perspective
- Keep work local when it blocks the immediate next step, requires tight integration, or would cost more to delegate than to do directly
- Never block execution on a missing specialized writer role if the orchestrator can safely complete the task

### Codex

Use `spawn_agent` to start a sub-agent, `wait_agent` to collect its result, and `close_agent` when its slice is finished. The default role mapping is:
- research and codebase evidence -> `explorer`
- documentation and API verification -> `docs_researcher`
- correctness, regression, security, and missing tests review -> `reviewer`
- routine implementation -> `worker`, or a write-capable project-local role

The shipped `explorer`, `docs_researcher`, and `reviewer` are read-only. If roles cover only part of the work, keep the orchestrator on the main thread for synthesis, integration, targeted edits, and verification command execution.

## Companion Integration

- Let the runtime's required process companion own the plan and execute steps; this skill supplies only delegation mechanics inside them
- On Codex, the superpowers chain (`brainstorming` -> `writing-plans` -> `executing-plans` or `subagent-driven-development`) owns planning and execution, and its discipline skills apply inside each step
- Prefer project-local guidance over both, and reuse companion conventions instead of restating them

## Cost-Aware Selection

Keep cheapest-capable-agent selection:
- Mechanical, pattern-based, low-risk implementation -> cheapest capable executor
- Clear, scoped, multi-file implementation -> mid-tier executor
- High-ambiguity, architectural, or recovery work -> strongest executor
- Standard validation -> mid-tier validator
- Architecture-heavy or interdependent validation -> strongest validator

Do not spend a stronger model on work that a cheaper executor can complete safely.

Agent selection principle:

1. Analyze complexity, not file count
2. Start with the simplest capable agent
3. Use delegated writers only when file ownership is clean and parallelism is real
4. Reserve the orchestrator for cross-cutting integration and unblockers

## Research Delegation

Delegate deep research to the best available backend, but do bounded research directly when:
- the question is narrow
- the answer is needed immediately on the critical path
- the environment lacks a fitting research role
- delegation overhead would stall the work

Rules:
- Do not broad-scan the repo yourself unless delegation is unavailable or clearly slower than direct targeted inspection
- Do not use delegation as ceremony; every delegated researcher gets a concrete question
- Launch independent researchers in parallel when possible
- Wait for the minimum findings needed to unblock planning, then stop researching

## Handoff Packet

Before any delegated execution task, prepare a compact handoff packet containing:
- Goal of the current item
- Relevant files and ownership boundaries
- Facts established by prior research or prior agents
- Constraints to preserve
- Expected output
- Required tests or checks for that item
- Any unresolved risk the executor must watch

Do not dump raw history. Pass only the context needed to complete the next step correctly.

## Execution Policy

Prefer delegated executor agents whenever ownership is clear and the task is not purely integrative. The orchestrator may execute code changes directly only for:
- small or tightly coupled edits
- integration work
- fixes that immediately unblock validation
- tasks with no strong writer-role mapping

Do not force a "main orchestrator never edits" rule. However, do not let the main orchestrator absorb routine executor work by default.

### Parallelism Rules

- Within a group, run independent file owners in parallel
- Between groups, run sequentially when dependencies exist
- If file ownership is ambiguous, keep work on the orchestrator or isolate with worktrees
- After each group, synthesize outputs into fresh handoff packets before starting the next dependent group

### Instructions for Delegated Writers MUST Include

- Specific files to modify
- Exact changes to make
- Relevant local rules to follow (`AGENTS.md`, explicitly approved local skills, supported role configuration, and repository conventions)
- Expected outcome
- The current handoff packet
- File ownership boundaries
- Whether tests or docs are part of the assignment
- A reminder not to revert unrelated work from other agents or the user

Prefer `plan -> executor -> handoff -> next executor -> validation` over repeated orchestration loops when dependencies are straightforward.

## Refactor Mode

Use this mode when the task is a refactor rather than a behavior change.

- **Targeted refactor**: the user names the files or classes. Read them, map their dependencies and callers, and scope the change to that surface.
- **Exploratory refactor**: no target is given. Do a quick scan for candidate areas — oversized files, tangled packages, duplication, areas the user calls out — and confirm the shortlist with the user before changing code.

In both cases:
- Preserve behavior. A refactor does not change observable contracts, public APIs, or outputs.
- Run the relevant tests before the first edit and confirm they are green. If coverage does not lock down the behavior you are about to move, add characterization tests first.
- Keep the same tests green after every group of changes, and treat any test change as a signal to justify, not a routine step.
- Follow the target project's own style conventions rather than imposing a generic refactoring style.

## Validation

### Step 1: Project Verification

The orchestrator runs the most relevant local verification commands for the target project, for example typecheck, tests, build, lint, security checks, or framework-specific health checks. Run them after the implementation batch or a major dependency group, not after every step.

### Step 2: Delegate to Validators

If the code is in a reviewable state, delegate to validators:
- Codex: `reviewer`, `docs_researcher` for claim verification, `explorer` for regression tracing when needed
- Other harnesses: the project's review roles, or an independent review pass in a separate context

Validators can run in parallel if they check different risk surfaces. Routine correctness review goes to a mid-tier reviewer; security-sensitive or architecture-heavy review goes to the strongest reviewer.

### Step 3: Handle Results

- Minor issues > note, continue
- Major issues > fix with the same development agent or directly on the orchestrator if that is faster and safer
- Critical issues > stop, report to user

### Validation Exit Criteria

- Required commands completed or blockers clearly reported
- Review findings triaged
- Security-sensitive paths reviewed when applicable
- Tests added or updated when the change warrants them
- Documentation changes captured in the right project surface when needed

## Critical Rules Summary

- You MUST NOT use this skill on Claude Code; oh-my-claudecode replaces it there
- You MUST let the required process companion own planning and execution where one exists
- You MUST resolve the delegation backend from the active environment and use only roles it exposes
- You MUST prefer project-local guidance as the source of truth
- You MUST delegate broad research, independent implementation, and independent review when that adds value
- You MUST allow the orchestrator to do bounded critical-path work directly
- You MUST run in parallel whenever ownership is clean and dependencies allow it
- You MUST prepare a compact handoff packet before delegated execution steps
- You MUST validate after execution
- You MUST ask the user when a decision has non-obvious product, architecture, or risk consequences
