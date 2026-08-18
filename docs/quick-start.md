---
title: Quick Start
---

# Quick Start

Clone the repository and run commands from its root:

```bash
git clone https://github.com/quokkify/skills.git
cd skills
```

## Claude Code

Install the portable skills and Claude adapter:

```bash
./scripts/bootstrap.sh --provider claude --install-skills
```

The installer merges genericized templates into the selected runtime home, backs up changed files with a timestamp, and preserves foreign managed blocks. Add `--overlay /path/to/private-overlay` to layer private files after the public base. The overlay is read in place and is never copied into the checkout.

Your own employer conventions, project trust lists, credentialed MCP servers, private skills, and machine paths stay in your private overlay, outside this repository. See [ADR-0001](adr/0001-publish-generic-global-agent-adapters.md).

## Codex

Install the portable skills and Codex adapter:

```bash
./scripts/bootstrap.sh --provider codex --install-skills
```

The global Codex instruction file is a symlink to the checkout's shared base. After installation, open the Codex TUI and run `/hooks` to approve command hooks. For project-specific instructions, copy `adapters/codex/AGENTS.md` into a target project:

```bash
./scripts/install-codex-agents.sh /path/to/your/project
```

Codex discovers project-local skills from `.agents/skills`, not `.codex/skills`.

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

Add the canonical skill directory—not the repository root—to the Hermes configuration:

```yaml
skills:
  external_dirs:
    - /absolute/path/to/skills/skills
```

Start a new Hermes session after changing the discovery path. Keep shared edits on an isolated Git branch or worktree; an external directory is not a write-protection boundary.

## Claude Code and Codex Together

```bash
./scripts/bootstrap.sh --install-skills
```

The default provider is `all`. Use `--dry-run` to inspect the complete operation list safely.

## Update the Shared Checkout

From its clean `main` branch:

```bash
./scripts/sync-shared-skills.sh
```

The sync helper updates the Git checkout. Rerun the Codex adapter installer when its copied `AGENTS.md` changes.
