#!/bin/sh
# Helper for the renovate-adoption-review skill.
# Exit codes: 0 success, 2 usage error, 3 gh/jq/network failure.

script_dir=$(cd "$(dirname "$0")" && pwd)

usage() {
  cat >&2 <<USAGE
usage: renovate_adoption.sh inspect <pr> [--mode open|retro]
       renovate_adoption.sh sweep
       renovate_adoption.sh retro (--since <date|tag|sha> | --last <N>)
       renovate_adoption.sh owned-paths
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

cmd_sweep() {
  [ $# -eq 0 ] || usage
  require_tools
  allow=$(read_allowlist) || exit $?
  if ! list=$(gh pr list --author app/renovate --state open --limit 100 \
    --json number,title,body,headRefName,headRefOid 2>&1); then
    echo "gh failed: gh pr list --state open" >&2
    echo "$list" >&2
    exit 3
  fi
  printf '%s' "$list" | jq -L "$script_dir" --argjson allow "$allow" \
    'include "renovate_adoption"; map(inspect_item("open"; $allow))' \
    || fail "jq failed while sweeping open PRs"
}

cmd_retro() {
  since=""
  last=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --since)
        [ $# -ge 2 ] && [ -z "$since" ] || usage
        since="$2"
        shift 2
        ;;
      --last)
        [ $# -ge 2 ] && [ -z "$last" ] || usage
        last="$2"
        shift 2
        ;;
      *) usage ;;
    esac
  done
  if [ -n "$since" ] && [ -n "$last" ]; then usage; fi
  if [ -z "$since" ] && [ -z "$last" ]; then usage; fi

  limit=200
  if [ -n "$last" ]; then
    case "$last" in '' | *[!0-9]* | 0) usage ;; esac
    limit="$last"
  fi

  require_tools
  search=""
  if [ -n "$since" ]; then
    case "$since" in
      [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*) date="$since" ;;
      *)
        date=$(git log -1 --format=%cI "$since" -- 2>/dev/null) && [ -n "$date" ] \
          || { echo "unknown ref: $since" >&2; exit 2; }
        ;;
    esac
    search="merged:>=$date"
  fi

  allow=$(read_allowlist) || exit $?
  if [ -n "$search" ]; then
    list=$(gh pr list --author app/renovate --state merged --label dependencies \
      --search "$search" --limit "$limit" --json number,title,body,mergedAt 2>&1)
  else
    list=$(gh pr list --author app/renovate --state merged --label dependencies \
      --limit "$limit" --json number,title,body,mergedAt 2>&1)
  fi || {
    echo "gh failed: gh pr list --state merged" >&2
    echo "$list" >&2
    exit 3
  }
  printf '%s' "$list" | jq -L "$script_dir" --argjson allow "$allow" \
    'include "renovate_adoption"; retro_items($allow)' \
    || fail "jq failed while aggregating merged PRs"
}

cmd_owned_paths() {
  [ $# -eq 0 ] || usage
  require_tools
  root=$(repo_root)
  work=$(mktemp -d) || fail "mktemp failed"
  trap 'find "$work" -delete' EXIT
  : > "$work/results"
  for file in "$root"/.copier-answers*.yml; do
    [ -f "$file" ] || continue
    src=$(sed -n 's/^_src_path:[[:space:]]*//p' "$file" | head -n 1 | tr -d "\"'\r")
    commit=$(sed -n 's/^_commit:[[:space:]]*//p' "$file" | head -n 1 | tr -d "\"'\r")
    [ -n "$src" ] && [ -n "$commit" ] || continue
    case "$src" in
      https://github.com/*/*)
        slug=${src#https://github.com/}
        slug=${slug%.git}
        slug=${slug%/}
        ;;
      *)
        echo "skipping non-GitHub template source: $src" >&2
        continue
        ;;
    esac
    key=$(printf '%s@%s' "$slug" "$commit" | tr -c 'A-Za-z0-9._@-' '_')
    if [ ! -f "$work/$key.tree" ]; then
      if ! tree=$(gh api "repos/$slug/git/trees/$commit?recursive=1" 2>&1); then
        echo "gh failed: gh api repos/$slug/git/trees/$commit" >&2
        echo "$tree" >&2
        exit 3
      fi
      if ! copier=$(gh api "repos/$slug/contents/copier.yml?ref=$commit" \
        -H "Accept: application/vnd.github.raw" 2>&1); then
        echo "gh failed: gh api repos/$slug/contents/copier.yml" >&2
        echo "$copier" >&2
        exit 3
      fi
      if [ "$(printf '%s' "$tree" | jq -r '.truncated // false' 2>/dev/null)" = "true" ]; then
        echo "warning: template tree for $slug@$commit is truncated; owned paths may be incomplete" >&2
      fi
      printf '%s' "$tree" > "$work/$key.tree"
      printf '%s\n' "$copier" > "$work/$key.copier"
    fi
    res=$(jq -L "$script_dir" --rawfile copier "$work/$key.copier" --rawfile answers "$file" \
      'include "renovate_adoption"; owned_for($copier; $answers)' "$work/$key.tree") \
      || fail "jq failed while computing owned paths for $file"
    warn=$(printf '%s' "$res" | jq -r '.warn // empty')
    [ -z "$warn" ] || echo "warning: $warn in $file; skipping" >&2
    printf '%s' "$res" | jq -c '.paths' >> "$work/results"
  done

  jq -s 'add // [] | unique' "$work/results" || fail "jq failed while merging owned paths"
}

[ $# -ge 1 ] || usage
sub="$1"
shift
case "$sub" in
  inspect) cmd_inspect "$@" ;;
  sweep) cmd_sweep "$@" ;;
  retro) cmd_retro "$@" ;;
  owned-paths) cmd_owned_paths "$@" ;;
  *) usage ;;
esac
