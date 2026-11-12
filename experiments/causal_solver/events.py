"""Necessary, source-guarded III-14 events and joint-input lower bounds.

These clauses constrain original winning traces without selecting a transport
schedule.  See event_bounds.md for the projection and normalization arguments.
"""
from __future__ import annotations

from types import SimpleNamespace

import z3

from experiments.exact_frontier import iii14_problem as source
from experiments.transport_relaxation import model as geometry
from soko_mcp.oracle import PuzzleScriptOracle

ORIGINS = geometry.BORDER
STARTS = ((2, 2), (2, 4))
GOALS = geometry.GOALS
KEYS = 'UDLRA'


def _integer(value):
    return z3.BV2Int(value) if z3.is_bv(value) else value


def _max_zero(a, b):
    if isinstance(a, int) and isinstance(b, int):
        return max(0, a, b)
    return z3.If(a >= b, z3.If(a > 0, a, 0), z3.If(b > 0, b, 0))


def joint_distance(before, after):
    """Minimum directional-input count ignoring blockers and activity.

    Each argument is ((bard_x, bard_y), (druid_x, druid_y)); coordinates
    may be concrete integers, unsigned bitvectors, or Z3 integer expressions.
    """
    delta = [[_integer(q) - _integer(p) for p, q in zip(old, new)]
             for old, new in zip(before, after)]
    return sum(_max_zero(sign * delta[0][axis], sign * delta[1][axis])
               for axis in (0, 1) for sign in (-1, 1))


def _points(frame):
    return ((frame.bard_x, frame.bard_y), (frame.druid_x, frame.druid_y))


def _at(point, target):
    return z3.And(*[a == b for a, b in zip(point, target)])


def _terminal(frame):
    bard, druid = _points(frame)
    return z3.Or(z3.And(_at(bard, GOALS[0]), _at(druid, GOALS[1])),
                 z3.And(_at(bard, GOALS[1]), _at(druid, GOALS[0])))


def _sum_bools(values):
    return z3.Sum([z3.If(v, 1, 0) for v in values]) if values else z3.IntVal(0)


def _attach(solver, actions, frames, landmarks, *, wall_at=None,
            symmetry=False, full_states=None):
    source._guard_current_source()
    horizon = len(actions)
    if len(frames) != horizon + 1 or any(len(row) != 5 for row in actions):
        raise ValueError('Expected horizon+1 frames and five UDLRA actions per input')
    seen = tuple(tuple(z3.Bool(f'causal_seen_{t}_{x}_{y}') for x, y in ORIGINS)
                 for t in range(horizon + 1))
    solver.add(*[z3.Not(v) for v in seen[0]])
    release = []
    switches = []
    for t, row in enumerate(actions):
        before, after = frames[t:t + 2]
        preterminal = z3.Not(_terminal(before))
        holds = _at(_points(before)[1], _points(after)[1])
        events = []
        for j, origin in enumerate(ORIGINS):
            approaches = []
            for k, (dx, dy) in enumerate(geometry.DIRECTIONS.values()):
                # Arithmetic is on integers: boundary targets never wrap.
                approaches.append(z3.And(row[k],
                    _integer(before.druid_x) + dx == origin[0],
                    _integer(before.druid_y) + dy == origin[1]))
            event = z3.Bool(f'causal_release_{t}_{origin[0]}_{origin[1]}')
            cause = z3.And(preterminal, z3.Not(before.active), holds,
                           z3.Or(*approaches))
            if wall_at is not None:
                cause = z3.And(cause, wall_at(t, origin))
            solver.add(event == cause,
                       seen[t + 1][j] == z3.Or(seen[t][j], event))
            events.append(event)
        release.append(tuple(events))
        switches.append(z3.And(preterminal, row[4]))
        if symmetry and t + 1 < horizon:
            solver.add(z3.Not(z3.And(preterminal, row[4], actions[t + 1][4])))
        if symmetry and full_states is not None:
            changed = z3.Or(*[a != b for a, b in
                               zip(full_states[t], full_states[t + 1])])
            solver.add(z3.Implies(z3.And(preterminal, z3.Not(row[4])), changed))
    counts = tuple(_sum_bools(row) for row in seen)
    prefix, suffix, ready = [], [], []
    for t, frame in enumerate(frames):
        current = _points(frame)
        spent = joint_distance(STARTS, current) + counts[t] + _sum_bools(switches[:t])
        solver.add(spent <= t)
        prefix.append(spent)
        deficit = z3.If(counts[t] < 9, 9 - counts[t], 0)
        remaining = []
        for assigned in (GOALS, tuple(reversed(GOALS))):
            activate = z3.If(z3.And(z3.Not(frame.active),
                                    z3.Not(_at(current[0], assigned[0]))), 1, 0)
            remaining.append(joint_distance(current, assigned) + deficit + activate)
        solver.add(z3.Or(*[bound <= horizon - t for bound in remaining]))
        suffix.append(tuple(remaining))
        ready.append(counts[t] >= 9)
        if landmarks[t] is not None:
            solver.add(z3.Implies(landmarks[t], ready[-1]))
    return {'origins': ORIGINS, 'release': tuple(release), 'seen': seen,
            'seen_count': counts, 'switches': tuple(switches),
            'joint_prefix': tuple(prefix), 'suffix': tuple(suffix),
            'landmark_ready': tuple(ready), 'symmetry': bool(symmetry),
            'kind': 'actual_wall_release' if wall_at else 'hero_release_opportunity'}


