"""A fixed material-flow universe whose capacities depend on a hero schedule.

Every potential edge is retained, including edges currently having capacity
zero. A cut must contain *all* outgoing universal edges to remain a necessary
inequality for other schedules. Flow facts concern this transport relaxation;
they establish neither an original-game solution nor a global lower bound.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json

from . import allocation, flow_allocation, model


@dataclass(frozen=True)
class Arc:
    edge_id: int
    source: int
    target: int
    kind: str
    params: tuple


@dataclass(frozen=True)
class Universe:
    horizon: int
    node_labels: tuple[str, ...]
    edges: tuple[Arc, ...]
    source: int
    sink: int


def build_universe(horizon: int) -> Universe:
    """Build every potential origin, split-cell, transport and switch edge."""
    model.exact._guard_current_source()
    if type(horizon) is not int or horizon < 0:
        raise ValueError('horizon must be a nonnegative integer')
    labels = ['source', 'sink']
    origins = []
    for j in range(len(model.BORDER)):
        origins.append(len(labels))
        labels.append(f'origin_{j}')
    cells = {}
    for t in range(1, horizon + 1):
        for y in range(model.H):
            for x in range(model.W):
                cells[t, x, y] = len(labels), len(labels) + 1
                labels.extend((f'cell_in_{t}_{x}_{y}', f'cell_out_{t}_{x}_{y}'))
    switches = []
    for j in range(len(model.SWITCHES)):
        switches.append(len(labels))
        labels.append(f'switch_{j}')
    edges = []

    def add(source, target, kind='one', params=()):
        edges.append(Arc(len(edges), source, target, kind, params))

    for origin in origins:
        add(0, origin)
    for (t, x, y), (entry, exit_) in cells.items():
        add(entry, exit_, 'cell_free', (t, x, y))
    for t in range(1, horizon + 1):
        for j, (x, y) in enumerate(model.BORDER):
            add(origins[j], cells[t, x, y][0], 'release', (t, x, y))
    for t in range(1, horizon):
        for y in range(model.H):
            for x in range(model.W):
                exit_ = cells[t, x, y][1]
                add(exit_, cells[t + 1, x, y][0])
                for dx, dy in model.DIRECTIONS.values():
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < model.W and 0 <= ny < model.H:
                        add(exit_, cells[t + 1, nx, ny][0],
                            'carry', (t, x, y, nx, ny))
    for t in range(1, horizon + 1):
        for j, (x, y) in enumerate(model.SWITCHES):
            add(cells[t, x, y][1], switches[j], 'landmark', (t,))
    for switch in switches:
        add(switch, 1)
    return Universe(horizon, tuple(labels), tuple(edges), 0, 1)


def capacity(arc: Arc, assignment: Mapping) -> int:
    """Evaluate one exact Boolean capacity, without validating a whole trace.

    ``release(t, ...)`` uses input ``t-1``; ``carry(t, ...)`` uses input ``t``
    and the aura at frame ``t``. Only switch exits depend on the landmark.
    Raw predicates also support local controls with arbitrary hero positions.
    """
    if arc.kind == 'one':
        return 1
    if arc.kind == 'landmark':
        return int(assignment['landmark'] == arc.params[0])
    heroes = assignment['heroes']
    if arc.kind == 'cell_free':
        t, x, y = arc.params
        return int(all(allocation._point(heroes[t], hero) != (x, y)
                       for hero in ('bard', 'druid')))
    if arc.kind == 'release':
        t, x, y = arc.params
        key = assignment['route'][t - 1]
        before, after = heroes[t - 1:t + 1]
        delta = model.DIRECTIONS.get(key)
        druid = allocation._point(before, 'druid')
        return int(delta is not None and not before['active']
                   and allocation._point(after, 'druid') == druid
                   and allocation._step(druid, delta) == (x, y))
    if arc.kind == 'carry':
        t, x, y, nx, ny = arc.params
        key = assignment['route'][t]
        before, after = heroes[t:t + 2]
        delta = model.DIRECTIONS.get(key)
        bard = allocation._point(before, 'bard')
        return int(delta == (nx - x, ny - y) and before['active']
                   and allocation._point(after, 'bard') == allocation._step(bard, delta)
                   and allocation._near((x, y), bard))
    raise ValueError(f'unknown universal capacity kind: {arc.kind!r}')


def universe_identity(universe: Universe) -> str:
    """SHA-256 of the canonical v1 source, node and arc descriptor."""
    model.exact._guard_current_source()
    descriptor = {
        'version': 1,
        'source_identity': {
            'mechanics_sha256': model.exact.EXPECTED_SOURCE_SHA256,
            'rows': list(model.ROWS),
        },
        'horizon': universe.horizon,
        'node_labels': list(universe.node_labels),
        'edges': [[arc.edge_id, arc.source, arc.target, arc.kind, list(arc.params)]
                  for arc in universe.edges],
        'source': universe.source,
        'sink': universe.sink,
    }
    encoded = json.dumps(descriptor, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def evaluate_flow(universe: Universe, assignment: Mapping) -> dict:
    """Evaluate a complete valid master assignment and its universal min cut.

    The first distinct hero-goal pair must occur at the final frame, matching
    the conditional allocation contract. Invalid schedules raise ValueError.
    The cut boundary includes zero-capacity edges. Paths use universal node
    IDs; ``flow_edge_paths`` supplies the corresponding universal edge IDs
    for independent checking. The reconstructed witness follows
    ``flow_allocation._witness``.
    """
    model.exact._guard_current_source()
    if not isinstance(assignment, Mapping):
        raise ValueError('assignment must supply route, heroes and landmark')
    if any(key not in assignment for key in ('route', 'heroes', 'landmark')):
        raise ValueError('assignment must supply route, heroes and landmark')
    route = assignment['route']
    heroes = allocation._heroes(route, assignment['heroes'])
    if len(route) != universe.horizon:
        raise ValueError('route length must equal the universal horizon')
    landmark = assignment['landmark']
    if type(landmark) is not int or not 1 <= landmark <= universe.horizon:
        raise ValueError('landmark must be an integer from one through the horizon')
    if not allocation._goal_pair(heroes[-1]):
        raise ValueError('final heroes must occupy the two distinct goals')
    if any(allocation._goal_pair(frame) for frame in heroes[:-1]):
        raise ValueError('earlier hero-goal pairs require terminal absorption analysis')
    normalized = {'route': route, 'heroes': heroes, 'landmark': landmark}
    network = flow_allocation.Dinic()
    for label in universe.node_labels:
        network.add_node(label)
    capacities = [capacity(arc, normalized) for arc in universe.edges]
    for arc, value in zip(universe.edges, capacities):
        network.add_edge(arc.source, arc.target, value)
    value = network.max_flow(universe.source, universe.sink)
    source_side = {universe.source}
    pending = deque([universe.source])
    while pending:
        node = pending.popleft()
        for edge in network.graph[node]:
            if edge.capacity > 0 and edge.to not in source_side:
                source_side.add(edge.to)
                pending.append(edge.to)
    crossing = [arc for arc in universe.edges
                if arc.source in source_side and arc.target not in source_side]
    crossing_capacity = sum(capacities[arc.edge_id] for arc in crossing)
    if crossing_capacity != value:
        raise RuntimeError('maximum flow and universal cut capacity disagree')
    paths = []
    edge_paths = []
    witness = None
    if value == len(model.SWITCHES):
        labelled_paths = flow_allocation._decompose(network, universe.source, universe.sink)
        node_ids = {label: node for node, label in enumerate(universe.node_labels)}
        paths = [[node_ids[label] for label in path] for path in labelled_paths]
        edge_ids = {}
        for arc in universe.edges:
            pair = arc.source, arc.target
            if pair in edge_ids:
                raise ValueError('canonical universal flow must not contain parallel arcs')
            edge_ids[pair] = arc.edge_id
        edge_paths = [[edge_ids[pair] for pair in zip(path, path[1:])] for path in paths]
        witness = flow_allocation._witness(route, heroes, landmark, labelled_paths)
    return {'flow_value': value, 'source_side': sorted(source_side),
            'crossing_ids': [arc.edge_id for arc in crossing],
            'crossing_capacity': crossing_capacity,
            'flow_paths': paths, 'flow_edge_paths': edge_paths, 'witness': witness}


def _smoke():
    """Small inventory and known-reference controls; no unrestricted search."""
    from .diagnostic import baseline_heroes, hero_mappings

    inventories = {}
    for horizon, expected in ((1, (261, 203)), (47, (9921, 29413))):
        universe = build_universe(horizon)
        measured = len(universe.node_labels), len(universe.edges)
        if measured != expected:
            raise AssertionError((horizon, measured, expected))
        inventories[horizon] = {'nodes': measured[0], 'edges': measured[1]}
    route, frames = baseline_heroes()
    heroes = hero_mappings(frames)
    result = evaluate_flow(build_universe(len(route)),
                           {'route': route, 'heroes': heroes, 'landmark': 43})
    reference = flow_allocation.allocate_flow(route, heroes, 43)
    if result['flow_value'] != reference['flow_value'] or result['flow_value'] != 9:
        raise AssertionError('universal flow disagrees with the reference flow')
    return {'inventories': inventories, 'reference_flow': result['flow_value'],
            'reference_paths': len(result['flow_paths'])}


if __name__ == '__main__':
    print(json.dumps(_smoke(), indent=2))
