#!/usr/bin/env bash
# Publish a rendered demo to the orphan `demos` branch and link it from the merge request.
# Usage: publish.sh --repo <path> --mr <N> --sha <sha> --dir <dir> [--duration <sec>] [--dry-run --body-file <f>]
# <dir> must contain demo.mp4, scenario.mjs and scenario.json.
# --dry-run: no git writes, no push, no MR edit; prints the commit file list, video URL and new MR body.
# DEMO_SKIP_FORGE=1 (tests only): commit and push `demos`, but skip every gh/glab call.
# Exit codes: 0 ok, 5 push rejected, 64 usage error, other non-zero on tool failure.
set -eu -o pipefail

SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
SUMMARY="$SCRIPTS/summary.mjs"
BRANCH=demos

usage() {
  echo "$1" >&2
  echo "usage: publish.sh --repo <path> --mr <N> --sha <sha> --dir <dir> [--duration <sec>] [--dry-run --body-file <f>]" >&2
  exit 64
}

repo='' mr='' sha='' dir='' duration='' body_file='' dry_run=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo|--mr|--sha|--dir|--duration|--body-file)
      [ "$#" -ge 2 ] || usage "missing value for $1"
      case "$1" in
        --repo) repo="$2" ;;
        --mr) mr="$2" ;;
        --sha) sha="$2" ;;
        --dir) dir="$2" ;;
        --duration) duration="$2" ;;
        --body-file) body_file="$2" ;;
      esac
      shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    *) usage "unknown argument: $1" ;;
  esac
done

[ -n "$repo" ] && [ -n "$mr" ] && [ -n "$sha" ] && [ -n "$dir" ] || usage "--repo, --mr, --sha and --dir are required"
case "$mr" in ''|*[!0-9]*) usage "--mr must be a number: $mr" ;; esac
case "$sha" in *[!0-9a-f]*) usage "--sha must be a hex commit id: $sha" ;; esac
[ "${#sha}" -ge 12 ] || usage "--sha must have at least 12 hex characters: $sha"
git -C "$repo" rev-parse --git-dir >/dev/null 2>&1 || usage "not a git repository: $repo"
for f in demo.mp4 scenario.mjs scenario.json; do
  [ -f "$dir/$f" ] || usage "missing $f in $dir"
done
if [ "$dry_run" -eq 1 ]; then
  [ -n "$body_file" ] || usage "--dry-run requires --body-file"
  [ -f "$body_file" ] || usage "body file not found: $body_file"
elif [ -n "$body_file" ]; then
  usage "--body-file is only valid with --dry-run"
fi
if [ -z "$duration" ]; then
  duration=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$dir/demo.mp4")
fi
case "$duration" in ''|*[!0-9.]*) usage "invalid duration: $duration" ;; esac

sha12=$(printf '%s' "$sha" | cut -c1-12)
dest="demos/$mr/$sha12"

# remote.origin.url as configured (git remote get-url would expand insteadOf).
origin=$(git -C "$repo" config --get remote.origin.url) || usage "remote origin is not configured in $repo"
case "$origin" in
  *://*)
    rest="${origin#*://}"
    hostport="${rest%%/*}"
    project="${rest#*/}"
    host="${hostport#*@}"
    host="${host%%:*}" ;;
  *@*:*)
    rest="${origin#*@}"
    host="${rest%%:*}"
    project="${rest#*:}" ;;
  *) usage "unsupported origin URL: $origin" ;;
esac
project="${project%/}"
project="${project%.git}"
[ -n "$host" ] && [ -n "$project" ] || usage "cannot parse origin URL: $origin"

if [ "$host" = github.com ]; then
  forge=github
  video_url="https://github.com/$project/blob/$BRANCH/$dest/demo.mp4"
else
  forge=gitlab
  video_url="https://$host/$project/-/blob/$BRANCH/$dest/demo.mp4"
fi

tmp=$(mktemp -d)
wt="$tmp/worktree"
cleanup() {
  if [ -d "$wt" ]; then git -C "$repo" worktree remove --force "$wt" >/dev/null 2>&1 || true; fi
  rm -rf "$tmp"
}
trap cleanup EXIT

node "$SUMMARY" md --scenario-json "$dir/scenario.json" --sha "$sha12" --duration "$duration" --video-url "$video_url" > "$tmp/summary.md"
node "$SUMMARY" block --scenario-json "$dir/scenario.json" --sha "$sha12" --duration "$duration" --video-url "$video_url" > "$tmp/block.md"

if [ "$dry_run" -eq 1 ]; then
  echo "files:"
  for f in demo.mp4 scenario.json scenario.mjs summary.md; do echo "$dest/$f"; done
  echo "url: $video_url"
  echo "body:"
  node "$SUMMARY" replace --body-file "$body_file" --block-file "$tmp/block.md" 2>/dev/null
  exit 0
fi

if git -C "$repo" ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
  git -C "$repo" fetch -q origin "$BRANCH"
  if git -C "$repo" merge-base HEAD FETCH_HEAD >/dev/null 2>&1; then
    echo "origin/$BRANCH shares history with HEAD; it must be an orphan branch" >&2
    exit 1
  fi
  git -C "$repo" worktree add -q -B "$BRANCH" "$wt" FETCH_HEAD
else
  git -C "$repo" worktree add -q --detach "$wt"
  git -C "$wt" switch -q --orphan "$BRANCH"
fi

rm -rf "${wt:?}/$dest"
mkdir -p "$wt/$dest"
cp "$dir/demo.mp4" "$dir/scenario.json" "$dir/scenario.mjs" "$tmp/summary.md" "$wt/$dest/"
git -C "$wt" add -A -- "$dest"
if git -C "$wt" diff --cached --quiet; then
  echo "$dest is already up to date on $BRANCH; nothing to commit" >&2
else
  git -C "$wt" commit -q -m "docs(demo): MR !$mr at $sha12"
  if ! git -C "$wt" push -q origin "$BRANCH"; then
    echo "push of $BRANCH was rejected (another publish may have landed); re-run publish.sh, never force-push" >&2
    exit 5
  fi
fi

if [ "${DEMO_SKIP_FORGE:-}" != 1 ]; then
  if [ "$forge" = github ]; then
    (cd "$repo" && gh pr view "$mr" --json body -q .body) > "$tmp/body.md"
  else
    (cd "$repo" && glab mr view "$mr" -F json) |
      node -e 'let s="";process.stdin.on("data",(c)=>s+=c).on("end",()=>process.stdout.write(JSON.parse(s).description??""))' > "$tmp/body.md"
  fi
  node "$SUMMARY" replace --body-file "$tmp/body.md" --block-file "$tmp/block.md" > "$tmp/new-body.md" 2> "$tmp/replace.log"
  if [ "$forge" = github ]; then
    (cd "$repo" && gh pr edit "$mr" --body-file "$tmp/new-body.md") >/dev/null
  else
    (cd "$repo" && glab mr update "$mr" --description "$(cat "$tmp/new-body.md")") >/dev/null
  fi
  if grep -q '^replaced=true$' "$tmp/replace.log"; then
    note="Демо обновлено: $video_url"
    if [ "$forge" = github ]; then
      (cd "$repo" && gh pr comment "$mr" --body "$note") >/dev/null
    else
      (cd "$repo" && glab mr note "$mr" -m "$note") >/dev/null
    fi
  fi
fi

echo "$video_url"
