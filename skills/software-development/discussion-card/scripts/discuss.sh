#!/bin/sh
# discuss.sh <in.md> --plan <card.yaml> [-o out.html] [--ui auto|ru|en] [--previous old.html] [--allow-drop]
# discuss.sh --python | --mermaid
#
# Builds an offline interactive HTML discussion card from a Markdown file and a plan.
# Exit codes: 0 pass, 1 check fail or build error, 2 bad arguments or plan schema, 3 environment.
# Env: DISCUSS_VENV overrides the venv directory; it is replaced only when it carries the
#      .discussion-card marker that this script writes into venvs it builds.
#      DISCUSS_MERMAID overrides the Mermaid JS path; it is still verified against mermaid.lock.
# Venv handling is adapted from the md-to-html-page launcher (copied, not imported).

HERE=$(cd "$(dirname -- "$0")" && pwd) || exit 2
REQ="$HERE/requirements.txt"
LOCK="$HERE/mermaid.lock"
MARKER=.discussion-card
ROOT=${XDG_CACHE_HOME:-$HOME/.cache}/discussion-card

usage() {
    echo "usage: discuss.sh <in.md> --plan <card.yaml> [-o out.html] [--ui auto|ru|en] [--previous old.html] [--allow-drop]" >&2
    echo "       discuss.sh --python | --mermaid" >&2
    exit 2
}

venv_ok() {
    [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -I -c 'import markdown_it, mdit_py_plugins, linkify_it, pygments, yaml' 2>/dev/null
}

ensure_venv() {
    command -v python3 >/dev/null 2>&1 || { echo "discuss: python3 not found (need >= 3.10)" >&2; exit 3; }
    python3 -I -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
        || { echo "discuss: python3 >= 3.10 required" >&2; exit 3; }
    if [ -n "${DISCUSS_VENV:-}" ]; then
        VENV=$DISCUSS_VENV
    else
        key=$(python3 -I -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest()[:12])' "$REQ") \
            || { echo "discuss: cannot read requirements.txt" >&2; exit 3; }
        VENV=$ROOT/$key
    fi
    case $VENV in /*) ;; *) VENV=$PWD/$VENV ;; esac
    if venv_ok; then
        return 0
    fi
    if [ -e "$VENV" ] && [ ! -f "$VENV/$MARKER" ]; then
        echo "discuss: $VENV exists and was not built by discuss (no $MARKER marker); refusing to replace it" >&2
        exit 3
    fi
    BUILD="$VENV.tmp.$$"
    mkdir -p "$(dirname -- "$VENV")" || exit 3
    rm -rf "$BUILD"
    if python3 -I -m venv "$BUILD" \
        && "$BUILD/bin/python" -I -m pip install --disable-pip-version-check -q -r "$REQ" \
        && : > "$BUILD/$MARKER"; then
        if venv_ok; then
            # a concurrent run finished first: keep its venv, drop ours
            rm -rf "$BUILD"; BUILD=
            return 0
        fi
        if [ -e "$VENV" ]; then
            [ -f "$VENV/$MARKER" ] || { echo "discuss: $VENV was not built by discuss; refusing to replace it" >&2; exit 3; }
            rm -rf "$VENV"
        fi
        # never mv into an existing directory
        if [ -e "$VENV" ] || ! mv "$BUILD" "$VENV"; then
            if venv_ok; then rm -rf "$BUILD"; BUILD=; return 0; fi
            exit 3
        fi
        BUILD=
    else
        echo "discuss: venv setup failed" >&2
        rm -rf "$BUILD"
        exit 3
    fi
}

lock_value() {
    sed -n "s/^$1=//p" "$LOCK" | head -n 1
}

sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | cut -d ' ' -f 1
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | cut -d ' ' -f 1
    else
        echo "discuss: neither sha256sum nor shasum found" >&2
        return 1
    fi
}

ensure_mermaid() {
    want=$(lock_value sha256)
    version=$(lock_value version)
    url=$(lock_value url)
    if [ -z "$want" ] || [ -z "$version" ] || [ -z "$url" ]; then
        echo "discuss: bad mermaid.lock" >&2
        exit 3
    fi
    if [ -n "${DISCUSS_MERMAID:-}" ]; then
        MERMAID=$DISCUSS_MERMAID
        [ -f "$MERMAID" ] || { echo "discuss: DISCUSS_MERMAID not found: $MERMAID" >&2; exit 3; }
    else
        MERMAID=$ROOT/mermaid-$version.js
        if [ ! -f "$MERMAID" ]; then
            command -v curl >/dev/null 2>&1 || { echo "discuss: curl not found; cannot fetch mermaid" >&2; exit 3; }
            mkdir -p "$ROOT" || exit 3
            MTMP=$MERMAID.tmp.$$
            curl -fsSL -o "$MTMP" "$url" || { echo "discuss: mermaid download failed: $url" >&2; exit 3; }
            got=$(sha256_of "$MTMP") || exit 3
            if [ "$got" != "$want" ]; then
                echo "discuss: mermaid sha256 mismatch (expected $want, got $got)" >&2
                exit 3
            fi
            mv "$MTMP" "$MERMAID" || exit 3
            MTMP=
        fi
    fi
    got=$(sha256_of "$MERMAID") || exit 3
    if [ "$got" != "$want" ]; then
        echo "discuss: mermaid sha256 mismatch for $MERMAID (expected $want, got $got)" >&2
        exit 3
    fi
}

BUILD=
MTMP=
# shellcheck disable=SC2329 # invoked via trap
cleanup() {
    [ -n "$BUILD" ] && rm -rf "$BUILD"
    [ -n "$MTMP" ] && rm -f "$MTMP"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

case ${1:-} in
    --python)
        [ $# -eq 1 ] || usage
        ensure_venv
        printf '%s\n' "$VENV/bin/python"
        exit 0 ;;
    --mermaid)
        [ $# -eq 1 ] || usage
        ensure_mermaid
        printf '%s\n' "$MERMAID"
        exit 0 ;;
esac

IN=''; PLAN=''; OUT=''; UI=auto; PREV=''; ALLOW_DROP=0
while [ $# -gt 0 ]; do
    case $1 in
        --plan) [ $# -ge 2 ] || usage; PLAN=$2; shift 2 ;;
        -o) [ $# -ge 2 ] || usage; OUT=$2; shift 2 ;;
        --ui) [ $# -ge 2 ] || usage; UI=$2; shift 2 ;;
        --previous) [ $# -ge 2 ] || usage; PREV=$2; shift 2 ;;
        --allow-drop) ALLOW_DROP=1; shift ;;
        -h|--help) usage ;;
        -*) echo "discuss: unknown option: $1" >&2; usage ;;
        *) [ -z "$IN" ] || usage; IN=$1; shift ;;
    esac
done
[ -n "$IN" ] || usage
[ -n "$PLAN" ] || { echo "discuss: --plan is required" >&2; usage; }
case $UI in auto|ru|en) ;; *) echo "discuss: bad --ui: $UI" >&2; exit 2 ;; esac
case $IN in *.md) ;; *) echo "discuss: input must be a .md file: $IN" >&2; exit 2 ;; esac
[ -f "$IN" ] || { echo "discuss: input not found: $IN" >&2; exit 2; }
[ -f "$PLAN" ] || { echo "discuss: plan not found: $PLAN" >&2; exit 2; }
[ -z "$PREV" ] || [ -f "$PREV" ] || { echo "discuss: previous page not found: $PREV" >&2; exit 2; }
: "$ALLOW_DROP" "$OUT"

echo "build: not implemented" >&2
exit 1
