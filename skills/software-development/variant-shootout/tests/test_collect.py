import io
import json
import shutil
import sys
from contextlib import redirect_stderr
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from collect import collect, collect_run  # noqa: E402
from ledger import Ledger  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"


def by_name(records, name):
    return [r for r in records if r["name"] == name]


class CollectTest(unittest.TestCase):
    def setUp(self):
        self.junit = collect_run(FIX / "junit" / "basic", "junit", None)
        self.allure = collect_run(FIX / "allure" / "basic", "allure", "tms")

    def test_junit_passed(self):
        rec = [r for r in self.junit if r["test_id"] == "com.example.CartTest#addsItem"][0]
        self.assertEqual(rec["status"], "passed")
        self.assertEqual(rec["duration_ms"], 250)
        self.assertIsNone(rec["start_ms"])
        self.assertFalse(rec["retried"])

    def test_junit_failed_message(self):
        rec = by_name(self.junit, "removesItem")[0]
        self.assertEqual(rec["status"], "failed")
        self.assertIn("expected 0 but was 1", rec["failure"])

    def test_junit_flaky_failure_is_retried_failed(self):
        rec = by_name(self.junit, "appliesCoupon")[0]
        self.assertTrue(rec["retried"])
        self.assertEqual(rec["status"], "failed")

    def test_same_method_two_classes(self):
        ids = {r["test_id"] for r in by_name(self.junit, "addsItem")}
        self.assertEqual(ids, {"com.example.CartTest#addsItem", "com.example.OrderTest#addsItem"})

    def test_allure_same_history_id_retried(self):
        recs = by_name(self.allure, "retries")
        self.assertEqual(len(recs), 1)
        self.assertTrue(recs[0]["retried"])
        self.assertEqual(recs[0]["status"], "failed")
        self.assertEqual(recs[0]["stop_ms"], 3500)

    def test_allure_steps_without_times(self):
        rec = by_name(self.allure, "refunds")[0]
        self.assertEqual(rec["duration_ms"], 300)
        self.assertEqual(rec["failure"], "refund rejected")
        self.assertEqual(len(rec["steps"]), 1)
        self.assertIsNone(rec["steps"][0]["start_ms"])

    def test_allure_steps_flattened_depth_first(self):
        rec = by_name(self.allure, "pays")[0]
        self.assertEqual([s["name"] for s in rec["steps"]], ["open", "inner", "submit"])
        self.assertEqual(rec["test_id"], "com.example.PayTest.pays")
        self.assertEqual(rec["duration_ms"], 400)

    def test_external_id_from_tms_link(self):
        self.assertEqual(by_name(self.allure, "pays")[0]["external_id"], "C123")
        self.assertIsNone(by_name(self.allure, "refunds")[0]["external_id"])


