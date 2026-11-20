#!/usr/bin/env python3
"""Deterministic interleaved run schedule for comparing variants against a baseline."""
import argparse
import json
import sys


def build_schedule(variants, environments, runs_per_variant):
    """Return [{"seq", "variant", "environment"}]; variants[0] is the baseline.

    Within each environment, round r runs the variants rotated left by r.
    Environments are interleaved round by round.
    """
    if not variants:
        raise ValueError("at least one variant is required")
    if not environments:
        raise ValueError("at least one environment is required")
    if runs_per_variant < 1:
        raise ValueError("runs_per_variant must be positive")
    if runs_per_variant % len(environments) != 0:
        raise ValueError(
            f"runs_per_variant ({runs_per_variant}) must be divisible by "
            f"the number of environments ({len(environments)})"
        )
    rounds = runs_per_variant // len(environments)
    items = []
    for r in range(rounds):
        shift = r % len(variants)
        order = variants[shift:] + variants[:shift]
        for env in environments:
            for variant in order:
                items.append({"seq": len(items) + 1, "variant": variant, "environment": env})
    return items


def _csv(value):
    return [part.strip() for part in value.split(",") if part.strip()]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variants", required=True, type=_csv, help="comma list; first is the baseline")
    parser.add_argument("--environments", required=True, type=_csv)
    parser.add_argument("--runs", required=True, type=int, help="runs per variant")
    args = parser.parse_args(argv)
    try:
        items = build_schedule(args.variants, args.environments, args.runs)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    json.dump(items, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
