#!/usr/bin/env bash
# Read-only health check for the skill-improvement publishing harness.
#
# Verifies installation, hook registration, tracked Git hooks, the active forge
# provider, the validation toolchain, the lane worktree, and the rolling draft
# queue. It only reads: no file is written, no ref is moved, no branch is
# fetched, and every provider command is a query.
#
# Exit status: 0 healthy, 1 warnings, 2 critical.
#
# Every path is derived from the environment and from config.env, so the script
# is portable across machines, accounts, and operating systems.
set -uo pipefail

# The harness is runtime-generic, but each agent runtime keeps its home in a different
# place. Resolve by evidence rather than by assuming one runtime: the harness lives
# wherever its config.env does. An explicit override always wins.
#
# A runtime is identified by which setting the path came from, never by the directory
# name: CLAUDE_CONFIG_DIR and CODEX_HOME exist precisely so the home can sit anywhere,
# so matching on a trailing ".claude" would misclassify every relocated install.
runtime_candidates() {
  printf 'claude\t%s\n' "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
  printf 'codex\t%s\n'  "${CODEX_HOME:-$HOME/.codex}"
  printf 'hermes\t%s\n' "${HERMES_HOME:-$HOME/.hermes}"
}

runtime_label() {
  case "$1" in
    claude) printf 'Claude Code' ;;
    codex)  printf 'Codex' ;;
    hermes) printf 'Hermes' ;;
    *)      printf 'Unknown runtime' ;;
  esac
}

# "<kind><tab><path>" per line, for the runtimes actually present on this machine.
present_runtimes="$(
  runtime_candidates | while IFS="$(printf '\t')" read -r kind path; do
    [ -n "$path" ] || continue
    [ -d "$path" ] || continue
    printf '%s\t%s\n' "$kind" "$path"
  done
)"

AGENT_HOME=""
harness_homes=""
harness_home_explicit=0
if [ -n "${SKILL_HARNESS_HOME:-}" ]; then
  AGENT_HOME="$SKILL_HARNESS_HOME"
  harness_homes="$SKILL_HARNESS_HOME"
  harness_home_explicit=1
else
  harness_homes="$(
    printf '%s\n' "$present_runtimes" | while IFS="$(printf '\t')" read -r kind path; do
      [ -n "${path:-}" ] || continue
      { [ -f "$path/skill-harness/config.env" ] || [ -d "$path/skill-harness" ]; } && printf '%s\n' "$path"
    done
  )"
  AGENT_HOME="$(printf '%s\n' "$harness_homes" | awk 'NF { print; exit }')"
  [ -n "$AGENT_HOME" ] || AGENT_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
fi

HARNESS_DIR="$AGENT_HOME/skill-harness"
CONFIG_FILE="$HARNESS_DIR/config.env"

OFFLINE=0
for argument in "$@"; do
  case "$argument" in
    --offline) OFFLINE=1 ;;
    -h|--help)
      echo "Usage: harness_doctor.sh [--offline]"
      echo
      echo "  --offline  Skip provider commands that reach the network."
      exit 0
      ;;
    *)
      echo "harness-doctor: unknown argument '$argument'" >&2
      exit 2
      ;;
  esac
done

OK="  [ok]  "
WARN="  [warn]"
FAIL="  [FAIL]"
INFO="  [info]"

status_level=0
warnings=""
next_steps=""

raise() { [ "$1" -gt "$status_level" ] && status_level="$1"; return 0; }
note_warning() { warnings="${warnings}  - $1"$'\n'; }

# Steps are deduplicated: several checks can converge on the same remedy.
note_step() {
  case $'\n'"$next_steps" in
    *$'\n'"  - $1"$'\n'*) return 0 ;;
  esac
  next_steps="${next_steps}  - $1"$'\n'
}

# Keep output shareable: never print the operator's home directory.
redact() { printf '%s' "${1//$HOME/\~}"; }

section() { printf '\n%s:\n' "$1"; }
report_ok() { printf '%s %s\n' "$OK" "$1"; }
report_info() { printf '%s %s\n' "$INFO" "$1"; }
report_warn() { printf '%s %s\n' "$WARN" "$1"; raise 1; note_warning "$1"; }
report_fail() { printf '%s %s\n' "$FAIL" "$1"; raise 2; note_warning "$1"; }

printf 'HARNESS HEALTH CHECK\n'

# ---------------------------------------------------------------- installation
section "Runtimes"

if [ -z "$present_runtimes" ]; then
  report_warn "No agent runtime home found under the usual locations"
  note_step "Set SKILL_HARNESS_HOME to the agent home that owns the harness."
