#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! GIT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || [[ "$GIT_ROOT" != "$ROOT" ]]; then
  echo "Sync must run from this repository checkout." >&2
  exit 1
fi

BRANCH="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
if [[ "$BRANCH" != "main" ]]; then
  echo "Sync requires the main branch; current branch is '${BRANCH:-detached}'." >&2
  exit 1
fi

if [[ -n "$(git status --porcelain --untracked-files=normal)" ]]; then
  echo "Sync requires a clean checkout with no tracked or untracked changes." >&2
  exit 1
fi

TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/skills-sync.XXXXXX")"
TRUSTED_VALIDATOR="$TEMP_ROOT/validate_repo.py"
CANDIDATE_TREE="$TEMP_ROOT/candidate"
cleanup() {
  rm -rf "$TEMP_ROOT"
}
trap cleanup EXIT
cp scripts/validate_repo.py "$TRUSTED_VALIDATOR"
python3 "$TRUSTED_VALIDATOR" "$ROOT"

CURRENT_OID="$(git rev-parse 'HEAD^{commit}')"
git fetch --quiet --no-tags origin refs/heads/main:refs/remotes/origin/main
REMOTE_OID="$(git rev-parse 'refs/remotes/origin/main^{commit}')"

if ! git merge-base --is-ancestor "$CURRENT_OID" "$REMOTE_OID"; then
  echo "Sync refused: local main is ahead of or diverged from origin/main." >&2
  exit 1
fi

if [[ "$CURRENT_OID" != "$REMOTE_OID" ]]; then
  mkdir "$CANDIDATE_TREE"
  git archive "$REMOTE_OID" | tar -x -C "$CANDIDATE_TREE"
  python3 "$TRUSTED_VALIDATOR" "$CANDIDATE_TREE"
  git -c core.hooksPath=/dev/null merge --ff-only "$REMOTE_OID"
fi

if ! python3 "$TRUSTED_VALIDATOR" "$ROOT"; then
  echo "Sync reached the fetched revision, but trusted post-update validation failed. Inspect the checkout before using it." >&2
  exit 1
fi

UPDATED_OID="$(git rev-parse 'HEAD^{commit}')"
cleanup
trap - EXIT
printf 'Shared skills are synchronized at %s.\n' "$UPDATED_OID"
echo "Hermes: start a new session to load the updated external skills."
