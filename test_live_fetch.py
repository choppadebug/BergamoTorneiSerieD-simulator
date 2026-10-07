import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from live_fetch import DEFAULT_URL, refresh, request, retry_delay


def unavailable(code=503, headers=None):
    return HTTPError(DEFAULT_URL, code, 'Service Unavailable', headers or {}, None)


def saved_snapshot():
    teams = [dict(name=name, position=i+1, points=0, played=0, wins=0, draws=0,
                  losses=0, goals_for=0, goals_against=0, goal_difference=0, fair_play=0)
             for i, name in enumerate(['A', 'B'])]
    return dict(source_url=DEFAULT_URL, fetched_at='2026-10-07T10:00:00+00:00',
                leagues=[dict(id='1', name='Test', teams=teams)],
                calendars={'1': [dict(id='1', home='A', away='B', home_goals=None, away_goals=None)]})


class FetchRetryTests(unittest.TestCase):
    @patch('live_fetch.time.sleep')
    @patch('live_fetch.build_opener')
    def test_recovers_from_503(self, build, sleep):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"html":"ok"}'
        build.return_value.open.side_effect = [unavailable(), response]
        self.assertEqual(request(DEFAULT_URL, {'op': 22}), '{"html":"ok"}')
        self.assertEqual(build.return_value.open.call_count, 2)
        sleep.assert_called_once_with(2)

    @patch('live_fetch.time.sleep')
    @patch('live_fetch.build_opener')
    def test_stops_after_four_attempts(self, build, sleep):
        build.return_value.open.side_effect = [unavailable() for _ in range(4)]
        with self.assertRaises(HTTPError):
            request(DEFAULT_URL)
        self.assertEqual(build.return_value.open.call_count, 4)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [2, 4, 8])

    @patch('live_fetch.time.sleep')
    @patch('live_fetch.build_opener')
    def test_does_not_retry_permanent_errors(self, build, sleep):
        build.return_value.open.side_effect = unavailable(404)
        with self.assertRaises(HTTPError):
            request(DEFAULT_URL)
        sleep.assert_not_called()

    def test_retry_after_bounded(self):
        self.assertEqual(retry_delay(unavailable(headers={'Retry-After': '12'}), 0), 12)
        self.assertEqual(retry_delay(unavailable(headers={'Retry-After': '300'}), 0), 60)
        self.assertEqual(retry_delay(unavailable(headers={'Retry-After': 'bad'}), 1), 4)


class SnapshotFallbackTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name)/'live.json'
        self.original = saved_snapshot()
        self.path.write_text(json.dumps(self.original), encoding='utf-8')

    @patch('live_fetch.snapshot', side_effect=unavailable())
    def test_503_keeps_complete_old_snapshot_and_timestamp(self, snapshot):
        result = refresh(DEFAULT_URL, self.path, allow_stale=True)
        self.assertEqual(result['fetched_at'], self.original['fetched_at'])
        self.assertEqual(result['leagues'], self.original['leagues'])
        self.assertEqual(result['calendars'], self.original['calendars'])
        self.assertIn('503', result['refresh_warning'])
        self.assertIn('last_refresh_attempt', result)
        self.assertEqual(json.loads(self.path.read_text()), result)

    @patch('live_fetch.snapshot', side_effect=unavailable())
    def test_default_remains_strict(self, snapshot):
        original_text = self.path.read_text()
        with self.assertRaises(HTTPError):
            refresh(DEFAULT_URL, self.path)
        self.assertEqual(self.path.read_text(), original_text)

    @patch('live_fetch.snapshot', side_effect=URLError('temporary network failure'))
    def test_rejects_missing_or_invalid_fallback(self, snapshot):
        with self.assertRaises(FileNotFoundError):
            refresh(DEFAULT_URL, self.path.parent/'missing.json', True)
        for broken in ({}, dict(self.original, calendars={}),
                       dict(self.original, source_url=DEFAULT_URL.replace('/154/', '/155/'))):
            self.path.write_text(json.dumps(broken))
            with self.assertRaises((ValueError, KeyError)):
                refresh(DEFAULT_URL, self.path, True)

    @patch('live_fetch.snapshot', side_effect=ValueError('source schema changed'))
    def test_parser_errors_not_hidden(self, snapshot):
        with self.assertRaisesRegex(ValueError, 'schema changed'):
            refresh(DEFAULT_URL, self.path, True)

    @patch('live_fetch.snapshot')
    def test_success_clears_old_failure_metadata(self, snapshot):
        stale = dict(self.original, refresh_warning='old failure', last_refresh_attempt='old')
        self.path.write_text(json.dumps(stale))
        snapshot.return_value = copy.deepcopy(self.original)
        result = refresh(DEFAULT_URL, self.path, True)
        self.assertNotIn('refresh_warning', result)
        self.assertNotIn('last_refresh_attempt', result)
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])
