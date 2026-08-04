#!/usr/bin/env bash
# Deterministic prune assessment for never-triggered skills.
#
# Reads the local health signal, evaluates every never-triggered installed skill, and
# writes a verdict report with the evidence behind each verdict. It NEVER deletes an
# installed skill and never pushes. Only the explicit `--apply` mode acts, and only on
# `prune` verdicts: it removes those skills from the hub copy inside the lane worktree
# and commits the removal so it flows through the existing rolling draft PR.
#
# The plan's prune bar requires BOTH conditions: unused for 30+ days AND duplicated or
# too narrow. A single condition never yields `prune`. Two evidence guards exist because
# an absent signal is not evidence of disuse: a skill installed less than 30 days ago,
# or a usage log whose own history is shorter than 30 days, cannot support any prune
# claim and is reported as such.
#
# The keep list is hard-coded here on purpose and is re-checked in --apply. Written for
# bash 3.2 (macOS system bash).
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
HEALTH_DIR="$CLAUDE_DIR/skill-health"
SKILLS_DIR="$CLAUDE_DIR/skills"
CANDIDATES_DIR="$CLAUDE_DIR/skill-candidates"
STATE="$HEALTH_DIR/state.tsv"
USAGE_LOG="$HEALTH_DIR/usage.jsonl"
REVIEW="$HEALTH_DIR/health-review.sh"

NEVER_KEEP_LIST="skill-review orchestrator-workflow mr"
UNUSED_MIN_DAYS="${SKILL_PRUNE_MIN_DAYS:-30}"
DUP_STRONG="60"
DUP_PARTIAL="35"

# shellcheck source=/dev/null
[ -f "$HERE/config.env" ] && source "$HERE/config.env"

HUB_ROOT="${SKILL_HARNESS_MAIN:-}"
LANE_WORKTREE="${SKILL_HARNESS_WORKTREE:-}"
LANE="${SKILL_HARNESS_LANE:-}"
APPLY=0

usage() {
  cat <<'EOF'
Usage: skill_prune.sh [--apply]

  (default)  assess and write a verdict report; changes nothing
  --apply    commit removal of `prune`-verdict skills from the hub copy in the lane
             worktree (explicit approval step; never pushes, never touches installed
             skills, never removes a keep-listed skill)
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "skill_prune: unknown argument '$1'" >&2; usage >&2; exit 2 ;;
  esac
done

case "$UNUSED_MIN_DAYS" in
  ''|*[!0-9]*) echo "skill_prune: SKILL_PRUNE_MIN_DAYS must be a non-negative integer" >&2; exit 2 ;;
esac

TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/skill-prune.XXXXXX")" || exit 1
trap 'rm -rf "$TMP_ROOT"' EXIT

STOPWORDS="$TMP_ROOT/stopwords"
VERDICTS="$TMP_ROOT/verdicts.tsv"
: > "$VERDICTS"
cat > "$STOPWORDS" <<'EOF'
also
about
after
agent
agents
already
always
another
because
before
being
below
between
build
cannot
claude
code
does
done
each
else
every
from
have
into
just
like
made
make
more
most
must
need
needs
only
other
over
same
should
skill
skills
some
such
than
that
their
them
then
there
these
they
this
those
through
uses
using
what
when
where
which
while
with
without
work
would
your
EOF

now_epoch="$(date -u +%s)"
today="$(date -u +%Y-%m-%d)"
now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

file_mtime() {
  stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0
}

epoch_date() {
  case "${1:-}" in
    ''|*[!0-9]*) printf 'unknown\n'; return 0 ;;
  esac
  [ "$1" -gt 0 ] || { printf 'unknown\n'; return 0; }
  date -u -r "$1" +%Y-%m-%d 2>/dev/null || date -u -d "@$1" +%Y-%m-%d 2>/dev/null || printf 'unknown\n'
}

