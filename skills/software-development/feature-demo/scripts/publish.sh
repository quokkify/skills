#!/usr/bin/env bash
# Publish a rendered demo to the orphan `demos` branch and link it from the merge request.
# Usage: publish.sh --repo <path> --mr <N> --sha <sha> --dir <dir> [--duration <sec>] [--lang en|ru] [--note <text>] [--dry-run --body-file <f>]
# <dir> must contain demo.mp4, scenario.mjs and scenario.json.
# --dry-run: no git writes, no push, no MR edit; prints the commit file list, video URL and new MR body.
# DEMO_SKIP_FORGE=1 (tests only): commit and push `demos`, but skip every gh/glab call.
# Order: read the MR body, commit in a detached temporary worktree, push, edit the MR, comment.
# No local `demos` branch is created. GitHub is reached through the REST API only (`gh api`).
# Exit codes: 0 ok, 1 MR not found, origin unreachable or other tool failure, 5 push failed, 64 usage error.
set -Eeu -o pipefail
trap 'echo "publish.sh: command failed with exit $? at line $LINENO" >&2; exit 1' ERR

SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
SUMMARY="$SCRIPTS/summary.mjs"
BRANCH=demos

usage() {
  echo "$1" >&2
  echo "usage: publish.sh --repo <path> --mr <N> --sha <sha> --dir <dir> [--duration <sec>] [--lang en|ru] [--note <text>] [--dry-run --body-file <f>]" >&2
  exit 64
}

repo='' mr='' sha='' dir='' duration='' body_file='' dry_run=0 lang=en note=''
while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo|--mr|--sha|--dir|--duration|--body-file|--lang|--note)
      [ "$#" -ge 2 ] || usage "missing value for $1"
      case "$1" in
        --repo) repo="$2" ;;
        --mr) mr="$2" ;;
        --sha) sha="$2" ;;
        --dir) dir="$2" ;;
        --duration) duration="$2" ;;
        --body-file) body_file="$2" ;;
        --lang) lang="$2" ;;
        --note) note="$2" ;;
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
case "$lang" in
  en) updated_label="Demo updated" ;;
  ru) updated_label="Демо обновлено" ;;
  *) usage "--lang must be en or ru: $lang" ;;
esac
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
# The URL may embed credentials, so it is never printed.
origin=$(git -C "$repo" config --get remote.origin.url) || usage "remote origin is not configured in $repo"
bad_origin="unsupported origin URL in $repo (expected https://host/owner/repo or git@host:owner/repo)"
case "$origin" in
  *://*)
    rest="${origin#*://}"
    case "$rest" in */*) ;; *) usage "$bad_origin" ;; esac
    hostport="${rest%%/*}"
    project="${rest#*/}"
    host="${hostport##*@}"
    host="${host%%:*}" ;;
  *@*:*)
    rest="${origin#*@}"
    host="${rest%%:*}"
    project="${rest#*:}" ;;
  *) usage "$bad_origin" ;;
esac
project="${project%/}"
project="${project%.git}"
case "$host$project" in *@*|*:*) usage "$bad_origin" ;; esac
[ -n "$host" ] && [ -n "$project" ] || usage "$bad_origin"

if [ "$host" = github.com ]; then
  forge=github
  # The raw URL downloads the file in one click; the blob page offers only "View raw".
  video_url="https://github.com/$project/raw/$BRANCH/$dest/demo.mp4"
else
  forge=gitlab
  video_url="https://$host/$project/-/raw/$BRANCH/$dest/demo.mp4"
fi

tmp=$(mktemp -d)
wt="$tmp/worktree"
cleanup() {
  if [ -d "$wt" ]; then git -C "$repo" worktree remove --force "$wt" >/dev/null 2>&1 || true; fi
  rm -rf "$tmp"
}
trap cleanup EXIT

summary_args=(--scenario-json "$dir/scenario.json" --sha "$sha12" --duration "$duration" --video-url "$video_url" --lang "$lang")
[ -z "$note" ] || summary_args+=(--note "$note")
node "$SUMMARY" md "${summary_args[@]}" > "$tmp/summary.md"
node "$SUMMARY" block "${summary_args[@]}" > "$tmp/block.md"

if [ "$dry_run" -eq 1 ]; then
  echo "files:"
  for f in demo.mp4 scenario.json scenario.mjs summary.md; do echo "$dest/$f"; done
  echo "url: $video_url"
  echo "body:"
  node "$SUMMARY" replace --body-file "$body_file" --block-file "$tmp/block.md" 2>/dev/null
  exit 0
