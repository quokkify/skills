# Shared adapter contract

The shared adapter is one JSON-on-stdin hook contract for two runtimes: Claude Code and Codex CLI. Runtime-specific registration differs, while the executable scripts under `adapters/shared/hooks/` use the same input and output contract. The Git hooks are ordinary Git hooks and are runtime-neutral.

## Files and destinations

| Source | Claude Code destination | Codex CLI destination |
| --- | --- | --- |
| `AGENTS.base.md` | `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills-hub/AGENTS.base.md` | `$CODEX_HOME/AGENTS.md` |
| `hooks/hook-lib.sh` | `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/hook-lib.sh` | `$CODEX_HOME/hooks/hook-lib.sh` |
| `hooks/sessionstart-repo-context.sh` | `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/sessionstart-repo-context.sh` | `$CODEX_HOME/hooks/sessionstart-repo-context.sh` |
| `hooks/pretooluse-bash-guard.sh` | `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/pretooluse-bash-guard.sh` | `$CODEX_HOME/hooks/pretooluse-bash-guard.sh` |
| `hooks/completion-gate.sh` | `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/completion-gate.sh` | `$CODEX_HOME/hooks/completion-gate.sh` |
| `git-hooks/pre-commit` | the path from `git rev-parse --git-path hooks` as `pre-commit` | the path from `git rev-parse --git-path hooks` as `pre-commit` |
| `git-hooks/pre-push` | the path from `git rev-parse --git-path hooks` as `pre-push` | the path from `git rev-parse --git-path hooks` as `pre-push` |

These are templates: review existing user-owned configuration, copy the needed files manually, and preserve executable mode. No command in this repository installs this adapter or changes live hook configuration.

## Event mapping

| Event | Claude Code | Codex CLI | Script |
| --- | --- | --- | --- |
| `SessionStart` | registered | registered | `sessionstart-repo-context.sh` |
| `PreToolUse` | `Bash` matcher | `^Bash$` matcher | `pretooluse-bash-guard.sh` |
| `Stop` | registered | `*` matcher | `completion-gate.sh` |

## Claude Code wiring

Merge these entries into the `hooks` object in `settings.json`:

```json
{
  "SessionStart": [{"hooks": [{"type": "command", "command": "bash \"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/sessionstart-repo-context.sh\""}]}],
  "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "bash \"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/pretooluse-bash-guard.sh\""}]}],
  "Stop": [{"hooks": [{"type": "command", "command": "bash \"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/completion-gate.sh\""}]}]
}
```

## Codex CLI wiring

Merge these entries into `$CODEX_HOME/hooks.json`:

```json
{
  "SessionStart": [{"matcher": "*", "hooks": [{"type": "command", "command": "bash \"$CODEX_HOME/hooks/sessionstart-repo-context.sh\""}]}],
  "PreToolUse": [{"matcher": "^Bash$", "hooks": [{"type": "command", "command": "bash \"$CODEX_HOME/hooks/pretooluse-bash-guard.sh\""}]}],
  "Stop": [{"matcher": "*", "hooks": [{"type": "command", "command": "bash \"$CODEX_HOME/hooks/completion-gate.sh\""}]}]
}
```

Codex command hooks must be reviewed and trusted with `/hooks` in the Codex TUI. Hook layers are additive, so do not register the same command in both `$CODEX_HOME/hooks.json`, `config.toml`, and a trusted repository `.codex/hooks.json`.

## Behavior and opt-outs

Lifecycle hooks allow or no-op on internal parse, Git, or inspection errors. The completion gate derives its work tree from the stdin `cwd`, checks only lines added relative to `HEAD` (including non-ignored untracked files), and blocks with a nonempty `reason` for conservative placeholder markers: comment-prefixed `TODO`/`FIXME`, `test.skip`, `test.only`, `it.skip`, `it.only`, and obvious empty stub bodies.

All shared lifecycle hooks accept `SKILLS_HUB_DISABLE_HOOKS=1`; `SKILLS_HUB_SKIP_HOOKS=completion-gate,bash-guard,repo-context` disables named lifecycle hooks. Git hooks also accept `SKILLS_HUB_DISABLE_GIT_HOOKS=1` and `SKILLS_HUB_SKIP_GIT_HOOKS=pre-commit,pre-push`; the lifecycle variables apply to them too. Either `.skills-hooks-disable` at the work-tree root or `skills-hooks-disable` in the repository Git directory disables both kinds of hook.

`pre-commit` checks staged `ACMR` changes with `git diff --cached --check`. `pre-push` checks each pushed `ACMR` range. To run an additional repository-owned, executable check, configure a path with `git config skills-hub.check.pre-commit path/to/check` or `git config skills-hub.check.pre-push path/to/check`; relative paths resolve from the work-tree root. Neither template selects a stack, package manager, or vendor command.

The following events are deliberately uncovered because this adapter ships no corresponding shared script: Claude Code `UserPromptSubmit`, `PermissionRequest`, `PostToolUse`, `PostToolUseFailure`, `SubagentStart`, `SubagentStop`, `PreCompact`, `PostCompact`, and `SessionEnd`; Codex CLI `SessionEnd`, `UserPromptSubmit`, `PermissionRequest`, `PostToolUse`, `PreCompact`, `PostCompact`, `SubagentStart`, and `SubagentStop`. Add a separate reviewed script and wiring entry before enabling one.
