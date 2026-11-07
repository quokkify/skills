#!/usr/bin/env bash
# Convert a raw screencast into an MR-friendly H.264 mp4 within size and duration limits.
# Usage: render.sh <raw.webm> <demo.mp4>
# Prints one JSON line per encoding attempt; the last line is the final result.
# Exit codes: 0 ok, 3 limits exceeded after all fallbacks, 64 usage error.
set -eu -o pipefail

MAX_SEC="${DEMO_MAX_SEC:-180}"
MAX_BYTES="${DEMO_MAX_BYTES:-15728640}"
FIT_W=1280
FIT_H=800

usage() {
  echo "$1" >&2
  echo "usage: render.sh <raw.webm> <demo.mp4>" >&2
  exit 64
}

[ "$#" -eq 2 ] || usage "expected 2 arguments, got $#"
in="$1"
out="$2"
[ -f "$in" ] || usage "input not found: $in"
case "$MAX_SEC$MAX_BYTES" in
  *[!0-9]*) usage "DEMO_MAX_SEC and DEMO_MAX_BYTES must be positive integers" ;;
esac

for bin in ffmpeg ffprobe; do
  command -v "$bin" >/dev/null 2>&1 || { echo "$bin is required" >&2; exit 1; }
done

even='scale=trunc(iw/2)*2:trunc(ih/2)*2'
fit="min(1\\,min(${FIT_W}/iw\\,${FIT_H}/ih))"
fit_scale="scale=trunc(iw*${fit}/2)*2:trunc(ih*${fit}/2)*2"

encode() { # <crf> <filter>
  ffmpeg -v error -y -i "$in" -an -c:v libx264 -preset medium -crf "$1" \
    -vf "$2" -pix_fmt yuv420p -movflags +faststart "$out"
}

attempt() { # <crf> <scaled> <filter>
  encode "$1" "$3"
  duration=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$out")
  bytes=$(wc -c < "$out" | tr -d ' ')
  printf '{"durationSec":%s,"bytes":%s,"crf":%s,"scaled":%s}\n' "$duration" "$bytes" "$1" "$2"
}

attempt 22 false "$even"
if awk -v d="$duration" -v m="$MAX_SEC" 'BEGIN { exit !(d > m) }'; then
  echo "duration ${duration}s exceeds limit ${MAX_SEC}s; shorten the scenario (re-encoding cannot fix it)" >&2
  exit 3
fi
[ "$bytes" -le "$MAX_BYTES" ] && exit 0

attempt 28 false "$even"
[ "$bytes" -le "$MAX_BYTES" ] && exit 0

attempt 28 true "$fit_scale"
[ "$bytes" -le "$MAX_BYTES" ] && exit 0

echo "size ${bytes} bytes exceeds limit ${MAX_BYTES} after all fallbacks (crf 22, crf 28, crf 28 scaled to fit ${FIT_W}x${FIT_H})" >&2
exit 3
