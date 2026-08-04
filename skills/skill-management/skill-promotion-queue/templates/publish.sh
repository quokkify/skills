#!/usr/bin/env bash
# Thin wrapper around publish_queue.py. Runs from the lane worktree so the
# helper's Path.cwd() root is correct. Publication itself stays in the
# deterministic, fail-closed helper — this wrapper adds no Git side effects.
#
# Runtime-generic: repository, lane, and paths are read from the machine-local
# config.env beside this script. `--target primary` (default) publishes to the
# primary hub; `--target secondary` publishes to the optional secondary hub and
# exits with an explanation when that slot is not configured.
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$HERE/config.env"

# Credential model:
#   Default = SSH remote (git@github.com) + gh keyring. No token needed here.
#   Optional = a protected external env file with GH_TOKEN for HTTPS pushes.
# The token is never stored in the repo, remote URL, prompt, hook, or logs.
if [ -f "$HERE/credentials.env" ]; then
  # shellcheck source=/dev/null
  source "$HERE/credentials.env"
fi

TARGET=primary
while [ "$#" -gt 0 ]; do
  case "$1" in
    --target)
      [ "$#" -ge 2 ] || { echo "skill-harness: --target needs primary or secondary" >&2; exit 2; }
      TARGET="$2"
      shift 2
      ;;
    --target=*)
      TARGET="${1#--target=}"
      shift
      ;;
    *) break ;;
  esac
done

case "$TARGET" in
  primary)
    REPO="$SKILL_HARNESS_REPO"
    LANE="$SKILL_HARNESS_LANE"
    WORKTREE="$SKILL_HARNESS_WORKTREE"
    ;;
  secondary)
    REPO="${SKILL_HARNESS_SECONDARY_REPO:-}"
    LANE="${SKILL_HARNESS_SECONDARY_LANE:-}"
    WORKTREE="${SKILL_HARNESS_SECONDARY_WORKTREE:-}"
    if [ -z "$REPO" ]; then
      echo "skill-harness: no secondary hub configured." >&2
      echo "Set SKILL_HARNESS_SECONDARY_REPO, SKILL_HARNESS_SECONDARY_LANE, and" >&2
      echo "SKILL_HARNESS_SECONDARY_WORKTREE in $HERE/config.env to enable it." >&2
      echo "The secondary worktree must be a checkout whose origin is that repository." >&2
      exit 1
    fi
    if [ -z "$LANE" ] || [ -z "$WORKTREE" ]; then
      echo "skill-harness: secondary hub '$REPO' is missing its lane or worktree." >&2
      echo "Both SKILL_HARNESS_SECONDARY_LANE and SKILL_HARNESS_SECONDARY_WORKTREE are required." >&2
      exit 1
    fi
    ;;
  *)
    echo "skill-harness: unknown target '$TARGET' (expected primary or secondary)" >&2
    exit 2
    ;;
esac

if [ ! -e "$WORKTREE/.git" ]; then
  echo "skill-harness: $TARGET lane worktree missing at $WORKTREE" >&2
  exit 1
fi

cd "$WORKTREE"
exec python3 "$HERE/publish_queue.py" \
  --repository "$REPO" \
  --lane "$LANE" \
  "$@"
