# Workflow Boundaries

## Orchestrator workflows

- When the user mentions an orchestrator/workflow skill (e.g., orchestrator-workflow, refactor-workflow), FOLLOW the mandated phases (delegation, planning) BEFORE editing any files
- Do not skip Phase 1 / Phase 2 (assessment, deep research) and jump to Phase 4 (execution)
- Phase deviation = interruption + rework

## Pipeline / test execution

- Do NOT run pipelines or tests locally if the user indicates they will trigger them
- Wait and monitor instead — fetch logs from their run, not your own
- Only run locally when explicitly asked or when no remote pipeline exists

## Dependencies and configuration

- Do NOT add optional dependencies (loggers, reporters, telemetry) without an explicit request
- Do NOT auto-configure features (autoload, hooks, integrations) the user did not ask for
- Stay within the scope of the request; if scope is unclear, ASK before expanding

## Rationale

Past incidents:
- Skipped orchestrator phases → got interrupted (not_achieved result)
- Created an agent in `~/.claude/agents/` instead of project-local `.agents/` → required correction
- Added an unwanted ReportPortal logger dependency → had to be reverted
- Auto-configured autoloading without being asked
