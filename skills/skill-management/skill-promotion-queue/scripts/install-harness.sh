#!/usr/bin/env bash
# Install the skill-improvement publishing harness for Claude Code on this machine.
#
# Idempotent. Copies the runtime-generic harness scripts and the canonical
# publisher into the Claude config directory, seeds a machine-local config.env
# (never overwriting an existing one), and registers the Stop-hook completion
# gate. It installs machine-generic parts only; the per-machine lane and any
# credentials stay local and are never copied from another machine.
#
# Usage:
#   bash install-harness.sh --repo owner/name --lane my-machine \
#     --worktree /abs/path/to/lane-worktree --main /abs/path/to/main-checkout
#
# Any flag omitted is prompted for interactively (or takes a sensible default in
# a non-interactive shell). --lane defaults to a sanitized short hostname.
set -Eeuo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # .../skill-promotion-queue
TEMPLATES="$SKILL_DIR/templates"
PUBLISHER_SRC="$SKILL_DIR/scripts/publish_queue.py"
DEST="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skill-harness"
SETTINGS="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json"

repo="" ; lane="" ; worktree="" ; main=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) repo="$2"; shift 2 ;;
    --lane) lane="$2"; shift 2 ;;
    --worktree) worktree="$2"; shift 2 ;;
    --main) main="$2"; shift 2 ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

default_lane() {
  local h; h="$(hostname -s 2>/dev/null || hostname 2>/dev/null || echo machine)"
  printf '%s' "$h" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9._-' '-' \
    | sed 's/-\{2,\}/-/g; s/^-//; s/-$//'
}

prompt() { # var-name prompt-text default
  local __var="$1" __text="$2" __default="$3" __answer=""
  if [ -t 0 ]; then
    read -r -p "$__text${__default:+ [$__default]}: " __answer || true
  fi
  [ -z "$__answer" ] && __answer="$__default"
  printf -v "$__var" '%s' "$__answer"
}

[ -f "$PUBLISHER_SRC" ] || { echo "canonical publisher not found: $PUBLISHER_SRC" >&2; exit 1; }

mkdir -p "$DEST"
install -m 0755 "$TEMPLATES/completion_gate.sh" "$DEST/completion_gate.sh"
install -m 0755 "$TEMPLATES/publish.sh"         "$DEST/publish.sh"
install -m 0644 "$PUBLISHER_SRC"                "$DEST/publish_queue.py"
[ -f "$DEST/credentials.env.example" ] \
  || install -m 0644 "$TEMPLATES/credentials.env.example" "$DEST/credentials.env.example"
echo "installed harness scripts into $DEST"

if [ -f "$DEST/config.env" ]; then
  echo "config.env already exists — left unchanged (per-machine settings preserved)"
else
  # Non-interactive runs must not fall back to developer-specific defaults for
  # repository or paths: that would write an unreachable worktree and the gate
  # would silently no-op. Only --lane may be inferred (from the hostname).
  if [ ! -t 0 ]; then
    missing=""
    [ -n "$repo" ]     || missing="$missing --repo"
    [ -n "$worktree" ] || missing="$missing --worktree"
    [ -n "$main" ]     || missing="$missing --main"
    if [ -n "$missing" ]; then
      echo "install-harness: non-interactive run requires:$missing" >&2
      exit 2
    fi
  fi
  [ -n "$lane" ]     || prompt lane     "Unique lowercase lane for THIS machine" "$(default_lane)"
  [ -n "$repo" ]     || prompt repo     "Repository (owner/name)" "ylazakovich/skills"
  [ -n "$main" ]     || prompt main     "Absolute path to the stable main checkout" "$HOME/IdeaProjects/skills"
  [ -n "$worktree" ] || prompt worktree "Absolute path to the lane worktree" "$HOME/IdeaProjects/skills-lanes/$lane"
  # Emit shell-escaped assignments (config.env is sourced by bash) so values
  # containing &, #, or \ survive intact — no sed replacement pitfalls.
  ( umask 077
    {
      sed '/^SKILL_HARNESS_/,$d' "$TEMPLATES/config.example.env"
      printf 'SKILL_HARNESS_REPO=%q\n'     "$repo"
      printf 'SKILL_HARNESS_LANE=%q\n'     "$lane"
      printf 'SKILL_HARNESS_WORKTREE=%q\n' "$worktree"
      printf 'SKILL_HARNESS_MAIN=%q\n'     "$main"
    } > "$DEST/config.env" )
  echo "wrote $DEST/config.env (lane: $lane)"
fi

python3 - "$SETTINGS" <<'PY'
import json, os, sys

path = sys.argv[1]
command = 'bash "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skill-harness/completion_gate.sh"'

try:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
except FileNotFoundError:
    data = {}
except (ValueError, OSError) as error:
    print(f"settings.json unreadable ({error}); add the Stop hook manually:", file=sys.stderr)
    print("  " + command, file=sys.stderr)
    sys.exit(0)

stop = data.setdefault("hooks", {}).setdefault("Stop", [])

def registered(groups):
    for group in groups:
        for hook in (group or {}).get("hooks", []):
            if "completion_gate.sh" in (hook or {}).get("command", ""):
                return True
    return False

if registered(stop):
    print("Stop hook already registered — unchanged")
else:
    stop.append({"hooks": [{"type": "command", "command": command}]})
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    os.replace(temporary, path)
    print("registered Stop-hook completion gate in settings.json")
PY

cat <<EOF

Next steps:
  1. Create the lane worktree once, off the stable checkout:
       git -C "${main:-<main-checkout>}" worktree add \\
         "${worktree:-<lane-worktree>}" -b "automation/skill-improvements/${lane:-<lane>}"
  2. Each machine MUST use a different lane. Never point two machines at one branch.
  3. Credentials: default is SSH (git@github.com) + gh keyring — no token needed.
     For HTTPS only, copy credentials.env.example to credentials.env (chmod 600)
     and set GH_TOKEN.

Harness installed. The Stop hook holds completion while the lane queue is unsettled.
EOF
