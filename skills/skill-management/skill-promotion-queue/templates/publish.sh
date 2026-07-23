#!/usr/bin/env bash
# Thin wrapper around publish_queue.py. Runs from the lane worktree so the
# helper's Path.cwd() root is correct. Publication itself stays in the
# deterministic, fail-closed helper — this wrapper adds no Git side effects.
#
# Runtime-generic: repository, lane, and paths are read from the machine-local
# config.env beside this script.
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

if [ ! -e "$SKILL_HARNESS_WORKTREE/.git" ]; then
  echo "skill-harness: lane worktree missing at $SKILL_HARNESS_WORKTREE" >&2
  exit 1
fi

cd "$SKILL_HARNESS_WORKTREE"
exec python3 "$HERE/publish_queue.py" \
  --repository "$SKILL_HARNESS_REPO" \
  --lane "$SKILL_HARNESS_LANE" \
  "$@"
