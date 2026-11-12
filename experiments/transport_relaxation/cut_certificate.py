"""Independent checks for universal-network cuts and integral flow paths.

A certificate pins a partition of the *entire* immutable universe.  Its
boundary includes disabled arcs, because those arcs may become enabled in a
later master assignment.  Checking a cut needs no max-flow computation.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import hashlib
import json

from . import model

REQUIRED_FLOW = 9
_HERO_FIELDS = ('bard_x', 'bard_y', 'druid_x', 'druid_y', 'active')


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def _source_identity():
    return {'mechanics_sha256': model.exact.EXPECTED_SOURCE_SHA256,
            'rows': list(model.ROWS)}


def _integer(value, name, lower=0, upper=None):
    if type(value) is not int or value < lower or (upper is not None and value > upper):
        raise ValueError(f'invalid {name}')
    return value


def _sequence(value, name):
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f'{name} must be a sequence')
    return value


def _universe(universe):
    """Hash actual topology and predicates, independently of universe helpers."""
    horizon = _integer(universe.horizon, 'universe horizon')
    labels = _sequence(universe.node_labels, 'node labels')
    if not labels or any(type(label) is not str for label in labels) or len(set(labels)) != len(labels):
        raise ValueError('invalid or duplicate node labels')
    source = _integer(universe.source, 'source node', upper=len(labels) - 1)
    sink = _integer(universe.sink, 'sink node', upper=len(labels) - 1)
    if source == sink:
        raise ValueError('source and sink must differ')
    arcs = []
    by_id = {}
    for edge in _sequence(universe.edges, 'universe edges'):
        edge_id = _integer(edge.edge_id, 'edge ID')
        if edge_id in by_id:
            raise ValueError('duplicate universe edge ID')
        start = _integer(edge.source, 'edge source', upper=len(labels) - 1)
        end = _integer(edge.target, 'edge target', upper=len(labels) - 1)
        if start == end:
            raise ValueError('self edge in universe')
        params = list(_sequence(edge.params, 'predicate params'))
        if any(type(value) is not int for value in params):
            raise ValueError('predicate params must be exact integers')
        sizes = {'one': 0, 'cell_free': 3, 'release': 3, 'carry': 5, 'landmark': 1}
        if edge.kind not in sizes or len(params) != sizes[edge.kind]:
            raise ValueError('unknown predicate or invalid predicate params')
        if params:
            _integer(params[0], 'predicate time', lower=1, upper=horizon)
        if edge.kind == 'carry' and params[0] >= horizon:
            raise ValueError('carry needs a subsequent frame')
        if edge.kind in ('cell_free', 'release', 'carry'):
            _integer(params[1], 'predicate x', upper=model.W - 1)
            _integer(params[2], 'predicate y', upper=model.H - 1)
        if edge.kind == 'carry':
            _integer(params[3], 'carry target x', upper=model.W - 1)
            _integer(params[4], 'carry target y', upper=model.H - 1)
        arcs.append([edge_id, start, end, edge.kind, params])
        by_id[edge_id] = edge
    value = {'version': 1, 'horizon': horizon, 'node_labels': list(labels),
             'edges': arcs, 'source': source, 'sink': sink,
             'source_identity': _source_identity()}
    return _digest(value), by_id


def check_universe_spec(universe):
    """Independently check the complete production network against III-14.

    Run once before a production cut loop.  The generic certificate checker
    also supports tiny custom networks; this stricter guard binds a production
    universe to every potential arc in the source instance, including arcs
    disabled in the current assignment.  No universe-builder code is used.
    Node/arc iteration order is immaterial to topology; IDs must still index
    the supplied edge tuple, as required by the evaluator and master.
    """
    model.exact._guard_current_source()
    identity, _ = _universe(universe)
    rows = tuple(model.ROWS)
    if not rows or any(len(row) != len(rows[0]) for row in rows):
        raise ValueError('source instance has inconsistent row widths')
    width, height = len(rows[0]), len(rows)
    if (rows != tuple(model.exact.EXPECTED_ROWS)
            or (width, height) != (model.W, model.H)):
        raise ValueError('source instance rows or dimensions differ')
    # Recover origins and switches from source characters rather than reusing
    # the builder's cached coordinate inventories.
    origins = tuple((x, y) for y in range(height) for x in range(width)
                    if rows[y][x] == '#')
    switches = tuple((x, y) for y in range(height) for x in range(width)
                     if rows[y][x] == '}')
    if origins != tuple(model.BORDER) or switches != tuple(model.SWITCHES) or len(switches) != REQUIRED_FLOW:
        raise ValueError('source instance origin or switch inventory differs')
    labels = universe.node_labels
    if labels[universe.source] != 'source' or labels[universe.sink] != 'sink':
        raise ValueError('universe source or sink label differs')
    if [edge.edge_id for edge in universe.edges] != list(range(len(universe.edges))):
        raise ValueError('universe edge IDs must index the complete edge tuple')

    expected_nodes = {'source', 'sink'}
    expected = Counter()

    def cell(phase, t, x, y):
        return f'cell_{phase}_{t}_{x}_{y}'

    def arc(start, end, kind='one', params=()):
        expected[start, end, kind, params] += 1

    for j, (x, y) in enumerate(origins):
        origin = f'origin_{j}'
        expected_nodes.add(origin)
        arc('source', origin)
        for t in range(1, universe.horizon + 1):
            arc(origin, cell('in', t, x, y), 'release', (t, x, y))
    for j, (x, y) in enumerate(switches):
        switch = f'switch_{j}'
        expected_nodes.add(switch)
        arc(switch, 'sink')
        for t in range(1, universe.horizon + 1):
            arc(cell('out', t, x, y), switch, 'landmark', (t,))
    # Build movement arcs by destination. This is deliberately independent
    # of the builder's source-cell/direction traversal.
    for y in range(height):
        for x in range(width):
            neighbors = tuple((nx, ny) for nx, ny in
                              ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
                              if 0 <= nx < width and 0 <= ny < height)
            for t in range(1, universe.horizon + 1):
                entry, exit_ = cell('in', t, x, y), cell('out', t, x, y)
                expected_nodes.update((entry, exit_))
                arc(entry, exit_, 'cell_free', (t, x, y))
                if t > 1:
                    arc(cell('out', t - 1, x, y), entry)
                    for nx, ny in neighbors:
                        arc(cell('out', t - 1, nx, ny), entry,
                            'carry', (t - 1, nx, ny, x, y))
    if set(labels) != expected_nodes:
        raise ValueError('universe node inventory differs from source instance')
    actual = Counter((labels[edge.source], labels[edge.target], edge.kind, tuple(edge.params))
                     for edge in universe.edges)
    if actual != expected:
        missing, extra = sum((expected - actual).values()), sum((actual - expected).values())
        raise ValueError(f'universe arc inventory differs from source instance: {missing} missing, {extra} extra')
    return identity


def _assignment(universe, assignment):
    if not isinstance(assignment, Mapping) or set(assignment) != {'route', 'heroes', 'landmark'}:
        raise ValueError('assignment must supply route, heroes and landmark')
    route = assignment['route']
    if type(route) is not str or len(route) != universe.horizon or any(key not in 'UDLRA' for key in route):
        raise ValueError('invalid assignment route or horizon')
    heroes = _sequence(assignment['heroes'], 'hero frames')
    if len(heroes) != universe.horizon + 1:
        raise ValueError('hero frame count differs from horizon')
    normalized = []
    for frame in heroes:
        if not isinstance(frame, Mapping) or set(frame) != set(_HERO_FIELDS):
            raise ValueError('invalid hero frame fields')
        entry = {name: frame[name] for name in _HERO_FIELDS}
        for hero in ('bard', 'druid'):
            _integer(entry[hero + '_x'], 'hero x', upper=model.W - 1)
            _integer(entry[hero + '_y'], 'hero y', upper=model.H - 1)
        if type(entry['active']) is not bool:
            raise ValueError('hero active must be Boolean')
        normalized.append(entry)
    landmark = _integer(assignment['landmark'], 'assignment landmark', lower=1,
                        upper=universe.horizon)
    value = {'route': route, 'heroes': normalized, 'landmark': landmark}
    return value, _digest(value)


def _capacity(edge, assignment):
    """Exact integer predicate evaluation; deliberately does not call capacity."""
    kind, params = edge.kind, edge.params
    if kind == 'one':
        return 1
    t = params[0]
    if kind == 'landmark':
        return int(assignment['landmark'] == t)
    heroes, route = assignment['heroes'], assignment['route']
    x, y = params[1:3]
    if kind == 'cell_free':
        frame = heroes[t]
        return int((x, y) != (frame['bard_x'], frame['bard_y'])
                   and (x, y) != (frame['druid_x'], frame['druid_y']))
    if kind == 'release':
        before, after = heroes[t - 1:t + 1]
        key = route[t - 1]
        if key == 'A' or before['active']:
            return 0
        dx, dy = {'U': (0, -1), 'D': (0, 1), 'L': (-1, 0), 'R': (1, 0)}[key]
        return int((before['druid_x'], before['druid_y']) == (after['druid_x'], after['druid_y'])
                   and (x, y) == (before['druid_x'] + dx, before['druid_y'] + dy))
    if kind == 'carry':
        before, after = heroes[t:t + 2]
        key = route[t]
        if key == 'A' or not before['active']:
            return 0
        dx, dy = {'U': (0, -1), 'D': (0, 1), 'L': (-1, 0), 'R': (1, 0)}[key]
        return int((params[3], params[4]) == (x + dx, y + dy)
                   and (after['bard_x'], after['bard_y']) == (before['bard_x'] + dx, before['bard_y'] + dy)
                   and max(abs(x - before['bard_x']), abs(y - before['bard_y'])) <= 2)
    raise ValueError('unknown capacity predicate')


def _partition(universe, source_side):
    nodes = list(_sequence(source_side, 'source-side partition'))
    if any(type(node) is not int or not 0 <= node < len(universe.node_labels) for node in nodes):
        raise ValueError('invalid partition node')
    if len(set(nodes)) != len(nodes):
        raise ValueError('duplicate partition node')
    if universe.source not in nodes or universe.sink in nodes:
        raise ValueError('partition must contain source and exclude sink')
    return set(nodes)


def _boundary(universe, assignment, source_side):
    selected = _partition(universe, source_side)
    crossing = sorted((edge for edge in universe.edges
                       if edge.source in selected and edge.target not in selected),
                      key=lambda edge: edge.edge_id)
    records = [{'edge_id': edge.edge_id, 'source': edge.source, 'target': edge.target,
                'kind': edge.kind, 'params': list(edge.params),
                'capacity': _capacity(edge, assignment)} for edge in crossing]
    return records


def make_cut_certificate(universe, assignment, evaluation):
    """Construct a deficient-cut certificate from a proposed source partition.

    Solver-reported crossing lists and capacities are intentionally ignored.
    """
    identity, _ = _universe(universe)
    assignment, assignment_sha = _assignment(universe, assignment)
    if not isinstance(evaluation, Mapping) or 'source_side' not in evaluation:
        raise ValueError('evaluation must supply a source-side partition')
    source_side = sorted(_partition(universe, evaluation['source_side']))
    crossing = _boundary(universe, assignment, source_side)
    certificate = {'version': 1, 'kind': 'universal_flow_cut',
                   'horizon': universe.horizon, 'universe_sha256': identity,
                   'source_identity': _source_identity(), 'assignment_sha256': assignment_sha,
                   'required_flow': REQUIRED_FLOW, 'source_side': source_side,
                   'crossing_ids': [edge['edge_id'] for edge in crossing],
                   'crossing_edges': crossing,
                   'crossing_capacity': sum(edge['capacity'] for edge in crossing)}
    check_cut_certificate(universe, assignment, certificate)
    return certificate


def check_cut_certificate(universe, assignment, certificate):
    """Return verified boundary IDs, or raise ValueError on any mismatch.

    The returned IDs define the necessary inequality sum(capacity(ID)) >= 9
    for *every* future assignment in this same immutable universe.
    """
    identity, _ = _universe(universe)
    assignment, assignment_sha = _assignment(universe, assignment)
    if not isinstance(certificate, Mapping):
        raise ValueError('certificate must be a mapping')
    expected_metadata = {'version': 1, 'kind': 'universal_flow_cut',
                         'horizon': universe.horizon, 'universe_sha256': identity,
                         'source_identity': _source_identity(),
                         'assignment_sha256': assignment_sha, 'required_flow': REQUIRED_FLOW}
    for key, expected in expected_metadata.items():
        if key not in certificate or certificate[key] != expected or type(certificate[key]) is not type(expected):
            raise ValueError('certificate identity mismatch: ' + key)
    crossing = _boundary(universe, assignment, certificate.get('source_side'))
    ids = list(_sequence(certificate.get('crossing_ids'), 'crossing IDs'))
    if any(type(edge_id) is not int for edge_id in ids) or ids != [edge['edge_id'] for edge in crossing]:
        raise ValueError('crossing IDs omit, add, duplicate or reorder boundary arcs')
    records = certificate.get('crossing_edges')
    if not isinstance(records, list) or records != crossing:
        raise ValueError('crossing predicate descriptors or capacities differ')
    # Reject bools masquerading as 0/1 capacities under Python equality.
    for actual, expected in zip(records, crossing):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise ValueError('invalid crossing record fields')
        if any(type(actual[key]) is not int for key in ('edge_id', 'source', 'target', 'capacity')):
            raise ValueError('crossing record requires exact integers')
        if not isinstance(actual['params'], list) or any(type(x) is not int for x in actual['params']):
            raise ValueError('crossing params require exact integers')
    total = sum(edge['capacity'] for edge in crossing)
    if type(certificate.get('crossing_capacity')) is not int or certificate['crossing_capacity'] != total:
        raise ValueError('crossing capacity mismatch')
    if total >= REQUIRED_FLOW:
        raise ValueError('cut is not violated: capacity must be below nine')
    return tuple(ids)


def check_flow_witness(universe, assignment, flow_paths, required_flow=REQUIRED_FLOW):
    """Check unit source-to-sink EDGE-ID paths without relying on max flow.

    Pass ``evaluation['flow_edge_paths']``; ``flow_paths`` in the universal
    evaluator is a separate node-ID representation for inspection.
    """
    _, by_id = _universe(universe)
    assignment, _ = _assignment(universe, assignment)
    _integer(required_flow, 'required flow', lower=1)
    paths = _sequence(flow_paths, 'flow paths')
    if len(paths) != required_flow:
        raise ValueError('flow witness has wrong number of paths')
    used = Counter()
    origins, exits = set(), set()
    for value in paths:
        path = _sequence(value, 'flow path')
        if not path:
            raise ValueError('empty flow path')
        node, seen = universe.source, {universe.source}
        first = last = None
        for edge_id in path:
            if type(edge_id) is not int or edge_id not in by_id:
                raise ValueError('unknown flow edge ID')
            edge = by_id[edge_id]
            if edge.source != node or node == universe.sink or edge.target in seen:
                raise ValueError('disconnected, cyclic or illegal flow path')
            first = edge.target if first is None else first
            last = edge.source
            used[edge_id] += 1
            if used[edge_id] > _capacity(edge, assignment):
                raise ValueError('flow exceeds independently checked edge capacity')
            node = edge.target
            seen.add(node)
        if node != universe.sink:
            raise ValueError('flow path does not end at sink')
        if first in origins or last in exits:
            raise ValueError('flow paths must use distinct origins and switch exits')
        origins.add(first)
        exits.add(last)
    return True
