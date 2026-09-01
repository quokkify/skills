# Shared Agent Skills

**A portable operating layer for AI agents: shared skills, recoverable configuration, and safer execution harnesses.**

Generated with `quokkify/project-toolkit` at `v2.17.0`. Run `copier update` to apply future template changes; Renovate updates workflow version references independently.

![Skills ecosystem: public hub, private configuration vault, and agent harness](docs/assets/skills-ecosystem.svg)

The project is built around one idea: an agent should be able to **learn once, move between providers, recover its setup, and execute through explicit safety boundaries**.

> **Learn → Preserve → Execute safely**

## The Ecosystem

### 1. Skills Hub

This repository is the public, canonical source for reusable workflows. Every portable skill lives once under [`skills/`](skills) and can be consumed by **Hermes**, **Claude Code**, **Codex**, or another compatible agent without maintaining provider-specific copies.

- portable `SKILL.md` packages;
- references, templates, and deterministic helper scripts;
- review and promotion workflows for reusable lessons;
- validation, privacy checks, and release automation.

### 2. Genericized Global Adapters

Portable skills describe *how to work*; a global adapter decides *what a runtime loads before any skill runs*. This repository publishes that layer as **templates and genericized defaults only**: a runtime-neutral global instruction base plus cross-runtime lifecycle hook scripts under `adapters/shared/`, and thin per-runtime wiring under `adapters/claude/` and `adapters/codex/`.

Publishable means: no real credentials, no employer identifiers, no machine paths, no pinned personal model choices, and no session or transcript state. See [ADR-0001](docs/adr/0001-publish-generic-global-agent-adapters.md) for the decision that reversed the earlier "no global configuration" boundary and for the list of content that remains forbidden.

### 3. Private Configuration Vault

Your real personal configuration needs a different trust boundary. Employer conventions, project trust lists, credentialed MCP servers, employer-only skills, and machine paths live in a **separate private overlay repository**, merged over the public templates at install time, alongside backups with restore scripts and a version/source manifest.

The vault is intentionally **not part of this public repository**. Secrets, memories, transcripts, runtime databases, machine-specific settings, and raw agent-home snapshots must never be promoted here. See [Project Architecture](docs/project-architecture.md) for the boundary and recovery model.

### 4. Agent Harness

Skills describe *how to work*; a harness controls *how work is executed*. The harness layer connects agent runtimes to typed tools, validation, permissions, observations, approval gates, retries, and recovery contracts.

The included [`agent-harness-design`](skills/orchestration/agent-harness-design/SKILL.md) skill captures the design principles: make correct actions easy to express, unsafe actions hard to invoke accidentally, and failures easy to diagnose.

## What Exists Today

| Layer | Status | Where it lives |
| --- | --- | --- |
| Portable skill hub | Available | [`skills/`](skills) |
| Provider adapters | Available | [`adapters/`](adapters) |
| Genericized global adapter templates | Available; installed by `scripts/bootstrap.sh` | `adapters/shared/`, `adapters/claude/`, `adapters/codex/` |
| Harness design guidance | Available | [`agent-harness-design`](skills/orchestration/agent-harness-design/SKILL.md) |
| Validation and safe synchronization | Available | [`scripts/`](scripts), [`tests/`](tests), CI |
| Private overlay and configuration backup vault | Separate deployment | Deliberately outside this public repository |

## Repository Layout

```text
skills/
├── <category>/<skill-name>/SKILL.md     # canonical entry point
├── <category>/<skill-name>/references/ # supporting guidance
├── <category>/<skill-name>/scripts/    # deterministic helpers
└── <category>/<skill-name>/templates/  # reusable templates

adapters/
├── shared/                  # runtime-neutral global instruction base, lifecycle hooks, git hooks
├── claude/                  # Claude Code connection notes and per-runtime templates
├── codex/                   # Codex project instructions and per-runtime templates
└── hermes/                  # Hermes configuration example

docs/                        # architecture, decision records, catalog, and guides
scripts/                     # install, validation, and safe-sync helpers
tests/                       # dependency-free regression tests
```

`skills/` is the only source of truth for portable skills; a skill body must never be duplicated into an adapter. `adapters/` holds tool-specific configuration and genericized global templates. Your real personal, employer, and machine-specific configuration belongs in the separate private overlay, which is not a directory inside this repository. Claude Code discovers project skills from `.claude/skills`, while Codex uses `.agents/skills`—not `.codex/skills`.

