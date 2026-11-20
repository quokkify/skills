import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

from analyze import analyze, render_markdown  # noqa: E402
from ledger import Ledger  # noqa: E402

ITER = 300


def rec(seq, variant, env, test, status="passed", dur=1000, retried=False):
    return {
        "seq": seq, "variant": variant, "environment": env, "sha": "abc",
        "test_id": test, "name": test, "status": status, "retried": retried,
        "start_ms": seq * 100000, "stop_ms": seq * 100000 + dur, "duration_ms": dur,
        "failure": None, "external_id": None, "steps": [],
    }


def series(variant, env, test, durs, start=0, **kw):
    return [rec(start + i, variant, env, test, dur=d, **kw) for i, d in enumerate(durs)]


def entry(report, test, variant):
    return next(t for t in report["tests"] if t["test_id"] == test and t["variant"] == variant)


class AnalyzeTest(unittest.TestCase):
    def test_insufficient_data_when_one_pass(self):
        runs = series("base", "e1", "t", [1000, 1010, 990]) + [rec(10, "cand", "e1", "t", dur=500)]
        e = entry(analyze(runs, "base", "quick", iterations=ITER), "t", "cand")
        self.assertEqual(e["time_verdict"], "insufficient data")
        self.assertIsNone(e["delta_ms"])
        self.assertIsNone(e["ci_ms"])

    def test_faster_verdict(self):
        runs = (series("base", "e1", "t", [1000 + i for i in range(20)])
                + series("cand", "e1", "t", [500 + i for i in range(20)], start=100))
        r = analyze(runs, "base", "proof", iterations=ITER)
        e = entry(r, "t", "cand")
        self.assertEqual(e["time_verdict"], "faster")
        self.assertLess(e["ci_ms"][1], 0)
        self.assertLess(e["delta_ms"], 0)
        b = entry(r, "t", "base")
        self.assertEqual(b["stability_verdict"], "baseline")
        self.assertIsNone(b["time_verdict"])
        self.assertEqual(r["variants"], ["base", "cand"])

    def test_slower_and_no_difference(self):
        runs = (series("base", "e1", "t", [1000 + i for i in range(20)])
                + series("cand", "e1", "t", [2000 + i for i in range(20)], start=100)
                + series("base", "e1", "u", [1000, 1100, 900, 1050] * 5, start=200)
                + series("cand", "e1", "u", [1000, 1100, 900, 1050] * 5, start=300))
        r = analyze(runs, "base", "proof", iterations=ITER)
        self.assertEqual(entry(r, "t", "cand")["time_verdict"], "slower")
        self.assertEqual(entry(r, "u", "cand")["time_verdict"], "no measurable difference")

    def test_quick_mode_label_present(self):
        runs = (series("base", "e1", "t", [1000, 1001, 1002])
                + series("cand", "e1", "t", [900, 901, 902], start=10))
        r = analyze(runs, "base", "quick", iterations=ITER)
        self.assertIn("indicative", render_markdown(r, "en"))
        self.assertIn("ориентировочно", render_markdown(r, "ru"))
        r2 = analyze(runs, "base", "proof", iterations=ITER)
        self.assertNotIn("indicative", render_markdown(r2, "en"))

    def test_missing_test_flagged(self):
        runs = (series("base", "e1", "t", [1, 2, 3]) + series("cand", "e1", "t", [1, 2, 3], start=10)
                + series("base", "e1", "only_base", [1, 2], start=20))
        r = analyze(runs, "base", "quick", iterations=ITER)
        self.assertEqual(r["missing"], [{"test_id": "only_base", "absent_in": ["cand"]}])
        self.assertIn("only_base", render_markdown(r, "en"))

    def test_environment_disagreement(self):
        runs = (series("base", "e1", "t", [1000] * 3) + series("base", "e2", "t", [1000] * 3, start=10)
                + series("cand", "e1", "t", [990] * 3, start=20)
                + series("cand", "e2", "t", [1010] * 3, start=30))
        r = analyze(runs, "base", "quick", iterations=ITER)
        self.assertEqual(r["environment_disagreement"], ["t"])
        self.assertEqual(entry(r, "t", "cand")["per_environment"]["e1"]["delta_ms"], -10)
        self.assertEqual(entry(r, "t", "cand")["per_environment"]["e2"]["delta_ms"], 10)

    def test_retried_counts_as_failure(self):
        runs = [rec(i, "base", "e1", "t") for i in range(4)]
        runs += [rec(10, "cand", "e1", "t", status="failed", retried=True)]
        runs += [rec(11 + i, "cand", "e1", "t") for i in range(3)]
        runs += [rec(20, "cand", "e1", "t", status="skipped")]
        e = entry(analyze(runs, "base", "quick", iterations=ITER), "t", "cand")
        self.assertEqual((e["n"], e["passed"], e["failed"]), (4, 3, 1))

    def test_stability_verdict_and_floor(self):
        runs = ([rec(i, "base", "e1", "t", status="failed" if i < 12 else "passed") for i in range(30)]
                + [rec(100 + i, "cand", "e1", "t") for i in range(30)])
        r = analyze(runs, "base", "proof", iterations=ITER)
        e = entry(r, "t", "cand")
        self.assertEqual(e["stability_verdict"], "less flaky")
        self.assertAlmostEqual(e["fail_rate_floor"], 0.1)
        self.assertIsNone(entry(r, "t", "base")["fail_rate_floor"])
        self.assertIn("0/30 failed: failure rate likely below 10%", render_markdown(r, "en"))

    def test_selection_wall_and_links_and_retries(self):
        runs = [rec(1, "base", "e1", "a", dur=1000), rec(1, "base", "e1", "b", dur=500)]
        runs[1]["start_ms"] = runs[0]["start_ms"] + 2000
        runs[1]["stop_ms"] = runs[1]["start_ms"] + 500
        runs += series("cand", "e1", "a", [1, 2], start=5)
        rows = [{"seq": 5, "variant": "cand", "ci_url": "https://ci.example/2"},
                {"seq": 1, "variant": "base", "ci_url": "https://ci.example/1"},
                {"seq": 6, "variant": "cand", "ci_url": None}]
        r = analyze(runs, "base", "proof", iterations=ITER, retries="off", ledger_rows=rows)
        self.assertEqual(r["selection_wall_ms"]["base"], 2500)
        self.assertEqual(r["links"], {"base": ["https://ci.example/1"], "cand": ["https://ci.example/2"]})
        md = render_markdown(r, "en")
        self.assertIn("https://ci.example/2", md)
        self.assertNotIn("hidden failures", md)
        r2 = analyze(runs, "base", "proof", iterations=ITER, retries="unknown")
        self.assertIn("hidden failures", render_markdown(r2, "en"))

    def test_proven_section_lists_only_findings(self):
        runs = (series("base", "e1", "t", [1000 + i for i in range(20)])
                + series("cand", "e1", "t", [500 + i for i in range(20)], start=100))
        md = render_markdown(analyze(runs, "base", "proof", iterations=ITER), "en")
        proven = md.split("## What is proven")[1].split("## What is not proven")[0]
        self.assertIn("faster", proven)
        self.assertNotIn("no measurable difference", proven)

    def test_cli_writes_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            runs = series("base", "e1", "t", [1000, 1001, 999]) + series("cand", "e1", "t", [900, 901, 899], start=10)
            (d / "runs.jsonl").write_text("\n".join(json.dumps(x) for x in runs) + "\n")
            led = Ledger(d / "ledger.jsonl")
            led.plan([{"seq": 0, "variant": "base", "environment": "e1"}], {"base": "abc"})
            led.update(0, ci_url="https://ci.example/9")
            proc = subprocess.run(
                [sys.executable, str(SKILL / "scripts" / "analyze.py"), "--runs", str(d / "runs.jsonl"),
                 "--ledger", str(d / "ledger.jsonl"), "--baseline", "base", "--mode", "quick",
                 "--lang", "ru", "--out", str(d / "out")], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads((d / "out" / "report.json").read_text())["mode"], "quick")
            self.assertIn("ориентировочно", (d / "out" / "report.md").read_text())
            self.assertIn("https://ci.example/9", (d / "out" / "report.md").read_text())


if __name__ == "__main__":
    unittest.main()
