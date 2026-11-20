#!/usr/bin/env python3
"""Append-only JSONL ledger of planned and executed runs; the last row per seq wins."""
import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

STATES = ("planned", "running", "done", "infra_error", "no_results", "invalid")
PENDING_STATES = ("planned", "running", "no_results")
FINISHED_STATES = ("done", "infra_error")
FIELDS = (
    "seq", "variant", "environment", "sha", "state", "results_dir",
    "ci_url", "started_at", "finished_at", "observed_sha",
)


class Ledger:
    def __init__(self, path):
        self.path = Path(path)

    def _append(self, row):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")

    def _read(self):
        latest = {}
        if not self.path.exists():
            return latest
        with self.path.open(encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{self.path}:{lineno}: invalid JSON ({exc})") from exc
                latest[row["seq"]] = row
        return latest

    def plan(self, items, shas):
        existing = self._read()
        for item in items:
            if item["seq"] in existing:
                continue
            variant = item["variant"]
            if variant not in shas:
                raise ValueError(f"no sha provided for variant {variant!r}")
            row = {f: None for f in FIELDS}
            row.update(
                seq=item["seq"], variant=variant, environment=item["environment"],
                sha=shas[variant], state="planned",
            )
            self._append(row)

    def update(self, seq, **fields):
        unknown = set(fields) - set(FIELDS)
        if unknown:
            raise ValueError(f"unknown fields: {sorted(unknown)}")
        current = self._read()
        if seq not in current:
            raise KeyError(f"seq {seq} is not planned")
        row = dict(current[seq])
        row.update(fields)
        if row["state"] not in STATES:
            raise ValueError(f"unknown state {row['state']!r}")
        if row.get("observed_sha") is not None and row["observed_sha"] != row["sha"]:
            row["state"] = "invalid"
        self._append(row)
        return row

    def rows(self):
        return [row for _, row in sorted(self._read().items())]

    def pending(self):
        return [r for r in self.rows() if r["state"] in PENDING_STATES]

    def infra_ratio(self):
        finished = [r for r in self.rows() if r["state"] in FINISHED_STATES]
        if not finished:
            return 0.0
        return sum(r["state"] == "infra_error" for r in finished) / len(finished)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    sub = parser.add_subparsers(dest="command", required=True)
    p_plan = sub.add_parser("plan", help="plan runs from schedule.py JSON")
    p_plan.add_argument("--schedule", required=True, help="path to schedule JSON, or - for stdin")
    p_plan.add_argument("--shas", required=True, help="variant=sha,variant=sha")
    p_upd = sub.add_parser("update", help="append an update for one seq")
    p_upd.add_argument("--seq", required=True, type=int)
    for field in FIELDS:
        if field != "seq":
            p_upd.add_argument(f"--{field.replace('_', '-')}", dest=field)
    sub.add_parser("status", help="print counts per state and infra_ratio")
    args = parser.parse_args(argv)
    ledger = Ledger(args.path)
    try:
        if args.command == "plan":
            raw = sys.stdin.read() if args.schedule == "-" else Path(args.schedule).read_text(encoding="utf-8")
            shas = dict(pair.split("=", 1) for pair in args.shas.split(",") if pair)
            ledger.plan(json.loads(raw), shas)
        elif args.command == "update":
            fields = {f: getattr(args, f) for f in FIELDS if f != "seq" and getattr(args, f) is not None}
            if fields.get("state") == "running" and "started_at" not in fields:
                fields["started_at"] = _now()
            if fields.get("state") in FINISHED_STATES and "finished_at" not in fields:
                fields["finished_at"] = _now()
            ledger.update(args.seq, **fields)
        else:
            counts = Counter(r["state"] for r in ledger.rows())
            json.dump(
                {"counts": {s: counts.get(s, 0) for s in STATES}, "infra_ratio": ledger.infra_ratio()},
                sys.stdout, indent=2,
            )
            print()
    except (ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
