# Codex sub-agent orchestration profile

This repository contains portable skills under `skills/<category>/<name>/SKILL.md`. Treat that directory as the canonical index; do not hard-code a fixed skill count in project instructions.

## How Codex should use this repo

1. Treat the current assistant as the **main orchestrator**.
2. Prefer decomposition into specialist sub-tasks before large code changes.
3. Prefer project-local guidance in the target repo such as `AGENTS.md` and `.agents/` over bundled generic roles.
4. Use the skill instructions as the workflow source of truth.
5. Use the bundled references in each skill directory instead of assuming Claude-specific files exist.
6. Delegate to **native Codex subagents** (see below) rather than emulating roles inside a single thread.

## Native subagents

Codex CLI has first-class subagents. Multi-agent support is stable and enabled by default, so there is no feature flag to turn on and nothing to emulate.

Tools available to the orchestrator:

- `spawn_agent` — start a subagent with a role and a task.
- `send_input` — feed additional context to a running subagent.
- `wait_agent` — block on a subagent and collect its result.
- `resume_agent` — continue a subagent with its context intact.
- `close_agent` — tear a subagent down when its slice is finished.

In the TUI, `/agent` inspects and drives the same machinery.

Roles are declared in `config.toml` under the `[agents]` **table**, one subtable per role. There is no `[[agents]]` array-of-tables:

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 6

