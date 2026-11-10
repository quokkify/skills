#!/usr/bin/env python3
"""Helpers for reviewing GitLab merge requests with glab: URL parsing, diff positions, draft notes."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote, urlparse

MR_SEGMENT = "/-/merge_requests/"
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
NEW_PATH_PREFIX = "+++ "
OLD_PATH_PREFIX = "--- "
RENAME_FROM_PREFIX = "rename from "
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


@dataclass
class FileDiff:
    old_path: str
    lines: dict[int, tuple[str, int | None]] = field(default_factory=dict)


def parse_diff(diff_text: str) -> dict[str, FileDiff]:
    """Map new path -> FileDiff: old path and {new line: (text, old line or None if added)}."""
    result: dict[str, FileDiff] = {}
    current: FileDiff | None = None
    old_path: str | None = None
    new_no = old_no = 0
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
                current.lines[new_no] = (raw[1:], None)
                new_no += 1
                new_left -= 1
                continue
            if raw.startswith("-"):
                old_no += 1
                old_left -= 1
                continue
            if raw.startswith(" ") or raw == "":
                current.lines[new_no] = (raw[1:], old_no)
                new_no += 1
                old_no += 1
                old_left -= 1
                new_left -= 1
                continue
        if raw.startswith("diff --git "):
            current = None
            old_path = None
            old_left = new_left = 0
            continue
        if not in_hunk and raw.startswith(RENAME_FROM_PREFIX):
            old_path = raw[len(RENAME_FROM_PREFIX):]
            continue
        if not in_hunk and raw.startswith(OLD_PATH_PREFIX):
            source = _header_path(raw[len(OLD_PATH_PREFIX):], "a/")
            old_path = None if source == DEV_NULL else source
            continue
        if not in_hunk and raw.startswith(NEW_PATH_PREFIX):
            target = _header_path(raw[len(NEW_PATH_PREFIX):], "b/")
            if target == DEV_NULL:
                current = None
            else:
                current = result.setdefault(target, FileDiff(old_path or target))
            continue
        hunk = HUNK_RE.match(raw)
        if hunk:
            old_no = int(hunk.group(1))
            old_left = int(hunk.group(2)) if hunk.group(2) is not None else 1
            new_no = int(hunk.group(3))
            new_left = int(hunk.group(4)) if hunk.group(4) is not None else 1
            if current is None:
                old_left = new_left = 0
    return result


def _header_path(value: str, prefix: str) -> str:
    target = value.split("\t", 1)[0]
    return target[len(prefix):] if target.startswith(prefix) else target


def new_line_map(diff_text: str) -> dict[str, dict[int, str]]:
    """Map new path -> {new line number: text} for added and context lines."""
    return {
        path: {no: text for no, (text, _) in file.lines.items()}
        for path, file in parse_diff(diff_text).items()
    }


def position_for(diff_text: str, path: str, new_line: int) -> dict | None:
    """Return new/old path and line for a new-side line, or None if it is not in the diff."""
    file = parse_diff(diff_text).get(path)
    if file is None or new_line not in file.lines:
        return None
    return {
        "new_path": path,
        "old_path": file.old_path,
        "new_line": new_line,
        "old_line": file.lines[new_line][1],
    }


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
    old_path: str | None = None,
    old_line: int | None = None,
) -> dict:
    given = [diff_refs is not None, path is not None, new_line is not None]
    if not any(given):
        if old_path is not None or old_line is not None:
            raise ValueError("old_path and old_line need diff_refs, path and new_line")
        return {"note": note}
    if not all(given):
        raise ValueError("diff_refs, path and new_line must be given together")
    missing = [key for key in REF_KEYS if key not in diff_refs]
    if missing:
        raise ValueError(f"diff_refs is missing: {', '.join(missing)}")
    position = {"position_type": "text", **{key: diff_refs[key] for key in REF_KEYS}}
    position.update({"new_path": path, "old_path": old_path or path, "new_line": new_line})
    if old_line is not None:
        position["old_line"] = old_line
    return {"note": note, "position": position}


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _items(state: object) -> list[dict]:
    if not isinstance(state, dict):
        raise ValueError("state must be a JSON object")
    items = state.get("items", [])
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        raise ValueError("state items must be a list of objects")
    return items


def record_draft(state: dict, item_id: int, response: dict) -> dict:
    """Mark an item drafted with the draft id from a draft-note POST response."""
    items = _items(state)
    draft_id = response.get("id") if isinstance(response, dict) else None
    if not _is_int(draft_id):
        raise ValueError("response has no integer id")
    for item in items:
        if item.get("id") == item_id:
            item["status"] = "drafted"
            item["draft_id"] = draft_id
            return state
    raise ValueError(f"no item with id {item_id}")


def reconcile(state: dict, drafts: list[dict]) -> dict:
    """Compare drafted items with the API draft list by draft id."""
    items = _items(state)
    if not isinstance(drafts, list) or not all(isinstance(d, dict) for d in drafts):
        raise ValueError("drafts must be a list of objects")
    listed = {d["id"] for d in drafts if _is_int(d.get("id"))}
    drafted = [i for i in items if i.get("status") == "drafted"]
    referenced = {i["draft_id"] for i in drafted if _is_int(i.get("draft_id"))}
    missing = [i.get("id") for i in drafted
               if not _is_int(i.get("draft_id")) or i["draft_id"] not in listed]
    foreign = [d["id"] if _is_int(d.get("id")) else None
               for d in drafts if not _is_int(d.get("id")) or d["id"] not in referenced]
    seen: dict[int, list] = {}
    for i in drafted:
        if _is_int(i.get("draft_id")):
            seen.setdefault(i["draft_id"], []).append(i.get("id"))
    duplicate = [item for ids in seen.values() if len(ids) > 1 for item in ids]
    return {"missing": missing, "foreign": foreign, "duplicate": duplicate,
            "ok": not (missing or foreign or duplicate)}


def write_json_atomic(path: Path, data: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


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

    p = sub.add_parser(
        "position", help="print new/old path and line for a new-side line; exit 1 if not in the diff"
    )
    p.add_argument("diff_file")
    p.add_argument("path")
    p.add_argument("new_line", type=int)

    p = sub.add_parser("draft-payload", help="write a draft note JSON payload")
    p.add_argument("--note-file", required=True)
    p.add_argument("--refs-file")
    p.add_argument("--path")
    p.add_argument("--line", type=int)
    p.add_argument("--old-path", help="old-side path for a renamed file (default: --path)")
    p.add_argument("--old-line", type=int, help="old-side line; give it for unchanged lines only")
    p.add_argument("--out", required=True)

    p = sub.add_parser("record-draft", help="mark a state item drafted from a draft-note POST response")
    p.add_argument("--state", required=True)
    p.add_argument("--item", required=True, type=int)
    p.add_argument("--response", required=True)

    p = sub.add_parser(
        "reconcile", help="compare drafted items with the draft list; exit 1 if they differ"
    )
    p.add_argument("--state", required=True)
    p.add_argument("--drafts", required=True)
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
        if args.command == "position":
            diff = Path(args.diff_file).read_text(encoding="utf-8")
            position = position_for(diff, args.path, args.new_line)
            if position is None:
                return 1
            print(json.dumps(position))
            return 0
        if args.command == "record-draft":
            state_path = Path(args.state)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            response = json.loads(Path(args.response).read_text(encoding="utf-8"))
            write_json_atomic(state_path, record_draft(state, args.item, response))
            return 0
        if args.command == "reconcile":
            state = json.loads(Path(args.state).read_text(encoding="utf-8"))
            drafts = json.loads(Path(args.drafts).read_text(encoding="utf-8"))
            result = reconcile(state, drafts)
            print(json.dumps(result))
            return 0 if result["ok"] else 1
        note = Path(args.note_file).read_text(encoding="utf-8")
        refs = None
        if args.refs_file:
            refs = json.loads(Path(args.refs_file).read_text(encoding="utf-8"))
        payload = draft_note_payload(
            note, refs, args.path, args.line, args.old_path, args.old_line
        )
        Path(args.out).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return 0
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