## Quick Start

Clone the repository:

```bash
git clone https://github.com/quokkify/skills.git
cd skills
```

### Claude Code

```bash
./scripts/bootstrap.sh --provider claude --install-skills
```

This installs the shared hooks, Claude settings, and managed `CLAUDE.md` block with timestamped backups. Add `--overlay /path/to/private-overlay` to layer private files after the public base. The overlay is read in place and is never copied into this checkout.

### Codex

```bash
./scripts/bootstrap.sh --provider codex --install-skills
```

The installer creates `$CODEX_HOME/AGENTS.md` as a symlink to the selected shared base — the overlay's copy if `--overlay` provides one, otherwise the public checkout's — merges `config.toml` and `hooks.json`, installs native agent definitions and shared hooks, and configures global Git hooks. Review and approve command hooks in the Codex TUI with `/hooks`.

To install both runtimes (the default):

```bash
./scripts/bootstrap.sh --install-skills
```

Use `--dry-run` to print every planned operation without changing files, symlinks, or Git configuration.

### Hermes

Point Hermes directly at the canonical skill directory:

```yaml
skills:
  external_dirs:
    - /absolute/path/to/skills/skills
```

The same example is available at [`adapters/hermes/config.example.yaml`](adapters/hermes/config.example.yaml). Start a new Hermes session after changing the discovery path. A same-named profile-local skill can take precedence over the shared copy, so keep shared changes on an isolated Git branch or worktree.

## Browse the Hub

The repository currently contains **19 portable skills** spanning:

- orchestration and agent recovery;
- skill lifecycle and promotion;
- repository safety and quality gates;
- software development and browser QA;
- infrastructure operations;
- game troubleshooting and source reconnaissance.

Browse the complete [Skill Catalog](docs/skill-catalog.md) or open the [documentation site](https://quokkify.github.io/skills/).

## Update a Shared Checkout

From a clean checkout on `main`:

```bash
./scripts/sync-shared-skills.sh
```

The helper fetches only `origin/main`, validates the exact fetched snapshot with the currently trusted validator, allows fast-forward updates only, disables Git hooks during branch movement, and rejects concurrent checkout changes. It never executes scripts from the fetched tree.

Copied Codex adapter files are not refreshed by this command. Rerun the installer when `adapters/codex/AGENTS.md` changes.

## Validate Changes

Run the portable CI-equivalent gate:

```bash
./scripts/validate.sh --ci
```

Run the complete local gate, including full-history Gitleaks scanning:

```bash
./scripts/validate.sh --full
```

Gitleaks `8.30.1` or newer must be available on `PATH` or through `GITLEAKS_BIN` for `--full`.

## Update Project Scaffolding

The repository records its `quokkify/project-toolkit` template source and answers in [`.copier-answers.yml`](.copier-answers.yml). From a clean checkout, review and apply template updates with:

```bash
copier update --trust
```

Repository-specific validation remains in `scripts/validate.sh`; the generated update contract and reusable CI workflow keep shared project plumbing versioned without replacing that custom gate.

Optional repository-local Git hooks:

```bash
./scripts/install-git-hooks.sh
```

The validator checks skill layout and frontmatter, duplicate names, Markdown links, symlinks, machine-specific paths, and public/private boundaries.

## Security Boundary

This is a public repository. Do not commit credentials, memories, transcripts, sessions, runtime databases, private project context, machine-specific configuration, or backup archives. Read [SECURITY.md](SECURITY.md) before promoting locally generated material.

Every pull request runs repository validation and Gitleaks. Scanner success complements manual privacy review; it does not prove that content is appropriate to publish.

## Documentation

- [Project architecture](docs/project-architecture.md)
- [Decision records](docs/adr/index.md)
- [Quick start](docs/quick-start.md)
- [Skill catalog](docs/skill-catalog.md)
- [Using the skills](docs/guides/how-to-use-skills.md)
- [Reviewing and promoting skills](docs/guides/reviewing-and-promoting-skills.md)
- [Releases and dependency updates](docs/guides/releases-and-dependencies.md)
- [FAQ](docs/FAQ.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)