else
  printf '%s\n' "$present_runtimes" | while IFS="$(printf '\t')" read -r kind home; do
    [ -n "${home:-}" ] || continue
    if [ -d "$home/skill-harness" ]; then
      printf '%s %s\n' "$OK" "$(runtime_label "$kind") at $(redact "$home") — hosts the harness"
    else
      printf '%s %s\n' "$INFO" "$(runtime_label "$kind") at $(redact "$home") — present, no harness"
    fi
  done
fi

harness_count="$(printf '%s\n' "$harness_homes" | awk 'NF' | wc -l | tr -d ' ')"
if [ "$harness_count" -gt 1 ]; then
  report_warn "The harness is installed under more than one runtime home; they share one lane and will fight over it"
  note_step "Keep one harness install per machine, or give each runtime its own lane in its own config.env."
fi

section "Installation"

harness_present=0
if [ -d "$HARNESS_DIR" ]; then
  harness_present=1
  report_ok "Harness directory: $(redact "$HARNESS_DIR")"
elif [ "$harness_home_explicit" -eq 1 ]; then
  report_fail "Harness directory missing: $(redact "$HARNESS_DIR")"
  note_step "Install the harness, or unset SKILL_HARNESS_HOME on a machine that is not a publishing lane."
elif [ -n "$present_runtimes" ]; then
  report_info "No publishing harness selected; agent runtimes remain available for ordinary skill use"
else
  report_warn "No agent runtime home found under the usual locations"
  note_step "Set SKILL_HARNESS_HOME to the agent home that owns the harness, if this is a publishing lane."
fi

# publish_queue.py is executed as `python3 publish_queue.py`, so it is a library
# file and is deliberately not required to carry the executable bit.
REQUIRED_SCRIPTS="completion_gate.sh publish.sh skill_cycle.sh"
REQUIRED_MODULES="publish_queue.py"

if [ "$harness_present" -eq 1 ]; then
  missing=""
  not_executable=""
  for script in $REQUIRED_SCRIPTS; do
    if [ ! -f "$HARNESS_DIR/$script" ]; then
      missing="$missing $script"
    elif [ ! -x "$HARNESS_DIR/$script" ]; then
      not_executable="$not_executable $script"
    fi
  done
  for module in $REQUIRED_MODULES; do
    [ -f "$HARNESS_DIR/$module" ] || missing="$missing $module"
  done

  if [ -n "$missing" ]; then
    report_fail "Missing harness files:$missing"
    note_step "Reinstall the harness files listed above from your harness source."
  elif [ -n "$not_executable" ]; then
    report_warn "Present but not executable:$not_executable"
    note_step "Restore the executable bit: chmod +x $(redact "$HARNESS_DIR")/*.sh"
  else
    report_ok "All required scripts present and executable"
  fi
fi

LANE=""
REPO=""
WORKTREE=""
MAIN_REPO=""
BASE_OVERRIDE=""
SECONDARY_REPO=""
SECONDARY_LANE=""
SECONDARY_WORKTREE=""

# config.env is shell, so sourcing it into this scope would let it overwrite the
# reporting state and the exit code. Read it in a subshell and import only the
# harness keys.
read_config() {
  ( set +u
    # shellcheck source=/dev/null
    . "$CONFIG_FILE" 2>/dev/null || exit 0
    for key in SKILL_HARNESS_REPO SKILL_HARNESS_LANE SKILL_HARNESS_WORKTREE \
               SKILL_HARNESS_MAIN SKILL_HARNESS_BASE SKILL_HARNESS_SECONDARY_REPO \
               SKILL_HARNESS_SECONDARY_LANE SKILL_HARNESS_SECONDARY_WORKTREE; do
      eval "value=\${$key:-}"
      # One key per line, newlines stripped so a hostile value cannot inject rows.
      printf '%s=%s\n' "$key" "$(printf '%s' "$value" | tr -d '\n\r')"
    done
  )
}

if [ -r "$CONFIG_FILE" ]; then
  while IFS='=' read -r key value; do
    case "$key" in
      SKILL_HARNESS_REPO) REPO="$value" ;;
      SKILL_HARNESS_LANE) LANE="$value" ;;
      SKILL_HARNESS_WORKTREE) WORKTREE="$value" ;;
      SKILL_HARNESS_MAIN) MAIN_REPO="$value" ;;
      SKILL_HARNESS_BASE) BASE_OVERRIDE="$value" ;;
      SKILL_HARNESS_SECONDARY_REPO) SECONDARY_REPO="$value" ;;
      SKILL_HARNESS_SECONDARY_LANE) SECONDARY_LANE="$value" ;;
      SKILL_HARNESS_SECONDARY_WORKTREE) SECONDARY_WORKTREE="$value" ;;
    esac
  done <<EOF
