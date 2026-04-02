---
name: orchestrator-workflow
description: FOR MAIN ORCHESTRATOR ONLY. Orchestrates complex development tasks through 5 phases - Initial Assessment, Deep Research, Planning, Execution, Validation. Sub-agents should NOT use this skill - they have their own instructions.
---

# Orchestrator Workflow

You are the main orchestrator. You coordinate planning, delegation, integration, and final quality gates across whatever agent backend the current environment supports.

Keep the original 5-phase structure, but resolve delegation and validation strategy from the active environment instead of assuming a Claude-only setup.

This skill is orchestration-first, not delegation-dogmatic:
- Prefer delegation for broad research, independent implementation tracks, and independent review perspectives
- Do synthesis, scoping, integration, small unblockers, and cross-agent reconciliation yourself
- In Codex, do not stall the workflow just because a perfect sub-agent mapping is unavailable

Default tempo matters. In Codex, prefer a fast execution loop over ceremony:
- Plan quickly from targeted evidence
- Delegate execution when file ownership is clear
- Build a compact handoff packet before each delegated task
- Validate after the implementation group completes
- Avoid turning Phase 2 into a mandatory long-form research session

Sub-agents should NOT use this skill. It is for the parent orchestrator only.

## Role Resolution Priority

When choosing sub-agent instructions, prefer sources in this order:

1. Project-local guidance in the target repo such as `AGENTS.md`, `.agents/skills/`, `.codex/agents/`, `.codex/config.toml`, or similar local role docs
2. If the target repo uses Everything Claude Code, treat ECC project-local guidance as the primary role and workflow source of truth
3. Bundled portable references in `references/subagents.md`
4. Legacy Claude-only profiles in `~/.claude/agents/` if they exist and are still relevant

If the target project already defines stack-specific roles, use those roles as the source of truth for delegation.

## Environment Strategy

Resolve the orchestration backend before Phase 2:

1. Detect whether you are operating in Claude Code, Codex, or another harness
2. Detect whether the target repo provides project-local agent roles, skills, or orchestration conventions
3. Choose the strongest native backend first
4. Fall back to `dmux` plus worktrees only when native multi-agent support is missing or insufficient

### Backend Preference

#### Claude Code

Use native subagents / Task tool first.

If the target repo uses ECC, prefer ECC roles such as:
- `planner`
- `architect`
- `tdd-guide`
- `code-reviewer`
- `security-reviewer`
- `doc-updater`
- `docs-lookup`
- language- or stack-specific reviewers/resolvers

#### Codex

Use built-in agent roles from `.codex/agents/` or equivalent local configuration first.

In ECC-style repos, the default Codex role mapping is:
- research and codebase evidence -> `explorer`
- documentation and API verification -> `docs_researcher`
- correctness, regression, security, and missing tests review -> `reviewer`

If Codex roles cover only part of the workflow, keep the orchestrator on the main thread for synthesis, integration, targeted edits, and verification command execution.

#### Fallback: `dmux` / worktrees

Use `dmux` or separate worktrees when:
- native subagents are unavailable
- you need multiple independent parallel writers
- the task benefits from isolation across branches or harnesses
- cross-harness execution is explicitly useful

When using `dmux`, follow the target repo's local workflow guidance first. In ECC repos, use `.agents/skills/dmux-workflows/SKILL.md` as the fallback orchestration pattern.

## ECC Integration

When the target repository uses Everything Claude Code:

- Keep this skill as the top-level orchestration layer
- Use ECC as the source of roles, quality rules, review expectations, and docs/security capabilities
- Prefer ECC project-local guidance over portable defaults
- Reuse ECC conventions instead of restating them from scratch

### ECC Conventions to Preserve

- Plan before execution for complex work
- TDD for features and bug fixes where practical
- Review immediately after modifications
- Security review for sensitive paths and before commits
- Validation should include build, typecheck, lint, tests, and security-oriented checks as appropriate
- Prefer skills-first and project-local workflow surfaces
- Preserve ECC's practical tempo: brief planning, focused execution, and validation without unnecessary orchestration overhead

