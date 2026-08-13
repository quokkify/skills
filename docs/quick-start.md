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

That command installs skills only. Global configuration is a separate, optional layer: this repository publishes **genericized templates** under `adapters/shared/` and `adapters/claude/`—a runtime-neutral instruction base, lifecycle hook scripts, and per-runtime wiring—and never anyone's real configuration. Copy them by hand for now; a one-command installer that merges a private overlay over the templates arrives in a follow-up change.

Your own employer conventions, project trust lists, credentialed MCP servers, private skills, and machine paths stay in your private overlay, outside this repository. See [ADR-0001](adr/0001-publish-generic-global-agent-adapters.md).

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
