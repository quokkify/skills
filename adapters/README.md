# Tool Adapters

The reusable skills live once in [`../skills`](../skills). This directory contains tool-specific instructions and configuration that cannot be expressed as a portable skill, plus **genericized global templates** that a runtime loads before any skill runs.

- `shared/` — runtime-neutral global instruction base, cross-runtime lifecycle hook scripts, and git hooks
- `claude/` — Claude Code connection notes, `CLAUDE.block.md`, and `settings.template.json
- `codex/` — `README.md`, `AGENTS.md`, `config.template.toml`, `hooks.json`, and `agents/` subagent definitions
- `hermes/config.example.yaml` — example external skill directory configuration

## What may be published here

Templates and genericized defaults only. Every file must be safe for any reader to install:

- no credentials, tokens, or private endpoints;
- no employer, client, or private-project identifiers;
- no machine-specific home paths — use `$HOME`, `~/.claude/...`, `~/.codex/...`, or `/path/to/...`;
- no pinned personal model versions or one user's routing policy;
- no session, transcript, memory, or runtime-database state.

A template is *derived* from a real setup by removing everything specific to it. It is never a copy of one. `scripts/validate_repo.py` enforces the mechanical part of this rule; it does not replace reading the diff.

Your real configuration — employer conventions, project trust lists, credentialed MCP servers, private skills, machine paths — belongs in a private overlay repository merged over these templates at install time. That overlay is **not a directory inside this repository**. See [ADR-0001](../docs/adr/0001-publish-generic-global-agent-adapters.md).

## Rules

Do not copy skill content into an adapter. An adapter may point at a canonical skill by name; duplicating a skill body creates a second source of truth that drifts.

Anything that installs these templates must back up existing files, never silently overwrite a user's configuration, and preserve managed blocks written by other tools, such as `<!-- OMC:START -->…<!-- OMC:END -->`. No such installer ships yet; copy files manually until one does.

Claude Code uses `.claude/skills` and Codex uses `.agents/skills` for project-local discovery, but those are consumer locations rather than additional sources of truth in this repository.
