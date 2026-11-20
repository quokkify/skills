import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from schedule import build_schedule  # noqa: E402


class ScheduleTest(unittest.TestCase):
    def test_balanced_counts(self):
        items = build_schedule(["base", "a", "b"], ["e1", "e2", "e3"], 6)
        counts = Counter((i["variant"], i["environment"]) for i in items)
        self.assertEqual(len(counts), 9)
        self.assertTrue(all(c == 2 for c in counts.values()))
        self.assertEqual([i["seq"] for i in items], list(range(1, len(items) + 1)))

    def test_rotation(self):
        items = build_schedule(["base", "a"], ["e1"], 2)
        self.assertEqual([i["variant"] for i in items], ["base", "a", "a", "base"])

    def test_not_divisible_raises(self):
        with self.assertRaises(ValueError) as ctx:
            build_schedule(["base", "a"], ["e1", "e2", "e3"], 10)
        self.assertIn("divisible", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
