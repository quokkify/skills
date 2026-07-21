#!/usr/bin/env python3
"""Dependency-free structural and privacy checks for the public skills repository."""

from __future__ import annotations

import re
import string
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

EXCLUDED_PARTS = {".git", ".venv", "node_modules", "public", "__pycache__"}
FORBIDDEN_NAMES = {name.casefold() for name in ("MEMORY.md", "USER.md", "SOUL.md", "auth.json", "credentials.json", "settings.local.json")}
FORBIDDEN_DIRECTORIES = {"sessions", "transcripts", "snapshot", "snapshots", "backups"}
SKILL_SUPPORT_DIRECTORIES = {"assets", "references", "scripts", "templates"}
SKILLS_DIRECTORY = "skills"
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MACHINE_HOME_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:/(?:home|Users)/[A-Za-z0-9._-]+|/root)(?:/|$)"
)
WINDOWS_HOME_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:\\Users\\[A-Za-z0-9._-]+(?:\\|$)")
LOCAL_SECRET_RE = re.compile(r"(?<![A-Za-z0-9])~/\.secrets(?:/|\b)")


@dataclass(frozen=True)
class Skill:
    """A validated skill name and its entry point."""

    name: str
    path: Path


def repository_files(root: Path) -> list[Path]:
    """Return repository files while excluding generated and dependency trees."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    else:
        paths = [
            root / path.decode("utf-8", errors="surrogateescape")
            for path in result.stdout.split(b"\0")
            if path
        ]
        return sorted(path for path in paths if path.is_file() or path.is_symlink())
    return sorted(
        path
        for path in root.rglob("*")
        if (path.is_file() or path.is_symlink())
        and not any(part in EXCLUDED_PARTS for part in path.relative_to(root).parts)
    )


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str] | tuple[None, None]:
    """Parse the top-level scalars required by a SKILL.md frontmatter block."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, None

    try:
        closing = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        return None, None

    metadata: dict[str, str] = {}
    for line in lines[1:closing]:
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*?)\s*$", line)
        if not match:
            continue
        value = match.group(2)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        metadata[match.group(1)] = value
    return metadata, "\n".join(lines[closing + 1 :]).strip()


def markdown_link_destinations(text: str) -> list[tuple[int, str]]:
    """Extract inline-link destinations and their source lines from a document."""
    destinations: list[tuple[int, str]] = []
    cursor = 0
    while cursor < len(text):
        label_start = text.find("[", cursor)
        if label_start < 0:
            break
        if label_start > 0 and text[label_start - 1] == "!":
            cursor = label_start + 1
            continue
        label_end = text.find("]", label_start + 1)
        if label_end < 0 or label_end + 1 >= len(text) or text[label_end + 1] != "(":
            cursor = label_start + 1
            continue

        destination_start = label_end + 2
        depth = 1
        index = destination_start
        while index < len(text):
            character = text[index]
            if character == "\\":
                index += 2
                continue
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    line_number = text.count("\n", 0, label_start) + 1
                    destinations.append((line_number, text[destination_start:index]))
                    cursor = index + 1
                    break
            index += 1
        else:
            break
    return destinations


def markdown_destination(raw_destination: str) -> str:
    """Return a destination without an optional CommonMark link title."""
    value = raw_destination.strip()
    if value.startswith("<"):
        closing = value.find(">", 1)
        return value[1:closing] if closing >= 0 else value

    depth = 0
    index = 0
    while index < len(value):
        character = value[index]
        if character == "\\":
            index += 2
            continue
        if character == "(":
            depth += 1
        elif character == ")" and depth:
            depth -= 1
        elif character.isspace() and depth == 0:
            return value[:index]
        index += 1
    return value


def unescape_markdown_punctuation(value: str) -> str:
    """Decode CommonMark backslash escapes while preserving other backslashes."""
    result: list[str] = []
    index = 0
    while index < len(value):
        if value[index] == "\\" and index + 1 < len(value) and value[index + 1] in string.punctuation:
            result.append(value[index + 1])
            index += 2
            continue
        result.append(value[index])
        index += 1
    return "".join(result)