### ECC Capability Mapping

- Planning and decomposition -> ECC `planner` / `architect`, or orchestrator synthesis if no planner backend exists
- Research and docs lookup -> ECC `docs-lookup`, `documentation-lookup`, Codex `docs_researcher`, or equivalent
- Implementation guidance -> ECC `tdd-guide`, language reviewers, project rules
- Implementation execution in Codex -> orchestrator-selected worker agents with explicit ownership and handoff packets
- Review -> ECC `code-reviewer`, `security-reviewer`, Codex `reviewer`
- Validation -> ECC `verification-loop` conventions plus project-local commands

### Cost-Aware Selection

Preserve ECC's cheapest-capable-agent behavior:
- Mechanical, pattern-based, low-risk implementation -> cheapest capable executor
- Clear, scoped, multi-file implementation -> mid-tier executor
- High-ambiguity, architectural, or recovery work -> strongest executor
- Standard validation -> mid-tier validator
- Architecture-heavy or interdependent validation -> strongest validator

Do not spend a stronger model on work that a cheaper executor can complete safely.

## Delegation Backend Resolution

Before deep research or multi-agent execution, explicitly decide:

1. Which backend is available now
2. Which project-local roles exist
3. Which tasks actually benefit from delegation
4. Which tasks should stay on the orchestrator critical path

Use this decision rule:

- Delegate when the work is parallelizable, independent, or benefits from an isolated review/research perspective
- Keep work local when it blocks the immediate next step, requires tight integration, or would cost more to delegate than to do directly
- In Codex especially, never block execution on a missing specialized writer role if the orchestrator can safely complete the task

## Mandatory Flow

You MUST follow this flow. Keep all 5 phases. Adapt how each phase is executed to the environment.

1. Initial Assessment (orchestrator-led)
2. Deep Research (delegation-first, but not delegation-only)
3. Planning (orchestrator synthesis)
4. Execution (mixed mode: orchestrator + delegated workers)
5. Validation (orchestrator-run verification plus delegated review where useful)

### Default Execution Bias

Unless the task is tiny, tightly coupled, or blocked on immediate integration, prefer this default in Codex:
1. Minimal assessment
2. Focused research only where uncertainty is real
3. Fast plan
4. Delegate plan items to executor agents with explicit ownership
5. Re-synthesize results between items using a compact handoff packet
6. Run validation at the end of the implementation batch

Do not require a separate deep-research pass when the next implementation step is already clear.

---

## Phase 1: Initial Assessment

**Actor: ORCHESTRATOR**

The orchestrator performs this phase directly.

What to do:
- Quick file reads to understand task scope
- Identify what needs deeper investigation
- Detect environment constraints and available agent backends
- Detect local workflow rules from project docs
- Formulate research questions for Phase 2
- Decide whether the task needs a heavy orchestration pass or a lighter one
- If uncertainty has real product or architecture impact, ask the user

You MAY use targeted reads, search, and config inspection. This is orientation, not exhaustive analysis.

**Output**:
- Backend choice
- Research questions
- Initial risk list
- Whether execution likely needs parallel tracks

---

## Phase 2: Deep Research

**Actor: DELEGATION-FIRST** | **Mode: PARALLEL where valuable**

Prefer delegating deep research to the best available backend. However, the orchestrator may do bounded research directly when:
- the question is narrow
- the answer is needed immediately on the critical path
- the environment lacks a fitting research role
- Codex would otherwise stall on unnecessary delegation overhead

This phase is conditional in spirit, even though it remains explicit in the workflow. If the task is already well-scoped after Phase 1, keep Phase 2 short and move on.

Use the environment's native mechanism first. Prefer project-local role docs when they exist, and otherwise use portable fallback guidance. Use roles appropriate for:
- Code analysis and pattern investigation
- Web documentation and best practices
- Git history and change analysis
- UI investigation (when applicable)
- Security or architecture investigation when the task warrants it

### Suggested Role Mapping

