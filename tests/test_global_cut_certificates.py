"""Universal boundaries retain disabled edges and survive independent replay."""
from copy import deepcopy
from dataclasses import replace
import itertools
import unittest
from unittest.mock import patch

from experiments.transport_relaxation import cut_certificate as checker
from experiments.transport_relaxation import model, universal_flow as universal
from experiments.transport_relaxation.flow_allocation import Dinic


Arc, Universe = universal.Arc, universal.Universe


def assignment(landmark=1, occupied=False):
    frame = dict(bard_x=2, bard_y=2, druid_x=3, druid_y=3, active=False)
    frames = [dict(frame) for _ in range(3)]
    if occupied:
        frames[2]['bard_x'] = frames[2]['bard_y'] = 0
    return {'route': 'AA', 'heroes': frames, 'landmark': landmark}


def universe(edges, labels=('source', 'a', 'sink')):
    return Universe(2, labels, tuple(Arc(i, *edge) for i, edge in enumerate(edges)),
                    0, len(labels) - 1)


def direct_flow(graph, value):
    network = Dinic()
    for label in graph.node_labels:
        network.add_node(label)
    for arc in graph.edges:
        network.add_edge(arc.source, arc.target, universal.capacity(arc, value))
    return network.max_flow(graph.source, graph.sink)


