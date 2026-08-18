#!/usr/bin/env bash
# SessionStart context: tell the agent where the repository actually stands.
#
# Runtime-agnostic. Emits additionalContext with the current branch, whether the
# working tree is dirty, and how far HEAD has drifted from its upstream. No-ops
# cleanly outside a git work tree.
#
# Hook name for SKILLS_HUB_SKIP_HOOKS: repo-context

set -uo pipefail

HOOK_LIB_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./hook-lib.sh
. "$HOOK_LIB_DIR/hook-lib.sh"
hook_enable_failsafe

hook_read_input || true

WORKDIR="${HOOK_CWD:-$PWD}"
[ -d "$WORKDIR" ] || WORKDIR="$PWD"
GIT_ROOT="$(hook_git_root "$WORKDIR")"
[ -n "$GIT_ROOT" ] || hook_allow
hook_disabled repo-context "$GIT_ROOT" && hook_allow

branch="$(git -C "$GIT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
[ -n "$branch" ] || branch="(detached or unborn)"

dirty_count="$(git -C "$GIT_ROOT" status --porcelain 2>/dev/null | grep -c . || true)"
[ -n "$dirty_count" ] || dirty_count=0

if [ "$dirty_count" -eq 0 ] 2>/dev/null; then
  tree_state="clean"
else
  tree_state="dirty ($dirty_count changed path(s))"
fi

upstream="$(git -C "$GIT_ROOT" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true)"
if [ -n "$upstream" ]; then
  counts="$(git -C "$GIT_ROOT" rev-list --left-right --count "$upstream...HEAD" 2>/dev/null || true)"
  behind="${counts%%	*}"
  ahead="${counts##*	}"
  [ -n "$behind" ] || behind=0
  [ -n "$ahead" ] || ahead=0
  upstream_state="tracking $upstream, $ahead ahead / $behind behind"
else
  upstream_state="no upstream configured"
fi

runtime="$(hook_runtime)"

CONTEXT="Repository state at session start (shared hook, runtime: $runtime):
- root: $(basename -- "$GIT_ROOT")
- branch: $branch
- working tree: $tree_state
- upstream: $upstream_state

Re-check 'git status --short --branch' before editing if this session resumes or compacts."

hook_add_context "$CONTEXT" "${HOOK_EVENT:-SessionStart}"