fi

skip_forge=0
[ "${DEMO_SKIP_FORGE:-}" != 1 ] || skip_forge=1

if [ "$skip_forge" -eq 0 ]; then
  read_ok=1
  if [ "$forge" = github ]; then
    gh api "repos/$project/pulls/$mr" --jq '.body // ""' > "$tmp/body.md" || read_ok=0
  else
    (cd "$repo" && glab mr view "$mr" -F json) > "$tmp/mr.json" || read_ok=0
    if [ "$read_ok" -eq 1 ]; then
      node -e 'process.stdout.write(JSON.parse(require("fs").readFileSync(process.argv[1], "utf8")).description ?? "")' "$tmp/mr.json" > "$tmp/body.md"
    fi
  fi
  if [ "$read_ok" -eq 0 ]; then
    echo "cannot read MR !$mr of $project; nothing was published" >&2
    exit 1
  fi
  node "$SUMMARY" replace --body-file "$tmp/body.md" --block-file "$tmp/block.md" > "$tmp/new-body.md" 2> "$tmp/replace.log"
fi

ls_rc=0
git -C "$repo" ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>"$tmp/ls-remote.err" || ls_rc=$?
if [ "$ls_rc" -ne 0 ] && [ "$ls_rc" -ne 2 ]; then
  cat "$tmp/ls-remote.err" >&2
  echo "cannot read origin of $repo (git ls-remote exit $ls_rc); nothing was published" >&2
  exit 1
fi
# The commit is built in a detached worktree, so no local `demos` branch is ever created.
base=''
if [ "$ls_rc" -eq 0 ]; then
  git -C "$repo" fetch -q origin "$BRANCH"
  base=$(git -C "$repo" rev-parse FETCH_HEAD)
  if git -C "$repo" merge-base HEAD "$base" >/dev/null 2>&1; then
    echo "origin/$BRANCH shares history with HEAD; it must be an orphan branch" >&2
    exit 1
  fi
  git -C "$repo" worktree add -q --detach "$wt" "$base"
else
  git -C "$repo" worktree add -q --detach --no-checkout "$wt"
  git -C "$wt" read-tree --empty
fi

rm -rf "${wt:?}/$dest"
mkdir -p "$wt/$dest"
cp "$dir/demo.mp4" "$dir/scenario.json" "$dir/scenario.mjs" "$tmp/summary.md" "$wt/$dest/"
git -C "$wt" add -A -- "$dest"
tree=$(git -C "$wt" write-tree)
message="docs(demo): MR !$mr at $sha12"
pushed=0
if [ -n "$base" ] && [ "$tree" = "$(git -C "$wt" rev-parse "$base^{tree}")" ]; then
  echo "$dest is already up to date on $BRANCH; nothing to commit" >&2
else
  if [ -n "$base" ]; then
    commit=$(git -C "$wt" commit-tree "$tree" -p "$base" -m "$message")
  else
    commit=$(git -C "$wt" commit-tree "$tree" -m "$message")
  fi
  push_rc=0
  git -C "$wt" push -q origin "$commit:refs/heads/$BRANCH" 2>"$tmp/push.err" || push_rc=$?
  if [ "$push_rc" -ne 0 ]; then
    cat "$tmp/push.err" >&2
    echo "push of $BRANCH to origin failed (git push exit $push_rc); see the git output above. Nothing was force-pushed; re-run publish.sh once the cause is fixed" >&2
    exit 5
  fi
  pushed=1
fi

if [ "$skip_forge" -eq 0 ]; then
  if [ "$forge" = github ]; then
    gh api -X PATCH "repos/$project/pulls/$mr" -F "body=@$tmp/new-body.md" >/dev/null
  else
    (cd "$repo" && glab mr update "$mr" --description "$(cat "$tmp/new-body.md")") >/dev/null
  fi
  if [ "$pushed" -eq 1 ] && grep -q '^replaced=true$' "$tmp/replace.log"; then
    comment="$updated_label: $video_url"
    if [ "$forge" = github ]; then
      printf '%s\n' "$comment" > "$tmp/comment.md"
      gh api -X POST "repos/$project/issues/$mr/comments" -F "body=@$tmp/comment.md" >/dev/null
    else
      (cd "$repo" && glab mr note "$mr" -m "$comment") >/dev/null
    fi
  fi
fi

echo "$video_url"
