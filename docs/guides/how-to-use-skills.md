---
title: How to Use These Skills
---

# How to Use These Skills

This repo is meant to stay small and reusable.

It gives you:

- shared orchestration skills
- Claude-specific global config
- Codex project instructions
- a controlled skill-review and promotion workflow for Claude, Codex, and Hermes

## The Main Idea

There are two layers:

1. Shared skills that Claude Code, Codex, and Hermes can use
2. Tool-specific setup for the tool you actually work with

That is why setup happens in two steps instead of one.

## Claude Flow

Claude uses:

- installed skills from this repo
- files copied into `~/.claude` by `./scripts/install-claude-config.sh`

This gives Claude the reusable workflow plus the Claude-specific global setup.

## Codex Flow

Codex uses:

- installed skills from this repo
- `AGENTS.md` inside the target repo

This gives Codex the reusable workflow plus project-level instructions.

## Hermes Flow

Hermes uses the repository root as a `skills.external_dirs` entry. Each top-level skill directory then appears in the Hermes skill index and as a slash command.

External directories are mutable when filesystem permissions allow writes, so shared-skill promotion still goes through a Git branch or worktree and a pull request. A same-named local Hermes skill takes precedence over the external version.

## Skill Review Flow

After significant work, `skill-review` classifies the lesson, searches for an existing owner, prepares a private candidate, audits privacy and portability, and asks for approval. Approved candidates move through branch, validation, secret scan, and pull request. Routine work and temporary facts are skipped.

## How To Adapt This To Your Own Project

Keep this repo focused on orchestration.

Put stack-specific roles in the target project, for example:

- `AGENTS.md`
- `.agents/**/SKILL.md`
- project-specific rules files

The target repo should describe its own stack and domain. This repo should stay generic.

## Recommended Reading Order

If you are new to this repo:

1. Read [Quick Start](../quick-start.md)
2. Use the Claude, Codex, or Hermes path
3. Read [Reviewing and Promoting Skills](reviewing-and-promoting-skills.md) before promoting agent-generated knowledge
4. Come back here only if you need the longer explanation

## Related Pages

- [Home](../index.md)
- [Quick Start](../quick-start.md)
- [Reviewing and Promoting Skills](reviewing-and-promoting-skills.md)
- [FAQ](../FAQ.md)
