import random
import unittest
from collections import Counter

from league_simulator import Config, fixtures, play_season, simulate


class SimulatorTests(unittest.TestCase):
    def test_schedule(self):
        schedule = fixtures(11, 2)
        self.assertEqual(len(schedule), 110)
        self.assertEqual(set(Counter(t for match in schedule for t in match).values()), {20})
        self.assertEqual(len(set(schedule)), 110)
        self.assertTrue(all(a != b for a, b in schedule))

    def test_points_conservation_and_bounds(self):
        config = Config()
        schedule = fixtures(11, 2)
        rng = random.Random(12)
        for _ in range(100):
            points, ranking, draws = play_season(config, schedule, rng)
            self.assertEqual(sum(points), 330 - draws)
            self.assertTrue(all(0 <= p <= 60 for p in points))
            self.assertEqual([points[t] for t in ranking], sorted(points, reverse=True))
            self.assertEqual(sorted(ranking), list(range(11)))

    def test_all_draws(self):
        rows = simulate(Config(simulations=30, draw_probability=1))
        for row in rows:
            self.assertEqual(row['mean_points'], 20)
            self.assertEqual(row['lower_points'], 20)
            self.assertEqual(row['upper_points'], 20)

    def test_no_draws(self):
        config = Config(draw_probability=0)
        points, _, draws = play_season(config, fixtures(11, 2), random.Random(1))
        self.assertEqual(draws, 0)
        self.assertEqual(sum(points), 330)
        self.assertTrue(all(p % 3 == 0 for p in points))

    def test_reproducibility_and_rank_order(self):
        config = Config(simulations=100)
        rows = simulate(config)
        self.assertEqual(rows, simulate(config))
        for key in ('mean_points', 'median_points', 'lower_points', 'upper_points'):
            self.assertEqual([r[key] for r in rows], sorted((r[key] for r in rows), reverse=True))

    def test_invalid_configuration(self):
        for kwargs in ({'simulations': 0}, {'teams': 1}, {'legs': 0},
                       {'draw_probability': -0.1}, {'confidence': 1}):
            with self.assertRaises(ValueError):
                Config(**kwargs)


if __name__ == '__main__':
    unittest.main()
