---
title: Quick Start
---

# Quick Start

Clone this repo first. Run the commands below from the repo root.

## Claude

1. Install Claude Code.
2. Install the skills from this repo:

```bash
npx skills add <your-git-url-or-owner/repo> --skill '*' -g -a claude-code -y
```

3. Run:

```bash
./scripts/install-claude-config.sh
```

Done:

- Claude Code gets the reusable skills
- the Claude config is copied into `~/.claude`

## Codex

1. Install Codex.
2. Install the skills from this repo:

```bash
npx skills add <your-git-url-or-owner/repo> --skill '*' -g -a codex -y
```

3. Run:

```bash
./scripts/install-codex-agents.sh /path/to/your/project
```

Done:

- Codex gets the reusable skills
- your target repo gets an `AGENTS.md` file for this workflow

## Hermes

1. Clone this repository.
2. Add the repository root to `skills.external_dirs` in your Hermes configuration:

```yaml
skills:
  external_dirs:
    - /path/to/skills
```

3. Start a new session; after significant work, load `/skill-review` to decide whether a reusable lesson should be proposed.

Hermes external directories are mutable when the process has filesystem write access. Promote shared changes through a Git branch or worktree, not an in-place skill-management edit.

To update this direct shared checkout later, run `./scripts/sync-shared-skills.sh` from its clean `main` branch, then start a new Hermes session so the external skill directory is discovered again.

## If You Use Claude and Codex

Install both skill targets at once:

```bash
npx skills add <your-git-url-or-owner/repo> --skill '*' -g -a claude-code -a codex -y
```

Then run:

```bash
./scripts/install-claude-config.sh
./scripts/install-codex-agents.sh /path/to/your/project
```

Use this when:

- you want Claude to get the global config from `claude-config/`
- you want Codex to get `AGENTS.md` inside a working project

## What The Scripts Do

`./scripts/install-claude-config.sh`

- creates `~/.claude`
- copies `CLAUDE.md`
- copies `agents/`, `commands/`, and `output-styles/`
- installs `statusline-command.sh`

`./scripts/install-codex-agents.sh /path/to/your/project`

- creates the target directory if needed
- copies `codex/AGENTS.md` into that repo as `AGENTS.md`
