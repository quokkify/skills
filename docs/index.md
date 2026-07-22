---
title: Agent Skills Hub
---

<div class="hero" markdown>

# Skills that travel with your agents

A portable operating layer for **Hermes**, **Claude Code**, **Codex**, and future providers—built from a public skills hub, a separate private configuration vault, and a safety-focused agent harness.

[Get started](quick-start.md){ .md-button .md-button--primary }
[Explore the architecture](project-architecture.md){ .md-button }

</div>

![Skills ecosystem architecture](assets/skills-ecosystem.svg)

<div class="architecture-grid" markdown>

<div class="architecture-card" markdown>

## :material-bookshelf: One Skills Hub

Reusable workflows live once under `skills/`. Provider adapters stay thin, so knowledge does not drift between runtimes.

[Browse 19 skills](skill-catalog.md)

</div>

<div class="architecture-card architecture-card--private" markdown>

## :material-shield-lock: Private by Design

Configuration backups, secrets, memories, and runtime state belong in a separate private vault—not in this public repository.

[Understand the boundary](project-architecture.md#trust-boundaries)

</div>

<div class="architecture-card" markdown>

## :material-robot-industrial: Safer Execution

Typed tools, explicit permissions, deterministic observations, approval gates, and recovery contracts turn instructions into dependable agent behavior.

[Read the harness model](../skills/orchestration/agent-harness-design/SKILL.md)

</div>

</div>

## Start Here

1. Follow the [Quick Start](quick-start.md) for your agent.
2. Read [Project Architecture](project-architecture.md) to understand the three-layer model.
3. Browse the [Skill Catalog](skill-catalog.md).
4. Read [How to Use These Skills](guides/how-to-use-skills.md) for discovery paths and adapter behavior.
5. Read [Reviewing and Promoting Skills](guides/reviewing-and-promoting-skills.md) before publishing reusable lessons.

!!! info "One source of truth"
    Portable skill content lives under `skills/`. Tool-specific connection files live under `adapters/`. Private agent state stays outside the public repository.
