"""Pure Boolean/bitvector encoding of the retained integer master events.

No constraint is relaxed. Coordinates are zero-extended before signed
subtraction. For horizon H, N original border cells, and maximum joint travel
M=2(W-1)+2(height-1), every count/sum is in [0,H+N+M+1]. The selected width has
signed maximum at least H+N+M+2, so all additions, differences, maxima
and signed comparisons below equal their mathematical integer counterparts.

The event chronology, source guard and normalization argument are documented
in event_bounds.md. This alternative leaves events.py as the measured baseline.
"""
from __future__ import annotations

import z3

from . import events as baseline

ORIGINS = baseline.ORIGINS
STARTS = baseline.STARTS
GOALS = baseline.GOALS


def arithmetic_width(horizon):
    """A signed width covering every intermediate value without overflow."""
    if type(horizon) is not int or horizon < 0:
        raise ValueError('horizon must be a nonnegative integer')
    maximum = (horizon + len(ORIGINS) + 2 * (baseline.geometry.W - 1)
               + 2 * (baseline.geometry.H - 1) + 2)
    return maximum.bit_length() + 1


def _wide(value, width):
    if type(value) is int:
        return z3.BitVecVal(value, width)
    if not z3.is_bv(value) or value.size() > width:
        raise ValueError('Expected unsigned coordinate fitting arithmetic width')
    return z3.ZeroExt(width - value.size(), value)


def _max_zero(a, b):
    zero = z3.BitVecVal(0, a.size())
    return z3.If(a >= b, z3.If(a > zero, a, zero), z3.If(b > zero, b, zero))


def joint_distance(before, after, width):
    """Same J as events.joint_distance, with provably wide signed arithmetic."""
    delta = [[_wide(q, width) - _wide(p, width) for p, q in zip(old, new)]
             for old, new in zip(before, after)]
    terms = [_max_zero(sign * delta[0][axis], sign * delta[1][axis])
             for axis in (0, 1) for sign in (-1, 1)]
    return sum(terms, z3.BitVecVal(0, width))


def _sum_bools(values, width):
    """Balanced population count; every intermediate sum is nonnegative."""
    zero, one = z3.BitVecVal(0, width), z3.BitVecVal(1, width)
    layer = [z3.If(v, one, zero) for v in values]
    if not layer:
        return zero
    while len(layer) > 1:
        layer = [layer[i] + layer[i + 1] if i + 1 < len(layer) else layer[i]
                 for i in range(0, len(layer), 2)]
    return layer[0]


def add_master_constraints(master, *, symmetry=False):
    """Attach integer-equivalent events using only Bool and BitVec sorts.

    Preconditions match events.add_master_constraints: in-board coordinates,
    legal relaxed transitions, and terminal absorption supplied by the master.
    Returned numeric metadata uses signed, nonnegative bitvector values.
    """
    baseline.source._guard_current_source()
    horizon = master.horizon
    width = arithmetic_width(horizon)
    if (horizon != len(master.actions) or len(master.landmarks) != horizon
            or len(master.frames) != horizon + 1
            or any(len(row) != 5 for row in master.actions)):
        raise ValueError('Inconsistent master horizon or UDLRA actions')
    solver, frames = master.solver, master.frames
    seen = tuple(tuple(z3.Bool(f'causal_seen_{t}_{x}_{y}') for x, y in ORIGINS)
                 for t in range(horizon + 1))
    solver.add(*[z3.Not(v) for v in seen[0]])
    release, switches = [], []
    for t, row in enumerate(master.actions):
        before, after = frames[t:t + 2]
        preterminal = z3.Not(baseline._terminal(before))
        holds = baseline._at(baseline._points(before)[1], baseline._points(after)[1])
        events = []
        for j, origin in enumerate(ORIGINS):
            approaches = []
            for k, (dx, dy) in enumerate(baseline.geometry.DIRECTIONS.values()):
                # Reverse the constant target equation rather than performing
                # coordinate-width addition that could wrap at the boundary.
                px, py = origin[0] - dx, origin[1] - dy
                if 0 <= px < baseline.geometry.W and 0 <= py < baseline.geometry.H:
                    approaches.append(z3.And(row[k], before.druid_x == px,
                                               before.druid_y == py))
            event = z3.Bool(f'causal_release_{t}_{origin[0]}_{origin[1]}')
            solver.add(event == z3.And(preterminal, z3.Not(before.active), holds,
                                       z3.Or(*approaches)),
                       seen[t + 1][j] == z3.Or(seen[t][j], event))
            events.append(event)
        release.append(tuple(events))
        switches.append(z3.And(preterminal, row[4]))
        if symmetry and t + 1 < horizon:
            solver.add(z3.Not(z3.And(preterminal, row[4], master.actions[t + 1][4])))
    counts = tuple(_sum_bools(row, width) for row in seen)
    zero, nine = z3.BitVecVal(0, width), z3.BitVecVal(9, width)
    prefix, suffix, ready = [], [], []
    for t, frame in enumerate(frames):
        current = baseline._points(frame)
        spent = joint_distance(STARTS, current, width) + counts[t] + _sum_bools(switches[:t], width)
        solver.add(spent <= z3.BitVecVal(t, width))
        prefix.append(spent)
        deficit = z3.If(counts[t] < nine, nine - counts[t], zero)
        remaining = []
        for assigned in (GOALS, tuple(reversed(GOALS))):
            activate = z3.If(z3.And(z3.Not(frame.active),
                                    z3.Not(baseline._at(current[0], assigned[0]))),
                             z3.BitVecVal(1, width), zero)
            remaining.append(joint_distance(current, assigned, width) + deficit + activate)
        solver.add(z3.Or(*[bound <= z3.BitVecVal(horizon - t, width) for bound in remaining]))
        suffix.append(tuple(remaining))
        ready.append(counts[t] >= nine)
        if t:
            solver.add(z3.Implies(master.landmarks[t - 1], ready[-1]))
    return {'origins': ORIGINS, 'release': tuple(release), 'seen': seen,
            'seen_count': counts, 'switches': tuple(switches),
            'joint_prefix': tuple(prefix), 'suffix': tuple(suffix),
            'landmark_ready': tuple(ready), 'symmetry': bool(symmetry),
            'kind': 'hero_release_opportunity', 'arithmetic_width': width,
            'encoding': 'pure_bitvector'}
