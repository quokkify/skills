<!-- SKILLS-HUB:START -->
<!--
Managed block. `scripts/bootstrap.sh` injects everything between the SKILLS-HUB markers
into the configured Claude `CLAUDE.md` and updates it idempotently. Hand edits inside these
markers are lost. Put machine-local or personal rules OUTSIDE this block, or in a private
overlay file imported from outside it.

Installer substitution: the literal token @__SHARED_BASE__ below is replaced with an @-import
of the installed shared base, normally @~/.claude/skills-hub/AGENTS.base.md. Claude Code
resolves @-imports up to five hops deep, so the base may import further files itself.
-->

# Shared Agent Base

@__SHARED_BASE__

## Claude Code Deltas

The shared base is runtime-neutral. These points are specific to this runtime.

- **superpowers is required and owns the process.** Run its chain end to end: `brainstorming` →
  `writing-plans` → the execution mode the user picks at its handoff (`subagent-driven-development`
  or `executing-plans`; each runs its own reviews and ends in `finishing-a-development-branch`).
  Use `test-driven-development`, `systematic-debugging`, `requesting-code-review`,
  `receiving-code-review`, and `verification-before-completion` wherever they apply. Do not swap
  a step for an oh-my-claudecode workflow partway through the chain.
- **oh-my-claudecode is required and owns the agents.** It supplies the agent catalog, model
  routing, and hooks. When a superpowers skill dispatches a subagent, use `executor` for
  implementers and fixes, and `code-reviewer` for reviewers. The skill's prompt template replaces
  the agent's default task, including its report format. Map the skill's model tiers to
  `haiku` (cheap), `sonnet` (standard), and `opus` (most capable), and pass the model explicitly.
  Outside the chain, use `explore` for ad-hoc codebase search.
- **oh-my-claudecode workflows are opt-in.** `plan`, `ralplan`, `deep-interview`, `execute`,
  `review`, `verify`, `autopilot`, `ralph`, `team`, and `ultragoal` run only when the user types
  the workflow's slash command or asks for it by name. A trigger keyword that the hook detects in
  incidental text does not count. The "canonical workflows" list in the oh-my-claudecode managed
  block does not set the process on this runtime.
- **Missing companion.** The shared `sessionstart-prerequisites.sh` hook reports either one when
  it is not installed. Then tell the user what is missing and how to install it before any
  substantive work, and continue without it only when the user explicitly says so.
- **Subagents** are addressed through the Task/Agent tool by agent type, with definitions in
  `~/.claude/agents/*.md` (user scope) or `.claude/agents/*.md` (project scope). Do not hardcode a
  roster in instruction files; read the available types at run time.
- **Skills** are invoked as slash commands (`/<skill-name>`); project skills live in
  `.claude/skills/`. Verify a skill exists before invoking it.
- **Claude-only features** — plugins and marketplaces, a scriptable `statusLine`,
  `output-styles/`, the `permissions.allow` grammar, `disabledMcpjsonServers`, `skillOverrides`,
  the project-level `.mcp.json` convention, and `CLAUDE_CONFIG_DIR` — exist here and have no
  equivalent in other runtimes. Never assume they are available when writing portable guidance.
- **Hooks** follow the JSON-on-stdin contract shared with other runtimes, so hook scripts are
  portable even though their registration in `settings.json` is not.
- **Other managed blocks** in this file (for example an oh-my-claudecode block delimited by its own
  markers) are written by their own tooling. Do not hand-edit them and do not move them inside
  these markers.

<!-- SKILLS-HUB:END -->