[agents.reviewer]
description = "Reviewer focused on correctness, security, and missing tests."
config_file = "agents/reviewer.toml"
```

Each `config_file` is a standalone TOML agent definition, resolved relative to the declaring `config.toml` — for a global install that means `$CODEX_HOME/agents/*.toml`. Every definition MUST set `name`, `description`, and `developer_instructions`; `name` is the source of truth, not the filename. Definitions may also layer in `model`, `model_reasoning_effort`, `sandbox_mode`, `[mcp_servers.*]`, and `[[skills.config]]`.

Built-in roles are `default`, `worker`, and `explorer`. Declaring an agent named `explorer` intentionally overrides the built-in one.

Consequence for orchestration: parallelism is real, so ownership discipline matters more than role invention. Assign explicit implementation slices to subagents instead of collapsing routine execution into the main thread, and cap concurrency at what `max_concurrent_threads_per_session` allows.

## Native hooks

Codex hooks are native and do not need to be re-expressed as instructions. Eleven events fire: `SessionStart`, `SessionEnd`, `UserPromptSubmit`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `PreCompact`, `PostCompact`, `SubagentStart`, `SubagentStop`, `Stop`.

Key properties:

- Configure them in `$CODEX_HOME/hooks.json`, as `[[hooks.<Event>]]` blocks in `config.toml`, or in `<repo>/.codex/hooks.json` for a trusted project. **All layers are additive**, so declaring the same handler twice runs it twice.
- The stdin contract is the same JSON object Claude Code passes: `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `model`, plus `turn_id`, `permission_mode`, `tool_name`, `tool_use_id`, `tool_input`, and `tool_response` where applicable. Portable hook scripts work on both runtimes.
- Only handlers with `type = "command"` execute. `prompt` and `agent` handler types parse but are silently skipped — never rely on them.
- To block a tool call, return `permissionDecision: "deny"` with a non-empty `permissionDecisionReason`; `updatedInput` requires `permissionDecision: "allow"`. The universal escape hatch is exit code 2 with the reason on stderr.
- `Stop` and `SubagentStop` returning `decision: "block"` plus a `reason` creates a continuation prompt — this is how a completion gate forces more work.
- Non-managed command hooks are hash-trusted: approve them once via the in-TUI `/hooks` command. There is no `codex hooks` CLI subcommand.
- Kill switch: `[features] hooks = false`.

So when a rule is mechanically checkable — protected paths, formatting, completion gates, session context — implement it as a hook, not as prose an agent may skip.

## Post-task skill review

After significant work, use `skill-review` to decide whether a reusable procedure, correction, workaround, or missing instruction should become a skill change. Skip routine work, temporary state, and one-off facts.

Before loading it, verify that `skill-review` is available through the environment's skill discovery mechanism. It is a skill name, not a shell command. In Codex it resolves through `.agents/skills` (current directory up to the repo root), `$HOME/.agents/skills`, `/etc/codex/skills`, or `$CODEX_HOME/skills`, and is invoked as `$skill-review`; `/skills` lists what actually resolved. If it is unavailable, tell the user how to connect or install the repository skills, or present the candidate inline without inventing a command.

The review produces a private candidate first. Do not copy local agent state into the shared repository, edit public `main`, create a promotion branch, push, or open a pull request until the user approves the candidate. Approved shared changes must use the repository's branch, validation, secret-scan, and pull-request flow.

## Default Codex Tempo

Optimize for a short orchestration loop:
1. Build a quick plan from targeted evidence.
2. Split the plan into executor-owned items.
3. Prepare a compact handoff packet for each item.
4. Delegate execution when ownership is clear.
5. Re-synthesize only what the next item needs.
6. Run validation after the implementation batch.

Do not turn every task into a long research session. Research removes uncertainty; it is not the main output.

## Default Cost Policy

Treat Codex as cost-sensitive by default:
1. Prefer one executor over a swarm of agents.
2. Add a researcher only when uncertainty blocks execution.
3. Add a reviewer only after code reaches a stable state.
4. Parallelize only when ownership is clearly disjoint and the time savings justify the extra context cost.
5. Keep handoff packets compact so each agent loads only the minimum useful context.

Native subagents make parallelism cheap to *start*, not cheap to *run* — each thread loads its own context. Control cost with `agents.default_subagent_model` and `agents.default_subagent_reasoning_effort` for the global floor, per-agent `model_reasoning_effort` for the exceptions, and fewer delegations with shorter handoffs everywhere else.

## Role mapping

### Prefer project-local roles when present
- `planner`: task decomposition and execution plan.
- `architect`: architecture fit, boundaries, dependency impact.
- `backend-developer`: server-side implementation for the target stack.
- `frontend-developer`: client-side implementation for the target stack.
- `domain-rules-reviewer`: domain logic and business-rule compliance.
- `plan-reviewer`: final cross-check against the approved plan.

### Portable fallback roles
- `code-researcher`: exhaustive codebase analysis.
- `diff-researcher`: git history and diff analysis.
- `web-researcher`: official docs and best practices.
- `ui-researcher`: UI structure and behavior analysis.
- `implementation-generalist`: standard implementation within one slice.
- `validation-generalist`: standard correctness checks.
- `test-engineer`: regression-focused coverage updates.

### Roles shipped with this adapter
- `explorer`: read-only codebase evidence and regression tracing.
- `docs_researcher`: primary-doc and API verification.
- `reviewer`: correctness, regression, security, and missing tests review.

These three are the concrete `[agents.<name>]` declarations in this adapter's `config.template.toml`, backed by `agents/explorer.toml`, `agents/docs-researcher.toml`, and `agents/reviewer.toml`. They are read-only by design, so they never replace executor ownership: routine implementation still needs an explicit write-capable slice.

## Operating rules
- Make architectural decisions at orchestrator level.
- Run independent research or implementation tracks in parallel using `spawn_agent`, then collect with `wait_agent`.
- Keep the phases explicit even inside a single thread: assessment -> research -> planning -> execution -> validation.
- In full-stack repos, split backend and frontend work by ownership boundary before deciding whether the tracks can run in parallel.
- In domain-heavy repos, run a separate domain-rules review whenever business rules, statuses, calculations, or critical flows change.
- Prefer concise decision-focused reporting over long code walkthroughs.
- After code changes, always validate compilation, logic, and code quality.
- Prefer executor agents for routine implementation when ownership is clear.
- Keep the main orchestrator for synthesis, integration, and unblockers rather than default execution.
- Before each delegated implementation step, prepare a compact handoff packet with goal, facts, constraints, files, and expected output.
- Share results between agents through orchestrator-synthesized handoff packets, not by assuming peer-to-peer shared state.
- If the next implementation step is already clear, do not extend research just to satisfy process ceremony.
- Use the cheapest capable executor or reviewer the configured model tiers allow.
- Default execution shape should be `orchestrator plan -> one executor -> validation`, not `many agents by default`.
- Add a second executor only for truly disjoint files or layers.
- Add a research agent only for missing facts, not for routine repo reading.
- Add a review agent only after implementation, unless the task is security- or architecture-sensitive from the start.
- Keep authoring and review in separate passes; never self-approve in the same active context.

## Codex Budget Modes

### Cheap default
- 0-1 research agents
- 1 executor
- 0-1 reviewer
- Sequential groups unless parallelism is obviously profitable

Use this for most feature work, bug fixes, and refactors.

### Balanced
- 1 focused researcher
- 1-2 executors with clean ownership split
- 1 reviewer

Use this when parallel work will materially reduce elapsed time without duplicating context.

### High scrutiny
- Multiple specialized agents only for high-risk, security-sensitive, or architecture-heavy tasks

Do not enter this mode unless the task risk justifies the cost.

## Recommended project usage

Copy or symlink this file into a target repo as `AGENTS.md` when you want Codex to apply the same sub-agent orchestration style inside that project.

Note the shadowing trap: an `AGENTS.override.md` in the same directory **replaces** `AGENTS.md` rather than appending to it. Keep exactly one instruction file per directory level.

For a target repository, prefer its own local role docs, paths, stack constraints, verification commands, and documented domain source of truth.

The shared skills in this repository should act as orchestration glue, not as a replacement for project-local agent definitions.
