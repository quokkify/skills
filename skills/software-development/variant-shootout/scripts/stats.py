"""Stdlib statistics for variant-shootout verdicts."""
import math
import random
import statistics

FISHER_REL_TOL = 1e-7


def median(xs):
    return statistics.median(xs)


def iqr(xs):
    if len(xs) < 2:
        return (xs[0], xs[0])
    q = statistics.quantiles(xs, n=4, method="inclusive")
    return (q[0], q[2])


def _percentile(sorted_xs, p):
    n = len(sorted_xs)
    idx = min(max(math.ceil(p / 100 * n) - 1, 0), n - 1)
    return sorted_xs[idx]


def _weighted_delta(base, cand, strata, weights):
    return sum(weights[s] * (median(cand[s]) - median(base[s])) for s in strata)


def bootstrap_median_delta(base, cand, iterations=10000, seed=1234):
    """Return (delta, lo, hi): environment-weighted median difference with a 95% CI.

    delta = sum over strata of w_s * (median(cand_s) - median(base_s)), where
    w_s = (n_base_s + n_cand_s) / total, so a different per-stratum mix on the two
    sides cannot manufacture a difference. The bootstrap resamples within each
    stratum independently per side and reuses the original weights.
    """
    if not base and not cand:
        raise ValueError("empty input")
    for name in sorted(set(base) ^ set(cand)):
        side = "baseline" if name in base else "candidate"
        raise ValueError(f"stratum {name!r} present only in {side}")
    for side_name, side in (("baseline", base), ("candidate", cand)):
        for name, vals in side.items():
            if not vals:
                raise ValueError(f"stratum {name!r} has no {side_name} values")
    strata = sorted(base)
    total = sum(len(base[s]) + len(cand[s]) for s in strata)
    weights = {s: (len(base[s]) + len(cand[s])) / total for s in strata}
    delta = _weighted_delta(base, cand, strata, weights)
    rng = random.Random(seed)
    deltas = []
    for _ in range(iterations):
        b_res = {s: rng.choices(base[s], k=len(base[s])) for s in strata}
        c_res = {s: rng.choices(cand[s], k=len(cand[s])) for s in strata}
        deltas.append(_weighted_delta(b_res, c_res, strata, weights))
    deltas.sort()
    return (delta, _percentile(deltas, 2.5), _percentile(deltas, 97.5))


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    lo = 0.0 if k == 0 else max(0.0, center - margin)
    hi = 1.0 if k == n else min(1.0, center + margin)
    return (lo, hi)


def fisher_two_sided(k1, n1, k2, n2):
    total_k = k1 + k2
    total_n = n1 + n2
    denom = math.comb(total_n, total_k)

    def prob(x):
        return math.comb(n1, x) * math.comb(n2, total_k - x) / denom

    observed = prob(k1)
    lo = max(0, total_k - n2)
    hi = min(n1, total_k)
    threshold = observed * (1 + FISHER_REL_TOL)
    p = sum(q for q in (prob(x) for x in range(lo, hi + 1)) if q <= threshold)
    return min(1.0, p)


def rule_of_three(n):
    if n <= 0:
        raise ValueError("n must be positive")
    return 3 / n
