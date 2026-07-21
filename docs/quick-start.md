---
title: Quick Start
---

# Quick Start

Clone the repository and run commands from its root:

```bash
git clone https://github.com/ylazakovich/skills.git
cd skills
```

## Claude Code

Install the portable skills:

```bash
npx skills add ylazakovich/skills --skill '*' -g -a claude-code -y
```

Optionally install the files from `adapters/claude/` into `~/.claude`:

```bash
./scripts/install-claude-config.sh
```

## Codex

Install the portable skills:

```bash
npx skills add ylazakovich/skills --skill '*' -g -a codex -y
```

Optionally copy `adapters/codex/AGENTS.md` into a target project:

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
npx skills add ylazakovich/skills --skill '*' -g -a claude-code -a codex -y
./scripts/install-claude-config.sh
./scripts/install-codex-agents.sh /path/to/your/project
```

## Update the Shared Checkout

From its clean `main` branch:

```bash
./scripts/sync-shared-skills.sh
```

The sync helper updates the Git checkout. Rerun an adapter installer when copied files under `adapters/` change.
