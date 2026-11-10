#!/usr/bin/env python3
"""Helpers for reviewing GitLab merge requests with glab: URL parsing, diff line lookup, draft notes."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlparse

MR_SEGMENT = "/-/merge_requests/"
HUNK_RE = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
NEW_PATH_PREFIX = "+++ "
DEV_NULL = "/dev/null"
REF_KEYS = ("base_sha", "head_sha", "start_sha")


@dataclass(frozen=True)
class MrRef:
    host: str
    project_path: str
    iid: int

    @property
    def encoded_project(self) -> str:
        return quote(self.project_path, safe="")


def parse_mr_url(url: str) -> MrRef:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc or MR_SEGMENT not in parsed.path:
        raise ValueError(f"not a merge request URL: {url}")
    project, _, rest = parsed.path.partition(MR_SEGMENT)
    iid_text = rest.split("/", 1)[0]
    project = project.strip("/")
    if not project or not iid_text.isdigit():
        raise ValueError(f"not a merge request URL: {url}")
    return MrRef(parsed.netloc, project, int(iid_text))


def new_line_map(diff_text: str) -> dict[str, dict[int, str]]:
    """Map new path -> {new line number: text} for added and context lines."""
    result: dict[str, dict[int, str]] = {}
    current: dict[int, str] | None = None
    new_no = 0
    old_left = new_left = 0
    lines = diff_text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    for raw in lines:
        raw = raw.removesuffix("\r")
        in_hunk = old_left > 0 or new_left > 0
        if in_hunk and current is not None:
            if raw.startswith("\\"):
                continue
            if raw.startswith("+"):
                current[new_no] = raw[1:]
                new_no += 1
                new_left -= 1
                continue
            if raw.startswith("-"):
                old_left -= 1
                continue
            if raw.startswith(" ") or raw == "":
                current[new_no] = raw[1:]
                new_no += 1
                old_left -= 1
                new_left -= 1
                continue
        if raw.startswith("diff --git "):
            current = None
            old_left = new_left = 0
            continue
        if not in_hunk and raw.startswith(NEW_PATH_PREFIX):
            target = raw[len(NEW_PATH_PREFIX):].split("\t", 1)[0]
            if target == DEV_NULL:
                current = None
            else:
                path = target[2:] if target.startswith("b/") else target
                current = result.setdefault(path, {})
            continue
        hunk = HUNK_RE.match(raw)
        if hunk:
            old_left = int(hunk.group(1)) if hunk.group(1) is not None else 1
            new_no = int(hunk.group(2))
            new_left = int(hunk.group(3)) if hunk.group(3) is not None else 1
            if current is None:
                old_left = new_left = 0
    return result


def find_new_lines(diff_text: str, path: str, text: str) -> list[int]:
    wanted = text.strip()
    lines = new_line_map(diff_text).get(path, {})
    return [no for no, line in sorted(lines.items()) if line.strip() == wanted]


def in_diff(diff_text: str, path: str, new_line: int) -> bool:
    return new_line in new_line_map(diff_text).get(path, {})


def draft_note_payload(
    note: str,
    diff_refs: dict | None = None,
    path: str | None = None,
    new_line: int | None = None,
) -> dict:
    given = [diff_refs is not None, path is not None, new_line is not None]
    if not any(given):
        return {"note": note}
    if not all(given):
        raise ValueError("diff_refs, path and new_line must be given together")
    missing = [key for key in REF_KEYS if key not in diff_refs]
    if missing:
        raise ValueError(f"diff_refs is missing: {', '.join(missing)}")
    position = {"position_type": "text", **{key: diff_refs[key] for key in REF_KEYS}}
    position.update({"new_path": path, "old_path": path, "new_line": new_line})
    return {"note": note, "position": position}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("parse-url", help="parse a merge request URL into JSON")
    p.add_argument("url")

    p = sub.add_parser("new-line", help="list new-side line numbers whose text matches")
    p.add_argument("diff_file")
    p.add_argument("path")
    p.add_argument("text")

    p = sub.add_parser("in-diff", help="exit 0 if the new-side line is in the diff, else 1")
    p.add_argument("diff_file")
    p.add_argument("path")
    p.add_argument("line", type=int)

    p = sub.add_parser("draft-payload", help="write a draft note JSON payload")
    p.add_argument("--note-file", required=True)
    p.add_argument("--refs-file")
    p.add_argument("--path")
    p.add_argument("--line", type=int)
    p.add_argument("--out", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "parse-url":
            ref = parse_mr_url(args.url)
            print(json.dumps({
                "host": ref.host,
                "project_path": ref.project_path,
                "iid": ref.iid,
                "encoded_project": ref.encoded_project,
            }))
            return 0
        if args.command == "new-line":
            diff = Path(args.diff_file).read_text(encoding="utf-8")
            print(json.dumps(find_new_lines(diff, args.path, args.text)))
            return 0
        if args.command == "in-diff":
            diff = Path(args.diff_file).read_text(encoding="utf-8")
            return 0 if in_diff(diff, args.path, args.line) else 1
        note = Path(args.note_file).read_text(encoding="utf-8")
        refs = None
        if args.refs_file:
            refs = json.loads(Path(args.refs_file).read_text(encoding="utf-8"))
        payload = draft_note_payload(note, refs, args.path, args.line)
        Path(args.out).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return 0
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
