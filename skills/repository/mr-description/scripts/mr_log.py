#!/usr/bin/env python3
"""Edit log for merge request descriptions: draft vs final, bottleneck tags, retro stats.

Subcommands (all take --state-dir): record, find, attach, stats, mark-retro.
Prints JSON. Exit 0 = ok, 2 = usage error, 3 = no matching entry.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

TAGS = (
    "length",
    "main-point-not-first",
    "jargon",
    "density",
    "mechanism-not-outcome",
    "noise",
    "missing-context",
    "no-ask",
)
SIZES = ("small", "medium", "large")
LOG_NAME = "log.jsonl"


class UsageError(ValueError):
    """Invalid arguments."""


def slug(key: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]", "_", key).lstrip(".")
    return value or "_"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_entries(state: Path) -> list[dict]:
    path = state / LOG_NAME
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_entries(state: Path, entries: list[dict]) -> None:
    state.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in entries)
    (state / LOG_NAME).write_text(body, encoding="utf-8")


def append_entry(state: Path, entry: dict) -> None:
    state.mkdir(parents=True, exist_ok=True)
    with (state / LOG_NAME).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def parse_tags(raw: str) -> list[str]:
    tags = [tag.strip() for tag in raw.split(",") if tag.strip()]
    unknown = [tag for tag in tags if tag not in TAGS]
    if unknown:
        raise UsageError(f"unknown tags {unknown}; allowed: {', '.join(TAGS)}")
    return tags


def cmd_record(args: argparse.Namespace) -> dict:
    if args.size not in SIZES:
        raise UsageError(f"--size must be one of {SIZES}")
    tags = parse_tags(args.tags)
    draft = Path(args.draft).read_text(encoding="utf-8")
    final = Path(args.final).read_text(encoding="utf-8")
    entry = {
        "ts": now(),
        "branch": args.branch,
        "mr": args.mr,
        "size": args.size,
        "draft_words": len(draft.split()),
        "final_words": len(final.split()),
        "edited": draft.strip() != final.strip(),
        "tags": tags,
        "rubric": args.rubric,
        "cold_reader": args.cold_reader,
    }
    texts = args.state_dir / "texts" / slug(args.mr or args.branch)
    texts.mkdir(parents=True, exist_ok=True)
    (texts / "draft.md").write_text(draft, encoding="utf-8")
    (texts / "final.md").write_text(final, encoding="utf-8")
    append_entry(args.state_dir, entry)
    return entry


def records(entries: list[dict]) -> list[dict]:
    return [entry for entry in entries if entry.get("type") != "retro"]


def cmd_find(args: argparse.Namespace) -> dict | None:
    for entry in reversed(records(read_entries(args.state_dir))):
        if args.mr and entry.get("mr") == args.mr:
            return entry
        if args.branch and entry.get("branch") == args.branch:
            return entry
    return None


def cmd_attach(args: argparse.Namespace) -> dict:
    entries = read_entries(args.state_dir)
    attached = 0
    for entry in records(entries):
        if entry.get("branch") == args.branch and entry.get("mr") is None:
            entry["mr"] = args.mr
            attached += 1
    if attached:
        write_entries(args.state_dir, entries)
    return {"attached": attached}


def cmd_stats(args: argparse.Namespace) -> dict:
    entries = read_entries(args.state_dir)
    items = records(entries)
    if args.last:
        items = items[-args.last :]
    tag_counts: dict[str, int] = {}
    for entry in items:
        for tag in entry.get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    last_retro = max((index for index, entry in enumerate(entries) if entry.get("type") == "retro"), default=-1)
    since = len(records(entries[last_retro + 1 :]))
    count = len(items)
    return {
        "count": count,
        "tag_counts": dict(sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))),
        "accepted_unedited_share": (sum(not entry["edited"] for entry in items) / count) if count else 0.0,
        "avg_final_words": (sum(entry["final_words"] for entry in items) / count) if count else 0.0,
        "since_last_retro": since,
    }


def cmd_mark_retro(args: argparse.Namespace) -> dict:
    entry = {"ts": now(), "type": "retro"}
    append_entry(args.state_dir, entry)
    return entry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str) -> argparse.ArgumentParser:
        command = sub.add_parser(name)
        command.add_argument("--state-dir", required=True, type=Path)
        return command

    record = add("record")
    record.add_argument("--branch", required=True)
    record.add_argument("--mr")
    record.add_argument("--size", required=True)
    record.add_argument("--draft", required=True)
    record.add_argument("--final", required=True)
    record.add_argument("--tags", default="")
    record.add_argument("--rubric", required=True, choices=("ok", "fail"))
    record.add_argument("--cold-reader", required=True, choices=("ok", "fixed"))

    find = add("find")
    target = find.add_mutually_exclusive_group(required=True)
    target.add_argument("--mr")
    target.add_argument("--branch")

    attach = add("attach")
    attach.add_argument("--branch", required=True)
    attach.add_argument("--mr", required=True)

    stats = add("stats")
    stats.add_argument("--last", type=int)

    add("mark-retro")
    return parser


COMMANDS = {
    "record": cmd_record,
    "find": cmd_find,
    "attach": cmd_attach,
    "stats": cmd_stats,
    "mark-retro": cmd_mark_retro,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = COMMANDS[args.command](args)
    except (UsageError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        print(f"mr_log: {error}", file=sys.stderr)
        return 2
    if result is None:
        print("mr_log: no matching entry", file=sys.stderr)
        return 3
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
