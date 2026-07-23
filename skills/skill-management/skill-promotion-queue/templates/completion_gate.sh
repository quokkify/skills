#!/usr/bin/env bash
# Completion gate for the skill-improvement publishing harness.
#
# Registered as a Claude Code Stop hook. It HOLDS task completion when the lane
# queue is dirty, has unpushed commits, or has queued commits without an open
# draft PR. It NEVER publishes anything itself — the semantic decision to
# publish stays in the agent workflow, and the mechanical push stays in
# publish_queue.py. This gate only observes and nudges.
#
# Runtime-generic: every path and lane is read from the machine-local config.env
# beside this script. Fast no-op on the happy path (clean, synced, or no lane
# worktree).
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$HERE/config.env" 2>/dev/null || exit 0

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

WT="$SKILL_HARNESS_WORKTREE"
BR="automation/skill-improvements/$SKILL_HARNESS_LANE"
[ -e "$WT/.git" ] || exit 0

reasons=""
add() { reasons="${reasons}\n  - $1"; }

if [ -n "$(git -C "$WT" status --porcelain --untracked-files=normal 2>/dev/null || true)" ]; then
  add "the lane worktree has uncommitted changes"
fi

ahead_main="$(git -C "$WT" rev-list --count origin/main..HEAD 2>/dev/null || echo 0)"
if [ "${ahead_main:-0}" -gt 0 ]; then
  local_head="$(git -C "$WT" rev-parse HEAD 2>/dev/null || echo x)"
  remote_head="$(git -C "$WT" rev-parse "origin/$BR" 2>/dev/null || echo NONE)"
  if [ "$remote_head" = "NONE" ] || [ "$remote_head" != "$local_head" ]; then
    add "the lane has unpushed queued commits"
  fi
  if command -v gh >/dev/null 2>&1; then
    drafts="$(gh pr list --repo "$SKILL_HARNESS_REPO" --state open --head "$BR" \
      --json isDraft -q 'map(select(.isDraft)) | length' 2>/dev/null || echo ERR)"
    if [ "$drafts" = "0" ]; then
      add "there are queued commits but no open draft PR for lane $BR"
    fi
  fi
fi

[ -z "$reasons" ] && exit 0

MSG="Skill-queue completion gate: the lane queue is not settled:${reasons}\n\nResolve it before finishing — commit or discard changes, then run:\n  bash \"$HERE/publish.sh\"\nThis gate does not publish for you. If this task is 'local only' / 'do not publish', discard the lane changes instead."

printf '%s' "$MSG" | python3 -c 'import sys,json; print(json.dumps({"decision":"block","reason":sys.stdin.read()}))'
exit 0
