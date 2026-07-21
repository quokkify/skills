---
title: Skill Catalog
---

# Skill Catalog

Every entry below is stored once at `skills/<category>/<name>/SKILL.md` and can be discovered by Claude Code, Codex, or Hermes through their normal skill-loading mechanisms. The category headings match the directory that groups each skill on disk.

## orchestration

- [`orchestrator-workflow`](../skills/orchestration/orchestrator-workflow/SKILL.md) — coordinate complex implementation work through discovery, planning, execution, and validation.
- [`refactor-workflow`](../skills/orchestration/refactor-workflow/SKILL.md) — perform controlled refactoring with explicit evidence and verification.
- [`agent-failure-recovery`](../skills/orchestration/agent-failure-recovery/SKILL.md) — stop retry loops, re-observe world state, run one discriminating probe, and recover containably.
- [`agent-harness-design`](../skills/orchestration/agent-harness-design/SKILL.md) — design safe, diagnosable tools, schemas, observations, permissions, and recovery contracts for autonomous agents.

## skill-management

- [`skill-review`](../skills/skill-management/skill-review/SKILL.md) — review reusable lessons and promote approved changes safely.
- [`skill-promotion-queue`](../skills/skill-management/skill-promotion-queue/SKILL.md) — accumulate pre-authorized, public-safe skill improvements in a per-agent rolling draft pull request.
- [`agent-knowledge-lifecycle`](../skills/skill-management/agent-knowledge-lifecycle/SKILL.md) — share, evolve, secure, and synchronize reusable agent knowledge.
- [`shared-skill-library-maintenance`](../skills/skill-management/shared-skill-library-maintenance/SKILL.md) — maintain one portable skill library with thin runtime adapters.

## repository

- [`repository-quality-gates`](../skills/repository/repository-quality-gates/SKILL.md) — design exact-artifact validators, Git hooks, and CI gates.
- [`secure-git-checkout-operations`](../skills/repository/secure-git-checkout-operations/SKILL.md) — safely update long-lived Git checkouts consumed by automation.
- [`codebase-onboarding`](../skills/repository/codebase-onboarding/SKILL.md) — map an unfamiliar repository's architecture, entry points, conventions, data flow, and safe verification commands.

## software-development

- [`architecture-decision-records`](../skills/software-development/architecture-decision-records/SKILL.md) — record and maintain significant architecture decisions with grounded alternatives, consequences, and revisit triggers.
- [`interaction-state-audit`](../skills/software-development/interaction-state-audit/SKILL.md) — trace UI interactions through shared state, effects, and asynchronous writers to explain incorrect final state.
- [`ai-assisted-regression-testing`](../skills/software-development/ai-assisted-regression-testing/SKILL.md) — counter shared AI author-review assumptions with executable regression oracles across important boundaries.
- [`browser-qa`](../skills/software-development/browser-qa/SKILL.md) — collect safe browser-based release evidence for runtime health, interactions, visual baselines, and accessibility.

## devops

- [`linux-storage-maintenance`](../skills/devops/linux-storage-maintenance/SKILL.md) — diagnose disk pressure and reclaim space conservatively.
- [`vps-reverse-proxy-operations`](../skills/devops/vps-reverse-proxy-operations/SKILL.md) — configure and audit public HTTPS reverse proxies on a VPS.

## games

- [`game-performance-troubleshooting`](../skills/games/game-performance-troubleshooting/SKILL.md) — diagnose FPS, stutter, latency, and packet-loss symptoms.
- [`game-source-reconnaissance`](../skills/games/game-source-reconnaissance/SKILL.md) — investigate open-source game mechanics and permitted automation seams.

Provider-specific references are included only when they document public contracts or reusable failure modes. Personal, account, infrastructure, and private-project evidence is excluded.
