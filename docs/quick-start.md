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

Install the portable skills:

```bash
npx skills add quokkify/skills --skill '*' -g -a claude-code -y
```

No global Claude configuration is copied. Agent personas, output styles, status lines, and project-specific commands remain user- or project-owned.

## Codex

Install the portable skills:

```bash
npx skills add quokkify/skills --skill '*' -g -a codex -y
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
npx skills add quokkify/skills --skill '*' -g -a claude-code -a codex -y
./scripts/install-codex-agents.sh /path/to/your/project
```

## Update the Shared Checkout

From its clean `main` branch:

```bash
./scripts/sync-shared-skills.sh
```

The sync helper updates the Git checkout. Rerun the Codex adapter installer when its copied `AGENTS.md` changes.
