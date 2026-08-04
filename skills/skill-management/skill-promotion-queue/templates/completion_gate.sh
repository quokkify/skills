#!/usr/bin/env bash
# Completion gate for the skill-improvement publishing harness.
#
# Registered as a Claude Code Stop hook. It HOLDS task completion when the lane
# queue is dirty, has unpushed commits, or has queued commits without an open
# draft PR. It NEVER publishes anything itself — the semantic decision to
# publish stays in the agent workflow, and the mechanical push stays in
# publish_queue.py. This gate only observes and nudges.
#
# It also carries non-blocking advisories: candidates left staged past their
# shelf life, and the one-shot summary that the background skill_cycle.sh leaves
# behind (an async SessionStart hook cannot inject context itself, so this Stop
# hook is its delivery channel). Advisories never hold completion.
#
# Runtime-generic: every path and lane is read from the machine-local config.env
# beside this script. Fast no-op on the happy path (clean, synced, or no lane
# worktree, and nothing to advise).
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CANDIDATES_DIR="$CLAUDE_DIR/skill-candidates"
CYCLE_NOTICE="$HERE/.cycle-notice"
CANDIDATE_STALE_DAYS="${SKILL_CANDIDATE_STALE_DAYS:-14}"

INPUT="$(cat 2>/dev/null || true)"

# Loop protection: if we already blocked once this stop-cycle, let it stop.
if printf '%s' "$INPUT" | python3 -c 'import sys,json
try:
    d=json.load(sys.stdin)
except Exception:
    sys.exit(1)
sys.exit(0 if d.get("stop_hook_active") else 1)' 2>/dev/null; then
  exit 0
fi

advisories=""
advise() { advisories="${advisories}$1
"; }

case "$CANDIDATE_STALE_DAYS" in
  ''|*[!0-9]*) CANDIDATE_STALE_DAYS=14 ;;
esac

if [ -d "$CANDIDATES_DIR" ]; then
  stale_candidates="$(find "$CANDIDATES_DIR" -maxdepth 1 -type f -name '*.md' \
    ! -name 'README.md' ! -name 'TEMPLATE.md' \
    -mtime +"$CANDIDATE_STALE_DAYS" -print 2>/dev/null | sort || true)"
  if [ -n "$stale_candidates" ]; then
    stale_count="$(printf '%s\n' "$stale_candidates" | wc -l | tr -d ' ')"
    advise "Warning: $stale_count skill candidate(s) have been staged for >${CANDIDATE_STALE_DAYS} days:"
    advise "$(printf '%s\n' "$stale_candidates" | sed 's|.*/|  - |')"
    advise "  Decide them with the skill-review skill and queue approved changes to the lane, then:"
    advise "    bash \"$HERE/publish.sh\""
    advise "  Or discard the ones you do not want: rm $CANDIDATES_DIR/<candidate>.md"
  fi
fi

if [ -f "$CYCLE_NOTICE" ]; then
  notice="$(cat "$CYCLE_NOTICE" 2>/dev/null || true)"
  [ -n "$notice" ] && advise "$notice"
  rm -f "$CYCLE_NOTICE"
fi

emit_advisories_and_exit() {
  [ -z "$advisories" ] && exit 0
  printf '%s' "$advisories" | python3 -c 'import sys,json; print(json.dumps({"continue":True,"systemMessage":sys.stdin.read().strip()}))'
  exit 0
}

# shellcheck source=/dev/null
source "$HERE/config.env" 2>/dev/null || emit_advisories_and_exit

# config.env is written by hand on each machine, so treat every key as optional:
# under `set -u` a bare "$SKILL_HARNESS_..." would abort this Stop hook with exit 1
# the moment one line is missing. Without a worktree or lane there is no queue to
# inspect, so fall through to advisories instead.
WT="${SKILL_HARNESS_WORKTREE:-}"
LANE="${SKILL_HARNESS_LANE:-}"
REPO="${SKILL_HARNESS_REPO:-}"
BR="automation/skill-improvements/$LANE"
[ -n "$WT" ] || emit_advisories_and_exit
[ -n "$LANE" ] || emit_advisories_and_exit
[ -e "$WT/.git" ] || emit_advisories_and_exit

# Resolve the base branch instead of hard-coding origin/main: an explicit
# override wins, else the remote's default branch, else origin/main. Otherwise a
# non-main default would drop the ahead count to 0 and silently skip the checks.
BASE_REF="${SKILL_HARNESS_BASE:-}"
if [ -z "$BASE_REF" ]; then
  BASE_REF="$(git -C "$WT" symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || true)"
  [ -z "$BASE_REF" ] && BASE_REF="origin/main"
fi

reasons=""
add() { reasons="${reasons}
  - $1"; }

if [ -n "$(git -C "$WT" status --porcelain --untracked-files=normal 2>/dev/null || true)" ]; then
  add "the lane worktree has uncommitted changes"
fi

ahead_main="$(git -C "$WT" rev-list --count "$BASE_REF..HEAD" 2>/dev/null || echo 0)"
if [ "${ahead_main:-0}" -gt 0 ]; then
  local_head="$(git -C "$WT" rev-parse HEAD 2>/dev/null || echo x)"
  remote_head="$(git -C "$WT" rev-parse "origin/$BR" 2>/dev/null || echo NONE)"
  if [ "$remote_head" = "NONE" ] || [ "$remote_head" != "$local_head" ]; then
    add "the lane has unpushed queued commits"
  fi
  if [ -n "$REPO" ] && command -v gh >/dev/null 2>&1; then
    drafts="$(gh pr list --repo "$REPO" --state open --head "$BR" \
      --json isDraft -q 'map(select(.isDraft)) | length' 2>/dev/null || echo ERR)"
    if [ "$drafts" = "0" ]; then
      add "there are queued commits but no open draft PR for lane $BR"
    fi
  fi
fi

[ -z "$reasons" ] && emit_advisories_and_exit

MSG="Skill-queue completion gate: the lane queue is not settled:${reasons}

Resolve it before finishing — commit or discard changes, then run:
  bash \"$HERE/publish.sh\"
This gate does not publish for you. If this task is 'local only' / 'do not publish', discard the lane changes instead."

if [ -n "$advisories" ]; then
  MSG="$MSG

$advisories"
fi

printf '%s' "$MSG" | python3 -c 'import sys,json; print(json.dumps({"decision":"block","reason":sys.stdin.read()}))'
exit 0