days_since() {
  case "${1:-}" in
    ''|*[!0-9]*) printf -- '-1\n'; return 0 ;;
  esac
  [ "$1" -gt 0 ] || { printf -- '-1\n'; return 0; }
  printf '%s\n' $(( (now_epoch - $1) / 86400 ))
}

is_keep_listed() {
  local candidate="$1" entry
  for entry in $NEVER_KEEP_LIST; do
    [ "$entry" = "$candidate" ] && return 0
  done
  return 1
}

# Emits the YAML frontmatter block (between the first two --- fences) of a SKILL.md.
frontmatter() {
  [ -f "$1" ] || return 0
  awk 'NR == 1 && $0 != "---" { exit }
       NR == 1 { next }
       /^---[[:space:]]*$/ { exit }
       { print }' "$1"
}

has_critical_flag() {
  frontmatter "$1" | grep -Eq '^[[:space:]]*critical:[[:space:]]*(true|yes)[[:space:]]*$'
}

skill_description() {
  frontmatter "$1" | awk '
    /^description:/ { capture = 1; sub(/^description:[[:space:]]*/, ""); print; next }
    capture && /^[[:space:]]+/ { print; next }
    capture { exit }'
}

write_tokens() {
  local md="$1" out="$2"
  { printf '%s\n' "$(basename "$(dirname "$md")")"; skill_description "$md"; } \
    | tr '[:upper:]' '[:lower:]' \
    | tr -cs 'a-z0-9' '\n' \
    | awk 'length($0) >= 4' \
    | grep -vxF -f "$STOPWORDS" \
    | sort -u > "$out" || true
}

# Containment score in percent: |A n B| / min(|A|,|B|). Containment, not Jaccard, so a
# short description is not penalized for brevity against a long one.
overlap_score() {
  local a="$1" b="$2" na nb shared smaller
  na="$(wc -l < "$a" | tr -d ' ')"
  nb="$(wc -l < "$b" | tr -d ' ')"
  [ "${na:-0}" -gt 0 ] || { printf '0\n'; return 0; }
  [ "${nb:-0}" -gt 0 ] || { printf '0\n'; return 0; }
  shared="$(comm -12 "$a" "$b" | wc -l | tr -d ' ')"
  smaller="$na"
  [ "$nb" -lt "$smaller" ] && smaller="$nb"
  printf '%s\n' $(( shared * 100 / smaller ))
}

if [ ! -f "$STATE" ]; then
  if [ -f "$REVIEW" ]; then
    bash "$REVIEW" >/dev/null 2>&1 || true
  fi
fi
[ -f "$STATE" ] || { echo "skill_prune: no health signal at $STATE — nothing to assess."; exit 0; }

signal_days=-1
if [ -f "$USAGE_LOG" ] && command -v jq >/dev/null 2>&1; then
  # awk, not `head -1`: once sort's output exceeds the pipe buffer a closing `head`
  # SIGPIPEs it, and under `set -e` + pipefail the 141 kills this script. Measured
  # fatal at ~4000 usage events, so `head` here would fail silently as the log grows.
  oldest_iso="$(jq -r '.ts // empty' "$USAGE_LOG" 2>/dev/null | sed '/^$/d' | sort | awk 'NR == 1')"
  if [ -n "${oldest_iso:-}" ]; then
    oldest_epoch="$(python3 -c '
import calendar, sys, time
try:
    print(calendar.timegm(time.strptime(sys.argv[1], "%Y-%m-%dT%H:%M:%SZ")))
except Exception:
    print(0)' "$oldest_iso" 2>/dev/null || echo 0)"
    signal_days="$(days_since "$oldest_epoch")"
  fi
fi

hub_commit_epoch() {
  local hub_md="$1" value
  [ "$hub_md" != "-" ] || { printf '0\n'; return 0; }
  [ -n "$HUB_ROOT" ] || { printf '0\n'; return 0; }
  [ -d "$HUB_ROOT/.git" ] || { printf '0\n'; return 0; }
  value="$(git -C "$HUB_ROOT" log -1 --format=%at -- "$hub_md" 2>/dev/null || true)"
  case "${value:-}" in
    ''|*[!0-9]*) printf '0\n' ;;
    *) printf '%s\n' "$value" ;;
  esac
}

