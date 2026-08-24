#!/usr/bin/env bash
set -uo pipefail

HOOK_LIB_DIR="${BASH_SOURCE[0]%/*}"
. "$HOOK_LIB_DIR/hook-lib.sh"
hook_enable_failsafe

hook_read_input || hook_allow

if [ -n "$HOOK_EVENT" ] && [ "$HOOK_EVENT" != "Stop" ]; then
  hook_allow
fi

stop_hook_active="$(hook_field stop_hook_active)"
case "$stop_hook_active" in
  true|1) hook_allow ;;
esac

WORKDIR="${HOOK_CWD:-$PWD}"
[ -d "$WORKDIR" ] || WORKDIR="$PWD"
GIT_ROOT="$(hook_git_root "$WORKDIR")"
[ -n "$GIT_ROOT" ] || hook_allow
hook_disabled completion-gate "$GIT_ROOT" && hook_allow

if ! reason="$("$HOOK_PY" - "$GIT_ROOT" <<'PY'
import os
import re
import subprocess
import sys

root = sys.argv[1]

try:
    diff = subprocess.check_output(
        ["git", "-C", root, "diff", "--no-ext-diff", "--unified=0",
         "--diff-filter=ACMR", "HEAD", "--"],
        stderr=subprocess.DEVNULL,
    ).decode("utf-8")
    untracked = subprocess.check_output(
        ["git", "-C", root, "ls-files", "--others", "--exclude-standard", "-z"],
        stderr=subprocess.DEVNULL,
    )
except (OSError, subprocess.CalledProcessError):
    sys.exit(1)

added = []
path = "(unknown file)"
for line in diff.splitlines():
    if line.startswith("+++ b/"):
        path = line[6:]
    elif line.startswith("+") and not line.startswith("+++"):
        added.append((path, line[1:]))

for raw_path in untracked.split(b"\0"):
    if not raw_path:
        continue
    relative = os.fsdecode(raw_path)
    if any(part in {"node_modules", ".venv", "__pycache__"} for part in relative.split(os.sep)):
        continue
    full_path = os.path.join(root, relative)
    try:
        content = open(full_path, "rb").read()
    except OSError:
        sys.exit(1)
    if b"\0" in content:
        continue
    added.extend((relative, line) for line in content.decode("utf-8", "replace").splitlines())

todo = re.compile(r"^\s*(?://|#|/\*|\*)\s*(?:TODO|FIXME)\b", re.IGNORECASE)
skip = re.compile(r"\b(?:test|it)\s*\.\s*(?:skip|only)\b")
python_stub = re.compile(r"^\s*(?:async\s+)?def\s+[A-Za-z_]\w*\s*\([^\n]*\)\s*(?:->[^:]+)?\s*:\s*(?:pass|\.\.\.)\s*(?:#.*)?$")
brace_stub = re.compile(r"^\s*(?:(?:public|private|protected|internal|static|async|final|virtual|override|export|default|function|fun|fn)\s+)*(?:[A-Za-z_$][\w$<>\[\],?]*\s+)?[A-Za-z_$][\w$]*\s*\([^\n{}]*\)\s*(?:=>\s*)?\{\s*\}\s*;?$")
arrow_stub = re.compile(r"^\s*(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=\s*(?:async\s*)?\([^\n{}]*\)\s*=>\s*\{\s*\}\s*;?$")

for index, (file_path, text) in enumerate(added):
    if todo.search(text):
        print(f"Added TODO/FIXME placeholder in {file_path}.")
        break
    if skip.search(text):
        print(f"Added skipped or exclusive test marker in {file_path}.")
        break
    if python_stub.search(text) or brace_stub.search(text) or arrow_stub.search(text):
        print(f"Added empty stub body in {file_path}.")
        break
    stripped = text.strip()
    previous_path, previous_text = added[index - 1] if index else ("", "")
    previous = previous_text.strip()
    if file_path == previous_path and stripped in {"pass", "..."} and re.search(r"^(?:async\s+)?def\s+[A-Za-z_]\w*\s*\([^\n]*\)\s*(?:->[^:]+)?\s*:\s*$", previous):
        print(f"Added empty stub body in {file_path}.")
        break
    if file_path == previous_path and stripped == "}" and re.search(r"\)\s*(?:=>\s*)?\{\s*$", previous):
        print(f"Added empty stub body in {file_path}.")
        break
PY
)"; then
  hook_allow
fi

[ -n "$reason" ] || hook_allow
hook_block_stop "$reason"
