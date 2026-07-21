#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:---fast}"

case "$MODE" in
  --fast|--ci|--full) ;;
  *)
    echo "Usage: $0 [--fast|--ci|--full]" >&2
    exit 2
    ;;
esac

cd "$ROOT"
python3 scripts/validate_repo.py

if [[ "$MODE" == "--fast" ]]; then
  exit 0
fi

python3 -m unittest discover -s tests -v

ZENSICAL_VERSION=""
if command -v zensical >/dev/null 2>&1; then
  ZENSICAL_VERSION="$(zensical --version 2>/dev/null | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -n 1 || true)"
fi

if [[ "$ZENSICAL_VERSION" == "0.0.24" ]]; then
  zensical build
elif command -v uvx >/dev/null 2>&1; then
  uvx --from zensical==0.0.24 zensical build
else
  echo "Full validation requires zensical 0.0.24 (or uvx to run it)." >&2
  exit 1
fi

echo "Documentation build: ok"

if [[ "$MODE" == "--full" ]]; then
  if [[ "$(git rev-parse --is-shallow-repository)" == "true" ]]; then
    echo "Full validation requires a complete Git history; this repository is shallow." >&2
    exit 1
  fi
  GITLEAKS_COMMAND="${GITLEAKS_BIN:-gitleaks}"
  if ! command -v "$GITLEAKS_COMMAND" >/dev/null 2>&1 && [[ ! -x "$GITLEAKS_COMMAND" ]]; then
    echo "Full validation requires gitleaks 8.30.1 or newer; set GITLEAKS_BIN if it is not on PATH." >&2
    exit 1
  fi
  GITLEAKS_VERSION="$("$GITLEAKS_COMMAND" version 2>/dev/null | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -n 1 || true)"
  if [[ -z "$GITLEAKS_VERSION" ]] || ! python3 - "$GITLEAKS_VERSION" <<'PY'
import sys
version = tuple(int(part) for part in sys.argv[1].split("."))
raise SystemExit(0 if version >= (8, 30, 1) else 1)
PY
  then
    echo "Full validation requires gitleaks 8.30.1 or newer; found '${GITLEAKS_VERSION:-unknown}'." >&2
    exit 1
  fi
  "$GITLEAKS_COMMAND" git --no-banner --log-opts="--all" .
fi

printf 'Validation mode %s: ok\n' "$MODE"