best_overlap() {
  local target_md="$1" self="$2"
  local target_tokens="$TMP_ROOT/target.tokens" other_tokens="$TMP_ROOT/other.tokens"
  local best_name="" best_score=0 best_usage=0 name other_usage other_md score
  write_tokens "$target_md" "$target_tokens"
  [ -s "$target_tokens" ] || { printf -- '-\t0\t0\n'; return 0; }
  while IFS="$(printf '\t')" read -r name other_usage _mtime _isha _hub _hsha _st; do
    [ -n "${name:-}" ] || continue
    [ "$name" != "$self" ] || continue
    other_md="$SKILLS_DIR/$name/SKILL.md"
    [ -f "$other_md" ] || continue
    write_tokens "$other_md" "$other_tokens"
    [ -s "$other_tokens" ] || continue
    score="$(overlap_score "$target_tokens" "$other_tokens")"
    if [ "$score" -gt "$best_score" ] || { [ "$score" -eq "$best_score" ] && [ "${other_usage:-0}" -gt "$best_usage" ]; }; then
      best_score="$score"
      best_name="$name"
      best_usage="${other_usage:-0}"
    fi
  done < "$STATE"
  printf '%s\t%s\t%s\n' "${best_name:--}" "$best_score" "$best_usage"
}

while IFS="$(printf '\t')" read -r name usage_count mtime installed_sha hub_md hub_sha row_state; do
  [ -n "${name:-}" ] || continue
  [ "${usage_count:-0}" = "0" ] || continue

  installed_md="$SKILLS_DIR/$name/SKILL.md"
  installed_days="$(days_since "$mtime")"
  hub_epoch="$(hub_commit_epoch "$hub_md")"
  hub_days="$(days_since "$hub_epoch")"

  verdict=""
  reason=""
  match="-"
  score=0

  if is_keep_listed "$name"; then
    verdict="keep-critical"
    reason="on the hard-coded core keep list"
  elif [ -f "$installed_md" ] && has_critical_flag "$installed_md"; then
    verdict="keep-critical"
    reason="frontmatter declares critical: true"
  elif [ "$row_state" = "local-only" ]; then
    verdict="not-hub-managed"
    reason="no hub copy; removal belongs to whichever installer owns it, not to the lane"
  elif [ "${signal_days:--1}" -lt "$UNUSED_MIN_DAYS" ]; then
    verdict="keep-insufficient-signal"
    reason="usage log covers only ${signal_days} day(s); ${UNUSED_MIN_DAYS}+ are required before absence of use is evidence"
  elif [ "${installed_days:--1}" -lt "$UNUSED_MIN_DAYS" ]; then
    verdict="keep-too-new"
    reason="installed ${installed_days} day(s) ago; below the ${UNUSED_MIN_DAYS}-day observation bar"
  else
    overlap="$(best_overlap "$installed_md" "$name")"
    match="$(printf '%s' "$overlap" | cut -f1)"
    score="$(printf '%s' "$overlap" | cut -f2)"
    if [ "${score:-0}" -ge "$DUP_STRONG" ] && [ "$match" != "-" ]; then
      verdict="prune"
      reason="unused ${installed_days}d and ${score}% description overlap with '${match}' (near-duplicate)"
    elif [ "${score:-0}" -ge "$DUP_PARTIAL" ] && [ "$match" != "-" ]; then
      verdict="merge-into:$match"
      reason="unused ${installed_days}d and ${score}% description overlap with '${match}' (partial duplication)"
    else
      verdict="review-manually"
      reason="unused ${installed_days}d but no duplication found (best ${score}% vs '${match}'); judge whether the pattern is too narrow to keep"
    fi
  fi

  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$name" "$verdict" "$reason" "$installed_days" "$hub_days" "$match" "$score" "$hub_md" >> "$VERDICTS"
done < "$STATE"

