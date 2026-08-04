#!/usr/bin/env bash
# Cadence driver for the whole skill-maintenance chain: refresh the health signal, stage
# upgrade candidates for skills that diverged from the hub, and refresh the prune
# assessment. Stages and reports only — it never publishes, deletes, or edits a skill.
#
# Registered as an async SessionStart hook, so it must be silent, bounded, and incapable
# of failing a session start: every step is optional, every failure is swallowed, and the
# exit status is always 0.
#
# An async SessionStart hook cannot inject context into the session that started it, so
# when a run produces something new it leaves a one-shot summary in .cycle-notice.
# completion_gate.sh (Stop hook) delivers and clears it.
#
# Two guards keep it from running constantly across many sessions a day: the
# .last-cycle stamp with SKILL_CYCLE_INTERVAL_DAYS, and an atomic lock directory so
# simultaneous session starts cannot overlap. The stamp is written up front — a crashed
# run must not turn every subsequent session start into a retry.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
HEALTH_DIR="$CLAUDE_DIR/skill-health"
CANDIDATES_DIR="$CLAUDE_DIR/skill-candidates"
STAMP="$HERE/.last-cycle"
LOCK="$HERE/.cycle.lock"
NOTICE="$HERE/.cycle-notice"
LOG="$HEALTH_DIR/cycle.log"
LOG_MAX_LINES=500
LOCK_STALE_SECONDS=3600

# shellcheck source=/dev/null
[ -f "$HERE/config.env" ] && source "$HERE/config.env" 2>/dev/null

INTERVAL_DAYS="${SKILL_CYCLE_INTERVAL_DAYS:-14}"
FORCE=0
case "${1:-}" in
  --force) FORCE=1 ;;
  -h|--help)
    echo "Usage: skill_cycle.sh [--force]"
    echo
    echo "  Runs health-review -> skill_upgrade -> skill_prune at most once every"
    echo "  SKILL_CYCLE_INTERVAL_DAYS days (currently ${INTERVAL_DAYS}). --force ignores the stamp."
    exit 0
    ;;
  '') ;;
  *) exit 0 ;;
esac

case "$INTERVAL_DAYS" in
  ''|*[!0-9]*) INTERVAL_DAYS=14 ;;
esac

file_mtime() {
  stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0
}

now_epoch="$(date -u +%s 2>/dev/null || echo 0)"
now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo unknown)"

if [ "$FORCE" -eq 0 ] && [ -f "$STAMP" ]; then
  stamp_epoch="$(file_mtime "$STAMP")"
  case "$stamp_epoch" in
    ''|*[!0-9]*) stamp_epoch=0 ;;
  esac
  if [ "$stamp_epoch" -gt 0 ]; then
    age_days=$(( (now_epoch - stamp_epoch) / 86400 ))
    [ "$age_days" -lt "$INTERVAL_DAYS" ] && exit 0
  fi
fi

if ! mkdir "$LOCK" 2>/dev/null; then
  lock_epoch="$(file_mtime "$LOCK")"
  case "$lock_epoch" in
    ''|*[!0-9]*) lock_epoch=0 ;;
  esac
  if [ "$lock_epoch" -gt 0 ] && [ $(( now_epoch - lock_epoch )) -lt "$LOCK_STALE_SECONDS" ]; then
    exit 0
  fi
  rm -rf "$LOCK" 2>/dev/null
  mkdir "$LOCK" 2>/dev/null || exit 0
fi
trap 'rm -rf "$LOCK" 2>/dev/null' EXIT

mkdir -p "$HEALTH_DIR" "$CANDIDATES_DIR" 2>/dev/null
: > "$STAMP" 2>/dev/null || true

log() {
  printf '%s  %s\n' "$now_iso" "$1" >> "$LOG" 2>/dev/null || true
}

list_candidates() {
  ls -1 "$CANDIDATES_DIR" 2>/dev/null \
    | grep -E '\.md$' \
    | grep -vx 'README.md' \
    | grep -vx 'TEMPLATE.md' \
    | sort
}

before="$(list_candidates)"
log "cycle start (interval ${INTERVAL_DAYS}d, force=${FORCE})"

steps_ok=0
steps_failed=0
run_step() {
  local label="$1" script="$2"
  shift 2
  if [ ! -f "$script" ]; then
    log "skip $label — $script not installed"
    return 0
  fi
  if bash "$script" "$@" >/dev/null 2>&1; then
    steps_ok=$((steps_ok + 1))
    log "ok   $label"
  else
    steps_failed=$((steps_failed + 1))
    log "fail $label (exit non-zero; see the script directly)"
  fi
  return 0
}

run_step "health-review" "$HEALTH_DIR/health-review.sh"
run_step "skill_upgrade" "$HERE/skill_upgrade.sh"
run_step "skill_prune" "$HERE/skill_prune.sh"

after="$(list_candidates)"
new_files="$(comm -13 <(printf '%s\n' "$before") <(printf '%s\n' "$after") 2>/dev/null | sed '/^$/d')"

stale_count=0
if [ -f "$HEALTH_DIR/state.tsv" ]; then
  stale_count="$(awk -F'\t' '$7 == "stale"' "$HEALTH_DIR/state.tsv" 2>/dev/null | wc -l | tr -d ' ')"
fi

if [ -n "$new_files" ]; then
  new_count="$(printf '%s\n' "$new_files" | wc -l | tr -d ' ')"
  {
    printf 'Skill cycle ran (every %s days) and produced %s new file(s) in %s:\n' \
      "$INTERVAL_DAYS" "$new_count" "$CANDIDATES_DIR"
    printf '%s\n' "$new_files" | sed 's/^/  - /'
    printf '  %s skill(s) currently diverge from the hub.\n' "${stale_count:-0}"
    printf '  Review with the skill-review skill. Staging is not approval — nothing was published.\n'
  } > "$NOTICE" 2>/dev/null || true
  log "cycle end — $new_count new candidate file(s), stale=$stale_count, ok=$steps_ok fail=$steps_failed"
else
  log "cycle end — no new candidates, stale=$stale_count, ok=$steps_ok fail=$steps_failed"
fi

if [ -f "$LOG" ]; then
  log_lines="$(wc -l < "$LOG" 2>/dev/null | tr -d ' ')"
  case "${log_lines:-0}" in
    ''|*[!0-9]*) log_lines=0 ;;
  esac
  if [ "$log_lines" -gt "$LOG_MAX_LINES" ]; then
    tail -n "$LOG_MAX_LINES" "$LOG" > "$LOG.trim" 2>/dev/null && mv -f "$LOG.trim" "$LOG" 2>/dev/null
  fi
fi

exit 0
