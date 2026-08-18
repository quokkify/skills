---
title: FAQ
---

# FAQ

## Do I need all three supported agents?

No. Install or connect only the path you use. Claude Code and Codex can share the same portable skills, while Hermes reads the canonical directory directly.

## Why are skills and adapters separate?

They have different responsibilities:

- `skills/` contains portable workflow knowledge shared by every supported agent.
- `adapters/` contains configuration specific to Claude Code, Codex, or Hermes.

Keeping those layers separate prevents three copies of the same skill from drifting apart.

## Should this repository contain `.claude/skills` and `.codex/skills`?

No. Claude Code uses `.claude/skills` for project-local discovery, but that is a consumer location rather than this repository's canonical store. Codex uses `.agents/skills` for project-local discovery; `.codex/skills` is not its documented project skill path.

Installers can place skills into each agent's supported discovery location without duplicating their source in Git.

## Can Hermes use the new layout directly?

Yes. Point `skills.external_dirs` at the nested canonical directory:

```yaml
skills:
  external_dirs:
    - /absolute/path/to/skills/skills
```

Start a new session after changing the path.

## Can Hermes edit an external skill directory?

Yes, if the process has filesystem write access. External directories are discovery sources, not read-only boundaries. Make shared changes in a separate Git branch or worktree and submit them through review.

A same-named local Hermes skill can take precedence over the shared version.

## What do the adapter installers do?

Claude Code needs no repository-owned global configuration: install the canonical skills through the skills CLI.

`./scripts/install-codex-agents.sh /path/to/project` copies `adapters/codex/AGENTS.md` into the target project as `AGENTS.md`.

The Codex script does not change the canonical files under `skills/`.

## Where should Claude Code sub-agents live?

Keep global personas under your own `~/.claude/agents/` and project-specific personas with the project that owns them. This repository does not publish them because agent roles, model names, tools, and project assumptions are not portable skills.

## How do I migrate from the old root-level layout?

Hermes recursively discovers nested skills, so an existing repository-root entry remains compatible. Point `skills.external_dirs` at `<checkout>/skills` if you want discovery limited to the canonical directory. The former global Claude configuration bundle is intentionally removed; the Codex installer command stays the same. Reinstall or update skills managed by the skills CLI so recorded source paths follow the new layout.

## Can a target project have its own rules?

Yes. Keep stack- and domain-specific rules in the target project, such as `AGENTS.md`, `CLAUDE.md`, or project-local skills. This repository should remain portable and generic.

## bootstrap.sh refuses to merge config.toml with "unrecognized keys" error

The Codex bootstrap installer (`./scripts/bootstrap.sh --provider codex`) now compares the keys in each existing section of your `config.toml` against the template's declared keys for that section. If it finds keys the template doesn't know about (legacy fields like `max_threads` from older Codex versions, hand-edited configs, or previously-deprecated names), it **refuses to merge** and shows:

```
bootstrap: section [agents] contains unrecognized keys: max_threads. Use --merge-unknown-keys to proceed anyway.
```

**Why?** Codex's `[agents]` table uses `serde(flatten)` for subtables like `[agents.explorer]`. When a flattened struct's table also contains keys outside its known field set, serde misreports a valid single-occurrence field as a "duplicate field" error instead of "unknown field". The TOML text is valid, but Codex fails to start.

**Fix options:**
1. **Manual (recommended):** Remove the legacy keys from your config before running bootstrap. Their values are already carried by the new template keys (e.g., `max_threads` → `max_concurrent_threads_per_session`).
2. **Force merge:** Run `./scripts/bootstrap.sh --provider codex --merge-unknown-keys` to allow the merge despite unknown keys. The legacy keys will be preserved alongside the new ones.
