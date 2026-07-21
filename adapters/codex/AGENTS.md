# Codex sub-agent orchestration profile

This repository contains portable skills under `skills/<name>/SKILL.md`. Treat that directory as the canonical index; do not hard-code a fixed skill count in project instructions.

## How Codex should use this repo

1. Treat the current assistant as the **main orchestrator**.
2. Prefer decomposition into specialist sub-tasks before large code changes.
3. Prefer project-local guidance in the target repo such as `AGENTS.md` and `.agents/` over bundled generic roles.
4. Use the skill instructions as the workflow source of truth.
5. Use the bundled references in each skill directory instead of assuming Claude-specific files exist.
6. When sub-agents are unavailable natively, emulate them explicitly by splitting work into these roles:
   - research
   - implementation
   - validation
   - test engineering

## Post-task skill review

After significant work, use `skill-review` to decide whether a reusable procedure, correction, workaround, or missing instruction should become a skill change. Skip routine work, temporary state, and one-off facts.

Before loading it, verify that `skill-review` is available through the environment's skill discovery mechanism. It is a skill name, not a shell command. If it is unavailable, tell the user how to connect or install the repository skills, or present the candidate inline without inventing a command.

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

If the environment does not expose explicit low-cost model tiers, control cost through fewer delegations and shorter context windows.

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

### Built-in Codex roles in ECC-style repos
- `explorer`: read-only codebase evidence and regression tracing.
- `docs_researcher`: primary-doc and API verification.
- `reviewer`: correctness, regression, security, and missing tests review.

These roles do not replace executor ownership. If native writer roles are missing, the orchestrator should still assign explicit implementation slices instead of collapsing routine execution into the main thread by default.
These roles also do not provide the same fine-grained cost ladder as Claude/ECC role families. When the backend supports model choice, prefer the cheapest capable executor. When it does not, compensate by reducing unnecessary delegation and keeping handoffs compact.

## Operating rules
- Make architectural decisions at orchestrator level.
- Run independent research or implementation tracks in parallel when the environment supports it.
- If parallel sub-agents are unavailable, still keep the phases explicit: assessment -> research -> planning -> execution -> validation.
- In full-stack repos, split backend and frontend work by ownership boundary before deciding whether the tracks can run in parallel.
- In domain-heavy repos, run a separate domain-rules review whenever business rules, statuses, calculations, or critical flows change.
- Prefer concise decision-focused reporting over long code walkthroughs.
- After code changes, always validate compilation, logic, and code quality.
- Prefer executor agents for routine implementation when ownership is clear.
- Keep the main orchestrator for synthesis, integration, and unblockers rather than default execution.
- Before each delegated implementation step, prepare a compact handoff packet with goal, facts, constraints, files, and expected output.
- Share results between agents through orchestrator-synthesized handoff packets, not by assuming peer-to-peer shared state.
- If the next implementation step is already clear, do not extend research just to satisfy process ceremony.
- Use the cheapest capable executor or reviewer whenever the environment exposes model tiers.
- Default execution shape should be `orchestrator plan -> one executor -> validation`, not `many agents by default`.
- Add a second executor only for truly disjoint files or layers.
- Add a research agent only for missing facts, not for routine repo reading.
- Add a review agent only after implementation, unless the task is security- or architecture-sensitive from the start.

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

For a target repository, prefer its own local role docs, paths, stack constraints, verification commands, and documented domain source of truth.

The shared skills in this repository should act as orchestration glue, not as a replacement for project-local agent definitions.
