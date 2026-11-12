"""Unrestricted bounded hero master and exact universal-arc cut predicates.

Earlier wins can be represented at a later horizon by prepending held U inputs:
Druid may stay at the initial position and its target (2, 3) is not a border
origin. This preserves the material history while delaying its landmark.
"""
from dataclasses import dataclass, field

import z3

from . import model


@dataclass(frozen=True)
class HeroFrame:
    bard_x: z3.BitVecRef
    bard_y: z3.BitVecRef
    druid_x: z3.BitVecRef
    druid_y: z3.BitVecRef
    active: z3.BoolRef


@dataclass(frozen=True)
class Master:
    solver: z3.Solver
    actions: tuple
    frames: tuple
    landmarks: tuple
    horizon: int
    capacity_cache: dict = field(default_factory=dict, compare=False, repr=False)


def _goal(frame):
    a, b = model.GOALS
    return z3.Or(z3.And(model._at(frame.bard_x, frame.bard_y, a),
                        model._at(frame.druid_x, frame.druid_y, b)),
                 z3.And(model._at(frame.bard_x, frame.bard_y, b),
                        model._at(frame.druid_x, frame.druid_y, a)))


def build_master(horizon):
    if type(horizon) is not int or horizon < 0:
        raise ValueError('horizon must be a nonnegative integer')
    model.exact._guard_current_source()
    solver = z3.Solver()
    frames = tuple(HeroFrame(z3.BitVec(f'bard_x_{i}', 4),
                             z3.BitVec(f'bard_y_{i}', 3),
                             z3.BitVec(f'druid_x_{i}', 4),
                             z3.BitVec(f'druid_y_{i}', 3),
                             z3.Bool(f'active_{i}')) for i in range(horizon + 1))
    actions = tuple(tuple(z3.Bool(f'action_{i}_{key}') for key in model.KEYS)
                    for i in range(horizon))
    landmarks = tuple(z3.Bool(f'landmark_{t}') for t in range(1, horizon + 1))
    for f in frames:
        solver.add(z3.ULT(f.bard_x, model.W), z3.ULT(f.bard_y, model.H),
                   z3.ULT(f.druid_x, model.W), z3.ULT(f.druid_y, model.H))
    f = frames[0]
    solver.add(f.bard_x == 2, f.bard_y == 2, f.druid_x == 2,
               f.druid_y == 4, z3.Not(f.active))
    for i, row in enumerate(actions):
        before, after = frames[i:i + 2]
        solver.add(z3.PbEq([(v, 1) for v in row], 1), z3.Not(_goal(before)))
        bard_hold = model._same_position(before.bard_x, before.bard_y, after.bard_x, after.bard_y)
        druid_hold = model._same_position(before.druid_x, before.druid_y, after.druid_x, after.druid_y)
        solver.add(z3.Implies(row[4], z3.And(bard_hold, druid_hold,
                                               after.active == z3.Not(before.active))))
        for j, key in enumerate(model.KEYS[:4]):
            dx, dy = model.DIRECTIONS[key]
            bard_step = model._same_position(after.bard_x, after.bard_y,
                                              before.bard_x + dx, before.bard_y + dy)
            druid_step = model._same_position(after.druid_x, after.druid_y,
                                               before.druid_x + dx, before.druid_y + dy)
            active_rules = z3.And(z3.Or(bard_hold, bard_step),
                z3.Or(druid_hold, z3.And(z3.Not(bard_hold),
                    model._near(before.druid_x, before.druid_y, before.bard_x, before.bard_y), druid_step)))
            inactive_rules = z3.And(bard_hold, z3.Or(druid_hold, druid_step))
            solver.add(z3.Implies(row[j], z3.And(after.active == before.active,
                                                  z3.If(before.active, active_rules, inactive_rules))))
    solver.add(_goal(frames[-1]))
    solver.add(z3.PbEq([(v, 1) for v in landmarks], 1) if landmarks else z3.BoolVal(False))
    return Master(solver, actions, frames, landmarks, horizon)


