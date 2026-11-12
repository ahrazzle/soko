"""Production-universe controls against the conditional material-flow oracle."""
import unittest
from unittest.mock import patch

from experiments.transport_relaxation import flow_allocation, model, universal_flow
from experiments.transport_relaxation.diagnostic import (
    baseline_heroes, hero_mappings, shortened_heroes,
)
from experiments.transport_relaxation.flow_diagnostic import check_capacity


class UniversalFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.traces = {}
        for name, make in (('reference', baseline_heroes), ('constructed', shortened_heroes)):
            route, heroes = make()
            cls.traces[name] = (route, hero_mappings(heroes),
                                universal_flow.build_universe(len(route)))

    def test_production_inventory_at_one_and_47_inputs(self):
        for horizon, nodes, edges in ((1, 261, 203), (47, 9921, 29413)):
            with self.subTest(horizon=horizon):
                universe = universal_flow.build_universe(horizon)
                self.assertEqual(len(universe.node_labels), nodes)
                self.assertEqual(len(universe.edges), edges)
                self.assertEqual(universe.node_labels[universe.source], 'source')
                self.assertEqual(universe.node_labels[universe.sink], 'sink')
                self.assertEqual(len(set(universe.node_labels)), nodes)
                self.assertEqual([arc.edge_id for arc in universe.edges], list(range(edges)))

    def test_matched_schedules_and_landmarks_agree_with_conditional_flow(self):
        # Both traces contain a zero-flow prefix, a deficient intermediate
        # landmark, and a landmark admitting all nine material histories.
        cases = (('reference', 1, 0), ('reference', 31, 7), ('reference', 43, 9),
                 ('constructed', 1, 0), ('constructed', 31, 8), ('constructed', 42, 9))
        for name, landmark, expected in cases:
            with self.subTest(trace=name, landmark=landmark):
                route, heroes, universe = self.traces[name]
                assignment = {'route': route, 'heroes': heroes, 'landmark': landmark}
                actual = universal_flow.evaluate_flow(universe, assignment)
                conditional = flow_allocation.allocate_flow(route, heroes, landmark)
                self.assertEqual(conditional['status'], 'feasible' if expected == 9 else 'infeasible')
                self.assertEqual(actual['flow_value'], conditional['flow_value'])
                self.assertEqual(actual['flow_value'], expected)
                self.assertEqual(actual['crossing_capacity'], expected)
                side = set(actual['source_side'])
                self.assertIn(universe.source, side)
                self.assertNotIn(universe.sink, side)
                crossing = [arc for arc in universe.edges
                            if arc.source in side and arc.target not in side]
                self.assertEqual(actual['crossing_ids'], [arc.edge_id for arc in crossing])
                self.assertEqual(sum(universal_flow.capacity(arc, assignment) for arc in crossing), expected)
                # A cut containing only enabled arcs would lose all boundary
                # edges in the zero-flow control and would be globally wrong.
                self.assertTrue(any(universal_flow.capacity(arc, assignment) == 0 for arc in crossing))
                if expected == 9:
                    self._check_paths(universe, assignment, actual)
                    witness = dict(actual['witness'], landmark_frame=landmark)
                    self.assertTrue(check_capacity(witness))
                    self.assertEqual(len(witness['frames']), len(route) + 1)
                else:
                    self.assertEqual(actual['flow_paths'], [])
                    self.assertEqual(actual['flow_edge_paths'], [])
                    self.assertIsNone(actual['witness'])

    def _check_paths(self, universe, assignment, result):
        self.assertEqual(len(result['flow_paths']), 9)
        self.assertEqual(len(result['flow_edge_paths']), 9)
        used = set()
        for nodes, edge_ids in zip(result['flow_paths'], result['flow_edge_paths']):
            self.assertEqual(nodes[0], universe.source)
            self.assertEqual(nodes[-1], universe.sink)
            self.assertEqual(len(nodes), len(edge_ids) + 1)
            for pair, edge_id in zip(zip(nodes, nodes[1:]), edge_ids):
                self.assertNotIn(edge_id, used)
                used.add(edge_id)
                arc = universe.edges[edge_id]
                self.assertEqual(pair, (arc.source, arc.target))
                self.assertEqual(universal_flow.capacity(arc, assignment), 1)

    def test_invalid_hero_traces_raise_instead_of_reporting_flow(self):
        route, heroes, universe = self.traces['reference']
        cases = []
        initial = list(heroes)
        initial[0] = dict(initial[0], bard_x=3)
        cases.append(initial)
        illegal_move = list(heroes)
        illegal_move[4] = dict(illegal_move[4], bard_x=14, bard_y=6)
        cases.append(illegal_move)
        invalid_active = list(heroes)
        invalid_active[4] = dict(invalid_active[4], active=0)
        cases.append(invalid_active)
        cases.append(heroes[:-1])
        for index, broken in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(ValueError):
                universal_flow.evaluate_flow(universe,
                                             {'route': route, 'heroes': broken, 'landmark': 43})

    def test_invalid_landmarks_raise(self):
        route, heroes, universe = self.traces['reference']
        for landmark in (-1, 0, True, 49, 43.0, '43', None):
            with self.subTest(landmark=landmark), self.assertRaisesRegex(ValueError, 'landmark'):
                universal_flow.evaluate_flow(universe,
                                             {'route': route, 'heroes': heroes, 'landmark': landmark})

    def test_route_must_match_universal_horizon(self):
        route, heroes, _ = self.traces['reference']
        with self.assertRaisesRegex(ValueError, 'route length'):
            universal_flow.evaluate_flow(self.traces['constructed'][2],
                                         {'route': route, 'heroes': heroes, 'landmark': 43})

    def test_final_heroes_must_occupy_distinct_goals(self):
        route, heroes, _ = self.traces['reference']
        with self.assertRaisesRegex(ValueError, 'final heroes'):
            universal_flow.evaluate_flow(universal_flow.build_universe(len(route) - 1),
                                         {'route': route[:-1], 'heroes': heroes[:-1], 'landmark': 43})

    def test_goal_pair_before_final_frame_is_unsupported(self):
        route, heroes, _ = self.traces['reference']
        # An extra legal activation holds both goal positions but makes the
        # original terminal frame occur before the end of the supplied trace.
        route += 'A'
        heroes = list(heroes) + [dict(heroes[-1], active=not heroes[-1]['active'])]
        conditional = flow_allocation.allocate_flow(route, heroes, 43)
        self.assertEqual(conditional['status'], 'unsupported_trajectory')
        with self.assertRaisesRegex(ValueError, 'earlier hero-goal pairs'):
            universal_flow.evaluate_flow(universal_flow.build_universe(len(route)),
                                         {'route': route, 'heroes': heroes, 'landmark': 43})

    def test_build_checks_source_and_rejects_invalid_horizons(self):
        for horizon in (-1, True, 1.5):
            with self.subTest(horizon=horizon), self.assertRaises(ValueError):
                universal_flow.build_universe(horizon)
        with patch.object(model.exact, '_guard_current_source', side_effect=RuntimeError('guard')):
            with self.assertRaisesRegex(RuntimeError, 'guard'):
                universal_flow.build_universe(1)


if __name__ == '__main__':
    unittest.main()
