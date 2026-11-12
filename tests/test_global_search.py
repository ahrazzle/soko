"""Finite controls for cut-loop completeness and search claim boundaries."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

import z3

from experiments.transport_relaxation import cut_certificate, global_master, global_search, universal_flow
from experiments.transport_relaxation.flow_allocation import Dinic


def assignment(landmark):
    frame = dict(bard_x=2, bard_y=2, druid_x=3, druid_y=3, active=False)
    return {'route': 'AA', 'heroes': [dict(frame) for _ in range(3)], 'landmark': landmark}


def lanes(kinds):
    labels = ('source',) + tuple(f'lane_{i}' for i in range(9)) + ('sink',)
    edges = []
    for i, kind in enumerate(kinds):
        edges.append(universal_flow.Arc(len(edges), 0, i + 1, 'one', ()))
        predicate, params = ('one', ()) if kind == 0 else ('landmark', (kind,))
        edges.append(universal_flow.Arc(len(edges), i + 1, 10, predicate, params))
    return universal_flow.Universe(2, labels, tuple(edges), 0, 10)


def flow(graph, value):
    network = Dinic()
    for i in range(len(graph.node_labels)):
        network.add_node(i)
    for arc in graph.edges:
        network.add_edge(arc.source, arc.target, universal_flow.capacity(arc, value))
    result = network.max_flow(graph.source, graph.sink)
    return result, network.min_cut(graph.source)


class TinyCutLoopTests(unittest.TestCase):
    def test_complete_loop_matches_exhaustive_direct_flow(self):
        cases = [([2] * 9, {2}, 1), ([1] * 5 + [2] * 4, set(), 2),
                 ([0] * 8 + [2], {2}, 1), ([0] * 4 + [1] * 5, {1}, 0)]
        for kinds, expected, expected_cuts in cases:
            with self.subTest(kinds=kinds):
                graph = lanes(kinds)
                direct = {t for t in (1, 2) if flow(graph, assignment(t))[0] >= 9}
                self.assertEqual(direct, expected)
                landmarks = (z3.Bool('tiny_landmark_1'), z3.Bool('tiny_landmark_2'))
                solver = z3.Solver()
                solver.add(z3.PbEq([(v, 1) for v in landmarks], 1))
                master = SimpleNamespace(solver=solver, landmarks=landmarks, capacity_cache={})
                checked = 0
                for _ in range(3):
                    if solver.check() == z3.unsat:
                        outcome = None
                        break
                    # Exhaust the first remaining landmark before the second.
                    solver.push()
                    solver.add(landmarks[0])
                    t = 1 if solver.check() == z3.sat else 2
                    solver.pop()
                    value = assignment(t)
                    amount, cut = flow(graph, value)
                    if amount >= 9:
                        outcome = t
                        break
                    cert = cut_certificate.make_cut_certificate(graph, value, cut)
                    crossing = cut_certificate.check_cut_certificate(graph, value, cert)
                    expression = global_master.add_cut(master, graph, crossing)
                    checked += 1
                    for good in direct:
                        solver.push()
                        solver.add(landmarks[good - 1])
                        self.assertEqual(solver.check(), z3.sat)
                        self.assertTrue(z3.is_true(solver.model().eval(expression)))
                        solver.pop()
                    solver.push()
                    solver.add(landmarks[t - 1])
                    self.assertEqual(solver.check(), z3.unsat)
                    solver.pop()
                else:
                    self.fail('finite loop failed to terminate')
                self.assertEqual(checked, expected_cuts)
                self.assertEqual(outcome is not None, bool(direct))
                if outcome is not None:
                    self.assertIn(outcome, direct)


class SearchLimitTests(unittest.TestCase):
    def test_one_iteration_reference_control_remains_unknown(self):
        with TemporaryDirectory() as directory:
            result = global_search.search(Path(directory), 48, timeout_seconds=30,
                                          max_iterations=1, control=True)
            self.assertEqual(result['status'], 'unknown')
            self.assertEqual(result['reason'], 'iteration budget exhausted')
            self.assertEqual(result['cuts_checked'], 1)
            self.assertFalse(result['record_claim'])
            self.assertNotIn('abstract_lower_bound', result)
            self.assertTrue((Path(directory) / 'result.json').is_file())


if __name__ == '__main__':
    unittest.main()
