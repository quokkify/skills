---
title: FAQ
---

# FAQ

## Do I need Claude, Codex, and Hermes?

No. You can use only one path.

- If you use Claude Code, install the skills and run `./scripts/install-claude-config.sh`.
- If you use Codex, install the skills and run `./scripts/install-codex-agents.sh /path/to/your/project`.
- If you use Hermes, add the repository root to `skills.external_dirs` and start a new session.

## Can Hermes edit an external skill directory?

Yes, when the Hermes process has filesystem write access. External directories are discovery sources, not write-protection boundaries. Shared changes should use an isolated Git branch or worktree and a pull request rather than an in-place skill-management edit.

If a local Hermes skill has the same name as an external skill, the local version takes precedence.

## Why are skills and Claude config separate steps?

Because they do different jobs.

- the skills add reusable workflow logic
- the Claude config installs Claude-specific files into `~/.claude`

For Claude, you usually want both.

## Does Codex need `claude-config/`?

No.

For Codex, the important pieces are:

- the installed skills
- `AGENTS.md` inside the target project

## Do I run the scripts from my target project?

No.

Clone this repo and run the scripts from this repo root.

Example:

```bash
cd /path/to/skills
./scripts/install-claude-config.sh
./scripts/install-codex-agents.sh /path/to/your/project
```

## What does `install-codex-agents.sh` actually do?

It copies the repository file `codex/AGENTS.md` into your target repo as `AGENTS.md`.

That file tells Codex how to use this orchestration workflow.

## Why can Codex cost more than my previous Claude/ECC setup?

Because the two environments do not expose the same routing model.

- Claude + ECC has an explicit cost ladder with junior, middle, and senior roles, which makes cheapest-capable selection more predictable.
- Codex can follow the same workflow shape, but cost control is often achieved through fewer delegations, shorter handoffs, and a tighter `plan -> executor -> validation` loop.

If Codex starts feeling expensive, the first thing to check is not only model choice but also whether the workflow is spawning unnecessary research or review steps.

## What is the cheapest default behavior I should expect in Codex?

The intended cheap default is:

- quick plan
- one executor
- validation at the end

Research agents should be added only when missing facts block execution. Review agents should usually be added after implementation reaches a stable state.

## Can my target project still have its own local rules?

Yes.

This repo is the shared orchestration layer. Your target project can still define its own local roles and rules in `AGENTS.md` or `.agents/**/SKILL.md`.
