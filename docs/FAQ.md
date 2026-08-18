---
title: FAQ
---

# FAQ

## Do I need all three supported agents?

No. Install or connect only the path you use. Claude Code and Codex can share the same portable skills, while Hermes reads the canonical directory directly.

## Why are skills and adapters separate?

They have different responsibilities:

- `skills/` contains portable workflow knowledge shared by every supported agent.
- `adapters/` contains configuration specific to Claude Code, Codex, or Hermes, plus the runtime-neutral global templates under `adapters/shared/`.

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

`./scripts/install-codex-agents.sh /path/to/project` copies `adapters/codex/AGENTS.md` into the target project as `AGENTS.md`. It does not change the canonical files under `skills/`.

The global adapter templates under `adapters/shared/`, `adapters/claude/`, and `adapters/codex/` have no installer yet; copy them manually until the merging installer ships in a follow-up change. Whatever installs them must back up existing files, never silently overwrite a user's configuration, and preserve managed blocks written by other tools, such as `<!-- OMC:START -->…<!-- OMC:END -->`.

## Does this repository publish global configuration?

It publishes **genericized templates**, not anyone's configuration. A runtime-neutral instruction base and lifecycle hook scripts live in `adapters/shared/`; per-runtime settings templates, hook wiring, subagent definitions, and an injectable `CLAUDE.md` block live in `adapters/claude/` and `adapters/codex/`.

Real personal content—employer conventions, project trust lists, credentialed MCP servers, private skills, machine paths, session or transcript state—remains forbidden here and belongs in a private overlay repository merged at install time. [ADR-0001](adr/0001-publish-generic-global-agent-adapters.md) records why the earlier "no global configuration" boundary was superseded and what stays out.

## Where should Claude Code sub-agents live?

At runtime they live in your own `~/.claude/agents/`, or with the project that owns them. This repository may publish **subagent definition templates** under `adapters/claude/`, but only genericized ones: capability-based roles with no employer context, no private tool names, and no pinned personal model versions. A persona tied to one employer, project, or model choice stays in your private overlay.

## How do I migrate from the old root-level layout?

Hermes recursively discovers nested skills, so an existing repository-root entry remains compatible. Point `skills.external_dirs` at `<checkout>/skills` if you want discovery limited to the canonical directory. The Codex installer command stays the same. Reinstall or update skills managed by the skills CLI so recorded source paths follow the new layout.

The old layout's global Claude configuration bundle—one user's real `~/.claude` tree—was removed and is not coming back. Its replacement is the genericized template layer under `adapters/`, which shares none of that content; see [ADR-0001](adr/0001-publish-generic-global-agent-adapters.md).

## Can a target project have its own rules?

Yes. Keep stack- and domain-specific rules in the target project, such as `AGENTS.md`, `CLAUDE.md`, or project-local skills. This repository should remain portable and generic.
