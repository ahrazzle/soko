"""Conditional material allocation with harvested-token occupancy capacities.

The fixed hero trace must first occupy the two distinct goals at its final
frame. Origin release edges represent optional first harvests. Released tokens
share a time-expanded board with capacity one per cell and cannot overlap a
hero through the requested common landmark. Unharvested walls, unselected
material, and post-landmark ghost occupancy remain deliberately unconstrained.
This is a stronger relaxation, not a puzzle solver or a global record search.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from . import allocation, model


@dataclass
class Edge:
    to: int
    reverse: int
    capacity: int
    original_capacity: int


class Dinic:
    """Integer max flow with labelled nodes and an explicit residual min cut."""

    def __init__(self):
        self.labels = []
        self.graph = []
        self.forward_edges = []

    def add_node(self, label):
        index = len(self.graph)
        self.labels.append(label)
        self.graph.append([])
        return index

    def add_edge(self, start, end, capacity=1):
        if type(capacity) is not int or capacity < 0:
            raise ValueError('edge capacity must be a nonnegative integer')
        if start == end:
            raise ValueError('self edges are not needed by this network')
        forward = Edge(end, len(self.graph[end]), capacity, capacity)
        backward = Edge(start, len(self.graph[start]), 0, 0)
        self.forward_edges.append((start, len(self.graph[start])))
        self.graph[start].append(forward)
        self.graph[end].append(backward)

    def max_flow(self, source, sink):
        if source == sink:
            raise ValueError('source and sink must differ')
        result = 0
        while True:
            levels = [-1] * len(self.graph)
            levels[source] = 0
            pending = deque([source])
            while pending:
                node = pending.popleft()
                for edge in self.graph[node]:
                    if edge.capacity > 0 and levels[edge.to] < 0:
                        levels[edge.to] = levels[node] + 1
                        pending.append(edge.to)
            if levels[sink] < 0:
                return result
            cursors = [0] * len(self.graph)

            def push(available):
                # Use an explicit DFS stack: long time-expanded traces must
                # not depend on Python's recursion limit.
                nodes, limits, path = [source], [available], []
                while nodes:
                    node = nodes[-1]
                    if node == sink:
                        sent = limits[-1]
                        for start, index in path:
                            edge = self.graph[start][index]
                            edge.capacity -= sent
                            self.graph[edge.to][edge.reverse].capacity += sent
                        return sent
                    while cursors[node] < len(self.graph[node]):
                        edge = self.graph[node][cursors[node]]
                        if edge.capacity > 0 and levels[edge.to] == levels[node] + 1:
                            break
                        cursors[node] += 1
                    if cursors[node] == len(self.graph[node]):
                        nodes.pop()
                        limits.pop()
                        if path:
                            parent, _ = path.pop()
                            cursors[parent] += 1
                        continue
                    index = cursors[node]
                    edge = self.graph[node][index]
                    path.append((node, index))
                    nodes.append(edge.to)
                    limits.append(min(limits[-1], edge.capacity))
                return 0

            while True:
                sent = push(sum(edge.capacity for edge in self.graph[source]))
                if not sent:
                    break
                result += sent

    def min_cut(self, source):
        reachable = {source}
        pending = deque([source])
        while pending:
            node = pending.popleft()
            for edge in self.graph[node]:
                if edge.capacity > 0 and edge.to not in reachable:
                    reachable.add(edge.to)
                    pending.append(edge.to)
        crossing = []
        for node, index in self.forward_edges:
            edge = self.graph[node][index]
            if node in reachable and edge.to not in reachable and edge.original_capacity:
                crossing.append({'from': self.labels[node], 'to': self.labels[edge.to],
                                 'capacity': edge.original_capacity,
                                 'flow': edge.original_capacity - edge.capacity})
        return {'capacity': sum(edge['capacity'] for edge in crossing),
                'crossing_edges': crossing,
                'source_side': [self.labels[node] for node in sorted(reachable)],
                'sink_side_count': len(self.graph) - len(reachable)}


def _build_network(route, heroes, landmark_frame):
    """Construct a network from already validated, normalized hero mappings."""
    network = Dinic()
    source = network.add_node('source')
    sink = network.add_node('sink')
    origins = [network.add_node(f'origin_{j}') for j in range(len(model.BORDER))]
    for node in origins:
        network.add_edge(source, node)
    cells = {}
    # No material has been harvested at frame zero. All releases occur at a
    # Druid input's destination frame, so layer zero needs no board nodes.
    for t in range(1, landmark_frame + 1):
        occupied = {allocation._point(heroes[t], hero) for hero in ('bard', 'druid')}
        for y in range(model.H):
            for x in range(model.W):
                if (x, y) in occupied:
                    continue
                entry = network.add_node(f'cell_in_{t}_{x}_{y}')
                exit_ = network.add_node(f'cell_out_{t}_{x}_{y}')
                cells[t, x, y] = entry, exit_
                network.add_edge(entry, exit_)
    for i, key in enumerate(route[:landmark_frame]):
        before, after = heroes[i:i + 2]
        if key == 'A' or before['active']:
            continue
        druid = allocation._point(before, 'druid')
        if allocation._point(after, 'druid') != druid:
            continue
        target = allocation._step(druid, model.DIRECTIONS[key])
        if target in model.BORDER and (i + 1, *target) in cells:
            origin_index = model.BORDER.index(target)
            network.add_edge(origins[origin_index], cells[i + 1, *target][0])
    for t in range(1, landmark_frame):
        before, after = heroes[t:t + 2]
        key = route[t]
        bard = allocation._point(before, 'bard')
        carries = key != 'A' and before['active'] and allocation._point(after, 'bard') != bard
        for y in range(model.H):
            for x in range(model.W):
                nodes = cells.get((t, x, y))
                if nodes is None:
                    continue
                same = cells.get((t + 1, x, y))
                if same is not None:
                    network.add_edge(nodes[1], same[0])
                if carries and allocation._near((x, y), bard):
                    target = allocation._step((x, y), model.DIRECTIONS[key])
                    following = cells.get((t + 1, *target))
                    if following is not None:
                        network.add_edge(nodes[1], following[0])
    for j, point in enumerate(model.SWITCHES):
        switch = network.add_node(f'switch_{j}')
        nodes = cells.get((landmark_frame, *point))
        if nodes is not None:
            network.add_edge(nodes[1], switch)
        network.add_edge(switch, sink)
    return network, source, sink


def _decompose(network, source, sink):
    """Extract the nine unit source-to-sink paths without mutating residuals."""
    remaining = {(node, index): network.graph[node][index].original_capacity - network.graph[node][index].capacity
                 for node, index in network.forward_edges}
    paths = []
    for node, index in network.forward_edges:
        if node != source or remaining[node, index] <= 0:
            continue
        current = source
        path = [network.labels[current]]
        while current != sink:
            candidates = [(i, edge) for i, edge in enumerate(network.graph[current])
                          if remaining.get((current, i), 0) > 0]
            if not candidates:
                raise RuntimeError('positive flow does not decompose to the sink')
            selected, edge = candidates[0]
            remaining[current, selected] -= 1
            current = edge.to
            path.append(network.labels[current])
        paths.append(path)
    return paths


def _witness(route, heroes, landmark_frame, paths):
    by_switch = {}
    matching = []
    for path in paths:
        origin_index = int(next(label for label in path if label.startswith('origin_')).split('_')[1])
        switch_index = int(next(label for label in path if label.startswith('switch_')).split('_')[1])
        origin = model.BORDER[origin_index]
        positions = {}
        for label in path:
            if label.startswith('cell_in_'):
                _, _, t, x, y = label.split('_')
                positions[int(t)] = (int(x), int(y))
        release = min(positions)
        token_path = [(*origin, False)] * release
        token_path.extend([(*positions[t], True) for t in range(release, landmark_frame + 1)])
        token_path.extend([token_path[-1]] * (len(route) - landmark_frame))
        by_switch[switch_index] = token_path
        matching.append({'switch_index': switch_index, 'switch': list(model.SWITCHES[switch_index]),
                         'origin_index': origin_index, 'origin': list(origin),
                         'harvest_frame': release})
    matching.sort(key=lambda entry: entry['switch_index'])
    if set(by_switch) != set(range(len(model.SWITCHES))):
        raise RuntimeError('flow witness does not cover all switch labels')
    token_paths = [by_switch[j] for j in range(len(model.SWITCHES))]
    frames = []
    seen = False
    first_landmark = None
    for t, heroes_at_t in enumerate(heroes):
        states = [path[t] for path in token_paths]
        at_landmark = all((state[0], state[1]) == switch for state, switch in zip(states, model.SWITCHES))
        if at_landmark and first_landmark is None:
            first_landmark = t
        seen = seen or at_landmark
        frames.append(dict(heroes_at_t, token_x=[state[0] for state in states],
                           token_y=[state[1] for state in states],
                           harvested=[state[2] for state in states], landmark_seen=seen))
    return {'frames': frames, 'first_landmark_frame': first_landmark,
            'origins': [entry['origin'] for entry in matching], 'matching': matching,
            'token_paths': [[{'x': x, 'y': y, 'harvested': flag} for x, y, flag in path]
                            for path in token_paths]}


def allocate_flow(route, hero_frames, landmark_frame):
    """Decide the conditional capacity-constrained flow allocation problem.

    Infeasibility applies only to these actions, heroes and common landmark.
    A feasible witness is also a witness for the base transport relaxation;
    neither outcome establishes a global bound or a puzzle solution.
    """
    model.exact._guard_current_source()
    report = {
        'status': 'invalid_trajectory', 'feasible': None,
        'scope': 'fixed hero trajectory and specified common landmark only',
        'refinement': 'capacity one for selected harvested material and no hero overlap through landmark',
        'unharvested_occupancy_constrained': False,
        'global_bound_claim': None, 'original_game_solution_claim': False,
        'route': route if isinstance(route, str) else None,
        'landmark_frame': landmark_frame if type(landmark_frame) is int else None,
        'frames': [],
    }
    try:
        heroes = allocation._heroes(route, hero_frames)
    except ValueError as exc:
        report['reason'] = str(exc)
        return report
    report['horizon'] = len(route)
    if type(landmark_frame) is not int or not 0 <= landmark_frame <= len(route):
        report.update(status='invalid_input', reason='landmark_frame must be an integer in the route horizon')
        return report
    if not allocation._goal_pair(heroes[-1]):
        report['reason'] = 'final heroes must occupy the two distinct goals'
        return report
    earlier_goals = [i for i, frame in enumerate(heroes[:-1]) if allocation._goal_pair(frame)]
    if earlier_goals:
        report.update(status='unsupported_trajectory',
                      reason='earlier hero-goal pairs require token-dependent terminal absorption analysis',
                      earlier_goal_frames=earlier_goals)
        return report
    network, source, sink = _build_network(route, heroes, landmark_frame)
    flow = network.max_flow(source, sink)
    cut = network.min_cut(source)
    if cut['capacity'] != flow:
        raise RuntimeError('maximum flow and residual cut capacity disagree')
    report.update(flow_value=flow, required_flow=len(model.SWITCHES), min_cut=cut,
                  graph_counts={'nodes': len(network.graph), 'edges': len(network.forward_edges),
                                'residual_edges': sum(map(len, network.graph))})
    if flow < len(model.SWITCHES):
        report.update(status='infeasible', feasible=False)
        return report
    paths = _decompose(network, source, sink)
    report.update(_witness(route, heroes, landmark_frame, paths))
    report.update(status='feasible', feasible=True, flow_paths=paths)
    return report
