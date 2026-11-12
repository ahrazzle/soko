"""Exact material allocation conditional on a fixed hero trace and landmark.

This oracle handles traces whose first distinct hero-goal pair is their final
frame. Earlier goal pairs are explicitly unsupported: token-dependent early
landmarks could otherwise activate terminal absorption before the supplied
trace ends. For the supported class, independent token dynamic programs and a
maximum matching exactly decide feasibility at the specified common landmark.
Neither a feasible allocation nor a Hall obstruction is a global game result.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass

from . import model

_HERO_FIELDS = ('bard_x', 'bard_y', 'druid_x', 'druid_y', 'active')


def _point(frame, hero):
    return frame[hero + '_x'], frame[hero + '_y']


def _inside(point):
    return 0 <= point[0] < model.W and 0 <= point[1] < model.H


def _near(first, second):
    return max(abs(first[0] - second[0]), abs(first[1] - second[1])) <= 2


def _step(point, delta):
    return point[0] + delta[0], point[1] + delta[1]


def _goal_pair(frame):
    return {_point(frame, 'bard'), _point(frame, 'druid')} == set(model.GOALS)


def _heroes(route, hero_frames):
    """Normalize and independently check all nonterminal hero action rules."""
    if not isinstance(route, str) or any(key not in model.KEYS for key in route):
        raise ValueError('route must be a string of UDLRA inputs')
    if not isinstance(hero_frames, Sequence) or len(hero_frames) != len(route) + 1:
        raise ValueError('hero_frames must contain exactly len(route) + 1 frames')
    normalized = []
    for i, value in enumerate(hero_frames):
        if is_dataclass(value) and not isinstance(value, type):
            value = asdict(value)
        if not isinstance(value, Mapping) or any(key not in value for key in _HERO_FIELDS):
            raise ValueError(f'hero frame {i} must supply {_HERO_FIELDS}')
        frame = {key: value[key] for key in _HERO_FIELDS}
        if any(type(frame[key]) is not int for key in _HERO_FIELDS[:4]):
            raise ValueError(f'hero frame {i} coordinates must be integers')
        if type(frame['active']) is not bool:
            raise ValueError(f'hero frame {i} active must be Boolean')
        if not _inside(_point(frame, 'bard')) or not _inside(_point(frame, 'druid')):
            raise ValueError(f'hero frame {i} is outside the board')
        normalized.append(frame)
    if normalized[0] != dict(bard_x=2, bard_y=2, druid_x=2, druid_y=4, active=False):
        raise ValueError('initial heroes or active hero differ from III-14')
    for i, key in enumerate(route):
        before, after = normalized[i:i + 2]
        bard, druid = _point(before, 'bard'), _point(before, 'druid')
        next_bard, next_druid = _point(after, 'bard'), _point(after, 'druid')
        if key == 'A':
            if next_bard != bard or next_druid != druid or after['active'] == before['active']:
                raise ValueError(f'hero transition {i}/{key}: A must hold positions and flip active')
            continue
        delta = model.DIRECTIONS[key]
        if after['active'] != before['active']:
            raise ValueError(f'hero transition {i}/{key}: directional input changed active')
        if not before['active']:
            if next_bard != bard or next_druid not in (druid, _step(druid, delta)):
                raise ValueError(f'hero transition {i}/{key}: illegal Druid movement')
        else:
            if next_bard not in (bard, _step(bard, delta)):
                raise ValueError(f'hero transition {i}/{key}: illegal Bard movement')
            can_carry = next_bard != bard and _near(druid, bard)
            if next_druid != druid and not (can_carry and next_druid == _step(druid, delta)):
                raise ValueError(f'hero transition {i}/{key}: illegal inactive Druid carriage')
    return tuple(normalized)


def _origin_history(route, heroes, origin, last_frame):
    """Each layer maps (x, y, harvested) to one predecessor state."""
    state = (origin[0], origin[1], False)
    history = [{state: None}]
    for i, key in enumerate(route[:last_frame]):
        before, after = heroes[i:i + 2]
        delta = model.DIRECTIONS.get(key)
        next_layer = {}
        for state in history[-1]:
            x, y, harvested = state
            # Every token can remain stationary in every action phase.
            next_layer.setdefault(state, state)
            if key == 'A':
                continue
            if not before['active']:
                druid = _point(before, 'druid')
                if (not harvested and _point(after, 'druid') == druid
                        and (x, y) == _step(druid, delta)):
                    next_layer.setdefault((x, y, True), state)
            elif (harvested and _point(after, 'bard') != _point(before, 'bard')
                  and _near((x, y), _point(before, 'bard'))):
                target = _step((x, y), delta)
                if _inside(target):
                    next_layer.setdefault((*target, True), state)
        history.append(next_layer)
    return history


def reachable_token_states(route, hero_frames, origin, frame):
    """Return exact one-token states for local controls, without a goal demand."""
    model.exact._guard_current_source()
    heroes = _heroes(route, hero_frames)
    if (not isinstance(origin, (tuple, list)) or len(origin) != 2
            or any(type(value) is not int for value in origin) or tuple(origin) not in model.BORDER):
        raise ValueError('origin must be one original border wall coordinate')
    if isinstance(frame, bool) or not isinstance(frame, int) or not 0 <= frame <= len(route):
        raise ValueError('frame must be an integer in the route horizon')
    states = _origin_history(route, heroes, tuple(origin), frame)[-1]
    return [{'x': x, 'y': y, 'harvested': flag} for x, y, flag in sorted(states)]


def _maximum_matching(adjacency):
    """Match switch indices to border-origin indices using augmenting paths."""
    by_origin = {}
    by_switch = {}

    def augment(switch, visited):
        for origin in adjacency[switch]:
            if origin in visited:
                continue
            visited.add(origin)
            if origin not in by_origin or augment(by_origin[origin], visited):
                by_origin[origin] = switch
                by_switch[switch] = origin
                return True
        return False

    for switch in range(len(adjacency)):
        augment(switch, set())
    return by_switch, by_origin


def _hall_obstruction(adjacency, by_switch, by_origin):
    """Alternating reachability from unmatched switches gives |N(S)| < |S|."""
    switches = set(range(len(adjacency))) - set(by_switch)
    origins = set()
    pending = deque(sorted(switches))
    while pending:
        switch = pending.popleft()
        for origin in adjacency[switch]:
            if origin in origins:
                continue
            origins.add(origin)
            matched = by_origin.get(origin)
            if matched is not None and matched not in switches:
                switches.add(matched)
                pending.append(matched)
    return {
        'switch_indices': sorted(switches),
        'switches': [list(model.SWITCHES[j]) for j in sorted(switches)],
        'origin_indices': sorted(origins),
        'neighbor_origins': [list(model.BORDER[j]) for j in sorted(origins)],
        'switch_count': len(switches), 'neighbor_count': len(origins),
        'deficiency': len(switches) - len(origins),
    }


def _path(history, target):
    state = target
    reverse = [state]
    for layer in reversed(history[1:]):
        state = layer[state]
        reverse.append(state)
    return list(reversed(reverse))


def allocate(route, hero_frames, landmark_frame):
    """Exactly allocate nine origins for this fixed trace and common landmark.

    Returns JSON-serializable data. ``infeasible`` is strictly conditional on
    the given valid hero trace and specified landmark. Earlier hero-goal pairs
    return ``unsupported_trajectory``, never an infeasibility claim. Feasible
    witnesses retain the supplied heroes and freeze tokens after the landmark.
    """
    model.exact._guard_current_source()
    report = {
        'status': 'invalid_trajectory', 'feasible': None,
        'scope': 'fixed hero trajectory and specified common landmark only',
        'global_bound_claim': None, 'original_game_solution_claim': False,
        'route': route if isinstance(route, str) else None,
        'landmark_frame': landmark_frame if type(landmark_frame) is int else None,
        'frames': [],
    }
    try:
        heroes = _heroes(route, hero_frames)
    except ValueError as exc:
        report['reason'] = str(exc)
        return report
    report['horizon'] = len(route)
    if isinstance(landmark_frame, bool) or not isinstance(landmark_frame, int) or not 0 <= landmark_frame <= len(route):
        report.update(status='invalid_input', reason='landmark_frame must be an integer in the route horizon')
        return report
    if not _goal_pair(heroes[-1]):
        report['reason'] = 'final heroes must occupy the two distinct goals'
        return report
    earlier_goals = [i for i, frame in enumerate(heroes[:-1]) if _goal_pair(frame)]
    if earlier_goals:
        report.update(status='unsupported_trajectory',
                      reason='earlier hero-goal pairs require token-dependent terminal absorption analysis',
                      earlier_goal_frames=earlier_goals)
        return report
    histories = [_origin_history(route, heroes, origin, landmark_frame) for origin in model.BORDER]
    adjacency = [[] for _ in model.SWITCHES]
    terminal_states = {}
    for origin_index, history in enumerate(histories):
        for switch_index, switch in enumerate(model.SWITCHES):
            for flag in (False, True):
                state = (*switch, flag)
                if state in history[-1]:
                    adjacency[switch_index].append(origin_index)
                    terminal_states[switch_index, origin_index] = state
                    break
    by_switch, by_origin = _maximum_matching(adjacency)
    report.update(matching_size=len(by_switch),
                  edges=[{'switch_index': j, 'switch': list(model.SWITCHES[j]),
                          'origin_indices': list(origins),
                          'origins': [list(model.BORDER[k]) for k in origins]}
                         for j, origins in enumerate(adjacency)],
                  matching=[{'switch_index': j, 'switch': list(model.SWITCHES[j]),
                             'origin_index': by_switch[j],
                             'origin': list(model.BORDER[by_switch[j]])}
                            for j in sorted(by_switch)])
    if len(by_switch) != len(model.SWITCHES):
        report.update(status='infeasible', feasible=False,
                      hall_obstruction=_hall_obstruction(adjacency, by_switch, by_origin))
        return report
    paths = []
    for j in range(len(model.SWITCHES)):
        origin_index = by_switch[j]
        path = _path(histories[origin_index], terminal_states[j, origin_index])
        path.extend([path[-1]] * (len(route) - landmark_frame))
        paths.append(path)
    witness = []
    seen = False
    first_landmark = None
    for i, heroes_at_i in enumerate(heroes):
        states = [path[i] for path in paths]
        at_landmark = all((state[0], state[1]) == switch for state, switch in zip(states, model.SWITCHES))
        if at_landmark and first_landmark is None:
            first_landmark = i
        seen = seen or at_landmark
        witness.append(dict(heroes_at_i,
                            token_x=[state[0] for state in states],
                            token_y=[state[1] for state in states],
                            harvested=[state[2] for state in states], landmark_seen=seen))
    report.update(status='feasible', feasible=True, frames=witness,
                  origins=[list(model.BORDER[by_switch[j]]) for j in range(len(model.SWITCHES))],
                  first_landmark_frame=first_landmark,
                  token_paths=[[{'x': x, 'y': y, 'harvested': flag} for x, y, flag in path]
                               for path in paths])
    return report