count_verdict() {
  awk -F'\t' -v want="$1" '$2 == want' "$VERDICTS" | wc -l | tr -d ' '
}

prune_count="$(count_verdict prune)"

if [ "$APPLY" -eq 1 ]; then
  if [ "${prune_count:-0}" -eq 0 ]; then
    echo "skill_prune: no 'prune' verdicts — nothing to apply."
    echo "Run without --apply to see the current assessment."
    exit 0
  fi
  # Without a hub root the "$HUB_ROOT"/* containment pattern below would degrade to /*
  # and stop constraining which paths may be removed. Refuse instead.
  [ -n "$HUB_ROOT" ] || { echo "skill_prune: SKILL_HARNESS_MAIN is not configured — cannot apply." >&2; exit 1; }
  [ -n "$LANE_WORKTREE" ] || { echo "skill_prune: SKILL_HARNESS_WORKTREE is not configured — cannot apply." >&2; exit 1; }
  [ -e "$LANE_WORKTREE/.git" ] || { echo "skill_prune: lane worktree missing at $LANE_WORKTREE — cannot apply." >&2; exit 1; }
  if [ -n "$(git -C "$LANE_WORKTREE" status --porcelain --untracked-files=normal 2>/dev/null || true)" ]; then
    echo "skill_prune: lane worktree is dirty — commit or discard before applying." >&2
    exit 1
  fi
  expected_branch="automation/skill-improvements/${LANE:-}"
  actual_branch="$(git -C "$LANE_WORKTREE" symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
  if [ -n "$LANE" ] && [ "$actual_branch" != "$expected_branch" ]; then
    echo "skill_prune: lane worktree is on '$actual_branch', expected '$expected_branch'." >&2
    exit 1
  fi

  removed=0
  while IFS="$(printf '\t')" read -r name verdict reason installed_days hub_days match score hub_md; do
    [ "$verdict" = "prune" ] || continue
    if is_keep_listed "$name"; then
      echo "skill_prune: refusing to remove keep-listed '$name'." >&2
      continue
    fi
    case "$hub_md" in
      "$HUB_ROOT"/*) rel_dir="$(dirname "${hub_md#"$HUB_ROOT"/}")" ;;
      *) echo "skill_prune: '$name' hub path '$hub_md' is outside $HUB_ROOT — skipping." >&2; continue ;;
    esac
    case "$rel_dir" in
      skills/*/"$name") ;;
      *) echo "skill_prune: '$name' resolves to unexpected hub path '$rel_dir' — skipping." >&2; continue ;;
    esac
    if [ ! -d "$LANE_WORKTREE/$rel_dir" ]; then
      echo "skill_prune: '$rel_dir' absent from the lane worktree — skipping."
      continue
    fi
    git -C "$LANE_WORKTREE" rm -r -q -- "$rel_dir"
    echo "skill_prune: staged removal of $rel_dir"
    removed=$((removed + 1))
  done < "$VERDICTS"

  if [ "$removed" -eq 0 ]; then
    echo "skill_prune: nothing staged."
    exit 0
  fi
  git -C "$LANE_WORKTREE" commit -q -m "refactor(skills): prune $removed unused duplicate skill(s)"
  echo "skill_prune: committed $removed removal(s) in lane ${LANE:-$actual_branch}."
  echo "Publish when ready:  bash \"$HERE/publish.sh\""
  exit 0
fi

mkdir -p "$CANDIDATES_DIR"
REPORT="$CANDIDATES_DIR/prune-assessment-$today.md"

