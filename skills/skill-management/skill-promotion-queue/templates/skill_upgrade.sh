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
# The two checksums cover the whole skill directory, not just SKILL.md, so a change
# confined to scripts/ or references/ still lands as `stale`. hub_path stays the path
# of the hub SKILL.md; the directory is its parent.

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
  installed_dir="$SKILLS_DIR/$name"

  [ "$row_state" = "stale" ] || { echo "skill_upgrade: '$name' is '$row_state', not 'stale' — nothing to adopt."; exit 0; }
  [ -f "$installed_md" ] || { echo "skill_upgrade: installed SKILL.md missing for '$name'" >&2; exit 1; }
  [ "$hub_md" != "-" ] || { echo "skill_upgrade: '$name' has no hub copy to overwrite" >&2; exit 1; }

  [ -n "$LANE_WORKTREE" ] || { echo "skill_upgrade: SKILL_HARNESS_WORKTREE is not configured — cannot adopt." >&2; exit 1; }
  [ -e "$LANE_WORKTREE/.git" ] || { echo "skill_upgrade: lane worktree missing at $LANE_WORKTREE — cannot adopt." >&2; exit 1; }

  rel="$(lane_relative_hub_path "$hub_md")" || {
    echo "skill_upgrade: hub path '$hub_md' is outside $HUB_ROOT — refusing to adopt." >&2
    exit 1
  }
  # hub_path arrives from a machine-local file that nothing in this repository
  # validates, and it ends up in `rm -rf`. Validate its shape before any use of it.
  # Reject traversal textually first: in a shell `case` pattern `*` also matches `/`,
  # so `skills/*/<name>` on its own would happily admit `skills/../../victim/<name>`.
  rel_dir="$(dirname "$rel")"
  case "/$rel_dir/" in
    */../*|*/./*|*//*)
      echo "skill_upgrade: hub path '$rel_dir' contains a relative component — refusing to adopt." >&2
      exit 1
      ;;
  esac
  case "$rel_dir" in
    skills/*/*/*)
      echo "skill_upgrade: hub path '$rel_dir' is nested deeper than skills/<category>/<skill>." >&2
      exit 1
      ;;
    skills/*/"$name") ;;
    *)
      echo "skill_upgrade: '$name' resolves to unexpected hub path '$rel_dir' — refusing to adopt." >&2
      exit 1
      ;;
  esac

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

  # Adopt the whole skill, not only its entry point: a divergence may be entirely
  # inside scripts/ or references/, and copying SKILL.md alone would commit a revision
  # that never reproduces the behaviour it documents.
  target_dir="$LANE_WORKTREE/$rel_dir"
  [ -d "$target_dir" ] || { echo "skill_upgrade: '$rel_dir' does not exist in the lane worktree — fetch/reset the lane first." >&2; exit 1; }

  # Re-anchor on the resolved paths, so a symlinked component cannot land the removal
  # outside the lane either. Pattern matching alone proves nothing about where a path
  # actually points.
  lane_real="$(cd "$LANE_WORKTREE" && pwd -P)" || exit 1
  target_real="$(cd "$target_dir" && pwd -P)" || exit 1
  case "$target_real" in
    "$lane_real"/skills/*/"$name") ;;
    *)
      echo "skill_upgrade: '$target_real' resolves outside the lane worktree — refusing to replace it." >&2
      exit 1
      ;;
  esac

  # Replace the directory so files deleted locally are also dropped from the hub copy.
  # The old copy is moved aside rather than deleted, so a failed extraction restores it
  # instead of leaving the lane with a half-written skill.
  backup_dir="$target_real.adopt-backup.$$"
  rm -rf "$backup_dir"
  mv "$target_real" "$backup_dir"
  # mkdir before the pipeline, never inside its left side: both sides start
  # concurrently, so the reader can reach `cd` before the writer has created the target.
  mkdir -p "$target_real"
  if ! ( cd "$installed_dir" \
         && tar cf - \
              --exclude='.DS_Store' --exclude='*/.DS_Store' \
              --exclude='__pycache__' --exclude='*/__pycache__' \
              --exclude='.pytest_cache' --exclude='*/.pytest_cache' \
              . ) | ( cd "$target_real" && tar xf - ); then
    rm -rf "$target_real"
    mv "$backup_dir" "$target_real"
    echo "skill_upgrade: copying '$name' into the lane failed — the lane copy was restored." >&2
    exit 1
  fi
  rm -rf "$backup_dir"

  git -C "$LANE_WORKTREE" add -A -- "$rel_dir"
  if [ -z "$(git -C "$LANE_WORKTREE" status --porcelain -- "$rel_dir" 2>/dev/null || true)" ]; then
    echo "skill_upgrade: lane copy of '$name' already matches the installed version — nothing committed."
    exit 0
  fi

  git -C "$LANE_WORKTREE" commit -q -m "feat($name): adopt locally refined skill revision" -- "$rel_dir"
  echo "skill_upgrade: queued $rel_dir in lane ${LANE:-$actual_branch}."
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
  installed_dir="$SKILLS_DIR/$name"
  hub_dir="$(dirname "$hub_md")"
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

  # Recursive: the divergence that made this row `stale` may live entirely in a support
  # file. `diff -ur` also reports files present on only one side, so an added or deleted
  # script is visible rather than silently absent from the candidate.
  diff_body="$(diff -ur -x '.DS_Store' -x '__pycache__' -x '.pytest_cache' \
    "$hub_dir" "$installed_dir" 2>/dev/null || true)"
  changed_files="$(printf '%s\n' "$diff_body" \
    | awk -v installed="$installed_dir/" -v hub="$hub_dir/" '
        function strip(path) {
          if (index(path, installed) == 1) return substr(path, length(installed) + 1)
          if (index(path, hub) == 1) return substr(path, length(hub) + 1)
          return path
        }
        /^Only in /  { print; next }
        /^diff -ur? / { print strip($NF) }
      ' \
    | awk 'NR <= 20')"
  diff_lines="$(printf '%s\n' "$diff_body" | wc -l | tr -d ' ')"
  diff_note=""
  if [ "${diff_lines:-0}" -gt "$DIFF_MAX_LINES" ]; then
    diff_body="$(printf '%s\n' "$diff_body" | awk -v n="$DIFF_MAX_LINES" 'NR <= n')"
    diff_note="

