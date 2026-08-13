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
