---
title: How to Use These Skills
---

# How to Use These Skills

This repository has three intentionally separate layers:

1. `skills/` — portable workflow knowledge and the only source of truth.
2. `adapters/` — optional integration files and genericized global templates for a specific agent runtime, plus the runtime-neutral base under `adapters/shared/`.
3. A **private overlay**, kept in a separate repository, holding your real personal, employer, and machine-specific configuration.

Layers 1 and 2 are public because they contain no one's actual configuration. Layer 3 is never published here.

## Claude Code

Install the portable skills with the skills CLI. Claude Code supports personal skills under `~/.claude/skills` and project skills under `.claude/skills`.

Global configuration is separate and optional. The templates under `adapters/shared/` and `adapters/claude/` are genericized: a runtime-neutral instruction base, lifecycle hook scripts, settings and hook wiring, subagent definitions, and an injectable `CLAUDE.md` block. They contain no employer identifiers, credentials, machine paths, or pinned personal model versions. Copy them manually for now; a one-command installer that merges your private overlay over the templates arrives in a follow-up change, and any such installer must back up rather than overwrite existing files.

## Codex

Install the same portable skills for Codex. Codex discovers repository skills by walking from the current directory to the repository root and looking under `.agents/skills`; personal skills live under `$HOME/.agents/skills`.

The optional `./scripts/install-codex-agents.sh /path/to/project` helper copies `adapters/codex/AGENTS.md` into a target project. The repository deliberately does not maintain a duplicate `.codex/skills` tree.

For a manual installation of the full Codex adapter (including hooks, configuration, and agent definitions):

1. Set \$CODEX_HOME (defaults to `$HOME/.codex`). Export it so it stays set across each of the following commands, even if you run them as separate shell invocations:
   ```sh
   export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
   ```
2. Create necessary directories:
   ```sh
   mkdir -p "$CODEX_HOME/agents" "$CODEX_HOME/hooks"
   ```
3. Copy shared hook scripts (required for hooks in hooks.json to function), backing up any file already there:
   ```sh
   for f in sessionstart-repo-context.sh pretooluse-bash-guard.sh completion-gate.sh hook-lib.sh; do
     [ -e "$CODEX_HOME/hooks/$f" ] && cp "$CODEX_HOME/hooks/$f" "$CODEX_HOME/hooks/$f.bak"
     cp "adapters/shared/hooks/$f" "$CODEX_HOME/hooks/"
   done
   ```
4. Copy Codex-specific configuration and agent definitions, backing up any file already there:
   ```sh
   # Base config — do not overwrite an existing config.toml
   if [ ! -f "$CODEX_HOME/config.toml" ]; then
     cp adapters/codex/config.template.toml "$CODEX_HOME/config.toml"
   else
     echo "Warning: $CODEX_HOME/config.toml exists, skipping copy. Merge manually if needed."
   fi
   [ -e "$CODEX_HOME/hooks.json" ] && cp "$CODEX_HOME/hooks.json" "$CODEX_HOME/hooks.json.bak"
   cp adapters/codex/hooks.json "$CODEX_HOME/hooks.json"
   for f in adapters/codex/agents/*.toml; do
     base="$(basename "$f")"
     [ -e "$CODEX_HOME/agents/$base" ] && cp "$CODEX_HOME/agents/$base" "$CODEX_HOME/agents/$base.bak"
     cp "$f" "$CODEX_HOME/agents/"
   done
   ```
5. In the Codex TUI, run `/hooks` and approve the hook entries.

Note: The current hook set includes SessionStart, PreToolUse (bash-guard), and Stop. Other runtime events are not covered by the shipped hook scripts; you may add additional hooks as needed.

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

The helper updates the repository only. If you copied the Codex adapter into another location, rerun its installer when `adapters/codex/AGENTS.md` changes.

## Environment-Aware Orchestration

The portable orchestration skills prefer instructions from the target project before their bundled defaults. When a project provides Everything Claude Code or another local role catalog, those project-local roles remain authoritative.

The execution shape intentionally differs by agent:

- Claude Code prefers user- or project-owned routing when available. The published `adapters/` templates offer a genericized starting point that selects roles by capability; they do not pin model versions or encode one user's routing policy, and a private overlay or project file always wins.
- Codex defaults to a compact `plan -> executor -> validation` flow and adds research or review roles only for distinct risks.

The workflow remains shared; only delegation mechanics and tool-specific configuration belong in an adapter or target project.

## Project-Specific Rules

Keep stack- and domain-specific instructions in the target project, for example:

- `AGENTS.md` for Codex or other compatible agents
- `CLAUDE.md` for Claude Code
- `.agents/skills/<name>/SKILL.md` or `.claude/skills/<name>/SKILL.md` for truly project-local skills

Do not copy shared skills into multiple tracked directories in this repository, and do not duplicate a skill body into an adapter.

## Related Pages

- [Quick Start](../quick-start.md)
- [ADR-0001: Publish generic global agent adapters](../adr/0001-publish-generic-global-agent-adapters.md)
- [Reviewing and Promoting Skills](reviewing-and-promoting-skills.md)
- [FAQ](../FAQ.md)
