#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_HUB_ROOT="$ROOT" exec python3 - "$@" <<'PY'
import argparse
import copy
import datetime
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
try:
    import tomllib
except ImportError:
    tomllib = None


START = "<!-- SKILLS-HUB:START -->"
END = "<!-- SKILLS-HUB:END -->"
OMC_START = "# BEGIN OMC MANAGED MCP REGISTRY"
OMC_END = "# END OMC MANAGED MCP REGISTRY"


class BootstrapError(Exception):
    pass


def parse_args():
    parser = argparse.ArgumentParser(description="Install shared Skills Hub adapters")
    parser.add_argument("--provider", choices=("claude", "codex", "all"), default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overlay", type=pathlib.Path)
    parser.add_argument("--install-skills", action="store_true")
    parser.add_argument("--merge-unknown-keys", action="store_true",
                        help="Allow merging template keys into sections that contain unrecognized/legacy keys")
    return parser.parse_args()


def absolute(path):
    return pathlib.Path(path).expanduser().absolute()


def source_root():
    return pathlib.Path(os.environ["SKILLS_HUB_ROOT"])


def env_path(name, default):
    return absolute(os.environ.get(name, default))


def overlay_file(overlay, relative, public):
    if overlay is None:
        return public
    candidate = overlay / relative
    return candidate if candidate.exists() else public


def json_merge(existing, template):
    if isinstance(existing, (dict, list)) != isinstance(template, (dict, list)):
        raise BootstrapError("ambiguous JSON merge between structured and scalar values")
    if isinstance(existing, dict) != isinstance(template, dict) or isinstance(existing, list) != isinstance(template, list):
        raise BootstrapError("ambiguous JSON merge between incompatible containers")
    if isinstance(existing, dict) and isinstance(template, dict):
        result = copy.deepcopy(existing)
        for key, value in template.items():
            if key not in result:
                result[key] = copy.deepcopy(value)
            else:
                result[key] = json_merge(result[key], value)
        return result
    if isinstance(existing, list) and isinstance(template, list):
        result = copy.deepcopy(existing)
        seen = {json.dumps(item, sort_keys=True, separators=(",", ":")) for item in result}
        for item in template:
            marker = json.dumps(item, sort_keys=True, separators=(",", ":"))
            if marker not in seen:
                result.append(copy.deepcopy(item))
                seen.add(marker)
        return result
    return copy.deepcopy(existing)


def json_bytes(data):
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode()


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise BootstrapError(f"cannot parse JSON {path}: {exc}") from exc


def replace_marked_block(text, block, start, end, path):
    block = block.rstrip("\n")
    first = text.find(start)
    last = text.find(end)
    if (first < 0) != (last < 0) or (first >= 0 and last < first):
        raise BootstrapError(f"ambiguous managed block in {path}")
    if first < 0:
        separator = "" if not text or text.endswith("\n") else "\n"
        return text + separator + block + "\n"
    if text.find(start, first + len(start)) >= 0 or text.find(end, last + len(end)) >= 0:
        raise BootstrapError(f"multiple managed blocks in {path}")
    return text[:first] + block + text[last + len(end):]


def toml_keys(text):
    parsed = load_toml(text)
    section = ""
    keys = {"": set()}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            keys.setdefault(section, set())
        elif "=" in line:
            keys.setdefault(section, set()).add(line.split("=", 1)[0].strip())
    return parsed, keys


def load_toml(text):
    if tomllib is not None:
        try:
            return tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise BootstrapError(f"cannot parse TOML: {exc}") from exc
    section = ""
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            if not line.endswith("]") or line.count("[") not in (1, 2) or line.count("]") not in (1, 2):
                raise BootstrapError(f"cannot parse TOML near line {number}")
            section = line
            continue
        if "=" not in line:
            raise BootstrapError(f"cannot parse TOML near line {number}")
        value = line.split("=", 1)[1].strip()
        if value.count('"') % 2 or value.count("'") % 2:
            raise BootstrapError(f"cannot parse TOML near line {number}")
    return {"_validated": True}


def section_end_lines(lines):
    # Map each section name to the line index of the next table header (or
    # end of file), so a missing key can be inserted back into its own
    # table instead of always landing at the end of the file, where it
    # would be assigned to whatever table happens to be last. The boundary
    # backs up over any blank/comment lines immediately before that header,
    # since those conventionally document the upcoming table (e.g. a managed
    # block's opening marker) rather than the section being closed.
    ends = {}
    current_section = ""
    for index, raw in enumerate(lines):
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            boundary = index
            while boundary > 0:
                previous = lines[boundary - 1].strip()
                if previous == "" or previous.startswith("#"):
                    boundary -= 1
                else:
                    break
            ends[current_section] = boundary
            current_section = line[1:-1].strip()
    ends[current_section] = len(lines)
    return ends


def merge_toml(existing_text, template_text, allow_unknown_keys=False):
    _, existing_keys = toml_keys(existing_text)
    template_parsed, template_keys = toml_keys(template_text)
    lines = existing_text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    section_end = section_end_lines(lines)
    chunks = []
    current = []
    for raw in template_text.splitlines(keepends=True):
        line = raw.strip()
        if line.startswith("[") and line.endswith("]") and current:
            chunks.append(current)
            current = []
        current.append(raw)
    if current:
        chunks.append(current)
    trailing_additions = []
    insertions = {}
    for chunk in chunks:
        header = next((line.strip() for line in chunk if line.strip().startswith("[") and line.strip().endswith("]")), "")
        section = header[1:-1].strip() if header else ""
        if section not in existing_keys:
            trailing_additions.extend(chunk)
            continue
        # Check for unrecognized keys in existing section
        template_section_keys = template_keys.get(section, set())
        existing_section_keys = existing_keys.get(section, set())
        unknown_keys = existing_section_keys - template_section_keys
        if unknown_keys and not allow_unknown_keys:
            raise BootstrapError(
                f"section [{section}] contains unrecognized keys: {', '.join(sorted(unknown_keys))}. "
                f"Use --merge-unknown-keys to proceed anyway."
            )
        missing = []
        for raw in chunk:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key = line.split("=", 1)[0].strip()
            if key not in existing_keys[section]:
                missing.append(raw)
                existing_keys[section].add(key)
        if missing:
            insertions.setdefault(section_end[section], []).extend(["\n", *missing])
    merged_lines = []
    for index, raw in enumerate(lines):
        merged_lines.extend(insertions.pop(index, []))
        merged_lines.append(raw)
    merged_lines.extend(insertions.pop(len(lines), []))
    merged = "".join(merged_lines)
    if trailing_additions:
        if merged and not merged.endswith("\n\n"):
            merged += "\n"
        merged += "".join(trailing_additions)
    load_toml(merged)
    omc_before = extract_block(existing_text, OMC_START, OMC_END)
    omc_after = extract_block(merged, OMC_START, OMC_END)
    if omc_before != omc_after:
        raise BootstrapError("OMC managed TOML block changed unexpectedly")
    return merged


def extract_block(text, start, end):
    begin = text.find(start)
    if begin < 0:
        return None
    finish = text.find(end, begin)
    if finish < 0:
        raise BootstrapError("unterminated managed block")
    return text[begin:finish + len(end)]


def add(plan, changes, destination, content=None, mode=None, symlink=None):
    destination = absolute(destination)
    if destination.is_symlink():
        if symlink is not None and os.readlink(destination) == symlink:
            return
    elif destination.is_file():
        if symlink is None and destination.read_bytes() == content and stat.S_IMODE(destination.stat().st_mode) == (mode or 0o600):
            return
    plan.append(str(destination))
    changes[destination] = (content, mode, symlink)


def copy_tree(root, relative, destination, overlay, plan, changes):
    public = root / "adapters" / relative
    overlay_dir = overlay / relative if overlay else None
    names = {source.name for source in public.iterdir() if source.is_file()}
    if overlay_dir and overlay_dir.is_dir():
        names.update(source.name for source in overlay_dir.iterdir() if source.is_file())
    for name in sorted(names):
        source = overlay_dir / name if overlay_dir and (overlay_dir / name).is_file() else public / name
        add(plan, changes, destination / name, source.read_bytes(), source.stat().st_mode & 0o777)


def build_plan(args):
    root = source_root()
    overlay = absolute(args.overlay) if args.overlay else None
    if overlay and not overlay.is_dir():
        raise BootstrapError(f"overlay is not a directory: {overlay}")
    plans = []
    changes = {}
    claude = args.provider in ("claude", "all")
    codex = args.provider in ("codex", "all")
    home = env_path("HOME", pathlib.Path.home())
    if claude:
        config = env_path("CLAUDE_CONFIG_DIR", home / ".claude")
        shared = overlay_file(overlay, pathlib.Path("shared/AGENTS.base.md"), root / "adapters/shared/AGENTS.base.md")
        add(plans, changes, config / "skills-hub/AGENTS.base.md", shared.read_bytes(), shared.stat().st_mode & 0o777)
        copy_tree(root, pathlib.Path("shared/hooks"), config / "hooks", overlay, plans, changes)
        settings_source = overlay_file(overlay, pathlib.Path("claude/settings.template.json"), root / "adapters/claude/settings.template.json")
        settings = read_json(settings_source)
        settings_path = config / "settings.json"
        if settings_path.exists():
            settings = json_merge(read_json(settings_path), settings)
        add(plans, changes, settings_path, json_bytes(settings), 0o600)
        block_source = overlay_file(overlay, pathlib.Path("claude/CLAUDE.block.md"), root / "adapters/claude/CLAUDE.block.md")
        block = block_source.read_text().replace("@__SHARED_BASE__", "@" + str(config / "skills-hub/AGENTS.base.md"))
        claude_path = config / "CLAUDE.md"
        current = claude_path.read_text() if claude_path.exists() else ""
        add(plans, changes, claude_path, replace_marked_block(current, block, START, END, claude_path).encode(), 0o600)
    if codex:
        config = env_path("CODEX_HOME", home / ".codex")
        shared = overlay_file(overlay, pathlib.Path("shared/AGENTS.base.md"), root / "adapters/shared/AGENTS.base.md")
        agents = config / "AGENTS.md"
        add(plans, changes, agents, None, None, str(shared))
        copy_tree(root, pathlib.Path("shared/hooks"), config / "hooks", overlay, plans, changes)
        config_source = overlay_file(overlay, pathlib.Path("codex/config.template.toml"), root / "adapters/codex/config.template.toml")
        config_path = config / "config.toml"
        merged = config_source.read_text() if not config_path.exists() else merge_toml(config_path.read_text(), config_source.read_text(), args.merge_unknown_keys)
        add(plans, changes, config_path, merged.encode(), 0o600)
        hooks_source = overlay_file(overlay, pathlib.Path("codex/hooks.json"), root / "adapters/codex/hooks.json")
        hooks = read_json(hooks_source)
        hooks_path = config / "hooks.json"
        if hooks_path.exists():
            hooks = json_merge(read_json(hooks_path), hooks)
        add(plans, changes, hooks_path, json_bytes(hooks), 0o600)
        agents_source = root / "adapters/codex/agents"
        overlay_agents = overlay / "codex/agents" if overlay else None
        agent_names = {source.name for source in agents_source.glob("*.toml")}
        if overlay_agents and overlay_agents.is_dir():
            agent_names.update(source.name for source in overlay_agents.glob("*.toml"))
        for name in sorted(agent_names):
            source = overlay_agents / name if overlay_agents and (overlay_agents / name).is_file() else agents_source / name
            destination = config / "agents" / source.name
            if destination.exists() and destination.read_bytes() != source.read_bytes():
                continue
            add(plans, changes, destination, source.read_bytes(), source.stat().st_mode & 0o777)
    git_hooks = root / "adapters/shared/git-hooks"
    git_dir = env_path("XDG_CONFIG_HOME", home / ".config") / "git/skills-hub-hooks"
    try:
        current_hooks = subprocess.run(
            ["git", "config", "--global", "--get", "core.hooksPath"], text=True, capture_output=True
        ).stdout.strip()
    except OSError as exc:
        raise BootstrapError(f"cannot run git: {exc}") from exc
    if current_hooks and not hooks_path_matches(current_hooks, git_dir):
        raise BootstrapError(f"refusing to replace foreign global core.hooksPath '{current_hooks}'")
    for source in sorted(item for item in git_hooks.iterdir() if item.is_file()):
        add(plans, changes, git_dir / source.name, source.read_bytes(), source.stat().st_mode & 0o777)
    return plans, changes, git_dir, current_hooks, args, root


def show_plan(plans, dry_run):
    print("Planned operations:")
    for item in plans:
        print(f"  {'would update' if dry_run else 'update'} {item}")
    if dry_run:
        print("Dry run: no files, symlinks, or git configuration were changed.")


def hooks_path_matches(current, expected):
    return bool(current) and (current == str(expected) or absolute(current) == expected)


def nearest_existing_ancestor(destination):
    candidate = destination.parent
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def apply(plans, changes, git_dir, old_hooks, args):
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
    backups = {}
    existing_dirs = set()
    stage_dirs = []
    fail_after = int(os.environ.get("BOOTSTRAP_TEST_FAIL_AFTER", "0"))
    count = 0
    staged_paths = {}
    git_changed = False
    try:
        for destination_text in plans:
            parent = pathlib.Path(destination_text).parent
            while parent != parent.parent:
                if parent.exists():
                    existing_dirs.add(parent)
                parent = parent.parent
        for destination_text in plans:
            destination = pathlib.Path(destination_text)
            item = changes[destination]
            if destination.exists() or destination.is_symlink():
                backup = destination.with_name(destination.name + f".bak.{timestamp}")
                backups[destination] = backup
            # Stage each replacement on the same filesystem as its
            # destination (rather than a shared tempfile.mkdtemp() root,
            # which may be a different device) so the os.replace() below is
            # always an atomic rename and never raises EXDEV.
            stage_dir = pathlib.Path(
                tempfile.mkdtemp(prefix="skills-hub-bootstrap-", dir=nearest_existing_ancestor(destination))
            )
            stage_dirs.append(stage_dir)
            staged = stage_dir / "staged"
            if item[2] is not None:
                staged.symlink_to(item[2])
            else:
                staged.write_bytes(item[0])
                os.chmod(staged, item[1] or 0o600)
            staged_paths[destination] = staged
        for destination in plans:
            destination = pathlib.Path(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination in backups:
                os.replace(destination, backups[destination])
            os.replace(staged_paths[destination], destination)
            count += 1
            if fail_after and count >= fail_after:
                raise BootstrapError("test-injected failure")
        if not hooks_path_matches(old_hooks, git_dir):
            subprocess.run(["git", "config", "--global", "core.hooksPath", str(git_dir)], check=True)
            git_changed = True
    except Exception as exc:
        for destination in reversed([pathlib.Path(p) for p in plans[:count]]):
            if destination.exists() or destination.is_symlink():
                destination.unlink()
            if destination in backups:
                os.replace(backups[destination], destination)
        if count < len(plans):
            for destination, backup in backups.items():
                if backup.exists() and not destination.exists() and destination not in [pathlib.Path(p) for p in plans[:count]]:
                    os.replace(backup, destination)
        if git_changed:
            if old_hooks:
                subprocess.run(["git", "config", "--global", "core.hooksPath", old_hooks], check=False)
            else:
                subprocess.run(["git", "config", "--global", "--unset", "core.hooksPath"], check=False)
        candidates = set()
        for destination_text in plans:
            candidate = pathlib.Path(destination_text).parent
            while candidate != candidate.parent:
                candidates.add(candidate)
                candidate = candidate.parent
        candidates = sorted(candidates, key=lambda item: len(item.parts), reverse=True)
        for candidate in candidates:
            if candidate not in existing_dirs and candidate.exists() and not any(candidate.iterdir()):
                candidate.rmdir()
        raise BootstrapError(f"installation rolled back: {exc}") from exc
    finally:
        for stage_dir in stage_dirs:
            shutil.rmtree(stage_dir, ignore_errors=True)


def install_skills(args):
    if not args.install_skills:
        return
    npx = shutil.which("npx")
    if npx is None:
        print("Warning: npx is not available; skipped official skills installation.", file=sys.stderr)
        return
    providers = ("claude-code", "codex") if args.provider == "all" else (("claude-code",) if args.provider == "claude" else ("codex",))
    for provider in providers:
        subprocess.run(
            [npx, "skills", "add", "quokkify/skills", "--skill", "*", "-g", "-a", provider, "-y"],
            check=True,
            timeout=600,
        )


def main():
    args = parse_args()
    plans, changes, git_dir, old_hooks, args, _ = build_plan(args)
    show_plan(plans, args.dry_run)
    if args.dry_run:
        return 0
    apply(plans, changes, git_dir, old_hooks, args)
    try:
        install_skills(args)
    except subprocess.SubprocessError as exc:
        print(f"Warning: official skills installation failed: {exc}", file=sys.stderr)
    if args.provider in ("codex", "all"):
        print("Codex hook handlers were installed. Open the Codex TUI and run /hooks to review and approve them.")
    print("Bootstrap installation complete.")
    return 0


try:
    raise SystemExit(main())
except BootstrapError as exc:
    print(f"bootstrap: {exc}", file=sys.stderr)
    raise SystemExit(1)
PY