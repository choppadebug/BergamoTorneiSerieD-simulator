"""Conservative CSV screening and simulation-based method-of-moments fit."""

import csv
from dataclasses import replace
from pathlib import Path
import random
from statistics import pvariance

from league_simulator import Config, fixtures, play_season


def read_table(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        rows = []
        for row in csv.reader(source):
            if not row or all(not cell.strip() for cell in row):
                continue
            while row and not row[-1].strip():
                row.pop()
            if len(row) != 5:
                raise ValueError("expected five populated columns")
            rows.append([int(cell.strip()) for cell in row])
    n = len(rows)
    if n < 2 or sorted(r[0] for r in rows) != list(range(1, n + 1)):
        raise ValueError("positions must be unique and consecutive from 1")
    rows.sort()
    if any(min(r) < 0 for r in rows):
        raise ValueError("negative values")
    if any(p != 3*w + d for _, p, w, d, l in rows):
        raise ValueError("points disagree with wins/draws; adjustment needs confirmation")
    if any(sum(r[2:]) != 2*(n-1) for r in rows):
        raise ValueError("not a complete double round robin by match counts")
    if sum(r[2] for r in rows) != sum(r[4] for r in rows) or sum(r[3] for r in rows) % 2:
        raise ValueError("league wins/losses or draws do not balance")
    if [r[1] for r in rows] != sorted((r[1] for r in rows), reverse=True):
        raise ValueError("positions not ordered by points")
    return rows


def fit_history(directory, trials=500):
    paths = sorted(Path(directory).glob("*.csv"))
    tables, included, excluded = [], [], []
    for path in paths:
        try:
            tables.append(read_table(path))
            included.append(path.name)
        except (ValueError, OSError) as exc:
            excluded.append((path.name, str(exc)))
    if not tables:
        raise ValueError(f"No eligible historical tables in {directory}")
    draw_rate = sum(r[3] for t in tables for r in t) / sum(sum(r[2:]) for t in tables for r in t)
    target = sum(pvariance(r[1]/(2*(len(t)-1)) for r in t) for t in tables)/len(tables)
    # Compare season dispersion at each source's actual size. Simulation
    # accounts for random match variation rather than calling all spread skill.
    candidates = []
    for step in range(21):
        spread = step / 5
        predicted = []
        for n in sorted({len(t) for t in tables}):
            config = Config(teams=n, draw_probability=draw_rate, strength_spread=spread)
            rng = random.Random(1729 + n)  # fixed fit seed; independent of forecast seed
            schedule = fixtures(n, 2)
            variance = 0
            for _ in range(trials):
                points, _, _ = play_season(config, schedule, rng)
                variance += pvariance(p/(2*(n-1)) for p in points)
            predicted.extend([variance/trials] * sum(len(t) == n for t in tables))
        loss = (sum(predicted)/len(predicted) - target)**2
        candidates.append((loss, spread))
    return dict(draw_probability=draw_rate, strength_spread=min(candidates)[1],
                included=included, excluded=excluded)


def blend(config, fitted, magnitude):
    if not 0 <= magnitude <= 1:
        raise ValueError("Historical calibration must be between 0 and 1")
    return replace(config,
                   draw_probability=(1-magnitude)*config.draw_probability + magnitude*fitted['draw_probability'],
                   strength_spread=magnitude*fitted['strength_spread'])
