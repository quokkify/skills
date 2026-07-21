---
title: FAQ
---

# FAQ

## Do I need all three supported agents?

No. Install or connect only the path you use. Claude Code and Codex can share the same portable skills, while Hermes reads the canonical directory directly.

## Why are skills and adapters separate?

They have different responsibilities:

- `skills/` contains portable workflow knowledge shared by every supported agent.
- `adapters/` contains configuration specific to Claude Code, Codex, or Hermes.

Keeping those layers separate prevents three copies of the same skill from drifting apart.

## Should this repository contain `.claude/skills` and `.codex/skills`?

No. Claude Code uses `.claude/skills` for project-local discovery, but that is a consumer location rather than this repository's canonical store. Codex uses `.agents/skills` for project-local discovery; `.codex/skills` is not its documented project skill path.

Installers can place skills into each agent's supported discovery location without duplicating their source in Git.

## Can Hermes use the new layout directly?

Yes. Point `skills.external_dirs` at the nested canonical directory:

```yaml
skills:
  external_dirs:
    - /absolute/path/to/skills/skills
```

Start a new session after changing the path.

## Can Hermes edit an external skill directory?

Yes, if the process has filesystem write access. External directories are discovery sources, not read-only boundaries. Make shared changes in a separate Git branch or worktree and submit them through review.

A same-named local Hermes skill can take precedence over the shared version.

## What do the adapter installers do?

`./scripts/install-claude-config.sh` copies the optional Claude files from `adapters/claude/` into `~/.claude`.

`./scripts/install-codex-agents.sh /path/to/project` copies `adapters/codex/AGENTS.md` into the target project as `AGENTS.md`.

Neither script changes the canonical files under `skills/`.

## Why does delegation differ between Claude Code and Codex?

The agents expose different routing controls. The optional Claude adapter defines explicit junior, middle, and senior model tiers. Codex generally controls cost with fewer delegations and a compact `plan -> executor -> validation` loop. Both still use the same portable workflow from `skills/`.

## How do I migrate from the old root-level layout?

Change Hermes `skills.external_dirs` from the repository root to `<checkout>/skills`. The adapter installer commands stay the same even though their source files moved under `adapters/`. Reinstall or update skills managed by the skills CLI so recorded source paths follow the new layout.

## Can a target project have its own rules?

Yes. Keep stack- and domain-specific rules in the target project, such as `AGENTS.md`, `CLAUDE.md`, or project-local skills. This repository should remain portable and generic.
