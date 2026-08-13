#!/usr/bin/env bash
# Shared lifecycle-hook library for Claude Code and Codex CLI.
#
# Both runtimes speak the same contract: one JSON object arrives on stdin, and
# the hook steers the agent either by printing a JSON control object on stdout
# (exit 0) or by exiting 2 with a human-readable reason on stderr. Sourcing this
# file gives a hook normalized input variables plus emitters that produce the
# exact JSON shapes both runtimes accept, so a single script serves both.
#
# Contract summary:
#   PreToolUse deny  -> {"hookSpecificOutput":{"hookEventName":"PreToolUse",
#                        "permissionDecision":"deny",
#                        "permissionDecisionReason":"<non-empty>"}}
#   extra context    -> {"hookSpecificOutput":{"hookEventName":"<event>",
#                        "additionalContext":"<text>"}}
#   Stop block       -> {"decision":"block","reason":"<text>"}
#   universal deny   -> exit 2, reason on stderr
#   allow / no-op    -> exit 0 with no stdout

HOOK_LIB_VERSION=1
HOOK_EXIT_INTENT=incidental

hook_locate_python() {
  local candidate
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

HOOK_PY="$(hook_locate_python || true)"

# A hook that crashes must never wedge the session: any unplanned non-zero
# status is downgraded to 0 (allow, non-blocking) unless an emitter marked the
# exit deliberate.
hook_on_exit() {
  local status=$?
  if [ "$status" -ne 0 ] && [ "$HOOK_EXIT_INTENT" != deliberate ]; then
    exit 0
  fi
  exit "$status"
}

hook_enable_failsafe() {
  trap hook_on_exit EXIT
}

hook_runtime() {
  if [ -n "${CODEX_HOME:-}" ]; then
    printf 'codex'
  elif [ -n "${CLAUDE_CONFIG_DIR:-}" ] || [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
    printf 'claude'
  else
    printf 'unknown'
  fi
}

hook_plugin_root() {
  printf '%s' "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}"
}

hook_read_input() {
  HOOK_EVENT=""
  HOOK_SESSION_ID=""
  HOOK_TRANSCRIPT_PATH=""
  HOOK_CWD=""
  HOOK_MODEL=""
  HOOK_TURN_ID=""
  HOOK_PERMISSION_MODE=""
  HOOK_TOOL_NAME=""
  HOOK_TOOL_USE_ID=""
  HOOK_TOOL_INPUT_JSON=""
  HOOK_TOOL_RESPONSE_JSON=""

  HOOK_RAW_INPUT="$(cat 2>/dev/null || true)"
  export HOOK_RAW_INPUT

  if [ -z "$HOOK_RAW_INPUT" ] || [ -z "$HOOK_PY" ]; then
    return 1
  fi

  local assignments
  assignments="$("$HOOK_PY" -c '
import json, os, shlex, sys

try:
    data = json.loads(os.environ.get("HOOK_RAW_INPUT", ""))
except Exception:
    sys.exit(1)
if not isinstance(data, dict):
    sys.exit(1)

scalars = (
    ("HOOK_EVENT", "hook_event_name"),
    ("HOOK_SESSION_ID", "session_id"),
    ("HOOK_TRANSCRIPT_PATH", "transcript_path"),
    ("HOOK_CWD", "cwd"),
    ("HOOK_MODEL", "model"),
    ("HOOK_TURN_ID", "turn_id"),
    ("HOOK_PERMISSION_MODE", "permission_mode"),
    ("HOOK_TOOL_NAME", "tool_name"),
    ("HOOK_TOOL_USE_ID", "tool_use_id"),
)
blobs = (
    ("HOOK_TOOL_INPUT_JSON", "tool_input"),
    ("HOOK_TOOL_RESPONSE_JSON", "tool_response"),
)

lines = []
for name, key in scalars:
    value = data.get(key)
    text = "" if value is None else value if isinstance(value, str) else json.dumps(value)
    lines.append("%s=%s" % (name, shlex.quote(text)))
for name, key in blobs:
    value = data.get(key)
    lines.append("%s=%s" % (name, shlex.quote("" if value is None else json.dumps(value))))
sys.stdout.write("\n".join(lines))
' 2>/dev/null)" || return 1

  [ -n "$assignments" ] || return 1
  eval "$assignments"
  return 0
}

# hook_field <dotted.path> — read an arbitrary value out of the raw payload,
# e.g. hook_field tool_input.command
hook_field() {
  [ -n "${HOOK_RAW_INPUT:-}" ] || return 0
  [ -n "$HOOK_PY" ] || return 0
  "$HOOK_PY" -c '
import json, os, sys

try:
    node = json.loads(os.environ.get("HOOK_RAW_INPUT", ""))
except Exception:
    sys.exit(0)
for part in sys.argv[1].split("."):
    if isinstance(node, dict) and part in node:
        node = node[part]
    else:
        sys.exit(0)
if node is None:
    sys.exit(0)
sys.stdout.write(node if isinstance(node, str) else json.dumps(node))
' "$1" 2>/dev/null || true
}

hook_emit_json() {
  local kind="$1"
  shift
  [ -n "$HOOK_PY" ] || return 1
  "$HOOK_PY" -c '
import json, sys

kind = sys.argv[1]
if kind == "deny":
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": sys.argv[2],
        }
    }
elif kind == "context":
    payload = {
        "hookSpecificOutput": {
            "hookEventName": sys.argv[2],
            "additionalContext": sys.argv[3],
        }
    }
elif kind == "stop-block":
    payload = {"decision": "block", "reason": sys.argv[2]}
else:
    sys.exit(1)
sys.stdout.write(json.dumps(payload))
sys.stdout.write("\n")
' "$kind" "$@"
}

