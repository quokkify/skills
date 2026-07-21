# Shared Agent Skills

Reusable agent workflows for **Claude Code**, **Codex**, and **Hermes**.

The repository keeps every portable skill in one canonical directory: [`skills/`](skills). Tool-specific files live separately in [`adapters/`](adapters), so workflow instructions are not duplicated or allowed to drift between agents.

## Repository Layout

```text
skills/
├── orchestrator-workflow/   # complex implementation workflow
├── refactor-workflow/       # controlled refactoring workflow
└── skill-review/            # review and promotion of reusable lessons

adapters/
├── claude/README.md         # Claude Code connection notes
├── codex/AGENTS.md          # optional Codex project instructions
└── hermes/                  # Hermes configuration example

docs/                        # detailed guides
scripts/                     # install, validation, and safe-sync helpers
tests/                       # dependency-free regression tests
```

`skills/` is the only source of truth for skills. Claude Code can discover project skills from `.claude/skills`, while Codex uses `.agents/skills`; this repository does not duplicate the same skills into those consumer-specific locations. Codex does not use `.codex/skills` as its project skill directory.

## Quick Start

Clone the repository:

```bash
git clone https://github.com/ylazakovich/skills.git
cd skills
```

### Claude Code

Install all portable skills:

```bash
npx skills add ylazakovich/skills --skill '*' -g -a claude-code -y
```

Claude Code needs no copied global adapter. Agent personas, output styles, status lines, and project-specific commands remain user- or project-owned.

### Codex

Install all portable skills:

```bash
npx skills add ylazakovich/skills --skill '*' -g -a codex -y
```

Optional: copy the shared Codex instructions into a target project:

```bash
./scripts/install-codex-agents.sh /path/to/your/project
```

This creates `/path/to/your/project/AGENTS.md` from [`adapters/codex/AGENTS.md`](adapters/codex/AGENTS.md).

### Hermes

Point Hermes directly at the canonical skill directory:

```yaml
skills:
  external_dirs:
    - /absolute/path/to/skills/skills
```

The same example is available at [`adapters/hermes/config.example.yaml`](adapters/hermes/config.example.yaml). Start a new Hermes session after adding or updating the directory.

A same-named skill under the local Hermes skill directory can take precedence over the shared copy. Keep shared changes in a Git branch or worktree rather than editing the stable checkout through skill-management tools.

## Available Skills

- [`orchestrator-workflow`](skills/orchestrator-workflow/SKILL.md) — plans and coordinates complex implementation tasks across supported agent environments.
- [`refactor-workflow`](skills/refactor-workflow/SKILL.md) — performs refactoring with explicit discovery, implementation, and verification phases.
- [`skill-review`](skills/skill-review/SKILL.md) — audits reusable lessons and promotes approved changes through a branch and pull request.

## Update A Shared Checkout

From a clean checkout on `main`:

```bash
./scripts/sync-shared-skills.sh
```

The helper fetches only `origin/main`, validates the exact fetched snapshot with the currently trusted validator, allows fast-forward updates only, disables Git hooks during branch movement, and rejects concurrent checkout changes. It never executes scripts from the fetched tree.

Copied Codex adapter files are not refreshed by this command. Rerun its installer when `adapters/codex/AGENTS.md` changes.

### Migrating From 0.3.x

- Hermes recursively discovers nested skills, so an existing repository-root entry remains compatible. Point it at `<checkout>/skills` to narrow discovery to the canonical directory.
- The former global Claude configuration bundle is intentionally no longer published; the Codex installer source moved from `codex/` to `adapters/codex/`.
- Reinstall or update skills managed by the skills CLI so its recorded source paths use the new layout.

## Validate Changes

Run the portable CI-equivalent checks:

```bash
./scripts/validate.sh --ci
```

Run the complete local gate, including full-history Gitleaks scanning:

```bash
./scripts/validate.sh --full
```

Gitleaks `8.30.1` or newer must be available on `PATH` or through `GITLEAKS_BIN` for `--full`.

Optional repository-local Git hooks:

```bash
./scripts/install-git-hooks.sh
```

The validator requires every skill entry point to live at `skills/<skill-name>/SKILL.md`. It also checks frontmatter, duplicate names, Markdown links, symlinks, machine-specific paths, and public/private boundaries.

## Security

This is a public repository. Do not commit credentials, memories, transcripts, sessions, runtime databases, private project context, or machine-specific configuration. Read [SECURITY.md](SECURITY.md) before promoting locally generated material.

Every pull request runs repository validation and Gitleaks. Scanner success complements manual privacy review; it does not prove that content is appropriate to publish.

## Documentation

- [Quick start](docs/quick-start.md)
- [Using the skills](docs/guides/how-to-use-skills.md)
- [Reviewing and promoting skills](docs/guides/reviewing-and-promoting-skills.md)
- [Releases and dependency updates](docs/guides/releases-and-dependencies.md)
- [FAQ](docs/FAQ.md)
