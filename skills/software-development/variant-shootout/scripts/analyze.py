#!/usr/bin/env python3
"""Turn normalised executions into per-test verdicts and a paste-ready Markdown block."""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ledger import Ledger  # noqa: E402
from stats import (  # noqa: E402
    bootstrap_median_delta,
    fisher_two_sided,
    iqr,
    median,
    rule_of_three,
    wilson,
)
from strings import STRINGS  # noqa: E402

ALPHA = 0.05
MIN_FLOOR_N = 3
TOP_REASONS = 3
REASON_CHARS = 120
MODES = ("quick", "proof")
RETRIES = ("off", "unknown")
DEFAULT_ITERATIONS = 10000
EXCLUDED_STATES = ("infra_error", "invalid", "no_results")
NMD = "no measurable difference"
INSUFFICIENT = "insufficient data"


def _counts(records):
    live = [r for r in records if r["status"] != "skipped"]
    passed = [r for r in live if r["status"] == "passed"]
    failed = [r for r in live if r["status"] in ("failed", "broken")]
    return live, passed, failed


def _durations(records):
    return [float(r["duration_ms"]) for r in records if r.get("duration_ms") is not None]


def _by_env(records):
    out = {}
    for r in records:
        out.setdefault(r["environment"], []).append(r)
    return out


def _per_environment(cand_recs, base_recs, is_base):
    base_env = _by_env(base_recs)
    result = {}
    for env, recs in sorted(_by_env(cand_recs).items()):
        live, passed, failed = _counts(recs)
        durs = _durations(passed)
        delta = None
        if not is_base and durs:
            bdurs = _durations(_counts(base_env.get(env, []))[1])
            if bdurs:
                delta = median(durs) - median(bdurs)
        result[env] = {
            "n": len(live), "passed": len(passed), "failed": len(failed),
            "median_ms": median(durs) if durs else None, "delta_ms": delta,
        }
    return result


def _time_comparison(base_recs, cand_recs, iterations):
    benv = {e: _durations(_counts(r)[1]) for e, r in _by_env(base_recs).items()}
    cenv = {e: _durations(_counts(r)[1]) for e, r in _by_env(cand_recs).items()}
    shared = [e for e in benv if benv[e] and cenv.get(e)]
    if not shared:
        return None, None, INSUFFICIENT
    if sum(len(benv[e]) for e in shared) < 2 or sum(len(cenv[e]) for e in shared) < 2:
        return None, None, INSUFFICIENT
    delta, lo, hi = bootstrap_median_delta(
        {e: benv[e] for e in shared}, {e: cenv[e] for e in shared}, iterations=iterations
    )
    if hi < 0:
        verdict = "faster"
    elif lo > 0:
        verdict = "slower"
    else:
        verdict = NMD
    return delta, [lo, hi], verdict


def _entry(test_id, variant, recs, base_recs, is_base, iterations):
    live, passed, failed = _counts(recs)
    durs = _durations(passed)
    n = len(live)
    entry = {
        "test_id": test_id, "variant": variant, "n": n,
        "passed": len(passed), "failed": len(failed),
        "median_ms": median(durs) if durs else None,
        "mean_ms": sum(durs) / len(durs) if durs else None,
        "min_ms": min(durs) if durs else None,
        "max_ms": max(durs) if durs else None,
        "iqr_ms": (iqr(durs)[1] - iqr(durs)[0]) if durs else None,
        "delta_ms": None, "ci_ms": None, "time_verdict": None,
        "fail_rate_ci": list(wilson(len(failed), n)) if n else None,
        "fail_rate_floor": rule_of_three(n) if n >= MIN_FLOOR_N and not failed else None,
        "fisher_p": None,
        "stability_verdict": "baseline" if is_base else NMD,
        "per_environment": _per_environment(recs, base_recs, is_base),
    }
    if not is_base:
        delta, ci, verdict = _time_comparison(base_recs, recs, iterations)
        entry["delta_ms"], entry["ci_ms"], entry["time_verdict"] = delta, ci, verdict
        bn = len(_counts(base_recs)[0])
        if not (n and bn):
            entry["stability_verdict"] = INSUFFICIENT
        else:
            bk = len(_counts(base_recs)[2])
            p = fisher_two_sided(bk, bn, len(failed), n)
            entry["fisher_p"] = p
            if p < ALPHA:
                entry["stability_verdict"] = (
                    "less flaky" if len(failed) / n < bk / bn else "more flaky"
                )
    return entry


