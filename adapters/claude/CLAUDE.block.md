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

- **oh-my-claudecode is required.** It is the orchestration layer on this runtime: it owns the
  agent catalog, model routing, and the plan → execute → review → verify workflows. Route
  delegation through its agents and workflows instead of inventing roles or re-implementing them
  from portable skills.
- **superpowers is required.** oh-my-claudecode owns planning and execution here (its `plan`,
  `ralplan`, `deep-interview`, `execute`, `review`, and `verify`). From superpowers, use
  `brainstorming` for design exploration of new features and the discipline skills
  (`test-driven-development`, `systematic-debugging`, `verification-before-completion`,
  `receiving-code-review`) inside each oh-my-claudecode step. Do not use superpowers
  `writing-plans`, `executing-plans`, or `subagent-driven-development` on this runtime;
  oh-my-claudecode replaces them.
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
