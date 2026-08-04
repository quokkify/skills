#!/usr/bin/env bash
# Automated intake for the `patch-existing` branch of the skill-review pipeline.
#
# Reads the local health signal (skill-health/state.tsv, refreshed on demand), picks
# the most-used installed skills whose SKILL.md no longer matches the hub checkout,
# and stages one upgrade candidate per skill in the private candidate directory. It
# proposes; it never publishes and never edits an installed skill.
#
# The only writing mode is the explicit `--adopt <skill>`: it copies the installed
# SKILL.md over its hub path inside the lane worktree and commits it, so the change
# flows through the existing rolling draft PR. Nothing is pushed here.
#
# Graceful no-op (exit 0) when the hub checkout, the lane worktree, or the health
# signal is unavailable. Written for bash 3.2 (macOS system bash).
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
HEALTH_DIR="$CLAUDE_DIR/skill-health"
SKILLS_DIR="$CLAUDE_DIR/skills"
CANDIDATES_DIR="$CLAUDE_DIR/skill-candidates"
STATE="$HEALTH_DIR/state.tsv"
USAGE_LOG="$HEALTH_DIR/usage.jsonl"
REVIEW="$HEALTH_DIR/health-review.sh"
DIFF_MAX_LINES=400

# shellcheck source=/dev/null
[ -f "$HERE/config.env" ] && source "$HERE/config.env"

HUB_ROOT="${SKILL_HARNESS_MAIN:-}"
LANE_WORKTREE="${SKILL_HARNESS_WORKTREE:-}"
LANE="${SKILL_HARNESS_LANE:-}"
TOP_N="${SKILL_UPGRADE_TOP_N:-5}"
FORCE=0
ADOPT=""

usage() {
  cat <<'EOF'
Usage: skill_upgrade.sh [--top N] [--force] [--adopt <skill-name>]

  --top N            consider at most N stale skills, most-used first (default 5)
  --force            overwrite an existing candidate for today instead of skipping
  --adopt <skill>    commit the installed SKILL.md over its hub copy in the lane
                     worktree (explicit approval step; never pushes)
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --top)
      [ "$#" -ge 2 ] || { echo "skill_upgrade: --top needs a value" >&2; exit 2; }
      TOP_N="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --adopt)
      [ "$#" -ge 2 ] || { echo "skill_upgrade: --adopt needs a skill name" >&2; exit 2; }
      ADOPT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "skill_upgrade: unknown argument '$1'" >&2; usage >&2; exit 2 ;;
  esac
done

case "$TOP_N" in
  ''|*[!0-9]*) echo "skill_upgrade: --top must be a non-negative integer" >&2; exit 2 ;;
esac

file_mtime() {
  stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0
}

today="$(date -u +%Y-%m-%d)"
now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

refresh_state() {
  [ -x "$REVIEW" ] || [ -f "$REVIEW" ] || return 1
  bash "$REVIEW" >/dev/null 2>&1 || return 1
  return 0
}

if [ ! -f "$STATE" ]; then
  refresh_state || { echo "skill_upgrade: no health signal at $STATE and health-review.sh unavailable — nothing to do."; exit 0; }
elif [ -f "$USAGE_LOG" ] && [ "$(file_mtime "$USAGE_LOG")" -gt "$(file_mtime "$STATE")" ]; then
  refresh_state || true
fi

[ -f "$STATE" ] || { echo "skill_upgrade: health signal still missing — nothing to do."; exit 0; }

if [ -z "$HUB_ROOT" ]; then
  echo "skill_upgrade: SKILL_HARNESS_MAIN is not set in config.env — nothing to do."
  exit 0
fi
if [ ! -d "$HUB_ROOT/skills" ]; then
  echo "skill_upgrade: hub checkout unavailable at $HUB_ROOT — nothing to do."
  exit 0
fi

# state.tsv columns: name usage mtime installed_sha hub_path hub_sha state
stale_rows() {
  awk -F'\t' '$7 == "stale" { print }' "$STATE" | sort -t"$(printf '\t')" -k2,2nr
}

