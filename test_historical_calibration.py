import tempfile
import unittest
from pathlib import Path

from historical_calibration import blend, fit_history, read_table
from league_simulator import Config, simulate


class HistoricalTests(unittest.TestCase):
    def test_blend_endpoints(self):
        base = Config(simulations=20)
        fit = dict(draw_probability=0.1, strength_spread=2)
        self.assertEqual(blend(base, fit, 0), base)
        self.assertEqual(simulate(blend(base, fit, 0)), simulate(base))
        self.assertEqual(blend(base, fit, 1).draw_probability, 0.1)
        self.assertEqual(blend(base, fit, 1).strength_spread, 2)
        self.assertAlmostEqual(blend(base, fit, 0.5).draw_probability, 0.175)
        self.assertEqual(blend(base, fit, 0.5).strength_spread, 1)
        with self.assertRaises(ValueError):
            blend(base, fit, 1.1)

    def test_screening_and_different_sizes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'two.csv').write_text('1,6,2,0,0,\n2,0,0,0,2\n')
            (root/'three.csv').write_text('1,12,4,0,0\n2,6,2,0,2\n3,0,0,0,4\n')
            (root/'bad.csv').write_text('1,6,2,0\n')
            fit = fit_history(root, trials=10)
            self.assertEqual(fit['included'], ['three.csv', 'two.csv'])
            self.assertEqual(fit['excluded'][0][0], 'bad.csv')
            self.assertEqual(fit['draw_probability'], 0)
            self.assertGreater(fit['strength_spread'], 0)

    def test_reject_inconsistent_or_incomplete(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'test.csv'
            for content in ('1,5,2,0,0\n2,0,0,0,2',
                            '1,3,1,0,0\n2,0,0,0,1',
                            '1,6,2,0,0\n1,0,0,0,2'):
                path.write_text(content)
                with self.assertRaises(ValueError):
                    read_table(path)

    def test_missing_history_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                fit_history(folder)
