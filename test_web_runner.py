import json
import unittest
from dataclasses import asdict

from league_simulator import Config, simulate
from web_runner import run_web


class BrowserBridgeTests(unittest.TestCase):
    def test_native_parity_and_histograms(self):
        config = Config(simulations=500)
        progress = []
        result = json.loads(run_web(json.dumps({'config': asdict(config)}),
                                    lambda *args: progress.append(args)))
        self.assertEqual(result['rows'], simulate(config))
        self.assertEqual(progress[-1], ('simulating', 500, 500))
        for row, counts in zip(result['rows'], result['distributions']):
            self.assertEqual(sum(counts.values()), 500)
            self.assertAlmostEqual(sum(int(p)*n for p, n in counts.items())/500,
                                   row['mean_points'], places=2)

    def test_uploaded_history_and_invalid_sources(self):
        payload = {'config': asdict(Config(simulations=10)), 'magnitude': 1,
                   'sources': [{'name': 'tiny.csv', 'text': '1,2,0,2,0\n2,2,0,2,0'}]}
        result = json.loads(run_web(json.dumps(payload)))
        self.assertEqual(result['config']['draw_probability'], 1)
        self.assertEqual(result['calibration']['included'], ['tiny.csv'])
        payload['sources'][0]['name'] = '../escape.csv'
        with self.assertRaises(ValueError):
            run_web(json.dumps(payload))

    def test_strength_model_preserves_histogram_totals(self):
        config = Config(simulations=300, teams=8, legs=1, strength_spread=1.8,
                        draw_probability=0.0925)
        result = simulate(config, include_distributions=True)
        self.assertEqual(result['rows'], simulate(config))
        for counts in result['distributions']:
            self.assertEqual(sum(counts.values()), config.simulations)
            self.assertTrue(all(0 <= points <= 21 for points in counts))
