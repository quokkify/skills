import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ledger import Ledger, main  # noqa: E402


def make_items(n):
    return [{"seq": i, "variant": "base", "environment": "e1"} for i in range(1, n + 1)]


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = Ledger(Path(self.tmp.name) / "ledger.jsonl")

    def test_resume_pending(self):
        self.ledger.plan(make_items(4), {"base": "y"})
        self.ledger.update(1, state="done")
        self.assertEqual([r["seq"] for r in self.ledger.pending()], [2, 3, 4])

    def test_plan_idempotent(self):
        self.ledger.plan(make_items(2), {"base": "y"})
        self.ledger.update(1, state="done")
        self.ledger.plan(make_items(2), {"base": "y"})
        self.assertEqual([r["state"] for r in self.ledger.rows()], ["done", "planned"])

    def test_replan_conflict_raises(self):
        self.ledger.plan(make_items(1), {"base": "y"})
        for item, shas in (
            ({"seq": 1, "variant": "cand", "environment": "e1"}, {"cand": "y"}),
            ({"seq": 1, "variant": "base", "environment": "e2"}, {"base": "y"}),
            ({"seq": 1, "variant": "base", "environment": "e1"}, {"base": "z"}),
        ):
            with self.assertRaisesRegex(ValueError, "seq 1"):
                self.ledger.plan([item], shas)
        self.assertEqual(len(self.ledger.path.read_text().splitlines()), 1)

    def test_replan_conflict_cli_exit_2(self):
        path = Path(self.tmp.name) / "ledger.jsonl"
        self.ledger.plan(make_items(1), {"base": "y"})
        sched = Path(self.tmp.name) / "s.json"
        sched.write_text(json.dumps(make_items(1)))
        err = io.StringIO()
        with redirect_stderr(err):
            rc = main([str(path), "plan", "--schedule", str(sched), "--shas", "base=z"])
        self.assertEqual(rc, 2)
        self.assertTrue(err.getvalue().startswith("error: "), err.getvalue())
        self.assertEqual(main([str(path), "plan", "--schedule", str(sched), "--shas", "base=y"]), 0)

    def test_sha_mismatch_invalid(self):
        self.ledger.plan(make_items(1), {"base": "y"})
        self.ledger.update(1, state="done", observed_sha="x")
        self.assertEqual(self.ledger.rows()[0]["state"], "invalid")

    def test_infra_ratio(self):
        self.ledger.plan(make_items(4), {"base": "y"})
        self.ledger.update(1, state="infra_error")
        for s in (2, 3, 4):
            self.ledger.update(s, state="done")
        self.assertEqual(self.ledger.infra_ratio(), 0.25)

    def test_infra_ratio_excludes_invalid_and_no_results(self):
        """Regression guard: invalid and no_results runs are not finished."""
        self.ledger.plan(make_items(6), {"base": "y"})
        self.ledger.update(1, state="infra_error")
        for s in (2, 3, 4):
            self.ledger.update(s, state="done")
        self.ledger.update(5, state="done", observed_sha="x")
        self.ledger.update(6, state="no_results")
        self.assertEqual(self.ledger.rows()[4]["state"], "invalid")
        self.assertEqual(self.ledger.infra_ratio(), 0.25)


    def test_pending_cli_prints_json_lines(self):
        path = Path(self.tmp.name) / "ledger.jsonl"
        self.ledger.plan(make_items(4), {"base": "y"})
        self.ledger.update(1, state="done")
        self.ledger.update(2, state="no_results")
        self.ledger.update(3, state="infra_error")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main([str(path), "pending"])
        self.assertEqual(rc, 0)
        rows = [json.loads(line) for line in buf.getvalue().splitlines()]
        self.assertEqual([(r["seq"], r["state"]) for r in rows], [(2, "no_results"), (4, "planned")])


    def test_run_id_round_trip_via_cli(self):
        path = Path(self.tmp.name) / "ledger.jsonl"
        self.ledger.plan(make_items(1), {"base": "y"})
        rc = main([str(path), "update", "--seq", "1", "--state", "running",
                   "--run-id", "4711", "--ci-url", "https://ci.example.com/4711"])
        self.assertEqual(rc, 0)
        row = self.ledger.rows()[0]
        self.assertEqual((row["run_id"], row["ci_url"]), ("4711", "https://ci.example.com/4711"))
        buf = io.StringIO()
        with redirect_stdout(buf):
            main([str(path), "pending"])
        self.assertEqual(json.loads(buf.getvalue())["run_id"], "4711")

    def test_reset_to_planned_clears_run_fields(self):
        self.ledger.plan(make_items(1), {"base": "y"})
        self.ledger.update(1, state="running", run_id="4711", ci_url="https://ci.example.com/4711",
                           results_dir="/abs/runs/1", started_at="t0")
        self.ledger.update(1, state="done", observed_sha="x", finished_at="t1")
        self.assertEqual(self.ledger.rows()[0]["state"], "invalid")
        row = self.ledger.update(1, state="planned")
        self.assertEqual(row["state"], "planned")
        for field in ("ci_url", "run_id", "results_dir", "observed_sha", "started_at", "finished_at"):
            self.assertIsNone(row[field], field)
        self.assertEqual(row["sha"], "y")

    def test_overlap_risk_survives_reset_and_is_cli_settable(self):
        self.ledger.plan(make_items(1), {"base": "y"})
        self.ledger.update(1, state="planned")
        main([str(Path(self.tmp.name) / "ledger.jsonl"), "update", "--seq", "1", "--overlap-risk", "yes"])
        self.assertEqual(self.ledger.rows()[0]["overlap_risk"], "yes")
        self.assertEqual(self.ledger.update(1, state="planned")["overlap_risk"], "yes")

    def test_cli_unknown_seq_error_has_no_quotes(self):
        path = Path(self.tmp.name) / "ledger.jsonl"
        self.ledger.plan(make_items(1), {"base": "y"})
        err = io.StringIO()
        with redirect_stderr(err):
            rc = main([str(path), "update", "--seq", "9", "--state", "done"])
        self.assertEqual(rc, 2)
        self.assertEqual(err.getvalue(), "error: seq 9 is not planned\n")


if __name__ == "__main__":
    unittest.main()