def decode(master, z3model):
    def val(v):
        result = z3model.eval(v, model_completion=True)
        return z3.is_true(result) if z3.is_bool(v) else result.as_long()
    return {'route': ''.join(next(k for k, v in zip(model.KEYS, row) if val(v))
                             for row in master.actions),
            'heroes': [{name: val(getattr(f, name)) for name in HeroFrame.__dataclass_fields__}
                       for f in master.frames],
            'landmark': next(t for t, v in enumerate(master.landmarks, 1) if val(v))}


def symbolic_capacity(master, arc):
    """Return a cached predicate shared by arcs with the same capacity rule."""
    key = (arc.kind, arc.params)
    if key not in master.capacity_cache:
        master.capacity_cache[key] = _capacity_expression(master, arc)
    return master.capacity_cache[key]


def _capacity_expression(master, arc):
    kind, p = arc.kind, arc.params
    if kind == 'one':
        return z3.BoolVal(True)
    if kind == 'landmark':
        (t,) = p
        return master.landmarks[t - 1]
    if kind == 'cell_free':
        t, x, y = p
        f = master.frames[t]
        return z3.And(z3.Not(model._at(f.bard_x, f.bard_y, (x, y))),
                      z3.Not(model._at(f.druid_x, f.druid_y, (x, y))))
    if kind == 'release':
        t, x, y = p
        before, after = master.frames[t - 1:t + 1]
        stay = model._same_position(before.druid_x, before.druid_y, after.druid_x, after.druid_y)
        return z3.And(z3.Not(before.active), stay, z3.Or(*[
            z3.And(master.actions[t - 1][i], model._at(before.druid_x + dx, before.druid_y + dy, (x, y)))
            for i, (dx, dy) in enumerate(model.DIRECTIONS.values())]))
    if kind == 'carry':
        t, x, y, nx, ny = p
        before, after = master.frames[t:t + 2]
        moved = z3.Not(model._same_position(before.bard_x, before.bard_y, after.bard_x, after.bard_y))
        keys = [z3.And(master.actions[t][i],
                       model._same_position(after.bard_x, after.bard_y,
                                            before.bard_x + dx, before.bard_y + dy))
                for i, (dx, dy) in enumerate(model.DIRECTIONS.values())
                if (x + dx, y + dy) == (nx, ny)]
        return z3.And(before.active, moved, model._near(before.bard_x, before.bard_y,
                        z3.BitVecVal(x, 4), z3.BitVecVal(y, 3)), z3.Or(*keys))
    raise ValueError(f'unknown arc kind: {kind!r}')


def add_cut(master, universe, crossing_ids, required_flow=9):
    if type(required_flow) is not int or required_flow < 0:
        raise ValueError('required_flow must be a nonnegative integer')
    edges = {edge.edge_id: edge for edge in universe.edges}
    ids = tuple(crossing_ids)
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate crossing edge id')
    grouped = {}
    for edge_id in ids:
        edge = edges[edge_id]
        key = (edge.kind, edge.params)
        if key in grouped:
            predicate, weight = grouped[key]
            grouped[key] = (predicate, weight + 1)
        else:
            grouped[key] = (symbolic_capacity(master, edge), 1)
    predicates = list(grouped.values())
    expression = z3.PbGe(predicates, required_flow) if predicates else z3.BoolVal(required_flow == 0)
    master.solver.add(expression)
    return expression


def pin_assignment(master, assignment):
    route, heroes, landmark = (assignment[k] for k in ('route', 'heroes', 'landmark'))
    if not isinstance(route, str) or len(route) != master.horizon or any(k not in model.KEYS for k in route):
        raise ValueError('invalid route')
    if len(heroes) != master.horizon + 1 or type(landmark) is not int or not 1 <= landmark <= master.horizon:
        raise ValueError('invalid heroes or landmark')
    for row, key in zip(master.actions, route):
        master.solver.add(row[model.KEYS.index(key)])
    for f, values in zip(master.frames, heroes):
        for name in HeroFrame.__dataclass_fields__:
            master.solver.add(getattr(f, name) == values[name])
    master.solver.add(master.landmarks[landmark - 1])