class GlobalCutCertificateTests(unittest.TestCase):
    def setUp(self):
        self.graph = universe([(0, 1, 'one', ()), (1, 2, 'landmark', (1,))])
        self.value = assignment(2)
        self.cert = checker.make_cut_certificate(self.graph, self.value,
                                                {'source_side': [0, 1], 'crossing_ids': [],
                                                 'crossing_capacity': 999})

    def test_minimal_disabled_edge_is_rebuilt_from_full_universe(self):
        self.assertEqual(self.cert['crossing_ids'], [1])
        self.assertEqual(self.cert['crossing_edges'][0]['capacity'], 0)
        self.assertEqual(checker.check_cut_certificate(self.graph, self.value, self.cert), (1,))
        broken = deepcopy(self.cert)
        broken['crossing_ids'] = []
        broken['crossing_edges'] = []
        with self.assertRaises(ValueError):
            checker.check_cut_certificate(self.graph, self.value, broken)
        # Another assignment enables exactly the omitted edge.
        self.assertEqual(universal.capacity(self.graph.edges[1], assignment(1)), 1)

    def test_independent_identity_matches_universe_hash(self):
        self.assertEqual(self.cert['universe_sha256'], universal.universe_identity(self.graph))
        self.assertEqual(self.cert['source_identity']['rows'], list(model.ROWS))
        for horizon in (1, 2):
            graph = universal.build_universe(horizon)
            self.assertEqual(checker._universe(graph)[0], universal.universe_identity(graph))

    def test_checker_does_not_call_solver_or_universe_capacity(self):
        with patch.object(universal, 'capacity', side_effect=AssertionError('not independent')), \
             patch.object(Dinic, 'max_flow', side_effect=AssertionError('must not solve')):
            self.assertEqual(checker.check_cut_certificate(self.graph, self.value, self.cert), (1,))

    def test_partition_corruptions_fail_closed(self):
        for nodes in ([1], [0, 1, 2], [0, 1, 1], [0, -1], [0, 3], [False, 1], None):
            with self.subTest(nodes=nodes):
                bad = deepcopy(self.cert)
                bad['source_side'] = nodes
                with self.assertRaises(ValueError):
                    checker.check_cut_certificate(self.graph, self.value, bad)

    def test_identity_and_capacity_corruptions_fail_closed(self):
        mutations = [dict(version=2), dict(horizon=3), dict(horizon=True),
                     dict(universe_sha256='0' * 64), dict(assignment_sha256='0' * 64),
                     dict(source_identity={}), dict(required_flow=1),
                     dict(crossing_ids=[]), dict(crossing_ids=[1, 1]),
                     dict(crossing_ids=[1, 0]), dict(crossing_capacity=1),
                     dict(crossing_capacity=False)]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                bad = deepcopy(self.cert)
                bad.update(mutation)
                with self.assertRaises(ValueError):
                    checker.check_cut_certificate(self.graph, self.value, bad)
        for key, value in [('kind', 'one'), ('params', [2]), ('capacity', 1),
                           ('capacity', False), ('source', 0), ('edge_id', 0),
                           ('target', 1)]:
            with self.subTest(key=key, value=value):
                bad = deepcopy(self.cert)
                bad['crossing_edges'][0][key] = value
                with self.assertRaises(ValueError):
                    checker.check_cut_certificate(self.graph, self.value, bad)

    def test_changed_assignment_topology_predicates_and_source_are_rejected(self):
        for graph in (replace(self.graph, horizon=3),
                      replace(self.graph, node_labels=('source', 'changed', 'sink')),
                      replace(self.graph, edges=(self.graph.edges[0],
                                                replace(self.graph.edges[1], params=(2,))))):
            with self.subTest(graph=graph), self.assertRaises(ValueError):
                checker.check_cut_certificate(graph, self.value, self.cert)
        with self.assertRaises(ValueError):
            checker.check_cut_certificate(self.graph, assignment(1), self.cert)
        with patch.object(model, 'ROWS', tuple(row.replace('#', '.') for row in model.ROWS)):
            with self.assertRaises(ValueError):
                checker.check_cut_certificate(self.graph, self.value, self.cert)

    def test_assignment_malformed_numbers_not_coerced(self):
        for field, value in [('landmark', True), ('landmark', 0), ('landmark', 3),
                             ('route', 'AX'), ('heroes', [])]:
            bad = deepcopy(self.value)
            bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                checker.check_cut_certificate(self.graph, bad, self.cert)
        for field, value in [('bard_x', True), ('bard_y', 7), ('active', 1)]:
            bad = deepcopy(self.value)
            bad['heroes'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                checker.check_cut_certificate(self.graph, bad, self.cert)

    def test_nine_capacity_cut_is_not_violated(self):
        graph = universe([(0, 1, 'one', ())] * 9 + [(1, 2, 'one', ())] * 9)
        with self.assertRaisesRegex(ValueError, 'not violated'):
            checker.make_cut_certificate(graph, self.value, {'source_side': [0, 1]})

    def test_exhaustive_tiny_cuts_preserve_all_feasible_assignments(self):
        # Two branches and four source partitions exhaust the complete tiny
        # cut space. Nine parallel arcs make the production threshold exact.
        graph = universe([(0, 1, 'one', ())] * 9 + [(1, 3, 'landmark', (1,))] * 9
                         + [(0, 2, 'one', ())] * 9 + [(2, 3, 'cell_free', (2, 0, 0))] * 9,
                         ('source', 'a', 'b', 'sink'))
        values = [assignment(landmark, occupied)
                  for landmark, occupied in itertools.product((1, 2), (False, True))]
        feasible = [value for value in values if direct_flow(graph, value) >= 9]
        self.assertEqual(len(feasible), 3)
        learned = []
        for value in values:
            for a, b in itertools.product((False, True), repeat=2):
                side = [0] + ([1] if a else []) + ([2] if b else [])
                boundary = [edge for edge in graph.edges if edge.source in side and edge.target not in side]
                total = sum(universal.capacity(edge, value) for edge in boundary)
                if total >= 9:
                    continue
                cert = checker.make_cut_certificate(graph, value, {'source_side': side})
                ids = checker.check_cut_certificate(graph, value, cert)
                learned.append(ids)
                for good in feasible:
                    self.assertGreaterEqual(sum(universal.capacity(graph.edges[i], good) for i in ids), 9)
        self.assertTrue(learned)
        # A positive-only cut would erase the only rescuing landmark edges.
        bad_value = assignment(2, True)
        cert = checker.make_cut_certificate(graph, bad_value, {'source_side': [0, 1, 2]})
        positive_only = [i for i in cert['crossing_ids'] if universal.capacity(graph.edges[i], bad_value)]
        self.assertEqual(positive_only, [])
        self.assertTrue(any(direct_flow(graph, good) == 9 for good in feasible))

    def test_independent_predicates_match_exact_integer_expected_values(self):
        value = assignment(2)
        value['route'] = 'UR'
        value['heroes'][0].update(druid_x=0, druid_y=1)
        value['heroes'][1].update(druid_x=0, druid_y=1, bard_x=2, bard_y=2, active=True)
        value['heroes'][2].update(bard_x=3, bard_y=2, druid_x=0, druid_y=1, active=True)
        cases = [('one', (), 1), ('landmark', (1,), 0), ('landmark', (2,), 1),
                 ('cell_free', (1, 2, 2), 0), ('cell_free', (1, 0, 1), 0),
                 ('cell_free', (1, 1, 1), 1), ('release', (1, 0, 0), 1),
                 ('release', (1, 0, 2), 0), ('release', (2, 1, 1), 0),
                 ('carry', (1, 4, 4, 5, 4), 1), ('carry', (1, 5, 4, 6, 4), 0),
                 ('carry', (1, 4, 4, 3, 4), 0)]
        for kind, params, expected in cases:
            edge = Arc(0, 0, 1, kind, params)
            with self.subTest(kind=kind, params=params):
                self.assertEqual(checker._capacity(edge, value), expected)
                self.assertEqual(checker._capacity(edge, value), universal.capacity(edge, value))
        value['heroes'][2]['bard_x'] = 2
        self.assertEqual(checker._capacity(Arc(0, 0, 1, 'carry', (1, 4, 4, 5, 4)), value), 0)


class GlobalFlowWitnessTests(unittest.TestCase):
    def setUp(self):
        self.graph = universe([(0, j, 'one', ()) for j in range(1, 10)]
                              + [(j, 10, 'landmark', (1,)) for j in range(1, 10)],
                              ('source',) + tuple(f'lane_{j}' for j in range(9)) + ('sink',))
        self.paths = [[j, j + 9] for j in range(9)]
        self.value = assignment(1)

    def test_nine_independent_paths_pass_without_solver_capacity(self):
        with patch.object(universal, 'capacity', side_effect=AssertionError('not independent')):
            self.assertTrue(checker.check_flow_witness(self.graph, self.value, self.paths))

    def test_bad_paths_and_shared_capacities_fail(self):
        cases = [self.paths[:-1], self.paths + [self.paths[0]],
                 [self.paths[0]] * 9,
                 [[9]] + self.paths[1:], [[0]] + self.paths[1:],
                 [[0, 99]] + self.paths[1:], [[False, 9]] + self.paths[1:],
                 [[0, 0, 9]] + self.paths[1:], [[0, 10]] + self.paths[1:],
                 [[]] + self.paths[1:]]
        for paths in cases:
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                checker.check_flow_witness(self.graph, self.value, paths)
        with self.assertRaisesRegex(ValueError, 'capacity'):
            checker.check_flow_witness(self.graph, assignment(2), self.paths)

    def test_parallel_arcs_are_unambiguous_by_edge_id(self):
        graph = replace(self.graph, edges=self.graph.edges + (Arc(99, 0, 1, 'one', ()),))
        paths = [[99, 9]] + self.paths[1:]
        self.assertTrue(checker.check_flow_witness(graph, self.value, paths))

    def test_reference_universe_witness_passes_independent_checker(self):
        from experiments.transport_relaxation.diagnostic import baseline_heroes, hero_mappings
        route, frames = baseline_heroes()
        graph = universal.build_universe(len(route))
        value = {'route': route, 'heroes': hero_mappings(frames), 'landmark': 43}
        result = universal.evaluate_flow(graph, value)
        self.assertEqual(result['flow_value'], 9)
        self.assertTrue(checker.check_flow_witness(graph, value, result['flow_edge_paths']))


class ProductionUniverseSpecTests(unittest.TestCase):
    def test_complete_production_inventory_is_checked_without_builder(self):
        for horizon in (0, 1, 2, 4):
            graph = universal.build_universe(horizon)
            with patch.object(universal, 'build_universe', side_effect=AssertionError('shared builder')):
                self.assertEqual(checker.check_universe_spec(graph), universal.universe_identity(graph))

    def test_missing_potential_arc_rejected_even_after_valid_renumbering(self):
        graph = universal.build_universe(2)
        # This release is disabled for many assignments. Removing it remains
        # a topology error even if a buggy builder reassigns contiguous IDs.
        removed = next(edge.edge_id for edge in graph.edges if edge.kind == 'release')
        edges = tuple(replace(edge, edge_id=i) for i, edge in
                      enumerate(edge for edge in graph.edges if edge.edge_id != removed))
        graph = replace(graph, edges=edges)
        self.assertTrue(checker._universe(graph)[0])  # structural hash alone accepts it
        with self.assertRaisesRegex(ValueError, 'arc inventory'):
            checker.check_universe_spec(graph)

    def test_invented_movement_and_changed_predicate_rejected(self):
        graph = universal.build_universe(2)
        carry = next(edge for edge in graph.edges if edge.kind == 'carry')
        # In-bounds coordinates and a valid label do not establish adjacency.
        target = graph.node_labels.index('cell_in_2_3_0')
        invented = replace(carry, target=target, params=(1, 0, 0, 3, 0))
        changed_source = replace(graph.edges[0], kind='landmark', params=(1,))
        for changed in (invented, changed_source):
            edges = tuple(changed if edge.edge_id == changed.edge_id else edge for edge in graph.edges)
            bad = replace(graph, edges=edges)
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, 'arc inventory'):
                checker.check_universe_spec(bad)

    def test_extra_duplicate_arc_node_ids_and_source_rejected(self):
        graph = universal.build_universe(1)
        duplicate = replace(graph.edges[0], edge_id=len(graph.edges))
        bad_graphs = [replace(graph, edges=graph.edges + (duplicate,)),
                      replace(graph, node_labels=graph.node_labels + ('invented',)),
                      replace(graph, source=2),
                      replace(graph, edges=(replace(graph.edges[0], edge_id=999),) + graph.edges[1:])]
        for bad in bad_graphs:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                checker.check_universe_spec(bad)

    def test_source_inventory_change_rejected(self):
        graph = universal.build_universe(1)
        with patch.object(model, 'BORDER', model.BORDER[:-1]):
            with self.assertRaisesRegex(ValueError, 'source instance'):
                checker.check_universe_spec(graph)

    def test_topology_check_allows_consistent_node_and_arc_reindexing(self):
        graph = universal.build_universe(2)
        old_to_new = {old: len(graph.node_labels) - 1 - old for old in range(len(graph.node_labels))}
        edges = tuple(replace(edge, edge_id=i, source=old_to_new[edge.source],
                              target=old_to_new[edge.target])
                      for i, edge in enumerate(reversed(graph.edges)))
        reordered = replace(graph, node_labels=tuple(reversed(graph.node_labels)), edges=edges,
                            source=old_to_new[graph.source], sink=old_to_new[graph.sink])
        self.assertEqual(checker.check_universe_spec(reordered), universal.universe_identity(reordered))


if __name__ == '__main__':
    unittest.main()
