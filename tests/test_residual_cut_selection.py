"""Checks for both extrema of the residual minimum-cut lattice."""
import itertools
import random
import unittest
from unittest.mock import patch

from experiments.causal_solver import master as causal
from experiments.transport_relaxation import cut_certificate, flow_allocation, universal_flow
from experiments.transport_relaxation.diagnostic import baseline_heroes, hero_mappings


class ResidualCutSelectionTests(unittest.TestCase):
    def test_extrema_match_exhaustive_cuts(self):
        rng = random.Random(9182)
        for _ in range(50):
            n = 6
            edges = [(u, v, rng.randrange(3)) for u in range(n) for v in range(n)
                     if u != v and rng.random() < 0.25]
            net = flow_allocation.Dinic()
            for node in range(n):
                net.add_node(str(node))
            for u, v, cap in edges:
                net.add_edge(u, v, cap)
            flow = net.max_flow(0, n - 1)
            cuts = []
            for bits in itertools.product((False, True), repeat=n - 2):
                side = {0} | {i + 1 for i, bit in enumerate(bits) if bit}
                cap = sum(c for u, v, c in edges if u in side and v not in side)
                if cap == flow:
                    cuts.append(side)
            self.assertTrue(cuts)
            smallest = set.intersection(*cuts)
            largest = set.union(*cuts)
            self.assertEqual(universal_flow.residual_source_partition(net, 0, n - 1), smallest)
            self.assertEqual(universal_flow.residual_source_partition(net, 0, n - 1, 'sink_minimal'), largest)

    def test_sink_reachability_includes_reverse_residual_edges(self):
        # A valid maximum flow sends s-a-b-t. The unused a-t edge makes b
        # reach t only through the positive reverse residual b-a.
        net = flow_allocation.Dinic()
        for label in 'sabt':
            net.add_node(label)
        for u, v in ((0, 1), (1, 2), (2, 3), (1, 3)):
            net.add_edge(u, v)
        for u, i in net.forward_edges[:3]:
            edge = net.graph[u][i]
            edge.capacity -= 1
            net.graph[edge.to][edge.reverse].capacity += 1
        self.assertEqual(universal_flow.residual_source_partition(net, 0, 3, 'sink_minimal'), {0})

    def test_reference_both_modes_and_independent_cut_certificates(self):
        route, frames = baseline_heroes()
        assignment = {'route': route, 'heroes': list(hero_mappings(frames)), 'landmark': 43}
        graph = universal_flow.build_universe(len(route))
        for mode in ('source_minimal', 'sink_minimal'):
            for evaluate in (universal_flow.evaluate_flow, causal.evaluate_flow):
                result = evaluate(graph, assignment, cut_selection=mode)
                self.assertEqual(result['flow_value'], 9)
                cut_certificate.check_flow_witness(graph, assignment, result['flow_edge_paths'])
                deficient = dict(assignment, landmark=1)
                result = evaluate(graph, deficient, cut_selection=mode)
                self.assertLess(result['flow_value'], 9)
                cert = cut_certificate.make_cut_certificate(graph, deficient, result)
                ids = cut_certificate.check_cut_certificate(graph, deficient, cert)
                self.assertEqual(list(ids), result['crossing_ids'])
                self.assertEqual(cert['crossing_capacity'], result['flow_value'])
                self.assertTrue(any(e['capacity'] == 0 for e in cert['crossing_edges']))

    def test_invalid_selection_and_endpoints_precede_flow(self):
        graph = universal_flow.Universe(0, ('s', 't'), (), 0, 1)
        with patch.object(flow_allocation.Dinic, 'max_flow', side_effect=AssertionError('called')):
            for evaluate in (universal_flow.evaluate_flow, causal.evaluate_flow):
                with self.assertRaises(ValueError):
                    evaluate(graph, {}, cut_selection='invalid')
                with self.assertRaises(ValueError):
                    evaluate(universal_flow.Universe(0, ('s', 't'), (), 0, 0), {})
        net = flow_allocation.Dinic()
        net.add_node('s')
        net.add_node('t')
        net.add_edge(0, 1)
        with self.assertRaises(ValueError):
            universal_flow.residual_source_partition(net, 0, 1, 'sink_minimal')


if __name__ == '__main__':
    unittest.main()