{
  echo "# Skill prune assessment"
  echo
  echo "Generated by \`skill_prune.sh\` on $now_iso. Nothing has been deleted."
  echo
  echo "| Setting | Value |"
  echo "|---|---|"
  echo "| Unused-days bar | $UNUSED_MIN_DAYS |"
  echo "| Usage-signal history | ${signal_days} day(s) |"
  echo "| Hub checkout | \`$HUB_ROOT\` |"
  echo "| Hard keep list | $(printf '%s' "$NEVER_KEEP_LIST" | sed 's/ /, /g') |"
  echo "| Near-duplicate threshold | ${DUP_STRONG}% description overlap |"
  echo "| Partial-duplicate threshold | ${DUP_PARTIAL}% description overlap |"
  echo
  if [ "${signal_days:--1}" -lt "$UNUSED_MIN_DAYS" ]; then
    echo "> **No skill can be pruned yet.** The usage log only covers ${signal_days} day(s)."
    echo "> Absence of use over a shorter window is not evidence of disuse, so every"
    echo "> never-triggered skill is held at \`keep-insufficient-signal\` regardless of"
    echo "> duplication. Re-run after the log spans ${UNUSED_MIN_DAYS}+ days."
    echo
  fi

  echo "## Verdicts"
  echo
  if [ -s "$VERDICTS" ]; then
    echo "| Skill | Verdict | Installed (days) | Best overlap | Evidence |"
    echo "|---|---|---|---|---|"
    sort -t"$(printf '\t')" -k2,2 -k1,1 "$VERDICTS" \
      | while IFS="$(printf '\t')" read -r name verdict reason installed_days hub_days match score hub_md; do
          [ -n "${name:-}" ] || continue
          if [ "$match" = "-" ]; then
            overlap_cell="—"
          else
            overlap_cell="${score}% \`$match\`"
          fi
          if [ "${installed_days:--1}" -lt 0 ]; then days_cell="unknown"; else days_cell="$installed_days"; fi
          echo "| \`$name\` | \`$verdict\` | $days_cell | $overlap_cell | $reason |"
        done
  else
    echo "- (every installed skill has been triggered — no prune candidates)"
  fi
  echo

  echo "## Summary"
  echo
  for v in prune review-manually keep-critical keep-too-new keep-insufficient-signal not-hub-managed; do
    n="$(count_verdict "$v")"
    [ "${n:-0}" -gt 0 ] && echo "- \`$v\`: $n"
  done
  merge_n="$(awk -F'\t' '$2 ~ /^merge-into:/' "$VERDICTS" | wc -l | tr -d ' ')"
  [ "${merge_n:-0}" -gt 0 ] && echo "- \`merge-into:*\`: $merge_n"
  echo

  echo "## Decision rules"
  echo
  echo "Both plan conditions must hold for \`prune\`: unused for ${UNUSED_MIN_DAYS}+ days AND"
  echo "duplicated by another skill. A skill that is merely unused gets \`review-manually\`,"
  echo "because \"too narrow to keep\" is a judgement call this script deliberately does not make."
  echo
  echo "- \`keep-critical\` — hard keep list or \`critical: true\` frontmatter. Never removable here."
  echo "- \`not-hub-managed\` — installed without a hub copy. The lane cannot remove it; use the"
  echo "  installer that put it there."
  echo "- \`merge-into:<skill>\` — fold the useful part into the named skill, then re-assess."
  echo "- \`prune\` — near-duplicate; removable from the hub via the lane."
  echo
  echo "## Next step"
  echo
  if [ "${prune_count:-0}" -gt 0 ]; then
    echo "Review each \`prune\` row above. Removal is queued to the lane (not pushed) with:"
    echo
    echo "      bash \"$HERE/skill_prune.sh\" --apply"
    echo
    echo "Then publish the rolling draft PR when ready: \`bash \"$HERE/publish.sh\"\`"
  else
    echo "No \`prune\` verdicts. Nothing to queue; no action required."
  fi
} > "$REPORT.tmp"
mv -f "$REPORT.tmp" "$REPORT"
chmod 600 "$REPORT"

echo "skill_prune: wrote $REPORT"
echo "skill_prune: prune=$prune_count review-manually=$(count_verdict review-manually) keep-critical=$(count_verdict keep-critical) keep-insufficient-signal=$(count_verdict keep-insufficient-signal) keep-too-new=$(count_verdict keep-too-new) not-hub-managed=$(count_verdict not-hub-managed)"
exit 0
