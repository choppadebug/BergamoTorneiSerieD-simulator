"""JSON boundary shared by the browser worker and native integration tests."""
import json
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from historical_calibration import blend, fit_history
from league_simulator import Config, simulate

_fit_cache = {}


def run_web(payload_json, report=None):
    payload = json.loads(payload_json)
    action = payload.get('action')
    if action == 'parse_standings':
        from live_standings import parse_standings, season_from_page
        raw = payload['raw']
        return json.dumps({'kind': 'live_standings', 'leagues': parse_standings(raw['page_html'], raw['standings_html']),
                           'season_start': season_from_page(raw['page_html']),
                           'source_url': raw['source_url'], 'fetched_at': raw['fetched_at']})
    if action == 'parse_calendar':
        from live_standings import parse_calendar
        return json.dumps({'kind': 'live_calendar', 'matches': parse_calendar(payload['raw']['calendar_html'], payload.get('season_start'))})
    if action == 'project_live':
        from live_projection import project_live
        return json.dumps(project_live(Config(**payload['config']), payload['league'], payload['matches'],
                                       prior_games=payload.get('prior_games', 6), report=report))
    config = Config(**payload['config'])
    magnitude = payload.get('magnitude', 0)
    if not 0 <= magnitude <= 1:
        raise ValueError('Historical influence must be between 0 and 1')
    fitted = None
    if magnitude:
        sources = payload.get('sources', [])
        names = [s['name'] for s in sources]
        if len(set(names)) != len(names):
            raise ValueError('Historical file names must be unique')
        if any(Path(n).name != n or '/' in n or '\\' in n or not n.endswith('.csv') for n in names):
            raise ValueError('Historical sources must have simple .csv file names')
        key = json.dumps(sources, sort_keys=True)
        if report:
            report('calibrating', 0, 0)
        if key not in _fit_cache:
            with TemporaryDirectory() as directory:
                for source in sources:
                    (Path(directory)/source['name']).write_text(source['text'], encoding='utf-8')
                fitted = fit_history(directory)
            _fit_cache.clear()  # retain only the latest source set
            _fit_cache[key] = fitted
        fitted = _fit_cache[key]
        config = blend(config, fitted, magnitude)
    result = simulate(config, include_distributions=True,
                      progress=(lambda done, total: report('simulating', done, total)) if report else None)
    result.update(config=asdict(config), magnitude=magnitude, calibration=fitted)
    return json.dumps(result)
