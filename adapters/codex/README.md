# Codex CLI adapter

Templates that bring Codex CLI to parity with a Claude Code setup using **Codex's own native mechanisms** — native hooks, native subagents, native skills — instead of re-implementing Claude features in prose.

Verified against Codex CLI **0.146.0**. Everything here is a template: no machine paths, no credentials, no employer-specific tooling. Machine-local values belong in a private overlay, never in this repository.

## Files in this directory

| File | Installs to | Purpose |
| --- | --- | --- |
| `AGENTS.md` | `$CODEX_HOME/AGENTS.md` (or a target repo's `AGENTS.md`) | Orchestration profile: tempo, cost policy, budget modes, handoff packets, role mapping, skill-review gate |
| `config.template.toml` | `$CODEX_HOME/config.toml` | Commented base config: runtime defaults, `[features]`, `[agents]` declarations, `[skills]`, example MCP servers |
| `hooks.json` | `$CODEX_HOME/hooks.json` | Native hook wiring for session, prompt, tool, compaction, subagent, and stop events |
| `agents/explorer.toml` | `$CODEX_HOME/agents/explorer.toml` | Read-only evidence gatherer; overrides the built-in `explorer` role |
| `agents/reviewer.toml` | `$CODEX_HOME/agents/reviewer.toml` | Correctness / security / missing-tests reviewer |
| `agents/docs-researcher.toml` | `$CODEX_HOME/agents/docs-researcher.toml` | Primary-doc and API verification; registered as `docs_researcher` |

`$CODEX_HOME` defaults to `~/.codex`.

Use `./scripts/bootstrap.sh --provider codex` to install these files with backups, additive JSON/TOML merges, rollback on failure, and a symlinked global `AGENTS.md`. Add `--overlay DIR` for a private layer or `--dry-run` to inspect operations without changing the system. The separate `scripts/install-codex-agents.sh` helper still copies project-level `AGENTS.md` files.

## Manual install

```sh
./scripts/bootstrap.sh --provider codex
```

Then, in the Codex TUI, run `/hooks` and approve the hook entries (see *Hook trust* below).

### Merging into an existing config.toml

Do not blindly overwrite a live `config.toml`. Two things must survive:

1. **Machine-local sections** — `[projects."..."]` trust entries, credentialed MCP servers, `notify`, `[desktop]`, `[tui]`, `[marketplaces]`, `[notice]`, `[shell_environment_policy]`. Those are written by the client or by you, and they are exactly what must never reach a public repository.
2. **Machine-managed regions** — anything between `# BEGIN OMC MANAGED MCP REGISTRY` and `# END OMC MANAGED MCP REGISTRY` is owned by oh-my-claudecode. Preserve the block verbatim or regenerate it with the tool that owns it.

Security note: if the live config contains `[projects."/"] trust_level = "trusted"`, delete it. That trusts the filesystem root, which makes every directory a trusted project and lets any repo's `.codex/config.toml` and `.codex/hooks.json` take effect without review. Grant trust per repository.

## Instruction files and the `AGENTS.override.md` trap

`AGENTS.override.md` **replaces** the `AGENTS.md` in the same directory. It does not append — this was verified empirically. A setup that ships both a base `AGENTS.md` and an `AGENTS.override.md` at the `$CODEX_HOME` level silently loses the base file's entire contents.

Therefore the intended layout uses exactly **one** file at that level: `$CODEX_HOME/AGENTS.md`, which may be a symlink to a shared base document (Codex follows symlinks for `AGENTS.md`). Personal or employer additions go into a project-level `AGENTS.md` inside the relevant repository, not into a same-directory override.

Related keys: `project_doc_max_bytes` (default 32768), `project_doc_fallback_filenames`, `project_root_markers` (default `[".git"]`). Avoid `model_instructions_file` — it replaces Codex's built-in instructions rather than `AGENTS.md`. `experimental_instructions_file` does not exist.

## Hooks

Codex hooks are native. Eleven events fire: `SessionStart`, `SessionEnd`, `UserPromptSubmit`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `PreCompact`, `PostCompact`, `SubagentStart`, `SubagentStop`, `Stop`.

The stdin contract is a single JSON object with `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `model`, plus `turn_id`, `permission_mode`, `tool_name`, `tool_use_id`, `tool_input`, and `tool_response` where applicable — **the same contract as Claude Code**, so a well-written hook script is portable across both runtimes.

### Where hooks are declared

`hooks.json` in this directory is the single source of truth for this adapter. Hooks can also be declared as `[[hooks.<Event>]]` blocks in `config.toml`, or in `<repo>/.codex/hooks.json` for a trusted project — but **all layers are additive**, so a handler declared twice runs twice. `config.template.toml` therefore contains no hook blocks, only a pointer and a commented TOML example for reference.

### Hook script locations

The `command` entries in `hooks.json` reference portable scripts under `$CODEX_HOME/hooks/`:

```text
$CODEX_HOME/hooks/session-start-context.sh
$CODEX_HOME/hooks/prompt-context.sh
$CODEX_HOME/hooks/guard-shell-command.sh
$CODEX_HOME/hooks/guard-protected-paths.sh
$CODEX_HOME/hooks/format-changed-files.sh
$CODEX_HOME/hooks/preserve-working-notes.sh
$CODEX_HOME/hooks/subagent-result-check.sh
$CODEX_HOME/hooks/completion-gate.sh
$CODEX_HOME/hooks/session-end-summary.sh
```

The shared, runtime-agnostic implementations live under `adapters/shared/hooks/` in this repository; the future installer copies them into `$CODEX_HOME/hooks/`. Remove or rename the corresponding entries in `hooks.json` for any script you do not install — a missing script makes the hook fail on every matching event.

### Blocking and control flow

- Deny a tool call with `permissionDecision: "deny"` plus a non-empty `permissionDecisionReason`.
- Rewrite arguments with `updatedInput`, which requires `permissionDecision: "allow"`.
- Universal escape hatch: exit code `2` with the reason on stderr.
- `Stop` / `SubagentStop` returning `decision: "block"` with a `reason` creates a continuation prompt — this is how `completion-gate.sh` forces more work instead of accepting a premature "done".
- Only `type = "command"` handlers execute. `prompt` and `agent` handler types parse without error and are then skipped.
- Per-handler knobs: `timeout` (seconds, default 600), `statusMessage`, `additionalContextLimit` (tokens, default 2500, `0` = unlimited), `async`.

### Hook trust

Non-managed command hooks are **hash-trusted**. After installing or editing `hooks.json` or any hook script, open the Codex TUI and run the `/hooks` command to review and approve the new hashes. Hooks do not run until approved, and editing a script invalidates its previous approval. There is no `codex hooks` CLI subcommand — approval is TUI-only.

Kill switch: `[features] hooks = false`.

## Subagents

Multi-agent support is stable and on by default (`codex features list` reports `multi_agent stable true`), so `config.template.toml` deliberately omits `[features] multi_agent = true` — the line would be redundant drift.

Orchestrator tools: `spawn_agent`, `send_input`, `resume_agent`, `wait_agent`, `close_agent`. TUI: `/agent`.

Configuration uses the `[agents]` **table** with one subtable per role. `[[agents]]` as an array-of-tables does not exist. `config_file` is resolved relative to the declaring `config.toml`.

Agent definition files are standalone TOML and **must** set `name`, `description`, and `developer_instructions`. `name` — not the filename — is the registered identity, which is why `agents/docs-researcher.toml` declares `name = "docs_researcher"`. Definitions may additionally layer `model`, `model_reasoning_effort`, `sandbox_mode`, `[mcp_servers.*]`, and `[[skills.config]]`.

Built-in roles are `default`, `worker`, and `explorer`; this adapter's `explorer` intentionally overrides the built-in one.

### Why no `model` in the agent files

Model ids rot fast. All three definitions omit `model` and inherit `agents.default_subagent_model` from `config.toml`, so a model migration is a one-line change in one file instead of an edit in every agent definition. Where a role genuinely needs a different cost/quality point, that is expressed with `model_reasoning_effort` (`high` for the reviewer, `medium` elsewhere), which does not name a model version. Each file carries a commented `# model = "<model-id>"` placeholder for a deliberate override.

## Profiles: migrating off `[profiles.*]`

`[profiles.<name>]` tables are **legacy** and can no longer be written. A profile is now a separate file in `$CODEX_HOME`:

```text
$CODEX_HOME/strict.config.toml
$CODEX_HOME/yolo.config.toml
```

```toml
# $CODEX_HOME/strict.config.toml
approval_policy = "on-request"
sandbox_mode = "read-only"
web_search = "cached"
```

Invoke with `codex --profile strict`. The profile file layers over `$CODEX_HOME/config.toml`; it does not replace it.

Full precedence, highest first:

1. CLI `-c key=value`
2. `<repo>/.codex/config.toml` (trusted projects only)
3. `$CODEX_HOME/<name>.config.toml` (active profile)
4. `$CODEX_HOME/config.toml`
5. `/etc/codex/config.toml`
6. built-in defaults

## Skills

Skills are native. Discovery roots, in order:

```text
$CWD/.agents/skills          (and each parent directory up to the repo root)
$REPO_ROOT/.agents/skills
$HOME/.agents/skills
/etc/codex/skills
$CODEX_HOME/skills           (live, but under-documented)
```

Invoke a skill as `$skill-name`; `/skills` lists what resolved. Configure extra roots with `[[skills.config]]` (`path`, `enabled`), plus `skills.bundled.enabled` and `skills.include_instructions`.

## MCP servers

STDIO: `command`, `args`, `env`, `cwd`. Streamable HTTP: `url`, `auth`, `bearer_token_env_var`, `http_headers`. **Plain SSE is not supported.**

Shared keys: `startup_timeout_sec` (default 10), `tool_timeout_sec` (default 60), `enabled`, `required`, `enabled_tools`, `disabled_tools`, `default_tools_approval_mode` (`auto` | `prompt` | `writes` | `approve`), and per-tool `[mcp_servers.<name>.tools.<tool>] approval_mode`.

`disable_response_storage` was removed — do not use it.

Only credential-free, publicly installable servers belong in the template. Anything requiring a token, an internal hostname, or a path into a local checkout goes in the private overlay.

## Claude Code vs Codex parity

| Capability | Claude Code | Codex CLI 0.146.0 | Notes |
| --- | --- | --- | --- |
| Global instructions | `~/.claude/CLAUDE.md` | `$CODEX_HOME/AGENTS.md` | Symlinks followed; `AGENTS.override.md` replaces rather than appends |
| Project instructions | `./CLAUDE.md` | `./AGENTS.md` | `project_doc_fallback_filenames` can read `CLAUDE.md` too |
| Hooks | native, JSON stdin contract | **native**, 11 events, same stdin contract | `hooks.json` and/or `[[hooks.*]]`; layers are additive |
| Hook approval | settings-based | hash-trusted, approved via TUI `/hooks` | Editing a script invalidates approval |
| Hook handler types | command | command only in practice | `prompt` / `agent` parse but never execute |
| Subagents | Task/Agent tool + `agents/*.md` | **native** `spawn_agent` family + `agents/*.toml` | Stable, on by default |
| Subagent model routing | per-agent `model` frontmatter | `default_subagent_model` + per-agent overrides | Same idea, different key names |
| Skills | `.claude/skills`, `/name` | `.agents/skills` and friends, `$name` | `/skills` lists resolved set |
| MCP servers | `.mcp.json` | `[mcp_servers.*]` in TOML | No plain SSE on the Codex side |
| Named runtime profiles | settings files | `$CODEX_HOME/<name>.config.toml` + `--profile` | `[profiles.*]` is legacy and unwritable |
| Sandbox / approvals | permission modes | `sandbox_mode` + `approval_policy` | Also settable per agent definition |
| Slash commands | project-scoped commands | not project-scoped | Use skills instead |
| Statusline | scriptable | not scriptable | Only ordered built-in `tui.status_line` item ids |

**Bottom line:** the parity gap that used to matter is closed. Hooks and subagents — the two mechanisms this profile depends on — are native in Codex with the same hook stdin contract as Claude Code, so portable hook scripts and a shared orchestration profile work on both runtimes. What remains are presentation and ergonomics gaps, not capability gaps.

### What Codex still cannot do

- **No scriptable statusline.** Claude Code runs an arbitrary command to render its status line. Codex only accepts an ordered list of built-in `tui.status_line` item ids; you choose and order what it already knows how to display.
- **No project-scoped slash commands.** There is no per-repository `/command` equivalent. Express repeatable project workflows as skills in `.agents/skills` and invoke them with `$skill-name`.
- **Hook handler types `prompt` and `agent` are inert.** They parse without error and are then skipped, so a hook that relies on them silently does nothing. Use `type = "command"`.
- **`/import` from Claude's `.mcp.json` is a one-time migration, not a live sync.** It copies server definitions into Codex config once; later edits on either side do not propagate. Re-run it deliberately, or maintain both.