def _failure_reasons(test_id, variant, recs):
    counts = {}
    for r in _counts(recs)[2]:
        msg = (r.get("failure") or "").strip()
        key = msg.splitlines()[0][:REASON_CHARS] if msg else None
        counts[key] = counts.get(key, 0) + 1
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0] or ""))[:TOP_REASONS]
    return {"test_id": test_id, "variant": variant,
            "reasons": [{"message": m, "count": c} for m, c in top]}


def _selection_wall(runs, variant):
    by_seq = {}
    for r in runs:
        if r["variant"] == variant:
            by_seq.setdefault(r["seq"], []).append(r)
    walls = []
    for recs in by_seq.values():
        starts = [r["start_ms"] for r in recs if r.get("start_ms") is not None and r.get("stop_ms") is not None]
        stops = [r["stop_ms"] for r in recs if r.get("start_ms") is not None and r.get("stop_ms") is not None]
        if starts:
            walls.append(max(stops) - min(starts))
    return median(walls) if walls else None


def analyze(runs, baseline, mode, iterations=DEFAULT_ITERATIONS, retries="unknown",
            lang="en", ledger_rows=None):
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if retries not in RETRIES:
        raise ValueError(f"retries must be one of {RETRIES}")
    variants_seen = {r["variant"] for r in runs}
    if baseline not in variants_seen:
        raise ValueError(f"baseline {baseline!r} has no executions")
    variants = [baseline] + sorted(variants_seen - {baseline})

    grouped = {}
    for r in runs:
        grouped.setdefault(r["test_id"], {}).setdefault(r["variant"], []).append(r)

    tests, missing, disagreement, reasons = [], [], [], []
    for test_id in sorted(grouped):
        per_variant = grouped[test_id]
        absent = [v for v in variants if v not in per_variant]
        if absent:
            missing.append({"test_id": test_id, "absent_in": absent})
        base_recs = per_variant.get(baseline, [])
        signs = set()
        for v in variants:
            if v not in per_variant:
                continue
            e = _entry(test_id, v, per_variant[v], base_recs, v == baseline, iterations)
            tests.append(e)
            if e["failed"]:
                reasons.append(_failure_reasons(test_id, v, per_variant[v]))
            for env in e["per_environment"].values():
                d = env["delta_ms"]
                if d is not None and d != 0:
                    signs.add((v, d > 0))
        for v in variants:
            if (v, True) in signs and (v, False) in signs:
                disagreement.append(test_id)
                break

    links = {v: [] for v in variants}
    link_states = {}
    excluded = {v: dict.fromkeys(EXCLUDED_STATES, 0) for v in variants}
    for row in sorted(ledger_rows or [], key=lambda x: x["seq"]):
        state = row.get("state")
        if state in EXCLUDED_STATES:
            excluded.setdefault(row["variant"], dict.fromkeys(EXCLUDED_STATES, 0))[state] += 1
        if row.get("ci_url") and row["variant"] in links:
            links[row["variant"]].append(row["ci_url"])
            if state not in (None, "done"):
                link_states[row["ci_url"]] = state

    comparisons = sum(
        verdict not in (None, INSUFFICIENT)
        for t in tests if t["variant"] != baseline
        for verdict in (t["time_verdict"], t["stability_verdict"])
    )

    return {
        "baseline": baseline, "mode": mode, "lang": lang, "retries": retries,
        "variants": variants,
        "environments": sorted({r["environment"] for r in runs}),
        "runs_per_variant": {v: len({r["seq"] for r in runs if r["variant"] == v}) for v in variants},
        "tests": tests, "missing": missing, "failure_reasons": reasons,
        "selection_wall_ms": {v: _selection_wall(runs, v) for v in variants},
        "environment_disagreement": disagreement,
        "links": links,
        "link_states": link_states,
        "excluded_runs": excluded,
        "alpha": ALPHA,
        "comparisons": comparisons,
    }


