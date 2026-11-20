import io
import json
import sys
from contextlib import redirect_stdout
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


if __name__ == "__main__":
    unittest.main()