(diff truncated at $DIFF_MAX_LINES of $diff_lines lines — run \`diff -ur \"$hub_dir\" \"$installed_dir\"\` for the full change)"
  fi

  hub_rel="$(lane_relative_hub_path "$hub_md" 2>/dev/null || printf '%s' "$hub_md")"
  hub_rel_dir="$(dirname "$hub_rel")"
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
    echo "| Installed skill | \`$installed_dir\` |"
    echo "| Installed digest | \`$installed_sha\` |"
    echo "| Hub skill | \`$hub_rel_dir\` |"
    echo "| Hub digest | \`$hub_sha\` |"
    echo "| Files diverged | ${changed_files:+$(printf '%s' "$changed_files" | tr '\n' ' ')} |"
    echo "| Hub last commit | ${hub_commit:-unknown} |"
    echo
    echo "## Divergence (hub -> installed, whole skill directory)"
    echo
    echo '```diff'
    printf '%s\n' "$diff_body"
    echo '```'
    [ -n "$diff_note" ] && printf '%s\n' "$diff_note"
    echo
    echo "## Agent task"
    echo
    echo "1. Read both revisions in full: the hub copy \`$hub_rel_dir\` and the installed copy,"
    echo "   including every support file, not only SKILL.md."
    echo "2. Classify every hunk above as one of: a genuine improvement worth promoting, a"
    echo "   machine-local or task-specific edit that must NOT reach the hub, or drift to revert."
    echo "3. Produce the merged content for every diverged file, keeping the improvements and"
    echo "   dropping the rest. A change to a bundled script must stay consistent with the"
    echo "   SKILL.md that documents it."
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