class CollectLedgerTest(unittest.TestCase):
    def test_collect_writes_only_done_rows_with_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            ledger = Ledger(tmp / "ledger.jsonl")
            ledger.plan(
                [
                    {"seq": 1, "variant": "base", "environment": "e1"},
                    {"seq": 2, "variant": "v1", "environment": "e1"},
                ],
                {"base": "abc", "v1": "def"},
            )
            ledger.update(1, state="done", results_dir=str(FIX / "junit" / "basic"))
            out = tmp / "runs.jsonl"
            n = collect(tmp / "ledger.jsonl", "junit", out, None)
            lines = [json.loads(x) for x in out.read_text().splitlines()]
            self.assertEqual(n, 4)
            self.assertEqual(len(lines), 4)
            self.assertTrue(
                all(r["seq"] == 1 and r["variant"] == "base" and r["sha"] == "abc" for r in lines)
            )

    def test_regression_collect_reads_only_current_row_attempt_dir(self):
        """Regression guard: a sibling attempt dir (orphaned run) is never read."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            runs = tmp / "runs" / "1"
            shutil.copytree(FIX / "junit" / "basic", runs / "attempt-2")
            (runs / "attempt-1").mkdir()
            (runs / "attempt-1" / "TEST-orphan.xml").write_text(
                '<testsuite name="o"><testcase classname="o.O" name="stale" time="1"/></testsuite>')
            ledger = Ledger(tmp / "ledger.jsonl")
            ledger.plan([{"seq": 1, "variant": "base", "environment": "e1"}], {"base": "abc"})
            ledger.update(1, state="running", results_dir=str(runs / "attempt-1"))
            ledger.update(1, state="planned")
            ledger.update(1, state="done", results_dir=str(runs / "attempt-2"))
            out = tmp / "runs.jsonl"
            collect(tmp / "ledger.jsonl", "junit", out, None)
            names = {json.loads(x)["test_id"] for x in out.read_text().splitlines()}
            self.assertFalse(any("stale" in n for n in names))
            self.assertTrue(names)

    def test_both_prefers_allure(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "x-result.json").write_text(json.dumps({
                "historyId": "h", "testCaseId": "t",
                "fullName": "com.example.CartTest.addsItem",
                "labels": [{"name": "testClass", "value": "com.example.CartTest"},
                           {"name": "testMethod", "value": "addsItem"}],
                "name": "addsItem", "status": "failed", "start": 0, "stop": 5}))
            (d / "TEST-x.xml").write_text(
                '<testsuite><testcase classname="com.example.CartTest" name="addsItem" time="1"/>'
                '<testcase classname="com.example.CartTest" name="other" time="1"/></testsuite>')
            recs = collect_run(d, "both", None)
            self.assertEqual(len(recs), 2)
            self.assertEqual(by_name(recs, "addsItem")[0]["status"], "failed")
            self.assertEqual(by_name(recs, "addsItem")[0]["duration_ms"], 5)

    def test_regression_parameterised_results_stay_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for i, value in enumerate(("a", "b")):
                (d / f"{i}-result.json").write_text(json.dumps({
                    "historyId": f"h{i}", "fullName": "com.example.CartTest.pays",
                    "name": "pays", "status": "passed", "start": 0, "stop": 1,
                    "parameters": [{"name": "kind", "value": value}]}))
            recs = collect_run(d, "allure", None)
            self.assertEqual(
                sorted(r["test_id"] for r in recs),
                ["com.example.CartTest.pays[kind=a]", "com.example.CartTest.pays[kind=b]"])

    def test_regression_identical_junit_copy_is_read_once(self):
        """Regression guard: a byte-identical copy of a result file is not a retry."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for sub in ("a", "b"):
                (d / sub).mkdir()
                (d / sub / "TEST-1.xml").write_text(
                    '<testsuite><testcase classname="c.A" name="m" time="1"/></testsuite>')
            err = io.StringIO()
            with redirect_stderr(err):
                recs = collect_run(d, "junit", None, seq=4)
            self.assertEqual(len(recs), 1)
            self.assertFalse(recs[0]["retried"])
            self.assertEqual(recs[0]["status"], "passed")
            self.assertEqual(err.getvalue(), "")

    def test_regression_duplicate_id_without_markers_is_not_a_retry(self):
        """Regression guard: two different files sharing an id keep one record, unretried, with a warning."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "TEST-1.xml").write_text(
                '<testsuite><testcase classname="c.A" name="m" time="1"/></testsuite>')
            (d / "TEST-2.xml").write_text(
                '<testsuite name="other"><testcase classname="c.A" name="m" time="2"/></testsuite>')
            err = io.StringIO()
            with redirect_stderr(err):
                recs = collect_run(d, "junit", None, seq=7)
            self.assertEqual(len(recs), 1)
            self.assertFalse(recs[0]["retried"])
            self.assertEqual(recs[0]["status"], "passed")
            self.assertEqual(recs[0]["duration_ms"], 2000)
            self.assertEqual(err.getvalue(), "warning: duplicate test_id c.A#m in seq 7; kept one\n")

    def test_allure_duplicate_id_with_distinct_history_keeps_latest_unretried(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for i, (status, stop) in enumerate((("failed", 9), ("passed", 5))):
                (d / f"{i}-result.json").write_text(json.dumps({
                    "historyId": f"h{i}", "fullName": "c.A.m", "name": "m",
                    "status": status, "start": 0, "stop": stop}))
            err = io.StringIO()
            with redirect_stderr(err):
                recs = collect_run(d, "allure", None, seq=2)
            self.assertEqual(len(recs), 1)
            self.assertFalse(recs[0]["retried"])
            self.assertEqual((recs[0]["status"], recs[0]["stop_ms"]), ("failed", 9))
            self.assertIn("warning: duplicate test_id c.A.m in seq 2; kept one", err.getvalue())

    def test_allure_unknown_or_missing_status_maps_to_broken(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "0-result.json").write_text(json.dumps({
                "historyId": "h0", "fullName": "c.A.u", "name": "u", "status": "unknown", "start": 0, "stop": 1}))
            (d / "1-result.json").write_text(json.dumps({
                "historyId": "h1", "fullName": "c.A.v", "name": "v", "start": 0, "stop": 1}))
            recs = collect_run(d, "allure", None)
            self.assertEqual({r["name"]: r["status"] for r in recs}, {"u": "broken", "v": "broken"})


    def test_regression_allure_without_history_id_is_not_grouped_by_full_name(self):
        """Regression guard: parameterised results without historyId are separate tests, not retries."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for i, value in enumerate(("a", "b")):
                (d / f"{i}-result.json").write_text(json.dumps({
                    "uuid": f"u{i}", "fullName": "com.example.CartTest.pays",
                    "name": "pays", "status": "passed", "start": 0, "stop": 1,
                    "parameters": [{"name": "kind", "value": value}]}))
            recs = collect_run(d, "allure", None)
            self.assertEqual(len(recs), 2)
            self.assertFalse(any(r["retried"] for r in recs))
            self.assertEqual({r["status"] for r in recs}, {"passed"})

    def test_regression_allure_copy_with_same_uuid_is_one_attempt(self):
        """Regression guard: a copied result file (same uuid) is not a retry."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            result = {"uuid": "u1", "historyId": "h", "fullName": "c.A.m", "name": "m",
                      "status": "passed", "start": 0, "stop": 4}
            for sub in ("a", "b"):
                (d / sub).mkdir()
                (d / sub / "u1-result.json").write_text(json.dumps(result))
            recs = collect_run(d, "allure", None)
            self.assertEqual(len(recs), 1)
            self.assertFalse(recs[0]["retried"])
            self.assertEqual(recs[0]["status"], "passed")

    def test_allure_distinct_uuids_in_history_group_are_a_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for i, (status, stop) in enumerate((("failed", 3), ("passed", 6))):
                (d / f"{i}-result.json").write_text(json.dumps({
                    "uuid": f"u{i}", "historyId": "h", "fullName": "c.A.m", "name": "m",
                    "status": status, "start": 0, "stop": stop}))
            recs = collect_run(d, "allure", None)
            self.assertEqual(len(recs), 1)
            self.assertTrue(recs[0]["retried"])
            self.assertEqual(recs[0]["status"], "failed")

    def test_regression_both_mode_matches_dotted_allure_id_to_junit(self):
        """Regression guard: Allure without class/method labels and JUnit for one test give one record."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "x-result.json").write_text(json.dumps({
                "uuid": "u", "historyId": "h", "fullName": "com.example.PayTest.pays",
                "name": "pays", "status": "failed", "start": 0, "stop": 5}))
            (d / "TEST-x.xml").write_text(
                '<testsuite><testcase classname="com.example.PayTest" name="pays" time="1"/></testsuite>')
            recs = collect_run(d, "both", None)
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["test_id"], "com.example.PayTest.pays")
            self.assertEqual((recs[0]["status"], recs[0]["duration_ms"]), ("failed", 5))

    def test_nested_modules_are_found_recursively(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for module, cls in (("orders", "c.OrderTest"), ("payments", "c.PaymentTest")):
                reports = d / module / "target" / "surefire-reports"
                reports.mkdir(parents=True)
                (reports / "TEST-suite.xml").write_text(
                    f'<testsuite><testcase classname="{cls}" name="m" time="1"/></testsuite>')
            allure = d / "orders" / "target" / "allure-results"
            allure.mkdir(parents=True)
            (allure / "a-result.json").write_text(json.dumps({
                "historyId": "h", "fullName": "c.OrderTest.n", "name": "n",
                "status": "passed", "start": 0, "stop": 2}))
            junit = collect_run(d, "junit", None)
            self.assertEqual(sorted(r["test_id"] for r in junit), ["c.OrderTest#m", "c.PaymentTest#m"])
            self.assertTrue(all(r["status"] == "passed" and not r["retried"] for r in junit))
            both = collect_run(d, "both", None)
            self.assertEqual(sorted(r["test_id"] for r in both),
                             ["c.OrderTest#m", "c.OrderTest.n", "c.PaymentTest#m"])


if __name__ == "__main__":
    unittest.main()
