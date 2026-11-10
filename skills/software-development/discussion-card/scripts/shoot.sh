#!/bin/sh
# shoot.sh <page.html> <out-dir> [--slides]
# Headless-Chrome screenshots: desktop.png (1280 wide), dark.png (forced dark), phone.png (390 px).
# With --slides, also slide-<id>.png at 1920x1080 for every slide id listed in #card-config,
# loading <page.html>#<id> so the presenter view opens on that slide.
# Browser: $CHROME_BIN, then the macOS Chrome app, then google-chrome, chromium, chromium-browser.
# Writes only into <out-dir>. Exit 2 on bad arguments or when no browser is found, 1 when a shot fails.
# Provenance: adapted from the md-to-html-page skill in this hub; --slides is new.

SLIDES=0
if [ $# -eq 3 ] && [ "$3" = "--slides" ]; then
    SLIDES=1
elif [ $# -ne 2 ]; then
    echo "usage: shoot.sh <page.html> <out-dir> [--slides]" >&2
    exit 2
fi
PAGE=$1
OUTDIR=$2
[ -f "$PAGE" ] || { echo "shoot: page not found: $PAGE" >&2; exit 2; }

MAC_CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [ -n "${CHROME_BIN:-}" ]; then
    CHROME=$CHROME_BIN
elif [ -x "$MAC_CHROME" ]; then
    CHROME=$MAC_CHROME
else
    CHROME=
    for c in google-chrome chromium chromium-browser; do
        if command -v "$c" >/dev/null 2>&1; then CHROME=$(command -v "$c"); break; fi
    done
fi
[ -n "$CHROME" ] && [ -x "$CHROME" ] || { echo "shoot: no Chrome/Chromium found (set CHROME_BIN)" >&2; exit 2; }

mkdir -p "$OUTDIR" || exit 2
OUTDIR=$(cd "$OUTDIR" && pwd) || exit 2
PAGE_DIR=$(cd "$(dirname -- "$PAGE")" && pwd) || exit 2
URL=file://$PAGE_DIR/$(basename -- "$PAGE")
HEIGHT=${SHOOT_HEIGHT:-2000}
WRAP=$OUTDIR/.phone-wrapper.html
# shellcheck disable=SC2329 # invoked via trap
cleanup() { rm -f "$WRAP"; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

shot() { # name size url extra-flags...
    name=$1; size=$2; url=$3; shift 3
    rm -f "$OUTDIR/$name.png" || exit 1
    "$CHROME" --headless=new --disable-gpu --hide-scrollbars --allow-file-access-from-files \
        --window-size="$size" "$@" --screenshot="$OUTDIR/$name.png" "$url" >/dev/null 2>&1
    [ -s "$OUTDIR/$name.png" ] || { echo "shoot: failed to write $name.png" >&2; exit 1; }
}

# Blink: preferredColorScheme 0 = dark, 1 = light; set explicitly so the host appearance does not leak in.
shot desktop "1280,$HEIGHT" "$URL" --blink-settings=preferredColorScheme=1
shot dark "1280,$HEIGHT" "$URL" --blink-settings=preferredColorScheme=0

# Headless Chrome will not go below ~500 px wide, so the page sits in a 390 px iframe.
printf '<!doctype html><html><body style="margin:0;background:#888"><iframe src="%s" style="border:0;width:390px;height:%spx;display:block"></iframe></body></html>\n' \
    "$URL" "$HEIGHT" > "$WRAP"
shot phone "500,$HEIGHT" "file://$WRAP" --blink-settings=preferredColorScheme=1

if [ "$SLIDES" -eq 1 ]; then
    command -v python3 >/dev/null 2>&1 || { echo "shoot: python3 required for --slides" >&2; exit 2; }
    SLIDE_IDS=$(python3 -I -c '
import json, re, sys
m = re.search(r"<script type=\"application/json\" id=\"card-config\">(.*?)</script>", open(sys.argv[1], encoding="utf-8").read(), re.S)
if not m:
    sys.exit(2)
for s in json.loads(m.group(1)).get("slides", []):
    if re.fullmatch(r"[A-Za-z0-9_-]+", s.get("id", "")):
        print(s["id"])
' "$PAGE") || { echo "shoot: no #card-config in $PAGE" >&2; exit 2; }
    for id in $SLIDE_IDS; do
        shot "slide-$id" "1920,1080" "$URL#$id" --blink-settings=preferredColorScheme=1
    done
fi
