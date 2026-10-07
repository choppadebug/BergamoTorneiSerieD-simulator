"""Fetch public Bergamo standings/fixtures for the local proxy or static snapshots."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, urlencode
from urllib.request import Request, urlopen, HTTPRedirectHandler, build_opener

from live_standings import parse_standings, parse_calendar, season_from_page

DEFAULT_URL = 'https://www.bergamotornei.com/it/t-teamtable/154/campionato-nazionale-asi-bergamo-tornei-calcio-a-7/'
ORIGIN = 'https://www.bergamotornei.com'


def validate_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'www.bergamotornei.com', 'bergamotornei.com'} or parsed.port not in (None, 443) or parsed.username or parsed.password:
        raise ValueError('Use an HTTPS standings URL on www.bergamotornei.com')
    match = re.fullmatch(r'/it/t-teamtable/(\d+)/([a-zA-Z0-9_-]+)/?', parsed.path)
    if not match or parsed.query or parsed.fragment:
        raise ValueError('Expected a Bergamo Tornei /it/t-teamtable/ID/name/ URL')
    return ORIGIN + parsed.path.rstrip('/') + '/', match[1]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Source redirected unexpectedly; use its canonical standings URL')


def request(url, data=None):
    payload = urlencode(data).encode() if data else None
    req = Request(url, data=payload, headers={'User-Agent': 'BergamoLeagueSimulator/1.0'})
    with build_opener(NoRedirect).open(req, timeout=25) as response:
        content = response.read(4_000_001)
        if len(content) > 4_000_000:
            raise ValueError('Source response exceeds 4 MB')
        return content.decode('utf-8')


def fetch_raw(url, round_id=None):
    url, tid = validate_url(url)
    result = {'source_url': url, 'fetched_at': datetime.now(timezone.utc).isoformat()}
    if round_id is not None:
        if not re.fullmatch(r'\d{1,10}', str(round_id)):
            raise ValueError('Invalid league identifier')
        data = json.loads(request(ORIGIN + '/system/include/ajax/public/league.php',
                                 {'op': 22, 'tid': tid, 'round': round_id}))
        if data.get('errors') or not isinstance(data.get('html'), str):
            raise ValueError('Source calendar request failed')
        result['calendar_html'] = data['html']
    else:
        result['page_html'] = request(url)
        data = json.loads(request(ORIGIN + '/system/include/ajax/public/league.php',
                                 {'op': 20, 'tid': tid, 'round': 'all'}))
        if data.get('errors') or not isinstance(data.get('html'), str):
            raise ValueError('Source standings request failed')
        result['standings_html'] = data['html']
    return result


def snapshot(url):
    raw = fetch_raw(url)
    leagues = parse_standings(raw['page_html'], raw['standings_html'])
    season = season_from_page(raw['page_html'])
    calendars = {}
    for league in leagues:
        calendar = fetch_raw(url, league['id'])
        calendars[league['id']] = parse_calendar(calendar['calendar_html'], season)
    return {'source_url': raw['source_url'], 'fetched_at': raw['fetched_at'],
            'season_start': season, 'leagues': leagues, 'calendars': calendars}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default=DEFAULT_URL)
    parser.add_argument('--output', type=Path, default=Path('data/live.json'))
    args = parser.parse_args()
    data = snapshot(args.url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Saved {len(data['leagues'])} leagues to {args.output}")
