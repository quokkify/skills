#!/usr/bin/env bash
# SessionStart prerequisites: tell the agent when a required companion is missing.
#
# Usage: sessionstart-prerequisites.sh <claude|codex>
#
# Claude Code requires oh-my-claudecode and superpowers; Codex CLI requires
# superpowers. Emits additionalContext only when something is missing and stays
# silent otherwise. Runs outside git work trees too, because the requirement is
# per runtime, not per repository.
#
# Hook name for SKILLS_HUB_SKIP_HOOKS: prerequisites

set -uo pipefail

HOOK_LIB_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./hook-lib.sh
. "$HOOK_LIB_DIR/hook-lib.sh"
hook_enable_failsafe

hook_read_input || true

WORKDIR="${HOOK_CWD:-$PWD}"
[ -d "$WORKDIR" ] || WORKDIR="$PWD"
hook_disabled prerequisites "$(hook_git_root "$WORKDIR")" && hook_allow

runtime="${1:-$(hook_runtime)}"
if [ -z "$HOOK_PY" ]; then
  HOOK_EXIT_INTENT=deliberate
  printf '%s\n' "Required agent companions could not be verified (shared prerequisites hook, runtime: $runtime): no python3 or python on PATH. Ask the user to confirm the required companions are installed before any substantive work."
  exit 0
fi

missing="$(PREREQ_RUNTIME="$runtime" PREREQ_CWD="$WORKDIR" "$HOOK_PY" -c '
import json, os, pathlib, re, shutil

home = pathlib.Path(os.environ.get("HOME", "~")).expanduser()
runtime = os.environ.get("PREREQ_RUNTIME", "")
cwd = pathlib.Path(os.environ.get("PREREQ_CWD", "."))


def read(path):
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def claude_plugin_enabled(config, name):
    candidates = [config / "settings.json", config / "settings.local.json",
                  cwd / ".claude" / "settings.json", cwd / ".claude" / "settings.local.json"]
    for path in candidates:
        try:
            plugins = json.loads(read(path) or "{}").get("enabledPlugins", {})
        except (json.JSONDecodeError, AttributeError):
            continue
        if isinstance(plugins, dict) and any(
            key.split("@", 1)[0] == name and value is True for key, value in plugins.items()
        ):
            return True
    return False


def codex_plugin_enabled(path, name):
    text = read(path)
    header = re.compile(r"^\s*\[plugins\.\"" + re.escape(name) + r"@[^\"]*\"\]\s*$")
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not header.match(line):
            continue
        for following in lines[index + 1:]:
            stripped = following.strip()
            if stripped.startswith("["):
                break
            if re.match(r"^enabled\s*=\s*false\b", stripped):
                return False
        return True
    return False


missing = []
if runtime == "claude":
    config = pathlib.Path(os.environ.get("CLAUDE_CONFIG_DIR") or home / ".claude")
    has_omc = (
        "<!-- OMC:START -->" in read(config / "CLAUDE.md")
        or claude_plugin_enabled(config, "oh-my-claudecode")
        or shutil.which("omc") is not None
    )
    if not has_omc:
        missing.append(
            "oh-my-claudecode: not detected. Install it from "
            "https://github.com/Yeachan-Heo/oh-my-claudecode and run /oh-my-claudecode:omc-setup."
        )
    if not claude_plugin_enabled(config, "superpowers"):
        missing.append("superpowers: not detected. Install it with /plugin install superpowers@claude-plugins-official.")
elif runtime == "codex":
    config = pathlib.Path(os.environ.get("CODEX_HOME") or home / ".codex")
    skills = home / ".agents" / "skills"
    has_superpowers = (
        any(codex_plugin_enabled(path, "superpowers") for path in (cwd / ".codex" / "config.toml", config / "config.toml"))
        or (skills / "superpowers").is_dir()
        or (skills / "using-superpowers" / "SKILL.md").is_file()
    )
    if not has_superpowers:
        missing.append("superpowers: not detected. Install it from the Codex plugin marketplace: /plugins, search superpowers, Install Plugin.")
print("\n".join("- " + item for item in missing))
' 2>/dev/null)" || hook_allow

[ -n "$missing" ] || hook_allow

CONTEXT="Required agent companions are missing (shared prerequisites hook, runtime: $runtime):
$missing

Before any substantive work, tell the user which companion is missing and how to install it. Do not emulate a missing companion's workflows from memory. Continue without it only when the user explicitly says so."

hook_add_context "$CONTEXT" "${HOOK_EVENT:-SessionStart}"