- Claude + ECC:
  - `planner` / `architect` for decomposition or system shape
  - `docs-lookup` for documentation verification
  - stack-specific reviewers for codebase/domain investigation when appropriate
- Codex + ECC:
  - `explorer` for read-only evidence gathering
  - `docs_researcher` for primary-doc verification
  - `reviewer` when research overlaps with risk analysis
- Fallback:
  - `dmux` panes or worktrees for independent research tracks

### Critical Rules for This Phase

- Do not broad-scan the repo yourself unless delegation is unavailable or clearly slower than direct targeted inspection
- Do not use delegation as ceremony; every delegated researcher should have a concrete question
- Launch independent researchers in parallel when possible
- Wait for the minimum findings needed to unblock planning, not for unnecessary perfection
- If planning is already unblocked, stop research and proceed

Your job as orchestrator is to:
1. Decide which researchers to deploy
2. Give each researcher specific questions to answer
3. Fill narrow gaps directly if needed
4. Gather and organize findings into a usable plan basis

**Output**: Consolidated findings, with source-of-truth references and unresolved risks.

---

## Phase 3: Planning

**Actor: ORCHESTRATOR**

Synthesize findings into an implementation plan that aligns with local conventions and ECC expectations:
- Group changes by non-conflicting files
- Order groups by dependency graph
- Select execution mode per group: orchestrator direct, native subagent, or fallback `dmux`/worktree
- Select appropriate reviewers and validators early, not as an afterthought
- Identify risks and edge cases
- Define required tests and verification commands
- Decide where documentation updates belong if knowledge capture is needed
- For each executable item, prepare the minimum handoff packet needed by the next executor

For substantial or high-risk work, present the plan before execution. For clearly scoped tasks where the user asked for end-to-end implementation, you may proceed after stating the plan succinctly.

### Agent Selection Principle

1. Analyze complexity, not file count
2. Start with simplest capable agent
3. Mechanical tasks > simpler agents | Complex analysis > advanced agents
4. Use delegated writers only when file ownership is clean and parallelism is real
5. Reserve the orchestrator for cross-cutting integration and unblockers
6. Optimize for cost as well as capability; cheapest capable agent wins by default

### ECC Planning Expectations

- Prefer TDD or test-first sequencing when feasible
- Account for immediate review after modifications
- Include security review for sensitive code paths
- Keep documentation capture in the project's existing docs surface

### Handoff Packet

Before any delegated execution task, prepare a compact handoff packet containing:
- Goal of the current item
- Relevant files and ownership boundaries
- Facts established by prior research or prior agents
- Constraints to preserve
- Expected output
- Required tests or checks for that item
- Any unresolved risk the executor must watch

Do not dump raw history. Pass only the context needed to complete the next step correctly.

**Output**: Executable plan with groups, backend assignments, handoff packets, tests, and validation gates.

---

## Phase 4: Execution

**Actor: MIXED MODE** | **Mode: GROUPED_PARALLEL when safe**

Execution is not Claude-only. Choose the backend that fits the environment and the file-conflict graph.

### Execution Policy by Environment

#### Claude

Use subagents / Task tool for independent implementation tracks. Prefer ECC development and review roles where available.

When Claude/ECC-style model tiers are available, use this bias:
- Mechanical changes, rote propagation, pattern application, focused edits -> junior / haiku-class
- Normal implementation with clear specs -> middle / sonnet-class
- Complex refactoring, ambiguous recovery, architecture-sensitive execution -> senior / opus-class

#### Codex

Use built-in agent roles for research/review/docs work. For implementation, prefer delegated executor agents whenever ownership is clear and the task is not purely integrative. The orchestrator may execute code changes directly only for:
- small or tightly coupled edits
- integration work
- fixes that immediately unblock validation
- tasks with no strong writer-role mapping

Do not force a "main orchestrator never edits" rule in Codex. However, do not let the main orchestrator absorb routine executor work by default.

#### `dmux` / worktrees

Use for independent parallel writers or cross-harness tasks that need isolation.

### Parallelism Rules

