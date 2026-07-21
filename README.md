# cc-subagents-repo

This repo adds reusable agent workflows for Claude Code, Codex, and Hermes.
If you want the short version: choose your tool below, connect the skills, and start working.

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

### Hermes

1. Clone this repository.
2. Add its root directory to the `skills.external_dirs` list in your Hermes configuration:

```yaml
skills:
  external_dirs:
    - /path/to/skills
```

3. Start a new Hermes session; after significant work, load `/skill-review` to decide whether a reusable lesson should be proposed.

Hermes external skill directories are mutable when filesystem permissions allow writes. Inspect shared skills normally, but promote approved changes through a Git branch or worktree instead of editing the shared checkout in place.

### Cost Expectations

- Claude + ECC has the most predictable cost ladder because the Claude config includes explicit junior/middle/senior routing aligned to Haiku, Sonnet, and Opus style usage.
- Codex is cost-aware too, but usually controls cost through fewer delegations, shorter handoffs, and tighter execution loops rather than the same fine-grained per-role model ladder.
- In practice, expect Claude/ECC to be better at cheapest-capable model routing, and Codex to be better when you keep execution compact: `plan -> one executor -> validation`.

### If You Use Claude and Codex

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

`./scripts/validate.sh --fast`
- validates skill frontmatter and directory names
- detects duplicate skill names and Markdown filenames that would shadow a skill in Hermes
- checks documentation links and targeted public-boundary rules

`./scripts/validate.sh --full`
- runs the fast checks, validator unit tests, and a Zensical documentation build
- rejects shallow clones and scans the complete Git history with Gitleaks
- requires Gitleaks 8.30.1 or newer on `PATH`, or in `GITLEAKS_BIN`

`./scripts/install-git-hooks.sh`
- configures this checkout to use the tracked `.githooks/` directory
- validates the staged snapshot before commits
- requires a clean worktree and validates the exact checked-out `HEAD` before pushes
- refuses to replace an existing `core.hooksPath` unless `--force` is explicitly supplied

`./scripts/sync-shared-skills.sh`
- updates a clean `main` checkout from `origin/main` using fetch plus fast-forward only
- validates the fetched tree with the currently trusted validator and its CI gate before moving `main`
- runs the CI validation gate after the update and refuses ahead or diverged histories
- prints the new-session step for Hermes; it does not restart an agent or reinstall copied Claude/Codex files

## Local Validation

Run the full gate before opening a pull request:

```bash
./scripts/validate.sh --full
```

To enable the same checks as repository-local Git hooks:

```bash
./scripts/install-git-hooks.sh
```

The validation workflow runs the portable checks on pull requests. The separate Secret Scan workflow remains the authoritative full-history Gitleaks gate in GitHub Actions.

## Updating A Shared Checkout

For a checkout used directly through Hermes `skills.external_dirs`, run:

```bash
./scripts/sync-shared-skills.sh
```

The command is fail-closed: it requires a clean `main`, fetches only `origin/main`, rejects non-fast-forward histories, validates the fetched snapshot with both the trusted current validator and the candidate CI gate before moving the branch, and validates again after the update. It never publishes local skills, changes Hermes configuration, or restarts a running agent.

After a successful update, start a new Hermes session so the external skill directory is discovered again. Claude/Codex files installed by copying are not refreshed by this command; use their normal installation flow when those copied adapters change.

## What Is In This Repo

- `orchestrator-workflow/` - main orchestration skill for complex tasks. Environment-aware: resolves delegation backend from the active environment (Claude Code + ECC agents, Codex built-in roles, or `dmux`/worktrees as fallback). Integrates with Everything Claude Code when present.
- `refactor-workflow/` - orchestration skill for refactoring tasks
- `skill-review/` - controlled post-task review and branch/PR promotion workflow for reusable lessons
- `claude-config/` - Claude-specific global config
- `codex/AGENTS.md` - Codex project instructions
- `.githooks/` - opt-in staged and pre-push validation hooks
- `scripts/` - install, validation, and safe shared-checkout helpers
- `tests/` - dependency-free validator and sync regression tests

## Important Notes

- Installing the skills and installing the Claude config are different steps.
- For Claude, the skills alone are not the full setup. You also need `./scripts/install-claude-config.sh`.
- For Codex, `claude-config/` is not required. The Codex flow uses the skills plus `AGENTS.md` in the target repo.
- For Hermes, point `skills.external_dirs` at the repository root. A same-named local Hermes skill takes precedence over the shared version.
- If cost predictability matters most, keep in mind that Claude and Codex do not expose the exact same routing controls. This repo now documents both paths separately.

## Security and Privacy

This repository is public and should contain only portable, redacted agent instructions. Keep credentials, memories, transcripts, snapshots, runtime databases, personal context, and private project rules outside this repository. Read [SECURITY.md](SECURITY.md) before promoting a locally generated skill or configuration change.

Every pull request runs a full-history Gitleaks scan. Scanner success complements manual review; it does not make personal or proprietary data safe to publish.

## Releases and Dependency Updates

Release Please creates version and changelog pull requests from Conventional Commit titles. Renovate maintains pinned GitHub Actions dependencies, and its configuration is validated on changes and weekly. See [Releases and dependency updates](docs/guides/releases-and-dependencies.md) for the complete workflow.

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

### Cost and Tempo by Environment

The execution model is intentionally different between environments:

- Claude + ECC:
  - favors explicit cheapest-capable routing
  - mechanical work should fall to junior/Haiku-class agents
  - normal implementation should fall to middle/Sonnet-class agents
  - senior/Opus-class agents should be reserved for ambiguity, architecture, and recovery

- Codex + ECC-style orchestration:
  - favors a compact execution shape over many agents
  - default shape should be `plan -> one executor -> validation`
  - research and review agents should be added only when they remove real uncertainty or cover a distinct risk
  - cost control comes mostly from fewer delegations and smaller handoff packets

## Skill Layout

The reusable skills live at the repo root:

- `orchestrator-workflow/SKILL.md`
- `refactor-workflow/SKILL.md`
- `skill-review/SKILL.md`

Each skill also includes bundled reference files, so it still works even when Claude-specific global files are not present.