$(read_config)
EOF

  config_gaps=""
  [ -n "$REPO" ] || config_gaps="$config_gaps SKILL_HARNESS_REPO"
  [ -n "$LANE" ] || config_gaps="$config_gaps SKILL_HARNESS_LANE"
  [ -n "$WORKTREE" ] || config_gaps="$config_gaps SKILL_HARNESS_WORKTREE"

  if [ -n "$config_gaps" ]; then
    report_fail "config.env is missing required keys:$config_gaps"
    note_step "Set the missing keys in $(redact "$CONFIG_FILE")."
  else
    report_ok "config.env found (repo: $REPO, lane: $LANE)"
  fi

  if [ -n "$SECONDARY_REPO" ]; then
    if [ -n "$SECONDARY_LANE" ] && [ -n "$SECONDARY_WORKTREE" ]; then
      report_info "Secondary hub configured: $SECONDARY_REPO (lane: $SECONDARY_LANE)"
    else
      report_warn "Secondary hub '$SECONDARY_REPO' is missing its lane or worktree key"
      note_step "Set SKILL_HARNESS_SECONDARY_LANE and SKILL_HARNESS_SECONDARY_WORKTREE, or remove SKILL_HARNESS_SECONDARY_REPO."
    fi
  fi
elif [ "$harness_present" -eq 1 ]; then
  report_fail "config.env missing or unreadable: $(redact "$CONFIG_FILE")"
  note_step "Create config.env with SKILL_HARNESS_REPO, SKILL_HARNESS_LANE, SKILL_HARNESS_WORKTREE, and SKILL_HARNESS_MAIN."
fi

BRANCH=""
[ -n "$LANE" ] && BRANCH="automation/skill-improvements/$LANE"

# -------------------------------------------------------- completion gate wiring
# The harness scripts are runtime-generic; only the wiring that runs them is not.
# `local-agent-bootstrap.md` asks each machine for "a completion gate appropriate to
# this agent runtime", so check the mechanism each installed runtime actually has
# rather than reporting every runtime against Claude Code's settings.json.
section "Completion Gate"

stop_hook=0
session_hook=0
gate_wired=0

# Claude Code: Stop and SessionStart hooks in the merged settings files. A hook event
# holds a list of groups, each with its own hooks list, and unrelated tools commonly
# register under the same event, so every command in every group must be searched.
check_claude_runtime() {
  home="$1"
  found=()
  for candidate in "$home/settings.json" "$home/settings.local.json"; do
    [ -f "$candidate" ] && found+=("$candidate")
  done

  if [ "${#found[@]}" -eq 0 ]; then
    report_warn "Claude Code: no settings file under $(redact "$home"); the completion gate is not wired"
    note_step "Register completion_gate.sh (Stop) and skill_cycle.sh (SessionStart) in $(redact "$home")/settings.json."
    return 0
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    report_warn "Claude Code: python3 unavailable; cannot inspect hook registration"
    return 0
  fi

  for settings_file in "${found[@]}"; do
    scan="$(python3 - "$settings_file" <<'PY' 2>/dev/null
import json, sys

try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        settings = json.load(handle)
except Exception:
    print("ERROR")
    raise SystemExit(0)

def commands(event):
    for group in settings.get("hooks", {}).get(event, []) or []:
        if not isinstance(group, dict):
            continue
        for hook in group.get("hooks", []) or []:
            if isinstance(hook, dict) and isinstance(hook.get("command"), str):
                yield hook["command"]

print("stop" if any("completion_gate.sh" in c for c in commands("Stop")) else "-")
print("session" if any("skill_cycle.sh" in c for c in commands("SessionStart")) else "-")
PY
)"
    if [ "$scan" = "ERROR" ] || [ -z "$scan" ]; then
      report_fail "Claude Code: $(redact "$settings_file") is not valid JSON"
      note_step "Repair $(redact "$settings_file"); invalid JSON disables every hook, not only the harness ones."
      continue
    fi
    case "$scan" in *stop*) stop_hook=1 ;; esac
    case "$scan" in *session*) session_hook=1 ;; esac
  done

  if [ "$stop_hook" -eq 1 ]; then
    report_ok "Claude Code: Stop hook registered (completion_gate.sh)"
    gate_wired=1
  else
    report_warn "Claude Code: no Stop hook for completion_gate.sh; an unsettled queue will never hold completion"
    note_step "Add completion_gate.sh as a Stop hook in $(redact "$home")/settings.json."
  fi

  if [ "$session_hook" -eq 1 ]; then
    report_ok "Claude Code: SessionStart hook registered (skill_cycle.sh)"
  else
    report_warn "Claude Code: no SessionStart hook for skill_cycle.sh; the maintenance cycle will never run"
    note_step "Add skill_cycle.sh as an async SessionStart hook in $(redact "$home")/settings.json."
  fi
}

