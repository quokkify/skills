#!/usr/bin/env python3
"""Deterministic rubric for a merge request description draft.

Usage: rubric.py --profile <profile.json> --text <draft.md> [--original <current.md>]
Prints a JSON report. Exit 0 = ok, 1 = failures, 2 = usage or profile error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_WORDS = 120
DEFAULT_LINES = 12
DEFAULT_HEADINGS = ["What changed", "Verification", "Needs from you"]
BULLET_MAX_WORDS = 20
BULLET_MAX_IDENTIFIERS = 1
MAX_BULLETS = 7

START_RE = re.compile(r"<!--\s*([\w-]+):start\s*-->")
END_RE = re.compile(r"<!--\s*([\w-]+):end\s*-->")
DETAILS_RE = re.compile(r"<details\b.*?</details>", re.IGNORECASE | re.DOTALL)
BULLET_RE = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
IDENTIFIER_RE = re.compile(r"`[^`]+`")
LINK_TARGET_RE = re.compile(r"\]\([^)]*\)")
PARENTHETICAL_RE = re.compile(r"\([^)]*\)")


class ProfileError(ValueError):
    """The profile cannot be used."""


def load_profile(profile: dict) -> dict:
    if not isinstance(profile, dict):
        raise ProfileError("profile must be a JSON object")
    budget = profile.get("word_budget") or {}
    if not isinstance(budget, dict):
        raise ProfileError("word_budget must be an object with 'words' and 'lines'")
    words = budget.get("words", DEFAULT_WORDS)
    lines = budget.get("lines", DEFAULT_LINES)
    if not isinstance(words, int) or not isinstance(lines, int) or words <= 0 or lines <= 0:
        raise ProfileError("word_budget.words and word_budget.lines must be positive integers")
    keep = []
    for pattern in profile.get("keep_lines") or []:
        try:
            keep.append(re.compile(pattern))
        except (re.error, TypeError) as error:
            raise ProfileError(f"invalid keep_lines pattern {pattern!r}: {error}") from error
    stop_list = [str(term).lower() for term in profile.get("stop_list") or [] if str(term).strip()]
    return {"words": words, "lines": lines, "keep": keep, "stop_list": stop_list}


def marker_blocks(text: str) -> tuple[list[str], list[str]]:
    """Return (complete foreign blocks, names of unbalanced markers)."""
    blocks: list[str] = []
    unbalanced: list[str] = []
    position = 0
    while True:
        start = START_RE.search(text, position)
        if not start:
            break
        name = start.group(1)
        end = re.compile(r"<!--\s*" + re.escape(name) + r":end\s*-->").search(text, start.end())
        if not end:
            unbalanced.append(name)
            position = start.end()
            continue
        blocks.append(text[start.start() : end.end()])
        position = end.end()
    remaining = text
    for block in blocks:
        remaining = remaining.replace(block, "", 1)
    for end in END_RE.finditer(remaining):
        unbalanced.append(end.group(1))
    return blocks, unbalanced


def visible_lines(text: str, blocks: list[str], keep: list[re.Pattern]) -> list[str]:
    for block in blocks:
        text = text.replace(block, "", 1)
    text = DETAILS_RE.sub("", text)
    result = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or START_RE.search(line) or END_RE.search(line):
            continue
        if any(pattern.search(line) for pattern in keep):
            continue
        result.append(line)
    return result


def content_words(line: str) -> list[str]:
    line = BULLET_RE.sub("", line)
    line = re.sub(r"^>\s*", "", line)
    return line.split()


def check(text: str, profile: dict, original: str | None = None) -> dict:
    settings = load_profile(profile)
    failures: list[dict] = []
    warnings: list[dict] = []

    if not text.strip():
        failures.append({"code": "empty_description", "detail": "the description is empty"})
        return report(failures, warnings, 0, 0, 0)

    blocks, unbalanced = marker_blocks(text)
    for name in unbalanced:
        failures.append({"code": "marker_block_unbalanced", "detail": f"marker block '{name}' has no matching start or end"})

    if original is not None:
        original_blocks, _ = marker_blocks(original)
        for block in original_blocks:
            if block not in text:
                name = START_RE.search(block).group(1)
                failures.append({"code": "marker_block_changed", "detail": f"block '{name}' from the current description is missing or edited"})

    lowered = text.lower()
    for term in settings["stop_list"]:
        if term in lowered:
            failures.append({"code": "stop_list_hit", "detail": f"stop-list term found: {term!r}"})

    lines = visible_lines(text, blocks, settings["keep"])
    words = sum(len(content_words(line)) for line in lines if not line.startswith("#"))
    bullets = [line for line in lines if BULLET_RE.match(line)]

    if words > settings["words"]:
        failures.append({"code": "over_budget_words", "detail": f"{words} visible words, budget {settings['words']}"})
    if len(lines) > settings["lines"]:
        failures.append({"code": "over_budget_lines", "detail": f"{len(lines)} visible lines, budget {settings['lines']}"})

    for bullet in bullets:
        body = BULLET_RE.sub("", bullet)
        if len(body.split()) > BULLET_MAX_WORDS:
            warnings.append({"code": "bullet_too_long", "detail": body})
        if len(IDENTIFIER_RE.findall(body)) > BULLET_MAX_IDENTIFIERS:
            warnings.append({"code": "bullet_identifiers", "detail": body})
        if PARENTHETICAL_RE.search(LINK_TARGET_RE.sub("]", IDENTIFIER_RE.sub("", body))):
            warnings.append({"code": "bullet_parenthetical", "detail": body})
    if len(bullets) > MAX_BULLETS:
        warnings.append({"code": "too_many_bullets", "detail": f"{len(bullets)} bullets; consider splitting the merge request"})

    seen: set[str] = set()
    for index, line in enumerate(lines):
        if not line.startswith("#"):
            continue
        heading = line.lstrip("#").strip().lower()
        if heading in seen:
            warnings.append({"code": "duplicate_section", "detail": line})
        seen.add(heading)
        following = lines[index + 1] if index + 1 < len(lines) else None
        if following is None or following.startswith("#"):
            warnings.append({"code": "empty_section", "detail": line})

    return report(failures, warnings, words, len(lines), len(bullets))


def report(failures: list[dict], warnings: list[dict], words: int, lines: int, bullets: int) -> dict:
    return {
        "ok": not failures,
        "failures": failures,
        "warnings": warnings,
        "stats": {"visible_words": words, "visible_lines": lines, "bullets": bullets},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--text", required=True, type=Path)
    parser.add_argument("--original", type=Path)
    args = parser.parse_args(argv)
    try:
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        text = args.text.read_text(encoding="utf-8")
        original = args.original.read_text(encoding="utf-8") if args.original else None
        result = check(text, profile, original)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ProfileError) as error:
        print(f"rubric: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