def _sec(ms):
    return "n/a" if ms is None else f"{ms / 1000:.1f}"


def _signed(ms):
    return "n/a" if ms is None else f"{ms / 1000:+.1f}"


def _pct(x):
    return f"{x * 100:.0f}"


def _row(cells):
    return "| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |"


def render_markdown(report, lang="en"):
    s = STRINGS[lang]
    vt = s["verdicts"]
    base = report["baseline"]
    candidates = [v for v in report["variants"] if v != base]
    runs = ", ".join(f"`{v}`: {n}" for v, n in report["runs_per_variant"].items())
    out = [f"# {s['title']}", "", f"## {s['method']}", ""]
    out.append(f"- {s['method_runs'].format(runs=runs)}")
    out.append(f"- {s['method_baseline'].format(baseline=base, candidates=', '.join(f'`{c}`' for c in candidates) or '-')}")
    out.append(f"- {s['method_envs'].format(envs=', '.join(report['environments']))}")
    out.append(f"- {s['method_mode'].format(mode=s['mode_' + report['mode']])}")
    out.append(f"- {s['method_retries_off'] if report['retries'] == 'off' else s['method_retries_unknown']}")
    out.append(f"- {s['method_interleave']}")

    out += ["", f"## {s['results']}", ""]
    cols = ["col_test", "col_variant", "col_n", "col_median", "col_delta", "col_time", "col_failures", "col_stability"]
    out.append(_row([s[c] for c in cols]))
    out.append("|" + "---|" * len(cols))
    cand_entries = [t for t in report["tests"] if t["variant"] != base]
    for t in cand_entries:
        if t["ci_ms"] is None:
            delta = "n/a"
        else:
            delta = f"{_signed(t['delta_ms'])} ({_signed(t['ci_ms'][0])}; {_signed(t['ci_ms'][1])})"
        ci = t["fail_rate_ci"]
        fails = f"{t['failed']}/{t['n']}"
        if ci:
            fails += f" ({_pct(ci[0])}%-{_pct(ci[1])}%)"
        row = [t["test_id"], t["variant"], str(t["n"]), _sec(t["median_ms"]), delta,
               vt[t["time_verdict"]], fails, vt[t["stability_verdict"]]]
        out.append(_row(row))
    out.append("")
    for v in report["variants"]:
        wall = report["selection_wall_ms"].get(v)
        line = s["wall_none"] if wall is None else s["wall_line"]
        out.append(f"- {line.format(variant=v, wall=_sec(wall))}")

    if len(report["environments"]) > 1:
        out += ["", f"### {s['per_env']}", ""]
        env_cols = ["col_test", "col_variant", "col_env", "col_n", "col_failed", "col_median", "col_env_delta"]
        out.append(_row([s[c] for c in env_cols]))
        out.append("|" + "---|" * len(env_cols))
        for t in report["tests"]:
            for env, e in t["per_environment"].items():
                out.append(_row([t["test_id"], t["variant"], env, str(e["n"]), str(e["failed"]),
                                 _sec(e["median_ms"]), _signed(e["delta_ms"])]))

    if report["failure_reasons"]:
        out += ["", f"## {s['failures']}", ""]
        for item in report["failure_reasons"]:
            parts = "; ".join(
                f"{x['count']}× " + (s["no_message"] if x["message"] is None
                                     else "`" + x["message"].replace("`", "'") + "`")
                for x in item["reasons"])
            out.append(f"- {s['failure_line'].format(variant=item['variant'], test=item['test_id'], reasons=parts)}")

    proven, unproven = [], []
    for t in cand_entries:
        for dim, verdict in (("dim_time", t["time_verdict"]), ("dim_stability", t["stability_verdict"])):
            line = s["verdict_line"].format(
                variant=t["variant"], test=t["test_id"], dim=s[dim], finding=vt[verdict])
            if verdict in ("faster", "slower", "more flaky", "less flaky"):
                proven.append(line)
            else:
                unproven.append(s["not_proven_line"].format(
                    variant=t["variant"], test=t["test_id"], dim=s[dim], finding=vt[verdict]))
    floors = []
    for t in report["tests"]:
        if t["fail_rate_floor"] is not None:
            floors.append(s["floor_line"].format(
                k=t["failed"], n=t["n"], pct=_pct(t["fail_rate_floor"]),
                variant=t["variant"], test=t["test_id"]))

    quick = report["mode"] == "quick"
    verdicts = [v for t in cand_entries for v in (t["time_verdict"], t["stability_verdict"])]
    out += ["", f"## {s['verdict']}", ""]
    if proven:
        summary = [f"- {x}" for x in proven]
        out += ([s["verdict_quick_prefix"], ""] if quick else []) + summary
    elif NMD in verdicts:
        out.append(s["verdict_none"])
    else:
        out.append(s["verdict_insufficient"])
    out += ["", f"## {s['proven_quick'] if quick else s['proven']}", ""]
    out += [f"- {x}" for x in proven] if proven else [s["proven_none"]]

    extra = []
    if report["mode"] == "quick":
        extra.append(s["quick_label"])
    if report["retries"] == "unknown":
        extra.append(s["retries_hidden"])
    if report["environment_disagreement"]:
        extra.append(s["env_disagreement"].format(
            tests=", ".join(f"`{t}`" for t in report["environment_disagreement"])))
    if report["missing"]:
        items = ", ".join(s["missing_item"].format(
            test=m["test_id"], variants=", ".join(m["absent_in"])) for m in report["missing"])
        extra.append(s["missing"].format(items=items))
    for v, counts in report["excluded_runs"].items():
        if any(counts.values()):
            extra.append(s["excluded_line"].format(
                variant=v, infra=counts["infra_error"], invalid=counts["invalid"],
                no_results=counts["no_results"]))
    c, alpha = report["comparisons"], report["alpha"]
    extra.append(s["comparisons_line"].format(c=c, alpha=f"{alpha:g}", x=f"{c * alpha:.2f}"))
    out += ["", f"## {s['not_proven']}", ""]
    items = extra + unproven + floors
    out += [f"- {x}" for x in items] if items else [s["not_proven_none"]]

    out += ["", f"## {s['links']}", ""]
    states = report["link_states"]

    def _link(url):
        return f"{url} ({states[url]})" if url in states else url

    link_lines = [s["link_line"].format(variant=v, urls=", ".join(_link(x) for x in u))
                  for v, u in report["links"].items() if u]
    out += [f"- {x}" for x in link_lines] if link_lines else [s["links_none"]]
    return "\n".join(out) + "\n"


def _load_runs(path):
    runs = []
    with Path(path).open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            if line.strip():
                try:
                    runs.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{lineno}: invalid JSON ({exc})") from exc
    return runs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", required=True)
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--mode", choices=MODES, required=True)
    ap.add_argument("--lang", choices=sorted(STRINGS), default="en")
    ap.add_argument("--retries", choices=RETRIES, default="unknown")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    try:
        report = analyze(_load_runs(args.runs), args.baseline, args.mode, retries=args.retries,
                         lang=args.lang, ledger_rows=Ledger(args.ledger).rows())
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "report.md").write_text(render_markdown(report, args.lang), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
