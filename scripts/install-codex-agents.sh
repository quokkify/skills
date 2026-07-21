#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 1 ]; then
  echo "Usage: $0 /path/to/target-repo" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$1"
mkdir -p "$TARGET"
cp "$ROOT/adapters/codex/AGENTS.md" "$TARGET/AGENTS.md"
printf 'Installed Codex AGENTS.md into %s\n' "$TARGET"