# Codex has no blocking stop hook. Its `notify` program runs on turn-ended, and its
# AGENTS.md carries the standing instruction. Either can carry the gate; report which,
# and never measure Codex against a settings.json it does not have.
check_codex_runtime() {
  home="$1"
  wired=0

  if [ -f "$home/config.toml" ] && grep -q 'completion_gate\.sh' "$home/config.toml" 2>/dev/null; then
    report_ok "Codex: completion_gate.sh wired through config.toml"
    wired=1
    gate_wired=1
  fi
  if [ -f "$home/AGENTS.md" ] && grep -qE 'completion_gate\.sh|skill-?harness|publish\.sh' "$home/AGENTS.md" 2>/dev/null; then
    report_ok "Codex: AGENTS.md instructs the agent to settle the queue"
    wired=1
    gate_wired=1
  fi

  if [ "$wired" -eq 0 ]; then
    report_warn "Codex: nothing wires the completion gate; a queued commit can go unnoticed on this runtime"
    note_step "Codex: run completion_gate.sh from the notify program in $(redact "$home")/config.toml, or state the settle-the-queue rule in $(redact "$home")/AGENTS.md."
  fi
}

# Hermes skills are discovered through skills.external_dirs in config.yaml. That is
# an ordinary read-only skill catalogue integration, not a publishing harness or a
# completion-gate contract. Only an explicitly installed harness is checked above;
# do not scan arbitrary Hermes YAML/TOML files or imply that Hermes completion is
# blocked by a Claude-compatible gate.
check_hermes_runtime() {
  home="$1"
  report_info "Hermes: skills.external_dirs provides skill discovery; no publishing gate is required"
}

# A `while read` loop would run in a subshell and lose gate_wired; feed it from a
# here-document so the counters survive.
while IFS="$(printf '\t')" read -r kind home; do
  [ -n "${home:-}" ] || continue
  case "$kind" in
    claude) check_claude_runtime "$home" ;;
    codex)  check_codex_runtime "$home" ;;
    hermes) check_hermes_runtime "$home" ;;
    *)      report_info "$(runtime_label "$kind") at $(redact "$home"): gate wiring not checked" ;;
  esac
done <<EOF
$present_runtimes
EOF

if [ -z "$present_runtimes" ]; then
  report_warn "No agent runtime home found; cannot check completion-gate wiring"
  note_step "Set SKILL_HARNESS_HOME to the agent home that owns the harness."
elif [ "$gate_wired" -eq 0 ]; then
  note_step "No runtime settles the queue automatically. Run publish.sh by hand, or wire the gate into one runtime."
fi

# ------------------------------------------------------------------------- git
section "Git Configuration"

