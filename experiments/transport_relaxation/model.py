"""A global nine-token transport relaxation for the original III-14 board.

Each token is labelled by the switch that it must reach at one historical
frame. Its initial position is an existentially chosen, distinct border wall.
Collisions, material type, doors and freezing are omitted. SAT therefore means
only that this relaxation is feasible; it is not a winning puzzle witness.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from collections.abc import Mapping, Sequence

import z3

from experiments.exact_frontier import iii14_problem as exact

W, H = 15, 7
ROWS = tuple(exact.EXPECTED_ROWS)
SWITCHES = tuple((x, y) for y, row in enumerate(ROWS)
                 for x, char in enumerate(row) if char == '}')
GOALS = tuple((x, y) for y, row in enumerate(ROWS)
              for x, char in enumerate(row) if char == 'G')
BORDER = tuple((x, y) for y, row in enumerate(ROWS)
               for x, char in enumerate(row) if char == '#')
TOKEN_COUNT = len(SWITCHES)
KEYS = 'UDLRA'
DIRECTIONS = {'U': (0, -1), 'D': (0, 1), 'L': (-1, 0), 'R': (1, 0)}

MODEL_CONTRACT = {
    'version': 1,
    'room': 'III-14',
    'board': 'original 15x7',
    'kind': 'global sound nine-token transport relaxation',
    'objective': 'historical nine-token switch landmark, then both heroes at distinct goals by horizon',
    'state_encoding': '4-bit x and 3-bit y coordinates; active, harvested and landmark booleans',
    'actions': list(KEYS),
    'action_encoding': 'one-hot Boolean variables named action_{zero_based_step}_{action}',
    'token_labels': 'nine switch positions in row-major order',
    'token_origins': 'existential pairwise-distinct original border wall cells',
    'harvest': 'Druid targets an unharvested token with a directional input and stays in place',
    'bard_transport': 'if Bard steps, each harvested token within prior Chebyshev distance two may independently stay or take the same step',
    'inactive_druid_transport': 'if Bard steps, Druid within prior Chebyshev distance two may stay or take the same step',
    'ignored_rules': ['collisions', 'walls', 'doors', 'material freezing', 'material deletion'],
    'deleted_material_representation': 'persistent optional-staying ghost tokens',
    'goal_absorbing': True,
    'prefix_or_neighborhood_restriction': False,
    'external_lower_bound_assumed': False,
    'source_guard': 'existing exact III-14 source and grid guard is checked for every build',
    'solver_result_semantics': {
        'sat': 'relaxation feasible; no puzzle solution or upper bound follows',
        'unsat': 'no modeled transport trace by horizon; transfers to original game only under the soundness argument',
        'unknown': 'inconclusive',
    },
    'original_game_equivalence_proved': False,
}


@dataclass(frozen=True)
class Frame:
    bard_x: z3.BitVecRef
    bard_y: z3.BitVecRef
    druid_x: z3.BitVecRef
    druid_y: z3.BitVecRef
    active: z3.BoolRef
    token_x: tuple[z3.BitVecRef, ...]
    token_y: tuple[z3.BitVecRef, ...]
    harvested: tuple[z3.BoolRef, ...]
    landmark_seen: z3.BoolRef


def new_frame(index: int) -> Frame:
    """Create symbolic fields; domain and transition constraints are separate."""
    return Frame(
        z3.BitVec(f'bard_x_{index}', 4), z3.BitVec(f'bard_y_{index}', 3),
        z3.BitVec(f'druid_x_{index}', 4), z3.BitVec(f'druid_y_{index}', 3),
        z3.Bool(f'active_{index}'),
        tuple(z3.BitVec(f'token_x_{index}_{j}', 4) for j in range(TOKEN_COUNT)),
        tuple(z3.BitVec(f'token_y_{index}_{j}', 3) for j in range(TOKEN_COUNT)),
        tuple(z3.Bool(f'harvested_{index}_{j}') for j in range(TOKEN_COUNT)),
        z3.Bool(f'landmark_seen_{index}'))


def frame_constraints(frame: Frame, values: Mapping) -> list[z3.BoolRef]:
    """Return equalities pinning any supplied Frame fields to concrete values.

    Coordinate and harvested tuples must have all nine entries. Omitted fields
    remain unconstrained, allowing projection controls to pin only known data.
    """
    known = {field.name for field in fields(Frame)}
    unknown = set(values) - known
    if unknown:
        raise ValueError(f'Unknown frame fields: {sorted(unknown)}')
    constraints = []
    for name, value in values.items():
        variable = getattr(frame, name)
        if isinstance(variable, tuple):
            if not isinstance(value, Sequence) or len(value) != TOKEN_COUNT:
                raise ValueError(f'{name} requires {TOKEN_COUNT} entries')
            constraints.extend(a == b for a, b in zip(variable, value))
        else:
            constraints.append(variable == value)
    return constraints


def _same_position(ax, ay, bx, by):
    return z3.And(ax == bx, ay == by)


def _at(x, y, point):
    return _same_position(x, y, *point)


def at_landmark(frame: Frame):
    return z3.And(*[_at(frame.token_x[j], frame.token_y[j], point)
                    for j, point in enumerate(SWITCHES)])


def is_terminal(frame: Frame):
    first, second = GOALS
    return z3.And(frame.landmark_seen, z3.Or(
        z3.And(_at(frame.bard_x, frame.bard_y, first),
               _at(frame.druid_x, frame.druid_y, second)),
        z3.And(_at(frame.bard_x, frame.bard_y, second),
               _at(frame.druid_x, frame.druid_y, first))))


def _components(frame: Frame):
    return (frame.bard_x, frame.bard_y, frame.druid_x, frame.druid_y,
            frame.active, *frame.token_x, *frame.token_y, *frame.harvested,
            frame.landmark_seen)


def _hold(before: Frame, after: Frame):
    return z3.And(*[old == new for old, new in zip(_components(before), _components(after))])


def _near(ax, ay, bx, by):
    # Unsigned comparisons avoid 4-bit signed-coordinate and subtraction-wrap bugs.
    dx = z3.If(z3.UGE(ax, bx), ax - bx, bx - ax)
    dy = z3.If(z3.UGE(ay, by), ay - by, by - ay)
    return z3.And(z3.ULE(dx, 2), z3.ULE(dy, 2))


def _stay_or_step(old_x, old_y, new_x, new_y, dx, dy):
    return z3.Or(_same_position(new_x, new_y, old_x, old_y),
                 _same_position(new_x, new_y, old_x + dx, old_y + dy))


def _transition(before: Frame, after: Frame, key: str):
    history = after.landmark_seen == z3.Or(before.landmark_seen, at_landmark(after))
    if key == 'A':
        return z3.And(history, after.active == z3.Not(before.active),
                      *[old == new for old, new in zip(
                          _components(before)[:4], _components(after)[:4])],
                      *[old == new for old, new in zip(before.token_x, after.token_x)],
                      *[old == new for old, new in zip(before.token_y, after.token_y)],
                      *[old == new for old, new in zip(before.harvested, after.harvested)])

    dx, dy = DIRECTIONS[key]
    bard_moved = z3.Not(_same_position(before.bard_x, before.bard_y,
                                      after.bard_x, after.bard_y))
    bard_rules = [
        _stay_or_step(before.bard_x, before.bard_y, after.bard_x, after.bard_y, dx, dy),
        after.active == before.active,
        *[old == new for old, new in zip(before.harvested, after.harvested)],
    ]
    for j in range(TOKEN_COUNT):
        can_carry = z3.And(bard_moved, before.harvested[j],
                           _near(before.token_x[j], before.token_y[j], before.bard_x, before.bard_y))
        token_stayed = _same_position(before.token_x[j], before.token_y[j],
                                      after.token_x[j], after.token_y[j])
        token_stepped = _same_position(after.token_x[j], after.token_y[j],
                                       before.token_x[j] + dx, before.token_y[j] + dy)
        bard_rules.append(z3.Or(token_stayed, z3.And(can_carry, token_stepped)))
    druid_stayed = _same_position(before.druid_x, before.druid_y,
                                  after.druid_x, after.druid_y)
    druid_stepped = _same_position(after.druid_x, after.druid_y,
                                   before.druid_x + dx, before.druid_y + dy)
    can_carry_druid = z3.And(bard_moved, _near(before.druid_x, before.druid_y,
                                             before.bard_x, before.bard_y))
    bard_rules.append(z3.Or(druid_stayed, z3.And(can_carry_druid, druid_stepped)))

    druid_rules = [
        _same_position(before.bard_x, before.bard_y, after.bard_x, after.bard_y),
        _stay_or_step(before.druid_x, before.druid_y, after.druid_x, after.druid_y, dx, dy),
        after.active == before.active,
        *[old == new for old, new in zip(before.token_x, after.token_x)],
        *[old == new for old, new in zip(before.token_y, after.token_y)],
    ]
    for j in range(TOKEN_COUNT):
        new_harvest = z3.And(z3.Not(before.harvested[j]), after.harvested[j])
        harvest_target = _same_position(before.token_x[j], before.token_y[j],
                                        before.druid_x + dx, before.druid_y + dy)
        druid_rules.extend([
            z3.Implies(before.harvested[j], after.harvested[j]),
            z3.Implies(new_harvest, z3.And(harvest_target, druid_stayed)),
        ])
    return z3.And(history, z3.If(before.active, z3.And(*bard_rules), z3.And(*druid_rules)))


def _bounds(frame: Frame):
    return [bound for x, y in [(frame.bard_x, frame.bard_y),
                              (frame.druid_x, frame.druid_y),
                              *zip(frame.token_x, frame.token_y)]
            for bound in (z3.ULT(x, W), z3.ULT(y, H))]


def transition_constraints(before: Frame, after: Frame, key: str):
    """Return bounded single-action constraints, including terminal absorption."""
    if not isinstance(key, str) or len(key) != 1 or key not in KEYS:
        raise ValueError('expected one action from UDLRA')
    return [*_bounds(before), *_bounds(after),
            z3.If(is_terminal(before), _hold(before, after), _transition(before, after, key))]


def build_problem(horizon: int):
    """Return solver, UDLRA action rows and frames for the complete relaxation."""
    if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 0:
        raise ValueError('horizon must be a nonnegative integer')
    exact._guard_current_source()
    solver = z3.Solver()
    frames = [new_frame(i) for i in range(horizon + 1)]
    actions = [[z3.Bool(f'action_{i}_{key}') for key in KEYS] for i in range(horizon)]
    for frame in frames:
        solver.add(*_bounds(frame))
    initial = frames[0]
    solver.add(*frame_constraints(initial, {
        'bard_x': 2, 'bard_y': 2, 'druid_x': 2, 'druid_y': 4,
        'active': False, 'harvested': (False,) * TOKEN_COUNT,
    }))
    solver.add(initial.landmark_seen == at_landmark(initial))
    for j in range(TOKEN_COUNT):
        solver.add(z3.Or(*[_at(initial.token_x[j], initial.token_y[j], point) for point in BORDER]))
        for k in range(j):
            solver.add(z3.Not(_same_position(initial.token_x[j], initial.token_y[j],
                                             initial.token_x[k], initial.token_y[k])))
    for i, selected in enumerate(actions):
        before, after = frames[i:i + 2]
        solver.add(z3.PbEq([(choice, 1) for choice in selected], 1))
        terminal = is_terminal(before)
        solver.add(z3.Implies(terminal, _hold(before, after)))
        for key, choice in zip(KEYS, selected):
            solver.add(z3.Implies(z3.And(z3.Not(terminal), choice),
                                  _transition(before, after, key)))
    solver.add(is_terminal(frames[-1]))
    return solver, actions, frames
