"""Earlier real wins survive the exact-compatible absorbing master."""
from copy import deepcopy
import unittest

import z3

from experiments.causal_solver import master
from experiments.transport_relaxation import global_master, universal_flow, cut_certificate


class CausalMasterTests(unittest.TestCase):
    def test_reference_and_postterminal_actions_preserve_active(self):
        for horizon in (48, 49, 50):
            with self.subTest(horizon=horizon):
                value = master.reference_assignment(horizon)
                problem = master.build_master(horizon, use_events=False)
                global_master.pin_assignment(problem, value)
                self.assertEqual(problem.solver.check(), z3.sat)
                self.assertEqual(master.validate_assignment(value, horizon), 48)
                self.assertEqual(global_master.decode(problem, problem.solver.model()), value)
        bad = deepcopy(value)
        bad['heroes'][-1]['active'] = not bad['heroes'][-1]['active']
        with self.assertRaisesRegex(ValueError, 'terminal'):
            master.validate_assignment(bad, 50)
        problem = master.build_master(50, use_events=False)
        global_master.pin_assignment(problem, bad)
        self.assertEqual(problem.solver.check(), z3.unsat)

    def test_padded_reference_has_independently_checked_flow(self):
        graph = universal_flow.build_universe(49)
        cut_certificate.check_universe_spec(graph)
        value = master.reference_assignment(49)
        result = master.evaluate_flow(graph, value)
        self.assertEqual(result['flow_value'], 9)
        self.assertTrue(cut_certificate.check_flow_witness(graph, value, result['flow_edge_paths']))

    def test_no_landmark_after_terminal_and_no_malformed_frames(self):
        value = master.reference_assignment(49)
        value['landmark'] = 49
        with self.assertRaisesRegex(ValueError, 'landmark'):
            master.validate_assignment(value, 49)
        problem = master.build_master(49, use_events=False)
        global_master.pin_assignment(problem, value)
        self.assertEqual(problem.solver.check(), z3.unsat)
        for key, field in (('bard_x', True), ('active', 1)):
            value = master.reference_assignment(48)
            value['heroes'][0][key] = field
            with self.assertRaises(ValueError):
                master.validate_assignment(value, 48)

    def test_zero_horizon_has_no_solution(self):
        self.assertEqual(master.build_master(0, use_events=False).solver.check(), z3.unsat)


if __name__ == '__main__':
    unittest.main()
