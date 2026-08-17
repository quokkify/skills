#!/usr/bin/env bash
# PreToolUse guard: refuse a short list of irreversible shell commands.
#
# Runtime-agnostic. Reads the PreToolUse payload on stdin, inspects
# tool_input.command, and denies with a permissionDecisionReason when the
# command matches a conservative denylist. Anything it cannot parse is allowed.
#
# Hook name for SKILLS_HUB_SKIP_HOOKS: bash-guard

set -uo pipefail

HOOK_LIB_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./hook-lib.sh
. "$HOOK_LIB_DIR/hook-lib.sh"
hook_enable_failsafe

hook_read_input || hook_allow

case "$HOOK_TOOL_NAME" in
  Bash|bash|Shell|shell|local_shell|LocalShell) ;;
  *) hook_allow ;;
esac

COMMAND="$(hook_field tool_input.command)"
[ -n "$COMMAND" ] || hook_allow

WORKDIR="${HOOK_CWD:-$PWD}"
[ -d "$WORKDIR" ] || WORKDIR="$PWD"
GIT_ROOT="$(hook_git_root "$WORKDIR")"
hook_disabled bash-guard "$GIT_ROOT" && hook_allow

# Quotes are stripped once so every pattern below can ignore them: `rm -rf "/"`
# and `rm -rf /` normalize to the same text.
COMMAND_NORM="$(printf '%s' "$COMMAND" | tr -d '\047\042')"

matches() {
  printf '%s' "$COMMAND_NORM" | grep -Eq -- "$1"
}

matches_nocase() {
  printf '%s' "$COMMAND_NORM" | grep -Eiq -- "$1"
}

# 1. Recursive+forced delete aimed at a filesystem or home root. Split into
#    four cheap checks instead of one unreadable regex: the rm invocation, a
#    recursive flag, a force flag (either order or bundled), and a root target.
RM_INVOCATION='(^|[;&|(]|[[:space:]])rm([[:space:]]|$)'
RM_RECURSIVE='(^|[[:space:]])-[[:alnum:]]*[rR][[:alnum:]]*([[:space:]]|$)|--recursive'
RM_FORCE='(^|[[:space:]])-[[:alnum:]]*f[[:alnum:]]*([[:space:]]|$)|--force'
RM_ROOT_TARGET='[[:space:]](/|/\*|\$HOME/?\*?|\$\{HOME\}/?\*?|~/?\*?)([[:space:]]|;|&|\||$)'
if matches "$RM_INVOCATION" && matches "$RM_RECURSIVE" && matches "$RM_FORCE" && matches "$RM_ROOT_TARGET"; then
  hook_deny "Refused: this looks like a recursive forced delete of a filesystem or home root. Delete a specific project-relative path instead, or re-run with SKILLS_HUB_SKIP_HOOKS=bash-guard if the target is genuinely intended."
fi

GIT_SUBCOMMAND_PREFIX='(^|[;&|]|[[:space:]])git([[:space:]]+-[^[:space:]]+)*[[:space:]]+'

# 2. Forced push at a protected branch. --force-with-lease is deliberately
#    allowed because it cannot silently discard someone else's commits.
PROTECTED_BRANCH='(^|[[:space:]:+/])(main|master|develop|trunk|production|release)([[:space:]]|$)'
FORCE_FLAG='(^|[[:space:]])(--force|-[[:alnum:]]*f[[:alnum:]]*)([[:space:]]|$)'
if matches "${GIT_SUBCOMMAND_PREFIX}push([[:space:]]|\$)" && matches "$FORCE_FLAG" && ! matches '--force-with-lease'; then
  if matches "$PROTECTED_BRANCH" || matches '(^|[[:space:]])(--all|--mirror)([[:space:]]|$)'; then
    hook_deny "Refused: forced push targeting a protected branch (main/master/develop/trunk/production/release) or every ref at once. Push to a feature branch, or use --force-with-lease on a branch you own."
  fi
fi

# 3. git reset --hard while the working tree has uncommitted changes: the
#    canonical way an agent destroys work it never showed the user.
if matches "${GIT_SUBCOMMAND_PREFIX}reset([[:space:]]|\$)" && matches '--hard'; then
  if [ -n "$GIT_ROOT" ] && [ -n "$(git -C "$GIT_ROOT" status --porcelain 2>/dev/null | head -n 1)" ]; then
    hook_deny "Refused: 'git reset --hard' would discard uncommitted changes in this working tree. Stash or commit first (git stash push -u), then reset."
  fi
fi

# 4. Raw block-device writes and filesystem creation.
if matches '(^|[;&|]|[[:space:]])dd([[:space:]]|$)' && matches 'of=/dev/(disk|rdisk|sd|hd|nvme|mmcblk)'; then
  hook_deny "Refused: 'dd' writing directly to a block device destroys the disk it targets. If this is intentional, run it outside the agent session."
fi
if matches '(^|[;&|]|[[:space:]])mkfs(\.[[:alnum:]]+)?([[:space:]]|$)'; then
  hook_deny "Refused: 'mkfs' formats a device and is never reversible. If this is intentional, run it outside the agent session."
fi

# 5. Piping a downloaded script straight into a shell — unreviewable remote
#    code execution. Two-step it: download, read, then run.
if matches_nocase '(curl|wget)[^|;&]*\|[[:space:]]*(sudo[[:space:]]+)?(?:(?:/usr/bin/env)[[:space:]]+)?(?:/[[:alnum:]_.-]+/)?(ba|z|da|k)?sh([[:space:]]|$)'; then
  hook_deny "Refused: piping a downloaded script directly into a shell executes unreviewed remote code. Download it to a file, read it, then run it explicitly."
fi

hook_allow
