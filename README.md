# cc-subagents-repo

This repo adds a reusable sub-agent workflow for Claude Code and Codex.
If you want the short version: install the skills, run one script from this repo, and start working.

## Quick Start

Clone this repo first, then run the commands below from the repo root.
Choose one path below.

### Claude

1. Install Claude Code.
2. Install the skills from this repo:

```bash
npx skills add <your-git-url-or-owner/repo> --skill '*' -g -a claude-code -y
```

3. Run the Claude setup script:

```bash
./scripts/install-claude-config.sh
```

Done: Claude Code gets the reusable skills, and the Claude config is copied into `~/.claude`.

### Codex

1. Install Codex.
2. Install the skills from this repo:

```bash
npx skills add <your-git-url-or-owner/repo> --skill '*' -g -a codex -y
```

3. Copy the Codex project instructions into the repo where you want to work:

```bash
./scripts/install-codex-agents.sh /path/to/your/project
```

Done: Codex gets the reusable skills, and your target repo gets an `AGENTS.md` file for this workflow.

### If You Use Both Claude and Codex

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

The `orchestrator-workflow` skill detects the active environment automatically and selects the appropriate delegation backend — no manual configuration needed.

## What Each Script Does

`./scripts/install-claude-config.sh`
- creates `~/.claude`
- copies `CLAUDE.md`
- copies `agents/`, `commands/`, and `output-styles/`
- installs `statusline-command.sh`

`./scripts/install-codex-agents.sh /path/to/your/project`
- creates the target directory if needed
- copies `codex/AGENTS.md` into that repo as `AGENTS.md`

## What Is In This Repo

- `orchestrator-workflow/` - main orchestration skill for complex tasks. Environment-aware: resolves delegation backend from the active environment (Claude Code + ECC agents, Codex built-in roles, or `dmux`/worktrees as fallback). Integrates with Everything Claude Code when present.
- `refactor-workflow/` - orchestration skill for refactoring tasks
- `claude-config/` - Claude-specific global config
- `codex/AGENTS.md` - Codex project instructions
- `scripts/` - install helpers

## Important Notes

- Installing the skills and installing the Claude config are different steps.
- For Claude, the skills alone are not the full setup. You also need `./scripts/install-claude-config.sh`.
- For Codex, `claude-config/` is not required. The Codex flow uses the skills plus `AGENTS.md` in the target repo.

## Adapting This To Your Project

This repo is the shared orchestration layer. Your target project can still define its own local roles and rules.

Recommended approach:

1. Keep these shared skills focused on orchestration.
2. Put stack-specific roles inside the target repo, for example in `AGENTS.md` or `.agents/**/SKILL.md`.
3. Let Codex prefer project-local instructions first and use the shared references here as fallback.

Example local roles:
- backend role -> Django / DRF / PostgreSQL
- frontend role -> React / TypeScript / Vite
- domain reviewer -> `DOMAIN_RULES.md`
- plan reviewer -> final check against the approved plan

### Everything Claude Code (ECC) Integration

If your target repo uses [Everything Claude Code](https://github.com/disler/everything-claude-code), the `orchestrator-workflow` skill integrates with it automatically:

- ECC project-local guidance takes priority over portable defaults
- ECC agent roles (`planner`, `tdd-guide`, `code-reviewer`, `security-reviewer`, `doc-updater`, etc.) are used for delegation in Claude
- Codex ECC roles (`explorer`, `docs_researcher`, `reviewer`) are used in Codex
- ECC validation conventions (`verification-loop`) are applied in Phase 5

No additional setup is needed. The orchestrator reads local role docs and ECC config during Phase 1.

## Skill Layout

The reusable skills live at the repo root:

- `orchestrator-workflow/SKILL.md`
- `refactor-workflow/SKILL.md`

Each skill also includes bundled reference files, so it still works even when Claude-specific global files are not present.
