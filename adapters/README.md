# Tool Adapters

The reusable skills live once in [`../skills`](../skills). This directory contains only tool-specific instructions and configuration that cannot be expressed as a portable skill.

- `claude/README.md` — Claude Code connection notes; no global personas or configuration bundle
- `codex/AGENTS.md` — optional project instructions for Codex
- `hermes/config.example.yaml` — example external skill directory configuration

Do not copy skill content into an adapter. Claude Code uses `.claude/skills` and Codex uses `.agents/skills` for project-local discovery, but those are consumer locations rather than additional sources of truth in this repository.
