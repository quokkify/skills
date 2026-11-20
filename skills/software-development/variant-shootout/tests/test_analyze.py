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
        rows = [{"seq": 5, "variant": "cand", "ci_url": "https://ci.example.com/2"},
                {"seq": 1, "variant": "base", "ci_url": "https://ci.example.com/1"},
                {"seq": 6, "variant": "cand", "ci_url": None}]
        r = analyze(runs, "base", "proof", iterations=ITER, retries="off", ledger_rows=rows)
        self.assertEqual(r["selection_wall_ms"]["base"], 2500)
        self.assertEqual(r["links"], {"base": ["https://ci.example.com/1"], "cand": ["https://ci.example.com/2"]})
        md = render_markdown(r, "en")
        self.assertIn("https://ci.example.com/2", md)
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

    def test_regression_guard_passes_counted_over_shared_environments_only(self):
        runs = (series("base", "e1", "t", [1000] * 5) + [rec(10, "base", "e2", "t", dur=1000)]
                + series("cand", "e1", "t", [0] * 5, start=20, status="failed")
                + [rec(30, "cand", "e2", "t", dur=500), rec(31, "cand", "e3", "t", dur=500)])
        e = entry(analyze(runs, "base", "proof", iterations=ITER), "t", "cand")
        self.assertEqual(e["time_verdict"], "insufficient data")
        self.assertIsNone(e["delta_ms"])

    def test_ru_findings_keep_dimension(self):
        runs = (series("base", "e1", "t", [1000 + i for i in range(20)])
                + series("cand", "e1", "t", [500 + i for i in range(20)], start=100))
        md = render_markdown(analyze(runs, "base", "proof", iterations=ITER), "ru")
        self.assertIn("время", md)
        self.assertIn("стабильность", md)

    def test_quick_mode_does_not_title_findings_as_proven(self):
        runs = (series("base", "e1", "t", [1000 + i for i in range(20)])
                + series("cand", "e1", "t", [500 + i for i in range(20)], start=100))
        md = render_markdown(analyze(runs, "base", "quick", iterations=ITER), "en")
        self.assertNotIn("What is proven", md)
        self.assertIn("Indicative findings (not proof)", md)
        ru = render_markdown(analyze(runs, "base", "quick", iterations=ITER), "ru")
        self.assertIn("Предварительные выводы (не доказательство)", ru)

    def test_absent_baseline_or_empty_n_is_insufficient_stability(self):
        runs = series("base", "e1", "other", [1, 2, 3]) + series("cand", "e1", "t", [1, 2, 3], start=10)
        runs += series("cand", "e1", "other", [1, 2, 3], start=20)
        e = entry(analyze(runs, "base", "quick", iterations=ITER), "t", "cand")
        self.assertEqual(e["stability_verdict"], "insufficient data")

    def test_floor_needs_three_executions(self):
        runs = series("base", "e1", "t", [1, 2]) + series("cand", "e1", "t", [1, 2], start=10)
        e = entry(analyze(runs, "base", "quick", iterations=ITER), "t", "cand")
        self.assertIsNone(e["fail_rate_floor"])

    def test_all_insufficient_has_no_no_difference_verdict(self):
        runs = [rec(0, "base", "e1", "other"), rec(1, "cand", "e1", "other", status="skipped"),
                rec(2, "cand", "e1", "t")]
        from strings import STRINGS
        for lang in ("en", "ru"):
            md = render_markdown(analyze(runs, "base", "proof", iterations=ITER), lang)
            self.assertNotIn(STRINGS[lang]["verdict_none"], md)
            self.assertIn(STRINGS[lang]["verdict_insufficient"], md)

    def test_cli_writes_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            runs = series("base", "e1", "t", [1000, 1001, 999]) + series("cand", "e1", "t", [900, 901, 899], start=10)
            (d / "runs.jsonl").write_text("\n".join(json.dumps(x) for x in runs) + "\n")
            led = Ledger(d / "ledger.jsonl")
            led.plan([{"seq": 0, "variant": "base", "environment": "e1"}], {"base": "abc"})
            led.update(0, ci_url="https://ci.example.com/9")
            proc = subprocess.run(
                [sys.executable, str(SKILL / "scripts" / "analyze.py"), "--runs", str(d / "runs.jsonl"),
                 "--ledger", str(d / "ledger.jsonl"), "--baseline", "base", "--mode", "quick",
                 "--lang", "ru", "--out", str(d / "out")], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads((d / "out" / "report.json").read_text())["mode"], "quick")
            self.assertIn("ориентировочно", (d / "out" / "report.md").read_text())
            self.assertIn("https://ci.example.com/9", (d / "out" / "report.md").read_text())



