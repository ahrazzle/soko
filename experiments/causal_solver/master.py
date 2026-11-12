"""A hero/action projection with genuine terminal absorption.

Every concrete <= H winning execution projects directly: retain the real
prefix, then hold both heroes and active identity after its first win. No
artificial initial inputs are needed. The selected material landmark must be
at or before that first terminal frame.
"""
from collections import deque

import z3

from experiments.transport_relaxation import allocation, cut_certificate
from experiments.transport_relaxation import flow_allocation, global_master, model, universal_flow


def build_master(horizon, *, use_events=True, symmetry=False, event_encoding='integer'):
    if type(horizon) is not int or horizon < 0:
        raise ValueError('horizon must be a nonnegative integer')
    if event_encoding not in ('integer', 'bitvector'):
        raise ValueError('unknown event arithmetic')
    model.exact._guard_current_source()
    solver = z3.Solver()
    frames = tuple(global_master.HeroFrame(
        z3.BitVec(f'bard_x_{i}', 4), z3.BitVec(f'bard_y_{i}', 3),
        z3.BitVec(f'druid_x_{i}', 4), z3.BitVec(f'druid_y_{i}', 3),
        z3.Bool(f'active_{i}')) for i in range(horizon + 1))
    actions = tuple(tuple(z3.Bool(f'action_{i}_{key}') for key in model.KEYS)
                    for i in range(horizon))
    landmarks = tuple(z3.Bool(f'landmark_{t}') for t in range(1, horizon + 1))
    for f in frames:
        solver.add(z3.ULT(f.bard_x, model.W), z3.ULT(f.bard_y, model.H),
                   z3.ULT(f.druid_x, model.W), z3.ULT(f.druid_y, model.H),
                   z3.Or(f.bard_x != f.druid_x, f.bard_y != f.druid_y))
    f = frames[0]
    solver.add(f.bard_x == 2, f.bard_y == 2, f.druid_x == 2,
               f.druid_y == 4, z3.Not(f.active))
    for i, selected in enumerate(actions):
        before, after = frames[i:i + 2]
        goal = global_master._goal(before)
        bard_hold = model._same_position(before.bard_x, before.bard_y, after.bard_x, after.bard_y)
        druid_hold = model._same_position(before.druid_x, before.druid_y, after.druid_x, after.druid_y)
        solver.add(z3.PbEq([(v, 1) for v in selected], 1))
        solver.add(z3.Implies(goal, z3.And(bard_hold, druid_hold, after.active == before.active)))
        solver.add(z3.Implies(z3.And(z3.Not(goal), selected[4]),
                             z3.And(bard_hold, druid_hold, after.active == z3.Not(before.active))))
        for j, key in enumerate(model.KEYS[:4]):
            dx, dy = model.DIRECTIONS[key]
            bard_step = model._same_position(after.bard_x, after.bard_y,
                                              before.bard_x + dx, before.bard_y + dy)
            druid_step = model._same_position(after.druid_x, after.druid_y,
                                               before.druid_x + dx, before.druid_y + dy)
            bard_rules = z3.And(z3.Or(bard_hold, bard_step),
                z3.Or(druid_hold, z3.And(z3.Not(bard_hold), druid_step,
                    model._near(before.druid_x, before.druid_y, before.bard_x, before.bard_y))))
            druid_rules = z3.And(bard_hold, z3.Or(druid_hold, druid_step))
            solver.add(z3.Implies(z3.And(z3.Not(goal), selected[j]),
                z3.And(after.active == before.active, z3.If(before.active, bard_rules, druid_rules))))
        # There is no new material landmark after the original game has ended.
        solver.add(z3.Implies(landmarks[i], z3.Not(goal)))
    solver.add(global_master._goal(frames[-1]))
    solver.add(z3.PbEq([(v, 1) for v in landmarks], 1) if landmarks else z3.BoolVal(False))
    result = global_master.Master(solver, actions, frames, landmarks, horizon)
    if use_events:
        if event_encoding == 'bitvector':
            from .bv_events import add_master_constraints
        else:
            from .events import add_master_constraints
        add_master_constraints(result, symmetry=symmetry)
    elif symmetry:
        raise ValueError('symmetry normalization requires the event module')
    return result


