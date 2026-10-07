import json
import unittest

from league_simulator import Config
from live_fetch import validate_url
from live_projection import project_live, validate_snapshot
from live_standings import parse_calendar, parse_standings, season_from_page
from web_runner import run_web


def sample():
    def team(name, position, points, wins, losses, gf, ga):
        return dict(name=name, position=position, points=points, played=1, wins=wins,
                    draws=0, losses=losses, goals_for=gf, goals_against=ga,
                    goal_difference=gf-ga, fair_play=0)
    league = dict(id='1', name='Test league', teams=[team('A', 1, 3, 1, 0, 2, 0), team('B', 2, 0, 0, 1, 0, 2)])
    fixtures = [dict(id='1', home='A', away='B', home_goals=2, away_goals=0, date='2026-10-01'),
                dict(id='2', home='B', away='A', home_goals=None, away_goals=None, date='2026-10-10')]
    return league, fixtures


class LiveProjectionTests(unittest.TestCase):
    def test_preserves_results_bounds_and_probabilities(self):
        league, fixtures = sample()
        config = Config(simulations=500)
        result = project_live(config, league, fixtures)
        self.assertEqual(result, project_live(config, league, fixtures))
        self.assertEqual(result['remaining_fixtures'], 1)
        self.assertEqual(result['timeline'][0]['teams'][0]['median_points'], 3)
        for team in result['teams']:
            self.assertAlmostEqual(sum(f['probability'] for f in team['finishes']), 1)
            self.assertGreaterEqual(team['points']['lower_points'], team['current']['points'])
            self.assertLessEqual(team['points']['upper_points'], team['current']['points']+3)
        for i in range(2):
            self.assertAlmostEqual(sum(t['finishes'][i]['probability'] for t in result['teams']), 1)
        self.assertGreater(result['teams'][0]['strength'], result['teams'][1]['strength'])

    def test_completed_season_uses_official_order(self):
        league, fixtures = sample()
        fixtures[1].update(home_goals=1, away_goals=1)
        for t in league['teams']:
            t['played'] += 1
            t['draws'] += 1
            t['points'] += 1
            t['goals_for'] += 1
            t['goals_against'] += 1
        result = project_live(Config(simulations=10), league, fixtures)
        self.assertEqual(result['remaining_fixtures'], 0)
        self.assertEqual(result['teams'][0]['finishes'][0]['probability'], 1)
        self.assertEqual(result['rows'][0]['lower_points'], 4)
        self.assertEqual(result['rows'][0]['upper_points'], 4)

    def test_points_adjustment_preserved(self):
        league, fixtures = sample()
        league['teams'][0]['points'] = 1
        result = project_live(Config(simulations=20), league, fixtures)
        self.assertIn('-2', result['warnings'][0])
        self.assertEqual(result['timeline'][0]['teams'][0]['median_points'], 1)

    def test_incomplete_or_inconsistent_calendar_rejected(self):
        league, fixtures = sample()
        with self.assertRaisesRegex(ValueError, 'complete round robin'):
            validate_snapshot(league['teams'], fixtures[:1], 2)
        fixtures[0]['home_goals'] = 3
        with self.assertRaisesRegex(ValueError, 'goals_for'):
            validate_snapshot(league['teams'], fixtures, 2)

    def test_zero_zero_is_completed(self):
        league, fixtures = sample()
        fixtures[1].update(home_goals=0, away_goals=0)
        with self.assertRaisesRegex(ValueError, 'played'):
            validate_snapshot(league['teams'], fixtures, 2)

    def test_goal_and_fairplay_treatment(self):
        league, fixtures = sample()
        result = project_live(Config(simulations=20), league, fixtures)
        league['teams'][0]['fair_play'] = -5
        other = project_live(Config(simulations=20), league, fixtures)
        self.assertEqual(result['rows'], other['rows'])

    def test_web_action(self):
        league, fixtures = sample()
        output = json.loads(run_web(json.dumps(dict(action='project_live', config={'simulations': 20}, league=league, matches=fixtures))))
        self.assertEqual(output['kind'], 'live_projection')
        self.assertEqual(output['config']['teams'], 2)


class ImportTests(unittest.TestCase):
    def test_host_restriction(self):
        self.assertEqual(validate_url('https://bergamotornei.com/it/t-teamtable/154/test/')[1], '154')
        for url in ['http://127.0.0.1/a', 'https://evil.com/it/t-teamtable/154/test/',
                    'https://www.bergamotornei.com:9999/it/t-teamtable/154/test/',
                    'https://www.bergamotornei.com/it/t-teamtable/154/test/?url=evil']:
            with self.assertRaises(ValueError):
                validate_url(url)

    def test_parallel_name_stat_rows_and_league_relationship(self):
        page = '<select name="round"><option value="1">League A</option><option value="2">League B</option></select>'
        def table(name, team):
            headers = ''.join(f'<div class="col-data">{s}</div>' for s in ['Pt', 'G', 'V', 'N', 'P', 'F', 'S', '+/-', 'FP'])
            cells = ''.join(f'<div class="col-data"><small>{n}</small></div>' for n in [3,1,1,0,0,2,0,2,0])
            return f'<div class="standing-table-title">{name}</div><div class="tables-container"><div class="left-table"><div class="tables-body"><div class="col-pos">1</div><div class="participant-name">{team}</div></div></div><div class="right-table"><div class="tables-header">{headers}</div><div class="tables-body">{cells}</div></div></div>'
        leagues = parse_standings(page, table('League A', 'Alpha &amp; Co')+table('League B', 'Beta'))
        self.assertEqual([l['id'] for l in leagues], ['1', '2'])
        self.assertEqual(leagues[0]['teams'][0]['name'], 'Alpha & Co')
        self.assertEqual(leagues[1]['teams'][0]['points'], 3)
        with self.assertRaises(ValueError):
            parse_standings(page, '<div>No tables</div>')

    def test_calendar_byes_pending_and_dates(self):
        def match(identifier, date, scores):
            return f'<div class="match-element"><a href="/it/match/{identifier}/a-b/"><div class="match-header">{date}</div><div class="participant-name">A</div><div class="participant-name">B</div><div class="match-right">{scores}</div></a></div>'
        html = '<div class="match-element">Turno di riposo</div>'
        html += match(1, 'Lun 12 OTT 21:00', '')
        html += match(2, 'Lun 11 GEN 21:00', '<div class="score">0</div><div class="score">0</div>')
        matches = parse_calendar(html, 2026)
        self.assertEqual(len(matches), 2)
        self.assertIsNone(matches[0]['home_goals'])
        self.assertEqual(matches[1]['home_goals'], 0)
        self.assertEqual(matches[0]['date'], '2026-10-12')
        self.assertEqual(matches[1]['date'], '2027-01-11')
        self.assertEqual(season_from_page('<p>Stagione 2026/2027</p>'), 2026)
