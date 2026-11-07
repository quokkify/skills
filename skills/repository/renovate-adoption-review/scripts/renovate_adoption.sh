#!/bin/sh
# Helper for the renovate-adoption-review skill.
# Exit codes: 0 success, 2 usage error, 3 gh/jq/network failure.

script_dir=$(cd "$(dirname "$0")" && pwd)

usage() {
  cat >&2 <<USAGE
usage: renovate_adoption.sh inspect <pr> [--mode open|retro]
USAGE
  exit 2
}

fail() {
  echo "$1" >&2
  exit 3
}

require_tools() {
  if ! command -v gh >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then
    fail "requires gh and jq"
  fi
}

repo_root() {
  git rev-parse --show-toplevel 2>/dev/null || pwd
}

read_allowlist() {
  file="$(repo_root)/.github/renovate-adoption.json"
  if [ -f "$file" ]; then
    jq -ce 'if (.allow // []) | (type == "array" and all(type == "string")) then (.allow // []) else error("allow must be an array of strings") end' "$file" \
      || { echo "invalid allowlist: $file" >&2; exit 2; }
  else
    echo '[]'
  fi
}

cmd_inspect() {
  pr=""
  mode="open"
  while [ $# -gt 0 ]; do
    case "$1" in
      --mode)
        [ $# -ge 2 ] || usage
        mode="$2"
        shift 2
        ;;
      -*) usage ;;
      *)
        [ -z "$pr" ] || usage
        pr="$1"
        shift
        ;;
    esac
  done
  [ -n "$pr" ] || usage
  case "$mode" in open | retro) ;; *) usage ;; esac

  require_tools
  allow=$(read_allowlist) || exit $?
  if ! view=$(gh pr view "$pr" --json number,title,body,headRefName,headRefOid 2>&1); then
    echo "gh failed: gh pr view $pr" >&2
    echo "$view" >&2
    exit 3
  fi
  printf '%s' "$view" | jq -L "$script_dir" \
    --arg mode "$mode" --argjson allow "$allow" \
    'include "renovate_adoption"; inspect_item($mode; $allow)' \
    || fail "jq failed while inspecting PR $pr"
}

[ $# -ge 1 ] || usage
sub="$1"
shift
case "$sub" in
  inspect) cmd_inspect "$@" ;;
  *) usage ;;
esac