check_hooks_path() {
  label="$1"
  root="$2"
  [ -n "$root" ] || return 0

  if [ ! -e "$root/.git" ]; then
    report_warn "$label is not a Git checkout: $(redact "$root")"
    note_step "$label: point its config.env key at a real checkout, or remove the stale key."
    return 0
  fi

  configured="$(git -C "$root" config --get core.hooksPath 2>/dev/null || true)"
  if [ -z "$configured" ]; then
    report_warn "$label has no core.hooksPath; tracked pre-commit and pre-push gates are inactive"
    note_step "$label: enable tracked hooks with the repository's hook installer, or set core.hooksPath in that checkout."
    return 0
  fi

  report_ok "$label core.hooksPath: $configured"

  case "$configured" in
    /*) hooks_dir="$configured" ;;
    *)  hooks_dir="$root/$configured" ;;
  esac

  if [ ! -d "$hooks_dir" ]; then
    report_fail "$label core.hooksPath points at a missing directory: $configured"
    note_step "$label: every commit and push fails until that directory exists."
    return 0
  fi

  for hook in pre-commit pre-push; do
    if [ ! -f "$hooks_dir/$hook" ]; then
      report_warn "$label is missing the $hook hook"
      note_step "$label: restore $configured/$hook from the repository."
    elif [ ! -x "$hooks_dir/$hook" ]; then
      report_warn "$label $hook hook is not executable; Git skips it without an error"
      note_step "$label: chmod +x $configured/$hook"
    else
      report_ok "$label $hook hook found and executable"
    fi
  done
}

if [ -z "$MAIN_REPO" ] && [ -z "$WORKTREE" ]; then
  report_info "No checkout configured; skipping Git hook checks"
else
  check_hooks_path "Main repo" "$MAIN_REPO"
  check_hooks_path "Lane worktree" "$WORKTREE"
fi

# -------------------------------------------------------------------- provider
section "Provider Detection"

gh_present=0
glab_present=0
gh_authed=0
glab_authed=0

command -v gh >/dev/null 2>&1 && gh_present=1
command -v glab >/dev/null 2>&1 && glab_present=1

if [ "$OFFLINE" -eq 1 ]; then
  report_info "Offline mode: provider authentication not verified"
  if [ "$gh_present" -eq 1 ]; then
    report_info "gh installed"
  else
    report_warn "gh is not installed; publish.sh and the draft-PR check cannot run"
    note_step "Install GitHub CLI, or treat this machine as local-only and disable the harness hooks."
  fi
  [ "$glab_present" -eq 1 ] && report_info "glab installed"
else
  if [ "$gh_present" -eq 1 ] && gh auth status >/dev/null 2>&1; then
    gh_authed=1
  fi
  if [ "$glab_present" -eq 1 ] && glab auth status >/dev/null 2>&1; then
    glab_authed=1
  fi

  if [ "$gh_authed" -eq 1 ]; then
    report_info "Active provider: GitHub (gh authenticated)"
  elif [ "$gh_present" -eq 1 ]; then
    report_warn "gh is installed but not authenticated; the queue cannot open or refresh its draft PR"
    note_step "Authenticate GitHub: gh auth login"
  else
    report_warn "gh is not installed; publish.sh and the draft-PR check cannot run"
    note_step "Install GitHub CLI, or treat this machine as local-only and disable the harness hooks."
  fi

  if [ "$glab_authed" -eq 1 ]; then
    report_info "GitLab CLI (glab) is installed and authenticated"
  elif [ "$glab_present" -eq 1 ]; then
    report_info "GitLab CLI (glab) is installed but not authenticated"
  fi
fi

# The harness is GitHub-only: publish_queue.py drives `gh`, and completion_gate.sh
# holds task completion on a GitHub draft PR. On a GitLab-primary machine those
# hooks block work that glab-based workflows are meant to finish.
if [ "$glab_authed" -eq 1 ] && [ "$gh_authed" -eq 0 ] && [ "$gate_wired" -eq 1 ]; then
  report_warn "GitLab detected but the completion gate is wired for a GitHub-only harness; it will conflict with glab workflows"
  note_step "Disable the harness here: unwire the completion gate from whichever runtime registers it (see the Completion Gate section above)."
  note_step "Alternatively rename $(redact "$CONFIG_FILE") — without it the gate becomes an unconditional no-op on every runtime."
elif [ "$glab_authed" -eq 1 ] && [ "$gh_authed" -eq 1 ]; then
  report_info "Both providers are authenticated; the harness will use GitHub for the lane queue"
fi

# ------------------------------------------------------- validation toolchain
# The tracked pre-push hook runs the repository's full validation, and the
# publisher runs its CI equivalent. Both are fail-closed, so a missing tool
# blocks every push and every publication from that checkout.
if [ -n "$WORKTREE" ] && [ -e "$WORKTREE/.git" ]; then
  section "Validation Toolchain"

  if [ -f "$WORKTREE/scripts/validate.sh" ]; then
    report_ok "scripts/validate.sh present in the lane worktree"
  else
    report_fail "scripts/validate.sh missing; publication aborts after the push preconditions"
    note_step "The lane worktree must be a checkout of the hub repository, which ships scripts/validate.sh."
  fi

  if command -v python3 >/dev/null 2>&1; then
    report_ok "python3 available (structural validation)"
  else
    report_fail "python3 missing; structural validation cannot run"
    note_step "Install python3; the harness and the repository validator both require it."
  fi

  if command -v zensical >/dev/null 2>&1 || command -v uvx >/dev/null 2>&1; then
    report_ok "Documentation build available (zensical or uvx)"
  else
    report_warn "Neither zensical nor uvx is installed; the documentation build step will fail"
    note_step "Install uvx (or the pinned zensical) so validate.sh can build the docs."
  fi

  if command -v gitleaks >/dev/null 2>&1 || [ -x "${GITLEAKS_BIN:-}" ]; then
    report_ok "gitleaks available (secret scan)"
  else
    report_warn "gitleaks is not installed; the pre-push full validation will refuse to run"
    note_step "Install gitleaks, or set GITLEAKS_BIN to its path."
  fi
fi

# --------------------------------------------------------------- lane worktree
section "Lane Status"

lane_ready=0
ahead_known=0
ahead=0

if [ -z "$WORKTREE" ] || [ -z "$LANE" ]; then
  report_info "No lane configured; skipping lane checks"
elif [ ! -e "$WORKTREE/.git" ]; then
  report_fail "Lane worktree missing: $(redact "$WORKTREE")"
  note_step "Recreate it: git -C <main checkout> worktree add <lane path> -b $BRANCH origin/<default branch>"
else
  report_ok "Worktree at: $(redact "$WORKTREE")"

  current_branch="$(git -C "$WORKTREE" symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
  if [ -z "$current_branch" ]; then
    report_fail "Lane worktree has a detached HEAD; publication refuses to run"
    note_step "Check out the lane branch in the worktree: $BRANCH"
  elif [ "$current_branch" != "$BRANCH" ]; then
    report_fail "Lane worktree is on '$current_branch', expected '$BRANCH'"
    note_step "Check out the lane branch in the worktree: $BRANCH"
  else
    report_ok "On correct branch: $BRANCH"
    lane_ready=1
  fi

  # A dirty tree is the most common publication refusal and does not depend on
  # resolving the base branch, so check it first and unconditionally.
  dirty="$(git -C "$WORKTREE" status --porcelain --untracked-files=normal 2>/dev/null || true)"
  if [ -n "$dirty" ]; then
    dirty_count="$(printf '%s\n' "$dirty" | wc -l | tr -d ' ')"
    report_warn "Working tree has $dirty_count uncommitted path(s); publication requires a clean worktree"
    note_step "Commit the lane changes, then run publish.sh — or discard them if this work is local-only."
  else
    report_ok "Working tree clean"
  fi

  # The publisher requires origin to be exactly the configured GitHub repository.
  if [ -n "$REPO" ]; then
    origin_url="$(git -C "$WORKTREE" remote get-url origin 2>/dev/null || true)"
    if [ -z "$origin_url" ]; then
      report_fail "Lane worktree has no 'origin' remote; publication cannot verify the target repository"
      note_step "Add an origin remote pointing at $REPO."
    else
      normalized="$(printf '%s' "$origin_url" \
        | sed -e 's|^[A-Za-z0-9+.-]*://||' -e 's|^[^@/]*@||' -e 's|^github\.com[:/]||' -e 's|\.git$||' -e 's|^/*||' -e 's|/*$||')"
      if [ "$(printf '%s' "$normalized" | tr 'A-Z' 'a-z')" = "$(printf '%s' "$REPO" | tr 'A-Z' 'a-z')" ]; then
        report_ok "Origin matches the configured repository: $REPO"
      else
        report_fail "Origin '$origin_url' does not match SKILL_HARNESS_REPO '$REPO'; publication refuses to run"
        note_step "Point the lane worktree's origin at $REPO, or correct SKILL_HARNESS_REPO in config.env."
      fi
    fi
  fi

  # Resolve the base branch the way publication will. The publisher asks GitHub
  # for the live default branch and ignores SKILL_HARNESS_BASE; only the
  # completion gate honours that override. Report the difference rather than
  # silently picking one.
  base_branch=""
  base_source=""
  if [ "$gh_authed" -eq 1 ] && [ -n "$REPO" ]; then
    base_branch="$(gh repo view "$REPO" --json defaultBranchRef --jq '.defaultBranchRef.name' 2>/dev/null || true)"
    [ -n "$base_branch" ] && base_source="GitHub default branch"
  fi
  if [ -z "$base_branch" ]; then
    base_branch="$(git -C "$WORKTREE" symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||' || true)"
    [ -n "$base_branch" ] && base_source="local origin/HEAD"
  fi
  if [ -z "$base_branch" ]; then
    base_branch="main"
    base_source="fallback"
  fi
  base_ref="origin/$base_branch"

  if [ -n "$BASE_OVERRIDE" ] && [ "$BASE_OVERRIDE" != "$base_ref" ]; then
    report_warn "SKILL_HARNESS_BASE is '$BASE_OVERRIDE' but publication uses '$base_ref' ($base_source); the completion gate and the publisher disagree"
    note_step "Align SKILL_HARNESS_BASE with the repository default branch, or remove the override."
  fi

  if ! git -C "$WORKTREE" rev-parse --verify --quiet "$base_ref" >/dev/null 2>&1; then
    report_warn "Base ref '$base_ref' is unknown locally; ahead/behind and queued-path checks are unavailable"
    note_step "Refresh the lane's remote refs before trusting the queue state (git fetch origin)."
  else
    ahead="$(git -C "$WORKTREE" rev-list --count "$base_ref..HEAD" 2>/dev/null || echo 0)"
    behind="$(git -C "$WORKTREE" rev-list --count "HEAD..$base_ref" 2>/dev/null || echo 0)"
    case "$ahead" in ''|*[!0-9]*) ahead=0 ;; esac
    case "$behind" in ''|*[!0-9]*) behind=0 ;; esac
    ahead_known=1

    if [ "$ahead" -eq 0 ]; then
      report_info "Queue is empty (no commits ahead of $base_ref)"
    else
      # --verify --quiet is required: a bare rev-parse echoes an unresolvable
      # name back on stdout, so a deleted remote branch would read as a hash.
      remote_head="$(git -C "$WORKTREE" rev-parse --verify --quiet "refs/remotes/origin/$BRANCH" 2>/dev/null || true)"
      [ -n "$remote_head" ] || remote_head=NONE
      local_head="$(git -C "$WORKTREE" rev-parse --verify --quiet HEAD 2>/dev/null || echo unknown)"
      if [ "$remote_head" = "NONE" ]; then
        report_warn "Queue has $ahead commit(s) ahead of $base_ref and the lane branch has never been pushed"
        note_step "Publish the queue: bash \"$(redact "$HARNESS_DIR")/publish.sh\""
      elif [ "$remote_head" = "$local_head" ]; then
        report_ok "Queue published: $ahead commit(s) ahead of $base_ref, remote in sync"
      elif git -C "$WORKTREE" merge-base --is-ancestor "origin/$BRANCH" HEAD >/dev/null 2>&1; then
        report_warn "Queue has $ahead commit(s) ahead of $base_ref that are not published"
        note_step "Publish the queue: bash \"$(redact "$HARNESS_DIR")/publish.sh\""
      else
        # This check reads a remote-tracking ref. A read-only doctor must not
        # fetch, so the ref may be stale: if the remote branch was deleted, the
        # publisher's own fetch finds nothing and publication proceeds normally.
        # Report the divergence without claiming a refusal that may not happen.
        report_warn "origin/$BRANCH is not an ancestor of local HEAD; if that remote branch still exists, publication refuses to force-push"
        note_step "Refresh remote refs (git fetch --prune origin) and re-run. If origin/$BRANCH is still a real, diverged branch, reconcile it by hand — publish.sh cannot resolve that."
      fi
    fi

    if [ "$behind" -gt 0 ]; then
      report_info "Lane is $behind commit(s) behind $base_ref (rebase before queueing new work)"
    fi

    # The publisher accepts only these top-level paths, and rejects any path
    # containing a forbidden component at any depth.
    if [ "$ahead" -gt 0 ]; then
      queued_paths="$(git -C "$WORKTREE" diff --name-only --diff-filter=ACMRTUXB "$base_ref...HEAD" 2>/dev/null || true)"
      disallowed="$(printf '%s\n' "$queued_paths" | awk -F/ '
        NF == 0 || $0 == "" { next }
        {
          bad = 0
          for (i = 1; i <= NF; i++) {
            part = tolower($i)
            if (part == "" || part == "." || part == ".." ||
                part == ".env" || part == ".git" || part == ".secrets" ||
                part == "auth.json" || part == "credentials.json" ||
                part == "memory.md" || part == "sessions" ||
                part == "transcripts" || part == "user.md") { bad = 1 }
          }
          if (NF == 1) {
            if ($1 != "README.md" && $1 != "SECURITY.md" && $1 != "THIRD_PARTY_NOTICES.md") bad = 1
          } else if ($1 != "skills" && $1 != "docs" && $1 != "tests" && $1 != "scripts" && $1 != "adapters") {
            bad = 1
          }
          if (bad) print
        }' || true)"
      if [ -n "$disallowed" ]; then
        report_fail "Queue contains paths the publisher refuses: $(printf '%s' "$disallowed" | tr '\n' ' ')"
        note_step "Remove those paths from the lane; the queue accepts only skills/, docs/, tests/, scripts/, adapters/ and the three allowed root files, and no path may contain a private component."
      else
        report_ok "Queued paths are inside the publishable set"
      fi
    fi
  fi
fi

# ------------------------------------------------------------- forge-side view
if [ "$gh_authed" -eq 1 ] && [ -n "$REPO" ]; then
  section "GitHub Status"
  report_ok "Authenticated to GitHub"

  if gh repo view "$REPO" --json name >/dev/null 2>&1; then
    report_ok "Repository accessible: $REPO"

    if [ -n "$BRANCH" ] && [ "$lane_ready" -eq 1 ]; then
      # The publisher inspects every open PR for the head, not only drafts: two
      # open PRs, or one that left draft, are both hard refusals.
      pr_json="$(gh pr list --repo "$REPO" --state open --head "$BRANCH" \
        --json number,isDraft,baseRefName 2>/dev/null || true)"
      # The JSON travels as an argument: a heredoc already owns stdin here.
      pr_summary="$(python3 - "${base_branch:-}" "$pr_json" <<'PY' 2>/dev/null || echo error
import json, sys

expected_base = sys.argv[1] if len(sys.argv) > 1 else ""
raw = (sys.argv[2] if len(sys.argv) > 2 else "").strip()
if not raw:
    print("error")
    raise SystemExit(0)
try:
    entries = json.loads(raw)
except Exception:
    print("error")
    raise SystemExit(0)
if not isinstance(entries, list):
    print("error")
    raise SystemExit(0)
if not entries:
    print("none")
    raise SystemExit(0)
if len(entries) > 1:
    print("many %d" % len(entries))
    raise SystemExit(0)
entry = entries[0] if isinstance(entries[0], dict) else {}
number = entry.get("number", "?")
base = entry.get("baseRefName", "")
if not entry.get("isDraft"):
    print("ready %s" % number)
elif expected_base and base and base != expected_base:
    print("base %s %s" % (number, base))
else:
    print("draft %s" % number)
PY
)"
      case "$pr_summary" in
        none)
          if [ "$ahead_known" -eq 1 ] && [ "$ahead" -gt 0 ]; then
            report_warn "No open PR for $BRANCH while the queue holds $ahead commit(s)"
            note_step "Publish the queue: bash \"$(redact "$HARNESS_DIR")/publish.sh\""
          elif [ "$ahead_known" -eq 1 ]; then
            report_info "No open PR for $BRANCH (expected while the queue is empty)"
          else
            report_info "No open PR for $BRANCH (queue depth unknown)"
          fi
          ;;
        draft\ *)
          report_ok "Draft PR #${pr_summary#draft } active for $BRANCH"
          ;;
        ready\ *)
          report_fail "PR #${pr_summary#ready } for $BRANCH is no longer a draft; publication refuses to update it"
          note_step "Return that PR to draft, or merge/close it so the next publication opens a fresh queue PR."
          ;;
        base\ *)
          rest="${pr_summary#base }"
          report_fail "PR #${rest%% *} targets '${rest#* }', not the default branch; publication refuses to update it"
          note_step "Retarget or close that PR so the queue PR points at the repository default branch."
          ;;
        many\ *)
          report_fail "${pr_summary#many } open PRs for $BRANCH; the publisher requires exactly one"
          note_step "Close the extra pull requests for $BRANCH, leaving a single draft."
          ;;
        *)
          report_warn "Could not read pull requests for $REPO"
          ;;
      esac
    fi
  else
    report_fail "Repository not accessible: $REPO"
    note_step "Check the repository name in config.env and the scopes on your gh token."
  fi
elif [ "$glab_authed" -eq 1 ] && [ "$gh_authed" -eq 0 ]; then
  section "GitLab Status"
  report_ok "Authenticated to GitLab"
  report_info "The harness has no GitLab publication path; lane queueing is unavailable on this machine"
  if [ -n "$WORKTREE" ] && [ -e "$WORKTREE/.git" ]; then
    if ( cd "$WORKTREE" && glab mr list --per-page 1 >/dev/null 2>&1 ); then
      report_info "glab resolves a project for the lane checkout"
    else
      report_info "glab cannot resolve a project for the lane checkout (its origin is a GitHub remote)"
    fi
  fi
fi

# --------------------------------------------------------------------- summary
printf '\n'
case "$status_level" in
  0) printf 'Status: OK\n' ;;
  1) printf 'Status: WARNINGS\n' ;;
  *) printf 'Status: CRITICAL\n' ;;
esac

if [ -n "$warnings" ]; then
  printf '\nWarnings:\n%s' "$warnings"
fi

if [ -n "$next_steps" ]; then
  printf '\nNext Steps:\n%s' "$next_steps"
else
  printf '\nNext Steps:\n  - None. The harness is healthy.\n'
fi

exit "$status_level"
