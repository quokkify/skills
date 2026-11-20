"""Normalise JUnit and Allure results of finished runs into runs.jsonl."""
import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ledger import Ledger  # noqa: E402

FORMATS = ("junit", "allure", "both")
RETRY_TAGS = ("flakyFailure", "flakyError", "rerunFailure", "rerunError")
ALLURE_STATUSES = ("passed", "failed", "broken", "skipped")


def _record(test_id, name, status, retried, start_ms, stop_ms, duration_ms,
            failure, external_id, steps):
    return {
        "test_id": test_id,
        "name": name,
        "status": status,
        "retried": retried,
        "start_ms": start_ms,
        "stop_ms": stop_ms,
        "duration_ms": duration_ms,
        "failure": failure,
        "external_id": external_id,
        "steps": steps,
    }


def _junit_file(path, data):
    records = []
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ET.ParseError(f"{path}: {exc}") from exc
    for suite in root.iter("testsuite"):
        for case in suite.findall("testcase"):
            classname = case.get("classname") or ""
            name = case.get("name") or ""
            duration_ms = round(float(case.get("time") or 0) * 1000)
            status, failure = "passed", None
            for tag, mapped in (("failure", "failed"), ("error", "broken"), ("skipped", "skipped")):
                el = case.find(tag)
                if el is not None:
                    status = mapped
                    failure = el.get("message") or (el.text or "").strip() or None
                    break
            retried = any(case.find(tag) is not None for tag in RETRY_TAGS)
            if retried:
                status = "failed"
                if failure is None:
                    el = next(case.find(t) for t in RETRY_TAGS if case.find(t) is not None)
                    failure = el.get("message") or (el.text or "").strip() or None
            # JUnit has no per-test start time; leave start/stop null rather than invent them.
            records.append(_record(f"{classname}#{name}", name, status, retried,
                                   None, None, duration_ms, failure, None, []))
    return records


def _flatten_steps(steps):
    out = []
    for step in steps or []:
        out.append({
            "name": step.get("name"),
            "start_ms": step.get("start"),
            "stop_ms": step.get("stop"),
            "status": step.get("status"),
        })
        out.extend(_flatten_steps(step.get("steps")))
    return out


def _external_id(result, label):
    if not label:
        return None
    for item in result.get("labels") or []:
        if item.get("name") == label:
            return item.get("value")
    for item in result.get("links") or []:
        if label in (item.get("name"), item.get("type")):
            return item.get("name") if item.get("type") == label else item.get("url")
    return None


def _allure_test_id(result):
    labels = {item.get("name"): item.get("value") for item in result.get("labels") or []}
    if labels.get("testClass") and labels.get("testMethod"):
        test_id = f"{labels['testClass']}#{labels['testMethod']}"
    else:
        test_id = result.get("fullName") or result.get("testCaseId")
    params = result.get("parameters") or []
    if params:
        test_id += "[" + ",".join(f"{p.get('name')}={p.get('value')}" for p in params) + "]"
    return test_id


def _reduce_duplicates(records, seq):
    """Keep one record per test_id: latest stop_ms wins (last read when missing).

    Retries are marked only by retry markers (JUnit flaky*/rerun*, Allure historyId), so a plain
    duplicate is neither retried nor failed; it is reported on stderr.
    """
    grouped = {}
    for rec in records:
        grouped.setdefault(rec["test_id"], []).append(rec)
    out = []
    for test_id, group in grouped.items():
        if len(group) == 1:
            out.append(group[0])
            continue
        best = group[0]
        for rec in group[1:]:
            stop = -1 if rec["stop_ms"] is None else rec["stop_ms"]
            best_stop = -1 if best["stop_ms"] is None else best["stop_ms"]
            if stop >= best_stop:
                best = rec
        print(f"warning: duplicate test_id {test_id} in seq {seq}; kept one", file=sys.stderr)
        out.append(best)
    return out


def _allure_dir(results_dir, label):
    by_history = {}
    for path in sorted(results_dir.rglob("*-result.json")):
        result = json.loads(path.read_text())
        key = result.get("historyId") or result.get("fullName") or result.get("uuid") or path.name
        by_history.setdefault(key, []).append(result)
    records = []
    for group in by_history.values():
        group.sort(key=lambda r: r.get("stop") or 0)
        result = group[-1]
        retried = len(group) > 1
        start, stop = result.get("start"), result.get("stop")
        duration = stop - start if start is not None and stop is not None else 0
        details = result.get("statusDetails") or {}
        status = result.get("status")
        if status not in ALLURE_STATUSES:
            status = "broken"
        records.append(_record(
            _allure_test_id(result),
            result.get("name"),
            "failed" if retried else status,
            retried, start, stop, duration,
            details.get("message") or None,
            _external_id(result, label),
            _flatten_steps(result.get("steps")),
        ))
    return records


def collect_run(results_dir, fmt, label, seq=None):
    """Return one normalised record per test found in results_dir (the results of run seq)."""
    if fmt not in FORMATS:
        raise ValueError(f"unknown format: {fmt}")
    results_dir = Path(results_dir)
    allure = _allure_dir(results_dir, label) if fmt in ("allure", "both") else []
    junit = []
    if fmt in ("junit", "both"):
        seen_hashes = set()
        for path in sorted(results_dir.rglob("TEST-*.xml")):
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest in seen_hashes:
                continue
            seen_hashes.add(digest)
            junit.extend(_junit_file(path, data))
    allure = _reduce_duplicates(allure, seq)
    junit = _reduce_duplicates(junit, seq)
    seen = {r["test_id"] for r in allure}
    return allure + [r for r in junit if r["test_id"] not in seen]


def collect(ledger_path, fmt, out, label):
    """Write one execution per test for every done run; return the count."""
    count = 0
    with Path(out).open("w") as handle:
        for row in Ledger(Path(ledger_path)).rows():
            if row.get("state") != "done" or not row.get("results_dir"):
                continue
            for record in collect_run(Path(row["results_dir"]), fmt, label, row["seq"]):
                full = {"seq": row["seq"], "variant": row["variant"],
                        "environment": row["environment"], "sha": row["sha"], **record}
                handle.write(json.dumps(full) + "\n")
                count += 1
    return count


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--format", required=True, choices=FORMATS, dest="fmt")
    parser.add_argument("--out", required=True)
    parser.add_argument("--label", default=None)
    args = parser.parse_args(argv)
    print(collect(Path(args.ledger), args.fmt, Path(args.out), args.label))


if __name__ == "__main__":
    main()
