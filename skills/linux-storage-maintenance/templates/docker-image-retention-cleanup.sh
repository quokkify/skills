#!/usr/bin/env bash
set -Eeuo pipefail

DAYS=7
DRY_RUN=0
STATE_DIR="${STATE_DIR:-/var/lib/docker-image-retention-cleanup}"
STATE_FILE="${STATE_FILE:-${STATE_DIR}/unused-images.tsv}"
LOCK_FILE="${LOCK_FILE:-${STATE_DIR}/lock}"
DOCKER_BIN="${DOCKER_BIN:-docker}"

MAX_DAYS=36500
usage() { printf 'Usage: %s [--days N (1-%d)] [--dry-run]\n' "$0" "$MAX_DAYS"; }

while (($#)); do
  case "$1" in
    --days)
      [[ $# -ge 2 && "$2" =~ ^[1-9][0-9]*$ ]] || { usage >&2; exit 2; }
      DAYS="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

if [[ ${#DAYS} -gt ${#MAX_DAYS} ]] ||
  { [[ ${#DAYS} -eq ${#MAX_DAYS} ]] && [[ "$DAYS" > "$MAX_DAYS" ]]; }; then
  echo "ERROR: --days must not exceed $MAX_DAYS" >&2
  exit 2
fi

command -v "$DOCKER_BIN" >/dev/null 2>&1 || { echo "ERROR: docker CLI not found" >&2; exit 1; }
command -v flock >/dev/null 2>&1 || { echo "ERROR: flock not found" >&2; exit 1; }
"$DOCKER_BIN" info >/dev/null 2>&1 || { echo "ERROR: Docker daemon is unavailable" >&2; exit 1; }

if ((DRY_RUN)); then
  [[ -d "$STATE_DIR" ]] || { echo "ERROR: dry-run requires existing state directory: $STATE_DIR" >&2; exit 1; }
else
  install -d -m 0750 "$STATE_DIR"
fi

exec 9>"$LOCK_FILE"
flock -n 9 || { echo "Another cleanup run is already active; exiting."; exit 0; }

if ((DRY_RUN)); then
  runtime_dir="${TMPDIR:-/tmp}"
  tmp_state=$(mktemp "${runtime_dir}/docker-image-retention-cleanup.XXXXXX")
else
  tmp_state=$(mktemp "${STATE_FILE}.tmp.XXXXXX")
fi

now=$(date +%s)
[[ "$now" =~ ^(0|[1-9][0-9]*)$ ]] || { echo "ERROR: system time is not a valid Unix timestamp" >&2; exit 1; }
retention_seconds=$((DAYS * 86400))
cleanup() {
  rm -f "$tmp_state"
}
trap cleanup EXIT

declare -A protected=()
if ! container_output=$("$DOCKER_BIN" ps -aq); then
  echo "ERROR: could not enumerate Docker containers; state was not changed" >&2
  exit 1
fi
container_ids=()
if [[ -n "$container_output" ]]; then
  mapfile -t container_ids <<< "$container_output"
fi
if ((${#container_ids[@]})); then
  if ! inspect_output=$("$DOCKER_BIN" inspect --format '{{.Image}}' "${container_ids[@]}"); then
    echo "ERROR: could not inspect Docker containers; state was not changed" >&2
    exit 1
  fi
  while IFS= read -r image_id; do
    [[ -n "$image_id" ]] && protected["$image_id"]=1
  done <<< "$inspect_output"
fi

declare -A first_unused=()
decimal_is_at_most() {
  local value="$1" limit="$2"
  [[ "$value" =~ ^(0|[1-9][0-9]*)$ ]] || return 1
  [[ ${#value} -lt ${#limit} ]] && return 0
  [[ ${#value} -gt ${#limit} ]] && return 1
  [[ "$value" == "$limit" || "$value" < "$limit" ]]
}
if [[ -f "$STATE_FILE" ]]; then
  while IFS=$'\t' read -r image_id first_seen; do
    [[ -z "$image_id" && -z "$first_seen" ]] && continue
    if [[ ! "$image_id" =~ ^sha256:[0-9a-f]{64}$ ]] ||
      ! decimal_is_at_most "$first_seen" "$now"; then
      echo "ERROR: malformed retention state; state was not changed" >&2
      exit 1
    fi
    first_unused["$image_id"]="$first_seen"
  done < "$STATE_FILE"
fi

if ! image_output=$("$DOCKER_BIN" image ls -aq --no-trunc); then
  echo "ERROR: could not enumerate Docker images; state was not changed" >&2
  exit 1
fi
image_ids=()
if [[ -n "$image_output" ]]; then
  mapfile -t image_ids < <(printf '%s\n' "$image_output" | sort -u)
fi
for image_id in "${image_ids[@]}"; do
  [[ "$image_id" =~ ^sha256:[0-9a-f]{64}$ ]] || {
    echo "ERROR: Docker returned an unexpected image identifier; state was not changed" >&2
    exit 1
  }
done
tracked=0 protected_count=0 deleted=0 failed=0 newly_unused=0

for image_id in "${image_ids[@]}"; do
  [[ -n "$image_id" ]] || continue
  if [[ -n "${protected[$image_id]:-}" ]]; then
    ((protected_count += 1))
    continue
  fi

  first_seen="${first_unused[$image_id]:-$now}"
  [[ -n "${first_unused[$image_id]:-}" ]] || ((newly_unused += 1))
  age=$((10#$now - 10#$first_seen))

  if ((age >= retention_seconds)); then
    if ((DRY_RUN)); then
      printf 'DRY-RUN: would delete %s (unused for %d days)\n' "$image_id" "$((age / 86400))"
      printf '%s\t%s\n' "$image_id" "$first_seen" >> "$tmp_state"
      ((tracked += 1))
    elif "$DOCKER_BIN" image rm "$image_id"; then
      printf 'Deleted %s after %d continuous unused days.\n' "$image_id" "$((age / 86400))"
      ((deleted += 1))
    else
      printf 'WARNING: could not delete %s; keeping it tracked for retry.\n' "$image_id" >&2
      printf '%s\t%s\n' "$image_id" "$first_seen" >> "$tmp_state"
      ((tracked += 1)); ((failed += 1))
    fi
  else
    printf '%s\t%s\n' "$image_id" "$first_seen" >> "$tmp_state"
    ((tracked += 1))
  fi
done

if ((DRY_RUN)); then
  echo "Dry run only; state was not changed."
else
  chmod 0640 "$tmp_state"
  mv -f "$tmp_state" "$STATE_FILE"
  trap - EXIT
fi

printf 'Summary: protected=%d tracked_unused=%d newly_unused=%d deleted=%d failed=%d retention_days=%d\n' \
  "$protected_count" "$tracked" "$newly_unused" "$deleted" "$failed" "$DAYS"
((failed == 0)) || exit 1
