#!/usr/bin/env bash
# Encode a raw webm screencast into an MR-friendly H.264 mp4.
# Usage: encode.sh <raw.webm> <out.mp4>
# Exit codes: 0 ok, 1 missing tool, 64 usage error.
set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: encode.sh <raw.webm> <out.mp4>" >&2
  exit 64
fi
in="$1"
out="$2"
[ -f "$in" ] || { echo "input not found: $in" >&2; exit 64; }

command -v ffmpeg >/dev/null 2>&1 || { echo "ffmpeg is required" >&2; exit 1; }

ffmpeg -v error -y -i "$in" -an -c:v libx264 -preset medium -crf 23 \
  -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" -pix_fmt yuv420p -movflags +faststart "$out"
