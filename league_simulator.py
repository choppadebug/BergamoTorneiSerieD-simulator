"""Bergamo Tornei Serie D: Monte Carlo points projections."""

import argparse
import csv
from dataclasses import dataclass
import math
from pathlib import Path
import random


@dataclass(frozen=True)
class Config:
    simulations: int = 10_000
    teams: int = 11
    legs: int = 2
    draw_probability: float = 0.25
    confidence: float = 0.90
    seed: int = 42
    strength_spread: float = 0.0

    def __post_init__(self):
        if self.simulations < 1 or self.teams < 2 or self.legs < 1:
            raise ValueError("Require simulations >= 1, teams >= 2, and legs >= 1")
        if not 0 <= self.draw_probability <= 1:
            raise ValueError("Draw probability must be between 0 and 1")
        if not 0 < self.confidence < 1:
            raise ValueError("Confidence must be strictly between 0 and 1")
        if not math.isfinite(self.strength_spread) or self.strength_spread < 0:
            raise ValueError("Strength spread must be finite and nonnegative")


def fixtures(teams, legs):
    """Generate pairings; reverse nominal home/away sides on alternating legs."""
    return [
        (a, b) if leg % 2 == 0 else (b, a)
        for leg in range(legs)
        for a in range(teams)
        for b in range(a + 1, teams)
    ]


def play_season(config, schedule, rng):
    points = [0] * config.teams
    draws = 0
    strengths = ([rng.gauss(0, config.strength_spread) for _ in points]
                 if config.strength_spread else [0] * config.teams)
    for home, away in schedule:
        outcome = rng.random()
        if outcome < config.draw_probability:
            points[home] += 1
            points[away] += 1
            draws += 1
        elif outcome < config.draw_probability + (1 - config.draw_probability) * (
            1 / (1 + math.exp(max(-700, min(700, strengths[away] - strengths[home]))))
        ):
            points[home] += 3
        else:
            points[away] += 3
    # A uniform random tie-break avoids favoring team IDs. It has no effect
    # on the points distribution by rank because tied teams have equal points.
    ranking = list(range(config.teams))
    rng.shuffle(ranking)
    ranking.sort(key=lambda team: points[team], reverse=True)
    return points, ranking, draws


def quantile(sorted_values, probability):
    """Inverse empirical CDF: an observed integer, with no interpolation."""
    import math

    index = max(0, math.ceil(probability * len(sorted_values)) - 1)
    return sorted_values[index]


def simulate(config, *, include_distributions=False, progress=None):
    rng = random.Random(config.seed)
    schedule = fixtures(config.teams, config.legs)
    by_rank = [[] for _ in range(config.teams)]
    for iteration in range(config.simulations):
        points, ranking, _ = play_season(config, schedule, rng)
        for rank, team in enumerate(ranking):
            by_rank[rank].append(points[team])
        if progress and ((iteration + 1) % 250 == 0 or iteration + 1 == config.simulations):
            progress(iteration + 1, config.simulations)
    tail = (1 - config.confidence) / 2
    rows = []
    for rank, values in enumerate(by_rank, start=1):
        values.sort()
        rows.append({
            "position": rank,
            "mean_points": round(sum(values) / len(values), 2),
            "median_points": quantile(values, 0.5),
            "lower_points": quantile(values, tail),
            "upper_points": quantile(values, 1 - tail),
            # Strictly beating the points of rank k is sufficient for top k
            # against that simulated table. This is a benchmark, not the
            # probability a real team qualifies after changing its results.
            "conservative_top_k_benchmark": (
                quantile(values, config.confidence) + 1 if rank < config.teams else 0
            ),
        })
    if include_distributions:
        from collections import Counter
        return {"rows": rows, "distributions": [dict(sorted(Counter(v).items())) for v in by_rank]}
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulations", type=int, default=10_000)
    parser.add_argument("--teams", type=int, default=11)
    parser.add_argument("--legs", type=int, default=2)
    parser.add_argument("--draw-probability", type=float, default=0.25)
    parser.add_argument("--confidence", type=float, default=0.90)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--csv", type=Path, help="Optional output CSV path")
    parser.add_argument("--historical-calibration", type=float, default=0,
                        metavar="0..1", help="Historical influence; default 0 (disabled)")
    parser.add_argument("--historical-dir", type=Path, default=Path(__file__).parent / "input")
    args = parser.parse_args()
    try:
        config = Config(**{k: v for k, v in vars(args).items()
                           if k not in ("csv", "historical_calibration", "historical_dir")})
        if not 0 <= args.historical_calibration <= 1:
            raise ValueError("Historical calibration must be between 0 and 1")
        if args.historical_calibration:
            from historical_calibration import fit_history, blend
            fitted = fit_history(args.historical_dir)
            config = blend(config, fitted, args.historical_calibration)
            print(f"Historical influence: {args.historical_calibration:.0%}")
            print("Included: " + ", ".join(fitted['included']))
            for name, reason in fitted['excluded']:
                print(f"Skipped {name}: {reason}")
            print(f"Fitted draw rate: {fitted['draw_probability']:.2%}; "
                  f"strength spread: {fitted['strength_spread']:.2f}")
            if fitted['strength_spread'] == 4:
                print("Warning: strength fit reached the search boundary (4.0).")
    except ValueError as exc:
        parser.error(str(exc))
    rows = simulate(config)
    games = config.legs * (config.teams - 1)
    print("Bergamo Tornei Serie D")
    print(f"{config.simulations:,} seasons | {config.teams} teams | {games} games/team")
    print(f"Draw probability: {config.draw_probability:.1%} | Seed: {config.seed}")
    print(f"Effective strength spread: {config.strength_spread:.2f}")
    print(f"Central {config.confidence:.1%} prediction ranges (not confidence intervals of the mean)")
    print(f"{'Position':>8} {'Mean':>8} {'Median':>8} {'Range':>11} {'Top-k benchmark*':>17}")
    for row in rows:
        interval = f"{row['lower_points']}-{row['upper_points']}"
        benchmark = row['conservative_top_k_benchmark']
        print(f"{row['position']:>8} {row['mean_points']:>8.2f} {row['median_points']:>8} {interval:>11} {benchmark:>17}")
    print("* One point above the selected percentile of rank k's points; top n needs 0.")
    print("  A conservative comparison with simulated cutoffs, not a qualification guarantee.")
    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"CSV saved to {args.csv}")


if __name__ == "__main__":
    main()
