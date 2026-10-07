"""Conditional remainder-of-season projections from reconciled standings/fixtures."""
from collections import Counter, defaultdict
from dataclasses import replace, asdict
import math
import random


def validate_snapshot(teams, matches, legs):
    if len(teams) < 2 or len({t['name'] for t in teams}) != len(teams):
        raise ValueError('League must have at least two uniquely named teams')
    names = {t['name']: i for i, t in enumerate(teams)}
    counts = [Counter() for _ in teams]
    pairs = Counter()
    seen = set()
    for match in matches:
        if match['id'] in seen:
            raise ValueError('Duplicate fixture ID')
        seen.add(match['id'])
        if match['home'] not in names or match['away'] not in names or match['home'] == match['away']:
            raise ValueError('Fixture contains unknown or identical teams')
        a, b = names[match['home']], names[match['away']]
        pairs[tuple(sorted((a, b)))] += 1
        x, y = match['home_goals'], match['away_goals']
        if (x is None) != (y is None):
            raise ValueError('Fixture has only one score')
        if x is None:
            continue
        if any(type(v) is not int or v < 0 for v in (x, y)):
            raise ValueError('Invalid fixture score')
        for i, gf, ga in ((a, x, y), (b, y, x)):
            counts[i].update(played=1, goals_for=gf, goals_against=ga,
                             wins=int(gf > ga), draws=int(gf == ga), losses=int(gf < ga))
    if len(pairs) != len(teams)*(len(teams)-1)//2 or any(v != legs for v in pairs.values()):
        raise ValueError('Calendar is not a complete round robin for the selected number of legs. Adjust legs or refresh the source; no fixtures were invented.')
    adjustments = []
    for team, actual in zip(teams, counts):
        for key in ('points', 'position', 'played', 'wins', 'draws', 'losses', 'goals_for', 'goals_against', 'goal_difference', 'fair_play'):
            if type(team.get(key)) is not int:
                raise ValueError(f"{team['name']}: missing or non-integer {key}")
        for key in ('played', 'wins', 'draws', 'losses', 'goals_for', 'goals_against'):
            if team[key] < 0 or team[key] != actual[key]:
                raise ValueError(f"{team['name']}: calendar {key}={actual[key]} but standings {key}={team[key]}. Refresh or check postponed/awarded matches.")
        if team['goal_difference'] != team['goals_for'] - team['goals_against']:
            raise ValueError(f"{team['name']}: goal difference does not reconcile")
        adjustment = team['points'] - 3*team['wins'] - team['draws']
        if adjustment:
            adjustments.append(f"{team['name']}: preserving official points adjustment {adjustment:+d}")
    if sorted(t['position'] for t in teams) != list(range(1, len(teams)+1)):
        raise ValueError('Standings positions are not unique and consecutive')
    return names, adjustments


def summary(counts, confidence):
    total = sum(counts.values())
    if not total:
        return None
    def q(p):
        threshold = max(1, math.ceil(p*total))
        cumulative = 0
        for points, count in sorted(counts.items()):
            cumulative += count
            if cumulative >= threshold:
                return points
    return dict(mean_points=round(sum(p*c for p, c in counts.items())/total, 2),
                median_points=q(.5), lower_points=q((1-confidence)/2),
                upper_points=q((1+confidence)/2), percentile=q(confidence))


