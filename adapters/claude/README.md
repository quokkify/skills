# Claude Code Adapter

This directory holds the Claude Code side of the global agent configuration that this repository
publishes. It complements — it does not replace — the portable skills in
[`../../skills`](../../skills).

## Three-layer model

Global agent instructions are assembled from three layers with different owners:

| Layer | Lives in | Owner | Contains |
| --- | --- | --- | --- |
| Shared base | [`../shared/AGENTS.base.md`](../shared/AGENTS.base.md) | this repository | runtime-neutral engineering standards: investigation discipline, no-fake-completion rules, delegation and parallelism, review separation, testing, security, commit conventions |
| Runtime adapter | this directory (Claude Code), `../codex` (Codex CLI) | this repository | only the deltas that a single runtime needs, plus config templates |
| Private overlay | a separate private repository, never here | the user | machine paths, employer conventions, credentials, personal context, real tool endpoints |

Earlier revisions of this file stated that the repository would never publish a global
`CLAUDE.md`. That policy has been narrowed rather than kept: the *genericized* base and adapter
artifacts are now published here, while everything personal or employer-specific stays in the
private overlay layer.

The same shared base serves both runtimes. Claude Code pulls it in through an `@` import;
Codex CLI reads it as `~/.codex/AGENTS.md`.

## Files

### `../shared/AGENTS.base.md`

The runtime-neutral instruction base. It never names a specific runtime where "the agent" works,
and it contains no machine paths. Rules that genuinely differ per runtime are deliberately absent
and live in the adapters instead.

### [`CLAUDE.block.md`](CLAUDE.block.md)

The exact block intended for injection into `~/.claude/CLAUDE.md`, delimited by
`<!-- SKILLS-HUB:START -->` and `<!-- SKILLS-HUB:END -->`.

`~/.claude/CLAUDE.md` must remain a real file, never a symlink and never wholly generated: other
tooling (for example oh-my-claudecode) maintains its own marker-delimited block in the same file
and rewrites it on update. The distinct `SKILLS-HUB` markers keep the two blocks from colliding.

The block carries an `@__SHARED_BASE__` token. An installer is expected to replace that literal
token with an `@` import of the installed base, normally `@~/.claude/skills-hub/AGENTS.base.md`.
Claude Code follows `@` imports up to five hops deep.

### [`settings.template.json`](settings.template.json)

A genericized template of `~/.claude/settings.json`. It is valid JSON, so it carries no comments;
the fields are documented here instead.

- `model`, `effortLevel`, `theme` — starting defaults; adjust freely.
- `statusLine` — the command shape is preserved, but the referenced script is a placeholder.
  Scriptable status lines are a Claude Code-only feature.
- `hooks` — seven events wired (`SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`,
  `PostToolUseFailure`, `SubagentStop`, `Stop`). Each entry invokes one dispatcher at
  `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/dispatch.sh` with the event name as its argument.
  The `${CLAUDE_CONFIG_DIR:-$HOME/.claude}` indirection is intentional and portable across
  machines — keep it. Hook payloads arrive as JSON on stdin, the same contract Codex CLI uses, so
  the scripts themselves are portable even though this registration format is not. The shared hook
  scripts are published under `adapters/shared/hooks/` in this repository and are expected to
  install into `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/`.
- `extraKnownMarketplaces` — the shape is shown with an obviously fake example source. Real
  marketplace entries are user-owned; plugins and marketplaces are Claude Code-only.

Deliberately absent: `env.PATH` (it was machine-specific), any `permissions` block (its allow-list
grammar is Claude-only and real entries contain machine paths), and anything naming a specific
machine or account.

## What stays user-owned

Out of scope for this repository, permanently:

- `settings.local.json` — git-ignored, machine-local, and never templated here.
- A `permissions` allow-list with real paths and commands.
- Plugin and marketplace installs, and any hooks those plugins manage. Plugin-managed hook entries
  in a real `settings.json` belong to the plugin, not to this template.
- MCP server definitions that carry credentials, private hostnames, or tokens.
- Employer- or client-specific conventions: internal repository names, issue-tracker keys, private
  registry paths, internal CI conventions.
- Personal subagent personas and output styles.

## Installer status

A bootstrap script (`scripts/bootstrap.sh`) that installs the base, injects the block, and seeds
the settings template is **forthcoming** and lands in a later change. Until it exists, treat the
files here as reviewed source material and apply them by hand; nothing in this directory installs
itself.

## Installing the skills

Skill installation is independent of the configuration layers above and already works. The adapter
identifier for Claude Code in the `npx skills` CLI is `claude-code`:

```bash
npx skills add quokkify/skills --skill '*' -g -a claude-code -y
```

The CLI writes the skills into Claude Code's supported personal skill directory. For project-only
use, Claude Code also discovers skills under `.claude/skills/`.

Do not copy skill content into this adapter — see [`../README.md`](../README.md).
