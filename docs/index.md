---
title: Skills Docs
---

# Skills for Claude Code, Codex, and Hermes

This repo gives you reusable agent workflows for three tools:

- Claude Code
- Codex
- Hermes

The short version is simple:

1. Install or connect the skills for your tool.
2. Run the relevant setup script, or add the repository root to Hermes `skills.external_dirs`.
3. Start working in your tool or target project.

## Choose Your Path

- [Quick Start](quick-start.md) for the shortest setup steps
- [How to Use These Skills](guides/how-to-use-skills.md) for the longer explanation
- [Reviewing and Promoting Skills](guides/reviewing-and-promoting-skills.md) for controlled post-task learning
- [FAQ](FAQ.md) for common setup questions

## What Is In This Repo

- `orchestrator-workflow/` for complex implementation tasks
- `refactor-workflow/` for refactoring tasks
- `skill-review/` for safe candidate review and branch/PR promotion
- `claude-config/` for Claude-specific global config
- `codex/AGENTS.md` for Codex project instructions
- `scripts/` for install helpers

## When To Use This Repo

Use this repo when:

- you want the same orchestration style in Claude Code
- you want Codex to work with a project-level `AGENTS.md`
- you want Hermes to discover the same shared skills from an external directory
- you want a shared workflow layer that target projects can extend locally

## Start Here

If you only need the practical steps, go to [Quick Start](quick-start.md).
