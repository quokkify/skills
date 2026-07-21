# Sub-agent catalog

These role profiles are portable defaults. They are not the top priority when the target repo already defines its own roles.

## Selection priority
1. Project-local role docs such as `AGENTS.md` or `.agents/**/SKILL.md`
2. This bundled portable catalog
3. Legacy Claude-only profiles in `~/.claude/agents/`

## Project-local roles example
- `planner`: turns the task into a short executable plan.
- `architect`: checks architecture fit, boundaries, and dependency impact.
- `backend-developer`: owns `backend/**`, API contracts, business logic, permissions, and data access for a Django/DRF stack.
- `frontend-developer`: owns `frontend/**`, routes, components, forms, state, and API integration for a React/Vite/TypeScript stack.
- `domain-rules-reviewer`: verifies that domain rules, statuses, and calculations still match the source of truth.
- `plan-reviewer`: checks that delivery matches the approved plan and highlights gaps or residual risk.

## Portable fallback roles

### Research
- `code-researcher`: deep code analysis, execution paths, dependencies, and file-level evidence.
- `diff-researcher`: git history, change intent, and migration risk.
- `web-researcher`: official documentation and current best practices.
- `ui-researcher`: UI structure, route flow, and interaction behavior.

### Implementation
- `implementation-generalist`: standard multi-file implementation work within one slice.
- `backend-specialist`: server-side logic, persistence, auth, APIs, and integrations.
- `frontend-specialist`: routes, components, forms, client state, and API consumption.
- `test-engineer`: coverage updates and regression-focused tests.

### Validation
- `validation-generalist`: standard correctness checks across touched code.
- `architecture-reviewer`: complex interdependent validation for higher-risk changes.

## Selection rules
1. Prefer repo-local roles over bundled roles.
2. Analyze complexity and ownership boundaries, not file count alone.
3. Start with the simplest capable role.
4. Split backend, frontend, and domain review into separate parallel tracks when ownership does not overlap.
5. Reserve the strongest reviewer for architecture-heavy or high-ambiguity work.
