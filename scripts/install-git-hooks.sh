#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORCE=false

if [[ "${1:-}" == "--force" ]]; then
  FORCE=true
elif [[ "$#" -ne 0 ]]; then
  echo "Usage: $0 [--force]" >&2
  exit 2
fi

cd "$ROOT"
if [[ "$(git rev-parse --show-toplevel)" != "$ROOT" ]]; then
  echo "Run this script from the skills repository checkout." >&2
  exit 1
fi

CURRENT="$(git config --local --get core.hooksPath || true)"
if [[ -n "$CURRENT" && "$CURRENT" != ".githooks" && "$FORCE" != true ]]; then
  echo "Refusing to replace existing core.hooksPath '$CURRENT'. Re-run with --force after reviewing it." >&2
  exit 1
fi

git config --local core.hooksPath .githooks
printf 'Installed repository hooks via core.hooksPath=%s\n' "$(git config --local --get core.hooksPath)"