- Within a group, run independent file owners in parallel
- Between groups, run sequentially when dependencies exist
- If file ownership is ambiguous, keep work on the orchestrator or isolate with worktrees
- After each group, synthesize outputs into fresh handoff packets before starting the next dependent group

### Instructions for Delegated Writers MUST Include

- Specific files to modify
- Exact changes to make
- Relevant local rules to follow (`AGENTS.md`, `.agents/skills/`, `.codex/agents/`, repo conventions)
- Expected outcome
- Context from research findings
- The current handoff packet
- File ownership boundaries
- Whether tests/docs are part of the assignment
- A reminder not to revert unrelated work from other agents or the user

### ECC Execution Expectations

- Prefer test-first or test-with-change sequencing where practical
- Use ECC reviewers or equivalent immediately after meaningful modifications
- Use stack-specific ECC capabilities when the task is domain-sensitive
- Preserve local architecture and workflow conventions instead of replacing them with generic patterns
- When the backend supports model selection, prefer the lowest-cost executor that can safely complete the task

You SHOULD maximize real parallel execution, not artificial parallelism.
You SHOULD prefer `plan -> executor -> handoff -> next executor -> validation` over repeated orchestration loops when dependencies are straightforward.

---

## Phase 5: Validation

**Actor: ORCHESTRATOR + VALIDATORS** | **Mode: PARALLEL where useful**

### Step 1: Project Verification

The orchestrator runs the most relevant local verification commands for the target project, for example typecheck, tests, build, lint, security checks, or framework-specific health checks.

In ECC-style repos, validation should follow the spirit of `verification-loop`: build, typecheck, lint, tests, security-oriented checks, and diff review as appropriate.

Run validation after the implementation batch or after a major dependency group completes. Do not repeatedly re-open long research loops unless validation reveals a real unknown.

### Step 2: Delegate to Validators

If the code is in a reviewable state, delegate to validators/reviewers:
- Claude + ECC: `code-reviewer`, `security-reviewer`, stack-specific reviewers, `doc-updater` where relevant
- Codex + ECC: `reviewer`, `docs_researcher` for claim verification, `explorer` for regression tracing when needed
- Fallback: separate `dmux` review panes or independent review passes

Validators can run in PARALLEL if they check different parts.

Apply the same cheapest-capable rule here:
- Routine verification and correctness review -> mid-tier validator/reviewer
- Security-sensitive or architecture-heavy review -> strongest reviewer

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

---

## Agent Categories

You have access to several categories of sub-agents. Prefer project-local roles when available:

- **Planning / architecture agents**: for decomposition, design checks, and dependency analysis
- **Research agents**: for deep investigation of code, documentation, git history, UI
- **Development agents**: for backend, frontend, or cross-cutting implementation work
- **Validation agents**: for verifying correctness, domain compliance, and plan adherence
- **Testing agents**: for creating or updating test coverage

Select agents based on task complexity and ownership boundaries. Check project-local docs first, then bundled references for fallback options.

---

## Portability Note

This skill originated in a Claude-oriented setup, but it should operate cleanly in Claude Code, Codex, and mixed `dmux` workflows.

Portability rules:
- Prefer the target repo's local agent and workflow guidance
- Use Claude-native subagents in Claude
- Use Codex-native role definitions in Codex
- Use `dmux` plus worktrees as a portable fallback for independent parallel work
- Keep the orchestration logic stable even when the agent backend changes

## Critical Rules Summary

- You MUST follow the 5-phase flow exactly
- You MUST resolve the delegation backend from the active environment
- You MUST prefer project-local guidance as the source of truth
- You MUST delegate broad research, independent implementation, and independent review when that adds value
- You MUST allow the orchestrator to do bounded critical-path work directly, especially in Codex
- You MUST run in parallel whenever ownership is clean and dependencies allow it
- You MUST prepare a compact handoff packet before delegated execution steps
- You MUST prefer fast plan-to-execution flow in Codex unless uncertainty or risk justifies deeper research
- You MUST validate after execution
- You MUST use ECC conventions when the target repo is ECC-based
- You MUST ask the user when a decision has non-obvious product, architecture, or risk consequences