lane_relative_hub_path() {
  local abs="$1"
  case "$abs" in
    "$HUB_ROOT"/*) printf '%s\n' "${abs#"$HUB_ROOT"/}" ;;
    *) return 1 ;;
  esac
}

if [ -n "$ADOPT" ]; then
  row="$(awk -F'\t' -v want="$ADOPT" '$1 == want { print; exit }' "$STATE")"
  [ -n "$row" ] || { echo "skill_upgrade: '$ADOPT' is not an installed skill in $STATE" >&2; exit 1; }

  name="$(printf '%s' "$row" | cut -f1)"
  hub_md="$(printf '%s' "$row" | cut -f5)"
  row_state="$(printf '%s' "$row" | cut -f7)"
  installed_md="$SKILLS_DIR/$name/SKILL.md"

  [ "$row_state" = "stale" ] || { echo "skill_upgrade: '$name' is '$row_state', not 'stale' — nothing to adopt."; exit 0; }
  [ -f "$installed_md" ] || { echo "skill_upgrade: installed SKILL.md missing for '$name'" >&2; exit 1; }
  [ "$hub_md" != "-" ] || { echo "skill_upgrade: '$name' has no hub copy to overwrite" >&2; exit 1; }

  [ -n "$LANE_WORKTREE" ] || { echo "skill_upgrade: SKILL_HARNESS_WORKTREE is not configured — cannot adopt." >&2; exit 1; }
  [ -e "$LANE_WORKTREE/.git" ] || { echo "skill_upgrade: lane worktree missing at $LANE_WORKTREE — cannot adopt." >&2; exit 1; }

  rel="$(lane_relative_hub_path "$hub_md")" || {
    echo "skill_upgrade: hub path '$hub_md' is outside $HUB_ROOT — refusing to adopt." >&2
    exit 1
  }
  target="$LANE_WORKTREE/$rel"
  [ -f "$target" ] || { echo "skill_upgrade: '$rel' does not exist in the lane worktree — fetch/reset the lane first." >&2; exit 1; }

  if [ -n "$(git -C "$LANE_WORKTREE" status --porcelain --untracked-files=normal 2>/dev/null || true)" ]; then
    echo "skill_upgrade: lane worktree is dirty — commit or discard before adopting." >&2
    exit 1
  fi

  expected_branch="automation/skill-improvements/${LANE:-}"
  actual_branch="$(git -C "$LANE_WORKTREE" symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
  if [ -n "$LANE" ] && [ "$actual_branch" != "$expected_branch" ]; then
    echo "skill_upgrade: lane worktree is on '$actual_branch', expected '$expected_branch'." >&2
    exit 1
  fi

  cp "$installed_md" "$target"
  if [ -z "$(git -C "$LANE_WORKTREE" status --porcelain -- "$rel" 2>/dev/null || true)" ]; then
    echo "skill_upgrade: lane copy of '$name' already matches the installed version — nothing committed."
    exit 0
  fi

  git -C "$LANE_WORKTREE" add -- "$rel"
  git -C "$LANE_WORKTREE" commit -q -m "feat($name): adopt locally refined skill revision" -- "$rel"
  echo "skill_upgrade: queued $rel in lane ${LANE:-$actual_branch}."
  echo "Publish when ready:  bash \"$HERE/publish.sh\""
  exit 0
fi

mkdir -p "$CANDIDATES_DIR"

# awk, not `head`: under `set -e` + pipefail a `head -n` that closes the pipe early
# SIGPIPEs the upstream writer, and the resulting 141 kills this script. awk reads its
# input to the end, so truncation can never abort the run.
selected="$(stale_rows | awk -v n="${TOP_N:-5}" 'NR <= n')"
if [ -z "$selected" ]; then
  echo "skill_upgrade: no stale hub-backed skills — nothing to upgrade."
  echo "Signal: $STATE"
  exit 0
fi

written=0
skipped=0
while IFS="$(printf '\t')" read -r name usage_count mtime installed_sha hub_md hub_sha row_state; do
  [ -n "${name:-}" ] || continue
  installed_md="$SKILLS_DIR/$name/SKILL.md"
  candidate="$CANDIDATES_DIR/$name-upgrade-$today.md"

  if [ ! -f "$installed_md" ] || [ ! -f "$hub_md" ]; then
    echo "skill_upgrade: skipping '$name' — installed or hub SKILL.md missing."
    skipped=$((skipped + 1))
    continue
  fi

  if [ -f "$candidate" ] && [ "$FORCE" -eq 0 ]; then
    echo "skill_upgrade: candidate already staged for '$name' today — skipping ($candidate)."
    skipped=$((skipped + 1))
    continue
  fi

  diff_body="$(diff -u "$hub_md" "$installed_md" 2>/dev/null || true)"
  diff_lines="$(printf '%s\n' "$diff_body" | wc -l | tr -d ' ')"
  diff_note=""
  if [ "${diff_lines:-0}" -gt "$DIFF_MAX_LINES" ]; then
    diff_body="$(printf '%s\n' "$diff_body" | awk -v n="$DIFF_MAX_LINES" 'NR <= n')"
    diff_note="

(diff truncated at $DIFF_MAX_LINES of $diff_lines lines — run \`diff -u \"$hub_md\" \"$installed_md\"\` for the full change)"
  fi

  hub_rel="$(lane_relative_hub_path "$hub_md" 2>/dev/null || printf '%s' "$hub_md")"
  hub_commit="$(git -C "$HUB_ROOT" log -1 --format='%h %ad' --date=short -- "$hub_md" 2>/dev/null || true)"

  {
    echo "# Skill upgrade candidate: $name"
    echo
    echo "Staged by \`skill_upgrade.sh\` on $now. Private staging — redact machine paths and"
    echo "task-specific detail before any promotion."
    echo
    echo "## Decision"
    echo
    echo '- Outcome: `patch-existing`'
    echo "- Proposed target: \`$name\`"
    echo "- Reason this target owns the workflow: the installed copy has diverged from the"
    echo "  hub revision, so the hub skill is already the owner of this procedure."
    echo
    echo "## Signal"
    echo
    echo "| Field | Value |"
    echo "|---|---|"
    echo "| Usage events | $usage_count |"
    echo "| Installed SKILL.md | \`$installed_md\` |"
    echo "| Installed sha256 | \`$installed_sha\` |"
    echo "| Hub SKILL.md | \`$hub_rel\` |"
    echo "| Hub sha256 | \`$hub_sha\` |"
    echo "| Hub last commit | ${hub_commit:-unknown} |"
    echo
    echo "## Divergence (hub -> installed)"
    echo
    echo '```diff'
    printf '%s\n' "$diff_body"
    echo '```'
    [ -n "$diff_note" ] && printf '%s\n' "$diff_note"
    echo
    echo "## Agent task"
    echo
    echo "1. Read both revisions in full: the hub copy \`$hub_rel\` and the installed copy."
    echo "2. Classify every hunk above as one of: a genuine improvement worth promoting, a"
    echo "   machine-local or task-specific edit that must NOT reach the hub, or drift to revert."
    echo "3. Produce the merged SKILL.md text that keeps the improvements and drops the rest."
    echo "4. Fill the sections below, then present \`patch-existing\` for approval. A staged"
    echo "   candidate is not approval."
    echo
    echo "## Reusable trigger"
    echo
    echo "Describe the class of future tasks that should load this skill."
    echo
    echo "## Generalized lesson"
    echo
    echo "Summarize the reusable procedure without raw transcripts, personal context, or"
    echo "private project detail."
    echo
    echo "## Proposed change"
    echo
    echo "List the exact sections to add or update in \`$hub_rel\`."
    echo
    echo "## Pitfalls"
    echo
    echo "- Failure mode:"
    echo "- Prevention or recovery:"
    echo
    echo "## Verification"
    echo
    echo "- Structural checks: \`./scripts/validate.sh --full\` in the hub checkout"
    echo "- Behavioral checks:"
    echo "- Security checks:"
    echo
    echo "## Privacy and portability audit"
    echo
    echo "- [ ] No credentials, tokens, cookies, keys, or secret values."
    echo "- [ ] No personal memory, transcripts, sessions, user profiles, or chat identifiers."
    echo "- [ ] No client data, private project rules, internal URLs, or infrastructure details."
    echo "- [ ] No real identities, account data, or machine-specific paths."
    echo "- [ ] Examples use fictional placeholders."
    echo "- [ ] The procedure applies beyond the task that produced it."
    echo "- [ ] Existing skills were checked for ownership and duplication."
    echo "- [ ] Commands and tools are real and prerequisites are explicit."
    echo
    echo "## Promotion plan"
    echo
    echo "- Conventional Commit title: \`feat($name): <concise description>\`"
    echo "- Files to change: \`$hub_rel\`"
    echo "- Queue mechanically (adopts the installed text verbatim, review the diff first):"
    echo
    echo "      bash \"$HERE/skill_upgrade.sh\" --adopt $name"
    echo
    echo "- Or hand-merge in the lane worktree, then: \`bash \"$HERE/publish.sh\"\`"
    echo "- User approval: pending"
  } > "$candidate.tmp"
  mv -f "$candidate.tmp" "$candidate"
  chmod 600 "$candidate"
  echo "skill_upgrade: staged $candidate"
  written=$((written + 1))
done <<< "$selected"

echo
echo "skill_upgrade: $written candidate(s) staged, $skipped skipped."
if [ "$written" -gt 0 ]; then
  echo "Review with the skill-review skill, then approve promotion explicitly."
fi
exit 0
