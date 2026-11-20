import json
import sys
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

    def test_regression_junit_same_id_in_two_files_collapses(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for n in (1, 2):
                (d / f"TEST-{n}.xml").write_text(
                    '<testsuite><testcase classname="c.A" name="m" time="1"/></testsuite>')
            recs = collect_run(d, "junit", None)
            self.assertEqual(len(recs), 1)
            self.assertTrue(recs[0]["retried"])
            self.assertEqual(recs[0]["status"], "failed")


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