def validate_assignment(assignment, horizon):
    """Validate the concrete prefix and absorbing suffix without a SAT solver."""
    if not isinstance(assignment, dict):
        raise ValueError('assignment must be a mapping')
    route, heroes, landmark = (assignment.get(k) for k in ('route', 'heroes', 'landmark'))
    if not isinstance(route, str) or len(route) != horizon or any(k not in model.KEYS for k in route):
        raise ValueError('invalid route')
    if not isinstance(heroes, list) or len(heroes) != horizon + 1:
        raise ValueError('invalid hero frames')
    for frame in heroes:
        if not isinstance(frame, dict) or type(frame.get('active')) is not bool:
            raise ValueError('invalid active identity')
        for hero in ('bard', 'druid'):
            for axis, limit in (('x', model.W), ('y', model.H)):
                value = frame.get(f'{hero}_{axis}')
                if type(value) is not int or not 0 <= value < limit:
                    raise ValueError('invalid hero coordinate')
        if allocation._point(frame, 'bard') == allocation._point(frame, 'druid'):
            raise ValueError('hero collision')
    first_win = next((t for t, f in enumerate(heroes) if allocation._goal_pair(f)), None)
    if first_win is None:
        raise ValueError('missing final goal pair')
    allocation._heroes(route[:first_win], heroes[:first_win + 1])
    if any(frame != heroes[first_win] for frame in heroes[first_win:]):
        raise ValueError('terminal frames must hold positions and active identity')
    if type(landmark) is not int or not 1 <= landmark <= first_win:
        raise ValueError('landmark must precede terminal absorption')
    return first_win


def evaluate_flow(universe, assignment):
    """Evaluate the fixed universal network after validating absorbed heroes."""
    validate_assignment(assignment, universe.horizon)
    network = flow_allocation.Dinic()
    for label in universe.node_labels:
        network.add_node(label)
    capacities = [universal_flow.capacity(arc, assignment) for arc in universe.edges]
    for arc, capacity in zip(universe.edges, capacities):
        network.add_edge(arc.source, arc.target, capacity)
    value = network.max_flow(universe.source, universe.sink)
    source_side, pending = {universe.source}, deque([universe.source])
    while pending:
        node = pending.popleft()
        for edge in network.graph[node]:
            if edge.capacity > 0 and edge.to not in source_side:
                source_side.add(edge.to)
                pending.append(edge.to)
    crossing = [arc.edge_id for arc in universe.edges
                if arc.source in source_side and arc.target not in source_side]
    if sum(capacities[i] for i in crossing) != value:
        raise ValueError('universal cut and flow disagree')
    paths = []
    if value == 9:
        labels = {label: i for i, label in enumerate(universe.node_labels)}
        edges = {(arc.source, arc.target): arc.edge_id for arc in universe.edges}
        for path in flow_allocation._decompose(network, universe.source, universe.sink):
            ids = [labels[label] for label in path]
            paths.append([edges[pair] for pair in zip(ids, ids[1:])])
        cut_certificate.check_flow_witness(universe, assignment, paths)
    return {'flow_value': value, 'source_side': sorted(source_side),
            'crossing_ids': crossing, 'crossing_capacity': value,
            'flow_edge_paths': paths}


def reference_assignment(horizon=48):
    from experiments.transport_relaxation.project import project
    reference = project()
    if horizon < len(reference.route):
        raise ValueError('reference horizon must be at least 48')
    names = ('bard_x', 'bard_y', 'druid_x', 'druid_y', 'active')
    heroes = [{name: getattr(frame, name) for name in names} for frame in reference.frames]
    padding = horizon - len(reference.route)
    return {'route': reference.route + 'A' * padding,
            'heroes': heroes + [dict(heroes[-1]) for _ in range(padding)],
            'landmark': reference.landmark}
