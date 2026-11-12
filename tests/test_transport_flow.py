"""Controls for fixed-hero vertex-capacity transport flow."""
import itertools
import unittest

from experiments.transport_relaxation import flow_allocation
from experiments.transport_relaxation.diagnostic import (
    baseline_heroes, check_witness, compare_original_heroes, hero_mappings,
    shortened_heroes,
)
from experiments.transport_relaxation.flow_diagnostic import check_capacity
from experiments.transport_relaxation.project import SWITCHES


class FlowAllocationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.route, cls.heroes = baseline_heroes()
        cls.reference = flow_allocation.allocate_flow(cls.route, hero_mappings(cls.heroes), 43)

    def test_reference_flow_is_collision_free_and_symbolically_valid(self):
        result = self.reference
        self.assertEqual(result['status'], 'feasible')
        self.assertEqual(result['flow_value'], 9)
        self.assertEqual(len({tuple(origin) for origin in result['origins']}), 9)
        frame = result['frames'][43]
        self.assertEqual(tuple(zip(frame['token_x'], frame['token_y'])), SWITCHES)
        self.assertTrue(all(frame['harvested']))
        self.assertTrue(check_capacity(result))
        self.assertEqual(check_witness(self.route, result)['status'], 'sat')

    def test_constructed_47_still_has_capacity_respecting_abstract_witness(self):
        route, heroes = shortened_heroes()
        result = flow_allocation.allocate_flow(route, hero_mappings(heroes), 42)
        self.assertEqual(result['status'], 'feasible')
        self.assertEqual(result['flow_value'], 9)
        self.assertTrue(check_capacity(result))
        self.assertEqual(check_witness(route, result)['status'], 'sat')
        self.assertFalse(compare_original_heroes(route, heroes)['winning'])

    def test_small_network_flow_equals_exhaustive_minimum_cut(self):
        # Enumerate every source-side cut independently; vary capacities,
        # include disconnected and parallel-edge cases.
        arcs = [(0, 1), (0, 2), (1, 2), (1, 3), (2, 3), (0, 1)]
        for variant in range(16):
            capacities = [((variant >> (i % 4)) & 1) * (1 + i % 2) for i in range(len(arcs))]
            graph = flow_allocation.Dinic()
            nodes = [graph.add_node(str(i)) for i in range(4)]
            for (u, v), capacity in zip(arcs, capacities):
                graph.add_edge(nodes[u], nodes[v], capacity)
            measured = graph.max_flow(nodes[0], nodes[3])
            cut_values = []
            for inner in itertools.product((False, True), repeat=2):
                side = {0} | {i + 1 for i, included in enumerate(inner) if included}
                cut_values.append(sum(c for (u, v), c in zip(arcs, capacities) if u in side and v not in side))
            self.assertEqual(measured, min(cut_values), variant)
            self.assertEqual(graph.min_cut(nodes[0])['capacity'], measured, variant)

    def test_infeasible_cut_has_reproducible_capacity(self):
        from experiments.transport_relaxation import allocation
        route, heroes = shortened_heroes()
        maps = hero_mappings(heroes)
        result = flow_allocation.allocate_flow(route, maps, 31)
        self.assertEqual(result['status'], 'infeasible')
        self.assertLess(result['flow_value'], 9)
        graph, source, sink = flow_allocation._build_network(route, allocation._heroes(route, maps), 31)
        cut = result['min_cut']
        source_side = set(cut['source_side'])
        self.assertIn(graph.labels[source], source_side)
        self.assertNotIn(graph.labels[sink], source_side)
        capacity = sum(graph.graph[u][i].original_capacity for u, i in graph.forward_edges
                       if graph.labels[u] in source_side and graph.labels[graph.graph[u][i].to] not in source_side)
        self.assertEqual(capacity, cut['capacity'])
        self.assertEqual(capacity, result['flow_value'])

    def test_hero_trajectory_validation(self):
        broken = list(hero_mappings(self.heroes))
        broken[4] = dict(broken[4], bard_x=14, bard_y=6)
        result = flow_allocation.allocate_flow(self.route, broken, 43)
        self.assertEqual(result['status'], 'invalid_trajectory')

    def test_capacity_checker_rejects_overlapping_tokens(self):
        result = dict(self.reference)
        frames = [dict(frame) for frame in result['frames']]
        frame = dict(frames[43])
        frame['token_x'] = list(frame['token_x'])
        frame['token_y'] = list(frame['token_y'])
        frame['token_x'][1] = frame['token_x'][0]
        frame['token_y'][1] = frame['token_y'][0]
        frames[43] = frame
        result['frames'] = frames
        with self.assertRaises(ValueError):
            check_capacity(result)

    def test_capacity_checker_rejects_hero_overlap(self):
        result = dict(self.reference)
        frames = [dict(frame) for frame in result['frames']]
        frame = dict(frames[43])
        frame['bard_x'] = frame['token_x'][0]
        frame['bard_y'] = frame['token_y'][0]
        frames[43] = frame
        result['frames'] = frames
        with self.assertRaises(ValueError):
            check_capacity(result)


if __name__ == '__main__':
    unittest.main()