hook_allow() {
  HOOK_EXIT_INTENT=deliberate
  exit 0
}

hook_deny() {
  local reason="${1:-Blocked by a shared safety hook.}"
  HOOK_EXIT_INTENT=deliberate
  if hook_emit_json deny "$reason"; then
    exit 0
  fi
  printf '%s\n' "$reason" >&2
  exit 2
}

hook_add_context() {
  local text="${1:-}"
  local event="${2:-${HOOK_EVENT:-SessionStart}}"
  [ -n "$text" ] || hook_allow
  HOOK_EXIT_INTENT=deliberate
  hook_emit_json context "$event" "$text" || true
  exit 0
}

hook_block_stop() {
  local reason="${1:-Work looks unfinished.}"
  HOOK_EXIT_INTENT=deliberate
  if hook_emit_json stop-block "$reason"; then
    exit 0
  fi
  printf '%s\n' "$reason" >&2
  exit 2
}

# Opt-outs, mirroring the escape-hatch style of the shared git hooks:
#   SKILLS_HUB_DISABLE_HOOKS=1        disable every shared lifecycle hook
#   SKILLS_HUB_SKIP_HOOKS=a,b         disable named hooks (comma separated)
#   .skills-hooks-disable             repo-local kill switch (also .git/…)
hook_disabled() {
  local name="$1"
  local root="${2:-}"

  if [ "${SKILLS_HUB_DISABLE_HOOKS:-0}" = "1" ]; then
    return 0
  fi

  case ",${SKILLS_HUB_SKIP_HOOKS:-}," in
    *",$name,"*) return 0 ;;
  esac

  if [ -n "$root" ]; then
    local git_disable_file
    git_disable_file="$(git -C "$root" rev-parse --git-path skills-hooks-disable 2>/dev/null || true)"
    if [ -f "$root/.skills-hooks-disable" ] || { [ -n "$git_disable_file" ] && [ -f "$git_disable_file" ]; }; then
      return 0
    fi
  fi
  return 1
}

hook_git_root() {
  local start="${1:-}"
  [ -n "$start" ] && [ -d "$start" ] || start="$PWD"
  git -C "$start" rev-parse --show-toplevel 2>/dev/null || true
}
