<!-- SKILLS-HUB:START -->
<!--
Managed block. The forthcoming installer injects everything between the SKILLS-HUB markers
into ~/.claude/CLAUDE.md and rewrites it in place on every run. Hand edits inside these
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