def add_master_constraints(master, *, symmetry=False):
    """Attach events to an absorbing hero master (UDLRA, coordinate frames).

    Release opportunities overapproximate actual conversions.  Every selected
    common material-flow landmark needs nine distinct prior opportunities.
    """
    if master.horizon != len(master.actions) or len(master.landmarks) != master.horizon:
        raise ValueError('Inconsistent master horizon')
    return _attach(master.solver, master.actions, master.frames,
                   (None, *master.landmarks), symmetry=symmetry)


def _mask_coordinate(mask, axis):
    return z3.Sum([z3.If(z3.Extract(i, i, mask) == 1,
                         i % geometry.W if axis == 0 else i // geometry.W, 0)
                   for i in range(geometry.W * geometry.H)])


def add_exact_constraints(solver, actions, states, *, symmetry=False):
    """Attach the same bounds to exact seven-component bitmask states.

    The caller supplies the complete legal transition, one-hot heroes and
    absorbing goal semantics.  Here release means an actual border wall hit.
    """
    frames = tuple(SimpleNamespace(bard_x=_mask_coordinate(s[2], 0),
                                  bard_y=_mask_coordinate(s[2], 1),
                                  druid_x=_mask_coordinate(s[3], 0),
                                  druid_y=_mask_coordinate(s[3], 1), active=s[4])
                   for s in states)
    m = source.model
    landmarks = tuple(((s[0] | s[1]) & m.BV(m.SW)) == m.BV(m.SW) for s in states)

    def wall_at(t, point):
        index = point[1] * geometry.W + point[0]
        return z3.Extract(index, index, states[t][0]) == 1

    return _attach(solver, actions, frames, landmarks, wall_at=wall_at,
                   symmetry=symmetry, full_states=states)


def canonical_full_state_key(state):
    """Collision-free settled-state key; material identities are already absent."""
    if len(state) != 7:
        raise ValueError('Expected walls, crates, Bard, Druid, active, notes, doors')
    result = []
    for i, value in enumerate(state):
        if isinstance(value, z3.ExprRef):
            value = z3.simplify(value)
            if z3.is_true(value) or z3.is_false(value):
                value = z3.is_true(value)
            elif z3.is_bv_value(value) or z3.is_int_value(value):
                value = value.as_long()
            else:
                raise ValueError('State key requires concrete values')
        if i in (4, 6):
            if type(value) is not bool:
                raise ValueError('Activity and doors must be Boolean')
        elif type(value) is not int or not 0 <= value < 1 << (geometry.W * geometry.H):
            raise ValueError('Invalid state bitmask')
        result.append(value)
    return tuple(result)


def _oracle_state(oracle):
    """Read concrete engine fields without using a symbolic transition adapter."""
    masks = [0, 0, 0, 0]
    for y, row in enumerate(oracle.obj):
        for x, item in enumerate(row):
            for j, chars in enumerate(('#', '*', 'B5', 'D6')):
                if item is not None and item in chars:
                    masks[j] |= 1 << (y * geometry.W + x)
    active = oracle.find_active()
    if active is None or any(mask.bit_count() != 1 for mask in masks[2:]):
        raise ValueError('Trace loses a required hero')
    notes = sum(1 << (y * geometry.W + x) for x, y in oracle.notes)
    opened = any(cell == 'PO' for row in oracle.floor for cell in row)
    return canonical_full_state_key((*masks, active[2] == 'B', notes, opened))


def _concrete_points(state):
    return tuple(((v.bit_length() - 1) % geometry.W,
                  (v.bit_length() - 1) // geometry.W) for v in state[2:4])


def extract_events(route):
    """Independently replay a concrete trace and extract events, including padding.

    Inputs after the first win use the bounded model's absorbing semantics.
    Both opportunities and actual wall conversions are reported separately.
    """
    source._guard_current_source()
    if not isinstance(route, str) or any(key not in KEYS for key in route):
        raise ValueError('Expected a UDLRA route')
    oracle = PuzzleScriptOracle(3, source.EXPECTED_ROWS)
    states = [_oracle_state(oracle)]
    seen, actual_seen = set(), set()
    history = [{'seen': (), 'actual_seen': (), 'switches': 0}]
    events, first_win, switches = [], None, 0
    for t, key in enumerate(route):
        before = states[-1]
        if first_win is None:
            alive, won = oracle.step(key)
            if not alive:
                raise ValueError(f'Trace loses at input {t + 1}')
            after = _oracle_state(oracle)
        else:
            after, won = before, False
        origin = None
        actual = False
        if first_win is None:
            if key == 'A':
                switches += 1
            elif not before[4] and before[3] == after[3]:
                x, y = _concrete_points(before)[1]
                dx, dy = geometry.DIRECTIONS[key]
                target = (x + dx, y + dy)
                if target in ORIGINS:
                    origin = target
                    seen.add(target)
                    actual = bool(before[0] & (1 << (target[1] * geometry.W + target[0])))
                    if actual:
                        actual_seen.add(target)
        events.append({'input': t + 1, 'key': key, 'origin': origin,
                       'actual_conversion': actual, 'preterminal': first_win is None})
        if won and first_win is None:
            first_win = t + 1
        states.append(after)
        history.append({'seen': tuple(sorted(seen)), 'actual_seen': tuple(sorted(actual_seen)),
                        'switches': switches})
    material_landmarks = tuple(t for t, state in enumerate(states)
                               if (state[0] | state[1]) & source.model.SW == source.model.SW)
    return {'route': route, 'states': tuple(states), 'events': tuple(events),
            'history': tuple(history), 'material_landmarks': material_landmarks,
            'first_win': first_win}


def normalize_route(route):
    """Delete true unchanged inputs and cancelling AA before first win.

    Replay each replacement and compare the complete seven-field state.  Stop
    at the first win; the bounded model can pad the resulting shorter witness.
    """
    extracted = extract_events(route)
    states, result = extracted['states'], []
    limit = extracted['first_win'] or len(route)
    i = 0
    while i < limit:
        if states[i] == states[i + 1]:
            i += 1
        elif i + 1 < limit and route[i:i + 2] == 'AA' and states[i] == states[i + 2]:
            i += 2
        else:
            result.append(route[i])
            i += 1
    normalized = ''.join(result)
    replay = extract_events(normalized)
    if replay['states'][-1] != states[limit]:
        raise AssertionError('Normalization changed the complete endpoint state')
    # Deleting a no-op can expose a new AA pair.
    return normalize_route(normalized) if normalized != route else normalized
