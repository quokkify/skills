---
name: refactor-workflow
description: FOR MAIN ORCHESTRATOR ONLY. Orchestrates refactoring tasks through 5 phases - Initial Assessment, Deep Research, Planning, Execution, Validation. Handles both targeted (specific files) and exploratory (find what needs refactoring) modes.
---

# Refactor Workflow

You are the orchestrator. Coordinate assessment, research, planning, execution, and validation through the strongest mechanism available in the active environment. Prefer delegation for independent or specialist work, but do bounded work directly when delegation is unavailable or would cost more than it saves.

## Role Resolution Priority

When choosing sub-agent instructions, prefer sources in this order:

1. Project-local guidance in the target repo such as `AGENTS.md`, `.agents/`, or similar local role docs.
2. Bundled portable references in `references/subagents.md`.

If the target project already defines stack-specific roles, use those roles as the source of truth for delegation.

## Input Handling

Check if specific files/classes were provided in the arguments:
- **Files provided**: Skip to targeted assessment (you know what to refactor)
- **No files provided**: Full discovery mode (find what needs refactoring)

---

## Mandatory Flow

You MUST follow this exact flow. No skipping. No deviations.

1. Initial Assessment (YOU do this)
2. Deep Research (delegation-first, with a bounded direct fallback)
3. Planning (YOU synthesize findings)
4. Execution (native delegation or orchestrator execution)
5. Validation (project verification plus independent review where useful)

---

## Phase 1: Initial Assessment

**Actor: YOU (orchestrator)**

YOU perform this phase directly. No sub-agents.

### If Specific Files Provided:
- Quick read of provided files to understand structure
- Identify dependencies and call hierarchies
- Note obvious issues (violations, duplication, complexity)
- Formulate specific research questions for Phase 2

### If No Specific Files:
- Quick project scan to identify candidate areas
- Look for common refactoring signals:
  - Large files (>500 lines)
  - Complex packages
  - Known problem areas mentioned by user
- Formulate discovery questions for Phase 2

You MAY use Read, Glob, Grep sparingly for initial context. This is NOT deep research - just quick orientation.

**Output**: List of files/areas to analyze, research questions for sub-agents.

---

## Phase 2: Deep Research

**Actor: DELEGATION-FIRST** | **Mode: PARALLEL where valuable**

Use the environment's native sub-agent mechanism when it is available. Prefer project-local role docs when they exist, and otherwise use the bundled portable role catalog. If no suitable delegation backend exists, perform bounded research directly and keep the evidence and scope explicit.

### Research Questions to Assign:

Assign one or more research-capable roles to investigate:
- Current implementation patterns and anti-patterns
- Dependencies and call hierarchies
- SOLID violations (SRP, OCP, LSP, ISP, DIP)
- Clean code violations (method length, complexity, naming)
- Hardcoded values that should be externalized
- Duplicate code across files/packages
- Missing dependency injection patterns
- Method-level SRP issues (methods doing too much)
- Test coverage and constraints on changes
- API boundaries that must be preserved

### Critical Rules for This Phase

- Prefer delegation for broad or independent investigations
- Keep direct orchestrator research targeted and bounded
- Parallelize only independent questions where expected savings justify coordination cost
- Wait for delegated findings before relying on them in the plan

If multiple areas need research, use separate researchers only when their scopes do not overlap and the active backend supports it efficiently.

**Output**: Collected findings from all sub-agents.

---

## Phase 3: Planning

**Actor: YOU (orchestrator)**

Synthesize research findings into refactoring plan:

### Task Grouping
- Group changes by non-conflicting files (for parallel execution)
- Order groups by dependency graph (dependent changes sequential)
- Identify which changes can run in parallel

### Agent Selection Per Group
- **Mechanical, localized refactors** → the simplest project-local implementation role that owns the files
- **Backend/domain/data/API refactors** → backend-oriented role for the target stack
- **Frontend/UI/state refactors** → frontend-oriented role for the target stack
- **Complex cross-cutting restructuring** → architect-guided implementation or the most capable generalist role available

### Risk Assessment
- Identify API compatibility concerns
- Note test constraints
- Flag high-risk changes

Present plan to user for approval before execution.

**Output**: Approved refactoring plan with parallel groups.

---

## Phase 4: Execution

**Actor: ORCHESTRATOR + AVAILABLE EXECUTORS** | **Mode: GROUPED**

Use the active environment's native delegation mechanism when suitable implementation roles are available. Otherwise execute the approved slice directly. Never invent a `task` tool or named role that the environment does not expose.

- Within group: agents run in PARALLEL (non-conflicting files)
- Between groups: SEQUENTIAL (dependencies)

### Agent Instructions MUST Include

- Specific files to modify
- Exact refactoring to apply
- Expected outcome
- Context from research findings
- API compatibility requirements

### Parallel Execution

Default to one capable executor for a coherent slice. Add parallel executors only for independent, non-conflicting ownership boundaries where expected time savings outweigh coordination and context costs. Run dependent groups sequentially.

---

## Phase 5: Validation

**Actor: ORCHESTRATOR-LED** | **Mode: PROJECT VERIFICATION + OPTIONAL DELEGATED REVIEW**

### Step 1: Project Verification

YOU run the most relevant local verification commands for the target project, for example typecheck, tests, build, lint, or framework-specific checks.

### Step 2: Delegate to Validators

If verification is clean, delegate to **validation agents**:
- Standard refactoring changes → the default validation or review role for the target project
- Complex/interdependent changes → the most capable validation or architecture-review role available

Validators can run in parallel if they check distinct risk surfaces and the coordination cost is justified.

### Step 3: Handle Results

- Minor issues → note, continue
- Major issues → fix with same development agent
- Critical issues → stop, report to user

---

## Refactoring Rules

These rules apply to ALL refactoring work:

- **Preserve behavior through tests** - Keep valid existing coverage and add or update tests when needed to lock down behavior, cover regressions, or reflect an intentional contract-preserving change
- **Use framework features** - Prefer framework/library solutions over custom code
- **Apply SRP** - At both class AND method level
- **Externalize config** - No hardcoded values that could change
- **Centralize concerns** - Cross-cutting logic in one place
- **No comments** - Unless explaining unclear business logic
- **Maintain API compatibility** - Don't break existing contracts
- **Small methods** - Extract when method does multiple things
- **Use project conventions for wiring dependencies** - do not introduce ad hoc construction or hidden global coupling

---

## Portability Note

This skill is backend-neutral. Prefer the target repository's own agent docs and native delegation mechanism when they exist. Use `references/subagents.md` and `references/output-style.md` as portable fallback guidance, not as a promise that named roles or tools exist.

## Critical Rules Summary

- You MUST follow the 5-phase flow exactly
- Prefer delegated research in Phase 2; use a bounded direct fallback when needed
- Use only roles and tools exposed by the active environment
- Parallelize only independent work with justified savings
- You MUST validate after execution
- Ask the user only when uncertainty materially changes the outcome and cannot be resolved from available evidence
- You MUST present plan to user before execution
