---
title: How to Use These Skills
---

# How to Use These Skills

This repository has two intentionally separate layers:

1. `skills/` — portable workflow knowledge and the only source of truth.
2. `adapters/` — optional integration files for a specific agent.

## Claude Code

Install the portable skills with the skills CLI. Claude Code supports personal skills under `~/.claude/skills` and project skills under `.claude/skills`.

The optional `./scripts/install-claude-config.sh` helper copies the files under `adapters/claude/` into `~/.claude`. These include agent definitions, commands, an output style, and a status line; they are not additional copies of the skills.

## Codex

Install the same portable skills for Codex. Codex discovers repository skills by walking from the current directory to the repository root and looking under `.agents/skills`; personal skills live under `$HOME/.agents/skills`.

The optional `./scripts/install-codex-agents.sh /path/to/project` helper copies `adapters/codex/AGENTS.md` into a target project. The repository deliberately does not maintain a duplicate `.codex/skills` tree.

## Hermes

Hermes reads the canonical directory directly:

```yaml
skills:
  external_dirs:
    - /absolute/path/to/skills/skills
```

Start a new session after changing the path or updating the checkout. External directories remain writable when filesystem permissions allow it, so use a Git branch or worktree for shared changes rather than editing the stable checkout through skill-management tools.

A same-named local Hermes skill can take precedence over an external one. Resolve collisions before assuming the shared copy is active.

## Safe Checkout Updates

From a clean direct checkout on `main`:

```bash
./scripts/sync-shared-skills.sh
```

The helper validates one exact fetched commit with a preserved copy of the current validator, rejects ahead or diverged history, disables Git hooks during the fast-forward, and never executes fetched scripts. Concurrent branch or worktree changes cause an error rather than a false success report.

The helper updates the repository only. If you copied adapter files into another location, rerun the relevant installer when `adapters/` changes.

## Environment-Aware Orchestration

The portable orchestration skills prefer instructions from the target project before their bundled defaults. When a project provides Everything Claude Code or another local role catalog, those project-local roles remain authoritative.

The execution shape intentionally differs by agent:

- Claude's optional adapter provides explicit junior, middle, and senior model routing.
- Codex defaults to a compact `plan -> executor -> validation` flow and adds research or review roles only for distinct risks.

The workflow remains shared; only delegation mechanics and tool-specific configuration belong in an adapter or target project.

## Project-Specific Rules

Keep stack- and domain-specific instructions in the target project, for example:

- `AGENTS.md` for Codex or other compatible agents
- `CLAUDE.md` for Claude Code
- `.agents/skills/<name>/SKILL.md` or `.claude/skills/<name>/SKILL.md` for truly project-local skills

Do not copy shared skills into multiple tracked directories in this repository.

## Related Pages

- [Quick Start](../quick-start.md)
- [Reviewing and Promoting Skills](reviewing-and-promoting-skills.md)
- [FAQ](../FAQ.md)
