# Sub-agent catalog

Only roles that actually exist are listed here. Never delegate to a role name the active backend does not expose.

## Selection priority
1. Project-local roles defined in the target repo's `.codex/agents` (or the active environment's equivalent role registry) take precedence
2. The built-in and shipped roles below

## Codex

### Built-in roles
- `default`: general-purpose sub-agent.
- `worker`: write-capable implementation within one slice.
- `explorer`: read-only codebase exploration.

### Roles shipped with the Codex adapter
- `explorer`: read-only codebase evidence and regression tracing. Overrides the built-in `explorer`.
- `docs_researcher`: primary-doc and API verification.
- `reviewer`: correctness, regression, security, and missing tests review.

The shipped roles are read-only, so implementation slices go to `worker` or a write-capable project-local role.

## Claude Code

Not applicable: oh-my-claudecode replaces this skill and owns the agent catalog on that runtime.

## Selection rules
1. Prefer repo-local roles over built-in or shipped roles.
2. Analyze complexity and ownership boundaries, not file count alone.
3. Start with the simplest capable role.
4. Split independent tracks into parallel sub-agents only when ownership does not overlap.
5. Reserve the strongest reviewer for architecture-heavy or high-ambiguity work.
