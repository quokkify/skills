import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from stats import (  # noqa: E402
    bootstrap_median_delta,
    fisher_two_sided,
    iqr,
    median,
    rule_of_three,
    wilson,
)


class WilsonTest(unittest.TestCase):
    def test_zero_failures(self):
        lo, hi = wilson(0, 30)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.11351709139047798, places=9)

    def test_all_failures(self):
        lo, hi = wilson(30, 30)
        self.assertEqual(hi, 1.0)
        self.assertAlmostEqual(lo, 1 - 0.11351709139047798, places=9)

    def test_empty(self):
        self.assertEqual(wilson(0, 0), (0.0, 1.0))


class FisherTest(unittest.TestCase):
    def test_reference(self):
        self.assertAlmostEqual(fisher_two_sided(3, 30, 0, 30), 0.23728813559322035, places=9)

    def test_symmetric(self):
        self.assertAlmostEqual(fisher_two_sided(0, 30, 3, 30), fisher_two_sided(3, 30, 0, 30), places=12)

    def test_identical_is_one(self):
        self.assertAlmostEqual(fisher_two_sided(5, 20, 5, 20), 1.0, places=9)


class RuleOfThreeTest(unittest.TestCase):
    def test_value(self):
        self.assertEqual(rule_of_three(30), 0.1)

    def test_zero_raises(self):
        with self.assertRaises(ValueError):
            rule_of_three(0)


class DescriptiveTest(unittest.TestCase):
    def test_median(self):
        self.assertEqual(median([3, 1, 2]), 2)
        self.assertEqual(median([1, 2, 3, 4]), 2.5)

    def test_iqr(self):
        self.assertEqual(iqr([1, 2, 3, 4, 5]), (2.0, 4.0))

    def test_iqr_single(self):
        self.assertEqual(iqr([7]), (7, 7))


class BootstrapTest(unittest.TestCase):
    def test_constant_equal(self):
        self.assertEqual(
            bootstrap_median_delta({"e": [5.0] * 10}, {"e": [5.0] * 10}), (0.0, 0.0, 0.0)
        )

    def test_clear_shift(self):
        base = {"e": [float(x) for x in range(100, 110)]}
        cand = {"e": [float(x) for x in range(70, 80)]}
        delta, lo, hi = bootstrap_median_delta(base, cand)
        self.assertEqual(delta, -30.0)
        self.assertLess(hi, 0)
        self.assertLessEqual(lo, delta)

    def test_same_seed_identical(self):
        base = {"a": [1.0, 2, 3, 9], "b": [4.0, 5, 6]}
        cand = {"a": [2.0, 3, 4, 8], "b": [5.0, 7, 9]}
        self.assertEqual(
            bootstrap_median_delta(base, cand, iterations=500, seed=7),
            bootstrap_median_delta(base, cand, iterations=500, seed=7),
        )

    def test_regression_environment_mix_does_not_manufacture_difference(self):
        """Regression guard: different per-environment compositions must not create a delta."""
        base = {"e1": [1000.0] * 20, "e2": [10000.0] * 2}
        cand = {"e1": [1000.0] * 2, "e2": [10000.0] * 20}
        self.assertEqual(bootstrap_median_delta(base, cand, iterations=500), (0.0, 0.0, 0.0))

    def test_weighted_by_shared_sample_sizes(self):
        base = {"e1": [100.0] * 3, "e2": [200.0] * 1}
        cand = {"e1": [90.0] * 1, "e2": [230.0] * 3}
        delta, lo, hi = bootstrap_median_delta(base, cand, iterations=200)
        self.assertAlmostEqual(delta, 0.5 * -10 + 0.5 * 30)
        self.assertAlmostEqual(lo, delta)
        self.assertAlmostEqual(hi, delta)

    def test_one_sided_stratum_raises(self):
        with self.assertRaisesRegex(ValueError, "b"):
            bootstrap_median_delta({"a": [1.0], "b": [2.0]}, {"a": [1.0]})

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            bootstrap_median_delta({}, {})


if __name__ == "__main__":
    unittest.main()
