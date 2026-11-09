#!/bin/sh
# mdpage.sh <in.md> [-o out.html] [--breaks auto|on|off] [--ui auto|ru|en]
# mdpage.sh --python
#
# Renders Markdown into one offline HTML page and gates it with check.py.
# Exit codes: 0 pass, 1 render error or check FAIL, 2 bad arguments, 3 venv setup failure.
# Env: MDPAGE_VENV overrides the venv directory.
#      MDPAGE_FORCE_FAIL=1 is a test hook: it corrupts the temp page before the check
#      so the FAIL path can be exercised. Not for normal use.

HERE=$(cd "$(dirname "$0")" && pwd) || exit 2
REQ="$HERE/requirements.txt"

usage() {
    echo "usage: mdpage.sh <in.md> [-o out.html] [--breaks auto|on|off] [--ui auto|ru|en]" >&2
    echo "       mdpage.sh --python" >&2
    exit 2
}

ensure_venv() {
    command -v python3 >/dev/null 2>&1 || { echo "mdpage: python3 not found (need >= 3.10)" >&2; exit 3; }
    python3 -I -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
        || { echo "mdpage: python3 >= 3.10 required" >&2; exit 3; }
    if [ -n "${MDPAGE_VENV:-}" ]; then
        VENV=$MDPAGE_VENV
    else
        key=$(python3 -I -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest()[:12])' "$REQ") \
            || { echo "mdpage: cannot read requirements.txt" >&2; exit 3; }
        VENV=${XDG_CACHE_HOME:-$HOME/.cache}/md-to-html-page/$key
    fi
    case $VENV in /*) ;; *) VENV=$PWD/$VENV ;; esac
    if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -I -c 'import markdown_it, mdit_py_plugins, linkify_it, pygments' 2>/dev/null; then
        return 0
    fi
    BUILD="$VENV.tmp.$$"
    mkdir -p "$(dirname "$VENV")" || exit 3
    rm -rf "$BUILD"
    if python3 -I -m venv "$BUILD" \
        && "$BUILD/bin/python" -I -m pip install --disable-pip-version-check -q -r "$REQ"; then
        rm -rf "$VENV"
        mv "$BUILD" "$VENV" || { rm -rf "$BUILD"; exit 3; }
        BUILD=
    else
        echo "mdpage: venv setup failed" >&2
        rm -rf "$BUILD"
        exit 3
    fi
}

TMP=
BUILD=
# shellcheck disable=SC2329 # invoked via trap
cleanup() {
    [ -n "$TMP" ] && rm -f "$TMP"
    [ -n "$BUILD" ] && rm -rf "$BUILD"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [ "${1:-}" = "--python" ]; then
    [ $# -eq 1 ] || usage
    ensure_venv
    printf '%s\n' "$VENV/bin/python"
    exit 0
fi

IN=''; OUT=''; BREAKS=auto; UI=auto
while [ $# -gt 0 ]; do
    case $1 in
        -o) [ $# -ge 2 ] || usage; OUT=$2; shift 2 ;;
        --breaks) [ $# -ge 2 ] || usage; BREAKS=$2; shift 2 ;;
        --ui) [ $# -ge 2 ] || usage; UI=$2; shift 2 ;;
        -h|--help) usage ;;
        -*) echo "mdpage: unknown option: $1" >&2; usage ;;
        *) [ -z "$IN" ] || usage; IN=$1; shift ;;
    esac
done
[ -n "$IN" ] || usage
case $BREAKS in auto|on|off) ;; *) echo "mdpage: bad --breaks: $BREAKS" >&2; exit 2 ;; esac
case $UI in auto|ru|en) ;; *) echo "mdpage: bad --ui: $UI" >&2; exit 2 ;; esac
case $IN in *.md) ;; *) echo "mdpage: input must be a .md file: $IN" >&2; exit 2 ;; esac
[ -f "$IN" ] || { echo "mdpage: input not found: $IN" >&2; exit 2; }
if [ -z "$OUT" ]; then
    base=$(basename "$IN" .md)
    OUT=$(dirname "$IN")/$base.html
fi
if [ "$OUT" = "$IN" ] || { [ -e "$OUT" ] && [ "$OUT" -ef "$IN" ]; }; then
    echo "mdpage: output would overwrite the input" >&2
    exit 2
fi
[ -d "$(dirname "$OUT")" ] || { echo "mdpage: output directory does not exist: $(dirname "$OUT")" >&2; exit 2; }

ensure_venv
PY=$VENV/bin/python

TMP=$OUT.tmp
if ! "$PY" -I "$HERE/render.py" "$IN" -o "$TMP" --ui "$UI" --breaks "$BREAKS"; then
    exit 1
fi

if [ -n "${MDPAGE_FORCE_FAIL:-}" ]; then
    printf '\nzzqxunlikelyword\n' >> "$TMP"
fi

if "$PY" -I "$HERE/check.py" "$IN" "$TMP"; then
    mv "$TMP" "$OUT" || exit 1
    TMP=
    exit 0
fi
exit 1
