"""Parse the public Bergamo Tornei standings and calendar HTML (no dependencies)."""
from html.parser import HTMLParser
import re


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def has(self, name):
        return name in self.attrs.get('class', '').split()

    def find(self, cls=None, tag=None):
        return [n for n in self.walk() if (cls is None or n.has(cls)) and (tag is None or n.tag == tag)]

    def walk(self):
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.walk()

    def text(self):
        return ' '.join(' '.join(c.text() if isinstance(c, Node) else c for c in self.children).split())


class Tree(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in {'img', 'br', 'input', 'meta', 'link', 'hr', 'source', 'area', 'wbr', 'embed'}:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack[-1].tag == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def integer(value):
    text = value.strip().replace('\u2212', '-')
    if not re.fullmatch(r'[+-]?\d+', text):
        raise ValueError(f'Expected an integer in standings, found {value!r}')
    return int(text)


def parse_standings(page_html, standings_html):
    page, root = Tree(page_html).root, Tree(standings_html).root
    rounds = {}
    for select in page.find(tag='select'):
        if select.attrs.get('name') == 'round':
            for option in select.find(tag='option'):
                if option.attrs.get('value', '').isdigit():
                    rounds[option.text().casefold()] = option.attrs['value']
    leagues, current = [], None
    columns = {'Pt': 'points', 'G': 'played', 'V': 'wins', 'N': 'draws', 'P': 'losses',
               'F': 'goals_for', 'S': 'goals_against', '+/-': 'goal_difference', 'FP': 'fair_play'}
    for node in root.walk():
        if node.has('standing-table-title'):
            current = node.text()
        if not node.has('tables-container'):
            continue
        if not current:
            raise ValueError('A standings table has no league title')
        left, right = node.find('left-table'), node.find('right-table')
        if len(left) != 1 or len(right) != 1:
            raise ValueError(f'{current}: unsupported table structure')
        names = left[0].find('tables-body')
        values = right[0].find('tables-body')
        headers = right[0].find('tables-header')
        if len(headers) != 1:
            raise ValueError(f'{current}: missing column headers')
        labels = [cell.text() for cell in headers[0].find('col-data')]
        if not set(columns).issubset(labels) or len(names) != len(values):
            raise ValueError(f'{current}: columns or row counts do not match')
        teams = []
        for name_row, data_row in zip(names, values):
            names_found = name_row.find('participant-name')
            cells = data_row.find('col-data')
            if len(names_found) != 1 or len(cells) != len(labels):
                raise ValueError(f'{current}: malformed team row')
            team = {'name': names_found[0].text(), 'position': integer(name_row.find('col-pos')[0].text())}
            for label, cell in zip(labels, cells):
                if label in columns:
                    team[columns[label]] = integer(cell.text())
            teams.append(team)
        league_id = rounds.get(current.casefold())
        if not league_id:
            raise ValueError(f'Cannot link {current} to its calendar round')
        leagues.append({'id': league_id, 'name': current, 'teams': teams})
        current = None
    if not leagues:
        raise ValueError('No league tables found. The source layout may have changed.')
    if len({l['id'] for l in leagues}) != len(leagues):
        raise ValueError('Duplicate league identifiers')
    return leagues


def parse_calendar(html, season_start=None):
    matches = []
    for node in Tree(html).root.find('match-element'):
        if 'Turno di riposo' in node.text():
            continue
        names = [n.text() for n in node.find('participant-name')]
        if len(names) != 2:
            raise ValueError('A calendar entry does not contain two teams; check byes or source changes')
        scores = [n.text() for n in node.find('score')]
        if not scores and node.find('match-right'):
            scores = ['', '']  # source uses an empty right pane for unplayed fixtures
        numeric = [bool(re.fullmatch(r'\d+', s)) for s in scores]
        if len(scores) != 2 or (any(numeric) and not all(numeric)):
            raise ValueError('A calendar entry has missing or ambiguous scores')
        if not any(numeric) and any(s not in ('', '-', '\u2013') for s in scores):
            raise ValueError('A fixture has a nonnumeric status instead of a supported score; check awarded or cancelled matches')
        anchors = node.find(tag='a')
        link = next((n.attrs.get('href', '') for n in anchors if '/match/' in n.attrs.get('href', '')), '')
        match_id = re.search(r'/match/(\d+)/', link)
        if not match_id:
            raise ValueError('Missing calendar match ID')
        headers = node.find('match-header')
        header = headers[0].text() if headers else ''
        date = re.search(r'(?:Lun|Mar|Mer|Gio|Ven|Sab|Dom)\s+\d{1,2}\s+[A-Za-zÀ-ÿ]+(?:\s+\d{4})?', header, re.I)
        date_iso = None
        if date and season_start:
            months = {'GEN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAG': 5, 'GIU': 6,
                      'LUG': 7, 'AGO': 8, 'SET': 9, 'OTT': 10, 'NOV': 11, 'DIC': 12}
            parts = date[0].split()
            month = months.get(parts[2].upper()[:3])
            if month:
                from datetime import date as calendar_date
                year = int(parts[3]) if len(parts) > 3 else season_start + (month < 7)
                date_iso = calendar_date(year, month, int(parts[1])).isoformat()
        matches.append({'id': match_id[1], 'home': names[0], 'away': names[1],
                        'home_goals': int(scores[0]) if all(numeric) else None,
                        'away_goals': int(scores[1]) if all(numeric) else None,
                        'date': date_iso, 'date_label': date[0] if date else 'Date to be confirmed', 'source_label': header})
    if len({m['id'] for m in matches}) != len(matches):
        raise ValueError('Duplicate matches in calendar response')
    return matches


def season_from_page(html):
    match = re.search(r'Stagione\s+(20\d{2})\s*/\s*20\d{2}', Tree(html).root.text(), re.I)
    return int(match[1]) if match else None
