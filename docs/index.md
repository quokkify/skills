---
title: Skills Docs
---

# Shared Agent Skills

Portable workflows for Claude Code, Codex, and Hermes.

## One Source of Truth

All reusable skills live under `skills/`. Tool-specific configuration lives under `adapters/` and must not duplicate skill content.

```text
skills/      portable skills
adapters/    Claude, Codex, and Hermes integration files
docs/        detailed documentation
scripts/     install, validation, and sync helpers
tests/       regression tests
```

## Start Here

1. Follow the [Quick Start](quick-start.md) for your agent.
2. Read [How to Use These Skills](guides/how-to-use-skills.md) for discovery paths and adapter behavior.
3. Read [Reviewing and Promoting Skills](guides/reviewing-and-promoting-skills.md) before publishing reusable lessons.
4. See the [FAQ](FAQ.md) for common setup questions.

## Included Skills

- `orchestrator-workflow` for complex implementation tasks
- `refactor-workflow` for controlled refactoring
- `skill-review` for privacy-aware review and promotion