def faster_runs():
    return (series("base", "e1", "t", [1000 + i for i in range(20)])
            + series("cand", "e1", "t", [500 + i for i in range(20)], start=100))


class ExcludedRunsTest(unittest.TestCase):
    def test_infra_error_row_is_reported_and_link_marked(self):
        rows = [{"seq": 0, "variant": "base", "state": "done", "ci_url": "https://ci.example.com/0"},
                {"seq": 1, "variant": "cand", "state": "infra_error", "ci_url": "https://ci.example.com/1"},
                {"seq": 2, "variant": "cand", "state": "invalid", "ci_url": None},
                {"seq": 3, "variant": "cand", "state": "no_results", "ci_url": None},
                {"seq": 4, "variant": "cand", "state": "infra_error", "ci_url": None}]
        r = analyze(faster_runs(), "base", "proof", iterations=ITER, ledger_rows=rows)
        self.assertEqual(r["excluded_runs"], {
            "base": {"infra_error": 0, "invalid": 0, "no_results": 0},
            "cand": {"infra_error": 2, "invalid": 1, "no_results": 1}})
        self.assertNotIn("infra", entry(r, "t", "cand"))
        md = render_markdown(r, "en")
        not_proven = md.split("## What is not proven")[1].split("## Links")[0]
        self.assertIn("`cand` excluded: 2 infra_error, 1 invalid, 1 without results", not_proven)
        self.assertNotIn("`base` excluded", not_proven)
        self.assertIn("https://ci.example.com/1 (infra_error)", md)
        self.assertIn("https://ci.example.com/0", md)
        self.assertNotIn("https://ci.example.com/0 (", md)
        ru = render_markdown(r, "ru")
        self.assertIn("`cand` исключено: 2 infra_error, 1 invalid, 1 без результатов", ru)

    def test_cli_reads_excluded_counts_from_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "runs.jsonl").write_text("\n".join(json.dumps(x) for x in faster_runs()) + "\n")
            led = Ledger(d / "ledger.jsonl")
            led.plan([{"seq": 0, "variant": "base", "environment": "e1"},
                      {"seq": 1, "variant": "cand", "environment": "e1"}], {"base": "abc", "cand": "def"})
            led.update(0, state="done")
            led.update(1, state="infra_error", ci_url="https://ci.example.com/7")
            proc = subprocess.run(
                [sys.executable, str(SKILL / "scripts" / "analyze.py"), "--runs", str(d / "runs.jsonl"),
                 "--ledger", str(d / "ledger.jsonl"), "--baseline", "base", "--mode", "proof",
                 "--out", str(d / "out")], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            md = (d / "out" / "report.md").read_text()
            self.assertIn("`cand` excluded: 1 infra_error, 0 invalid, 0 without results", md)
            self.assertIn("https://ci.example.com/7 (infra_error)", md)



class MultipleComparisonsTest(unittest.TestCase):
    def test_line_counts_non_insufficient_verdicts(self):
        runs = faster_runs() + series("base", "e1", "u", [1000, 1010, 990], start=300)
        runs += [rec(400, "cand", "e1", "u", dur=500)]
        runs += series("cand2", "e1", "t", [1000 + i for i in range(20)], start=500)
        r = analyze(runs, "base", "proof", iterations=ITER)
        # cand/t: time + stability; cand/u: stability only (time insufficient); cand2/t: time + stability
        self.assertEqual(r["comparisons"], 5)
        md = render_markdown(r, "en")
        not_proven = md.split("## What is not proven")[1].split("## Links")[0]
        self.assertIn("5 comparisons were tested at α = 0.05; about 5 × 0.05 = 0.25 of the "
                      "'proven' lines could be chance", not_proven)
        ru = render_markdown(r, "ru")
        self.assertIn("Проверено сравнений: 5 при α = 0.05; примерно 5 × 0.05 = 0.25", ru)

    def test_line_present_even_with_zero_comparisons(self):
        runs = [rec(0, "base", "e1", "other"), rec(2, "cand", "e1", "t")]
        r = analyze(runs, "base", "proof", iterations=ITER)
        self.assertEqual(r["comparisons"], 0)
        self.assertIn("0 comparisons were tested at α = 0.05", render_markdown(r, "en"))



class MethodLabelTest(unittest.TestCase):
    def test_method_line_names_runs_not_executions(self):
        md = render_markdown(analyze(faster_runs(), "base", "proof", iterations=ITER), "en")
        self.assertIn("- Runs per variant: `base`: 20, `cand`: 20", md)
        self.assertNotIn("Executions per variant", md)



def failing(seq, variant, test, message):
    r = rec(seq, variant, "e1", test, status="failed")
    r["failure"] = message
    return r


class ReportContentTest(unittest.TestCase):
    def test_failure_reasons_top_three_grouped(self):
        long = "y" * 200
        runs = series("base", "e1", "t", [1000] * 3)
        runs += [failing(10 + i, "base", "t", "boom\n at Foo.java:1") for i in range(3)]
        runs += [failing(20 + i, "base", "t", "timeout") for i in range(2)]
        runs += [failing(30, "base", "t", long), failing(31, "base", "t", None)]
        runs += [failing(32, "base", "t", None)]
        runs += series("cand", "e1", "t", [900] * 3, start=40) + [failing(50, "cand", "t", "boom")]
        r = analyze(runs, "base", "proof", iterations=ITER)
        self.assertEqual(r["failure_reasons"], [
            {"test_id": "t", "variant": "base", "reasons": [
                {"message": "boom", "count": 3}, {"message": None, "count": 2},
                {"message": "timeout", "count": 2}]},
            {"test_id": "t", "variant": "cand", "reasons": [{"message": "boom", "count": 1}]},
        ])
        runs.append(failing(33, "cand", "t", long))
        reasons = analyze(runs, "base", "proof", iterations=ITER)["failure_reasons"][1]["reasons"]
        self.assertIn({"message": "y" * 120, "count": 1}, reasons)
        md = render_markdown(r, "en")
        section = md.split("## Failures by reason")[1].split("## Verdict")[0]
        self.assertIn("- `base` on `t`: 3× `boom`; 2× (no message); 2× `timeout`", section)
        self.assertIn("- `cand` on `t`: 1× `boom`", section)
        ru = render_markdown(r, "ru")
        self.assertIn("## Падения по причинам", ru)
        self.assertIn("2× (без сообщения)", ru)

    def test_no_failure_section_without_failures(self):
        md = render_markdown(analyze(faster_runs(), "base", "proof", iterations=ITER), "en")
        self.assertNotIn("Failures by reason", md)

    def test_per_environment_table_only_with_several_environments(self):
        one = render_markdown(analyze(faster_runs(), "base", "proof", iterations=ITER), "en")
        self.assertNotIn("Per environment", one)
        runs = (series("base", "e1", "t", [1000] * 3) + series("base", "e2", "t", [2000] * 3, start=10)
                + series("cand", "e1", "t", [900] * 3, start=20)
                + series("cand", "e2", "t", [2100] * 2, start=30) + [failing(40, "cand", "t", "x")])
        for r in runs:
            if r["seq"] == 40:
                r["environment"] = "e2"
        r = analyze(runs, "base", "proof", iterations=ITER)
        md = render_markdown(r, "en")
        section = md.split("### Per environment")[1].split("## ")[0]
        self.assertIn("| Test | Variant | Environment | N | Failed | Median, s | Delta median, s |", section)
        self.assertIn("| t | base | e1 | 3 | 0 | 1.0 | n/a |", section)
        self.assertIn("| t | cand | e1 | 3 | 0 | 0.9 | -0.1 |", section)
        self.assertIn("| t | cand | e2 | 3 | 1 | 2.1 | +0.1 |", section)
        self.assertIn("### По окружениям", render_markdown(r, "ru"))

    def test_wall_time_secondary_line_per_variant(self):
        runs = [rec(1, "base", "e1", "a", dur=1000), rec(1, "base", "e1", "b", dur=500)]
        runs[1]["start_ms"] = runs[0]["start_ms"] + 2000
        runs[1]["stop_ms"] = runs[1]["start_ms"] + 500
        runs += series("cand", "e1", "a", [1, 2], start=5)
        for r in runs:
            if r["variant"] == "cand":
                r["start_ms"] = r["stop_ms"] = None
        r = analyze(runs, "base", "proof", iterations=ITER)
        md = render_markdown(r, "en")
        results = md.split("## Results")[1].split("## Verdict")[0]
        self.assertIn("- `base`: selection wall time 2.5 s (median per run; secondary, not a verdict)", results)
        self.assertIn("- `cand`: selection wall time n/a (no test timestamps)", results)
        ru = render_markdown(r, "ru")
        self.assertIn("- `base`: время всего прогона выборки 2.5 с (медиана по запускам; вторичная метрика, не вердикт)", ru)
        self.assertIn("- `cand`: время всего прогона выборки н/д (нет отметок времени тестов)", ru)


if __name__ == "__main__":
    unittest.main()