def validate_skills(root: Path, files: list[Path]) -> tuple[list[Skill], list[str]]:
    """Validate skill metadata and names, including Hermes filename collisions."""
    errors: list[str] = []
    skills: list[Skill] = []
    names: dict[str, Path] = {}

    skill_directories = {
        path.relative_to(root).parts[1]
        for path in files
        if len(path.relative_to(root).parts) >= 3
        and path.relative_to(root).parts[0] == SKILLS_DIRECTORY
    }
    repository_paths = {path.relative_to(root) for path in files}
    for directory in sorted(skill_directories):
        entry_point = Path(SKILLS_DIRECTORY) / directory / "SKILL.md"
        if entry_point not in repository_paths:
            errors.append(f"{entry_point}: canonical skill directory is missing SKILL.md")

    discovered_skill_files = [
        path for path in files if path.name == "SKILL.md" and not path.is_symlink()
    ]
    skill_files: list[Path] = []
    for path in discovered_skill_files:
        rel = path.relative_to(root)
        if len(rel.parts) != 3 or rel.parts[0] != SKILLS_DIRECTORY:
            errors.append(
                f"{rel}: skills must live at {SKILLS_DIRECTORY}/<skill-name>/SKILL.md"
            )
            continue
        skill_files.append(path)
    if not skill_files:
        errors.append(f"repository contains no skills under {SKILLS_DIRECTORY}/")
        return skills, errors

    for path in skill_files:
        rel = path.relative_to(root)
        try:
            metadata, body = parse_frontmatter(path)
        except UnicodeDecodeError:
            errors.append(f"{rel}: file is not valid UTF-8")
            continue
        if metadata is None:
            errors.append(f"{rel}: missing or unclosed YAML frontmatter")
            continue

        name = metadata.get("name", "").strip()
        description = metadata.get("description", "").strip()
        if not SKILL_NAME_RE.fullmatch(name):
            errors.append(f"{rel}: name must use lowercase kebab-case")
            continue
        if path.parent.name != name:
            errors.append(f"{rel}: frontmatter name '{name}' must match directory '{path.parent.name}'")
        if not description:
            errors.append(f"{rel}: description is required")
        elif description in {">", "|"}:
            errors.append(f"{rel}: description must be a single-line scalar")
        elif len(description) > 1024:
            errors.append(f"{rel}: description exceeds 1024 characters")
        if not body:
            errors.append(f"{rel}: skill body is empty")

        key = name.casefold()
        if key in names:
            errors.append(f"{rel}: duplicate skill name '{name}' also used by {names[key].relative_to(root)}")
        else:
            names[key] = path
            skills.append(Skill(name=name, path=path))

    skill_directories = [skill.path.parent for skill in skills]
    markdown_files = []
    for path in files:
        if path.suffix.casefold() != ".md" or path.is_symlink():
            continue
        is_support_file = any(
            path.is_relative_to(skill_directory)
            and path.relative_to(skill_directory).parts[0].casefold() in SKILL_SUPPORT_DIRECTORIES
            for skill_directory in skill_directories
        )
        if not is_support_file:
            markdown_files.append(path)
    for skill in skills:
        for path in markdown_files:
            if path == skill.path:
                continue
            if path.stem.casefold() == skill.name.casefold():
                errors.append(
                    f"{path.relative_to(root)}: Markdown filename collides with skill name "
                    f"'{skill.name}' from {skill.path.relative_to(root)}"
                )

    return skills, errors


def validate_public_boundary(root: Path, files: list[Path]) -> list[str]:
    """Reject targeted local-state, symlink, and machine-specific content."""
    errors: list[str] = []
    for path in files:
        rel = path.relative_to(root)
        parts = {part.casefold() for part in rel.parts[:-1]}
        if path.is_symlink():
            errors.append(f"{rel}: symbolic links are not allowed in the public skills repository")
            continue
        if path.name.casefold() in FORBIDDEN_NAMES:
            errors.append(f"{rel}: agent-local or credential-state filename is forbidden")
        if parts & FORBIDDEN_DIRECTORIES:
            errors.append(f"{rel}: private/runtime state directory is forbidden")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if MACHINE_HOME_RE.search(line):
                errors.append(f"{rel}:{line_number}: machine-specific home path is forbidden")
            if WINDOWS_HOME_RE.search(line):
                errors.append(f"{rel}:{line_number}: machine-specific Windows home path is forbidden")
            if LOCAL_SECRET_RE.search(line):
                errors.append(f"{rel}:{line_number}: local secret-store path is forbidden")
    return errors


def validate_markdown_links(root: Path, files: list[Path]) -> list[str]:
    """Validate local Markdown links without allowing host-filesystem escapes."""
    errors: list[str] = []
    for path in files:
        if path.is_symlink() or path.suffix.casefold() != ".md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"{path.relative_to(root)}: file is not valid UTF-8")
            continue
        for line_number, raw_target in markdown_link_destinations(text):
            target = unescape_markdown_punctuation(markdown_destination(raw_target))
            if not target or target.startswith(("#", "/", "mailto:", "http://", "https://")):
                continue
            target = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not target or any(marker in target for marker in ("<", ">", "*")):
                continue
            resolved = (path.parent / target).resolve()
            candidates = [resolved]
            if resolved.suffix == "":
                candidates.extend([resolved.with_suffix(".md"), resolved / "index.md"])
            if any(not candidate.is_relative_to(root) for candidate in candidates):
                errors.append(f"{path.relative_to(root)}:{line_number}: local link escapes repository")
                continue
            if not any(candidate.exists() for candidate in candidates):
                errors.append(f"{path.relative_to(root)}:{line_number}: broken local link")
    return errors


def validate_repository(root: Path) -> list[str]:
    """Run every portable repository check and return all discovered errors."""
    root = root.resolve()
    files = repository_files(root)
    _, skill_errors = validate_skills(root, files)
    return skill_errors + validate_public_boundary(root, files) + validate_markdown_links(root, files)


def main() -> int:
    """Run validation for the requested root and print a concise result."""
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    errors = validate_repository(root)
    if errors:
        print("Repository validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Repository validation: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