def project_live(config, league, matches, *, prior_games=6, report=None):
    teams = league['teams']
    config = replace(config, teams=len(teams))
    if not 1 <= prior_games <= 30:
        raise ValueError('Prior games must be between 1 and 30')
    names, warnings = validate_snapshot(teams, matches, config.legs)
    remaining = [m for m in matches if m['home_goals'] is None]
    remaining.sort(key=lambda m: (m.get('date') or '9999', m['id']))
    groups = defaultdict(list)
    for match in remaining:
        groups[match.get('date') or 'Date to be confirmed'].append(match)
    played = sum(t['played'] for t in teams)/2
    draws = sum(t['draws'] for t in teams)/2
    draw_rate = (draws + 20*config.draw_probability)/(played + 20)
    goals_per_team_game = (sum(t['goals_for'] for t in teams) + 2.5*prior_games*len(teams))/(2*played + prior_games*len(teams))
    strengths = []
    for t in teams:
        result_strength = math.log((t['wins'] + .5*t['draws'] + prior_games/2)/
                                   (t['losses'] + .5*t['draws'] + prior_games/2))
        goal_strength = math.log((t['goals_for'] + prior_games*goals_per_team_game)/
                                 (t['goals_against'] + prior_games*goals_per_team_game))
        strengths.append(max(-4, min(4, .65*result_strength + .35*goal_strength)))
    rank_points = [Counter() for _ in teams]
    team_points = [Counter() for _ in teams]
    team_ranks = [[Counter() for _ in teams] for _ in teams]
    dates = ['Current table', *groups]
    timeline_ranks = [[Counter() for _ in teams] for _ in dates]
    timeline_teams = [[Counter() for _ in teams] for _ in dates]
    rng = random.Random(config.seed)
    initial = [t['points'] for t in teams]
    initial_order = sorted(range(len(teams)), key=lambda i: teams[i]['position'])
    fixture_groups = [[(names[m['home']], names[m['away']]) for m in ms] for ms in groups.values()]
    probabilities = {(a, b): 1/(1+math.exp(strengths[b]-strengths[a])) for g in fixture_groups for a, b in g}
    for iteration in range(config.simulations):
        points = initial.copy()
        order = initial_order.copy()
        for day, fixtures in enumerate([[], *fixture_groups]):
            for a, b in fixtures:
                u = rng.random()
                if u < draw_rate:
                    points[a] += 1
                    points[b] += 1
                elif u < draw_rate + (1-draw_rate)*probabilities[a, b]:
                    points[a] += 3
                else:
                    points[b] += 3
            if day:
                rng.shuffle(order)
                order.sort(key=lambda i: points[i], reverse=True)
            for rank, i in enumerate(order):
                timeline_ranks[day][rank][points[i]] += 1
            for i, value in enumerate(points):
                timeline_teams[day][i][value] += 1
        for rank, i in enumerate(order):
            rank_points[rank][points[i]] += 1
            team_ranks[i][rank][points[i]] += 1
            team_points[i][points[i]] += 1
        if report and ((iteration+1) % 250 == 0 or iteration+1 == config.simulations):
            report('simulating', iteration+1, config.simulations)
    rows = []
    for rank, counts in enumerate(rank_points, 1):
        row = summary(counts, config.confidence)
        row['position'] = rank
        row['conservative_top_k_benchmark'] = row.pop('percentile') + 1 if rank < len(teams) else 0
        row.pop('percentile', None)
        rows.append(row)
    details = []
    for i, t in enumerate(teams):
        by_position = []
        for rank, counts in enumerate(team_ranks[i], 1):
            by_position.append({'position': rank, 'probability': sum(counts.values())/config.simulations,
                                'points': summary(counts, config.confidence)})
        details.append({'name': t['name'], 'current': t, 'strength': strengths[i],
                        'remaining_games': config.legs*(len(teams)-1)-t['played'],
                        'points': summary(team_points[i], config.confidence), 'finishes': by_position})
    if any(m.get('date') is None for m in remaining):
        warnings.append('Undated fixtures are grouped at the end; their real timing is unknown.')
    warnings.append('Strength estimates use results and goals with shrinkage, not an opponent-adjusted fitted model. Accuracy has not been backtested.')
    return {'kind': 'live_projection', 'config': asdict(config), 'league': league['name'],
            'rows': rows, 'teams': details, 'remaining_fixtures': len(remaining),
            'effective_draw_probability': draw_rate, 'prior_games': prior_games, 'warnings': warnings,
            'timeline': [{'date': date, 'positions': [summary(c, config.confidence) for c in ranks],
                          'teams': [summary(c, config.confidence) for c in ts]}
                         for date, ranks, ts in zip(dates, timeline_ranks, timeline_teams)]}
