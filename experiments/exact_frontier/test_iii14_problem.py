"""Fast contract and semantic controls; no record search."""
import unittest
from unittest.mock import patch

import z3

from experiments.exact_frontier.iii14_problem import (MODEL_CONTRACT, build_problem, calibrate, _verify_landmark_source, EXPECTED_ROWS, EXPECTED_SOURCE_SHA256)
from experiments.exact_frontier import iii14_smt as model
from soko_mcp.oracle import PuzzleScriptOracle


class ProblemTests(unittest.TestCase):
    def test_contract_and_global_shape(self):
        solver, actions, states = build_problem(1)
        self.assertIsInstance(solver, z3.Solver)
        self.assertEqual((len(actions), len(states)), (1, 2))
        self.assertEqual([str(a) for a in actions[0]], [f'action_0_{c}' for c in 'UDLRA'])
        self.assertFalse(MODEL_CONTRACT['prefix_or_neighborhood_restriction'])
        self.assertFalse(MODEL_CONTRACT['external_lower_bound_assumed'])
        self.assertTrue(MODEL_CONTRACT['goal_absorbing'])

    def test_zero_horizon_cannot_win(self):
        solver, _, _ = build_problem(0)
        self.assertEqual(solver.check(), z3.unsat)

    def test_source_guard_rejects_changes(self):
        _verify_landmark_source(EXPECTED_ROWS, EXPECTED_ROWS, EXPECTED_SOURCE_SHA256)
        with self.assertRaises(ValueError):
            _verify_landmark_source(EXPECTED_ROWS, EXPECTED_ROWS, '0' * 64)
        changed = list(EXPECTED_ROWS)
        changed[1] = '#' + '.' * 12 + '##'
        with self.assertRaises(ValueError):
            _verify_landmark_source(changed, EXPECTED_ROWS, EXPECTED_SOURCE_SHA256)
        with patch.object(model, 'ROWS', changed), self.assertRaises(ValueError):
            build_problem(1)
        changed_catalog = {'rooms': [{'id': 'III-14', 'grid': EXPECTED_ROWS, 'source': {'source_sha256': '0' * 64}}]}
        with patch('experiments.exact_frontier.iii14_problem.json.loads', return_value=changed_catalog), self.assertRaises(ValueError):
            build_problem(1)

    def test_landmarks_accept_baseline_trace(self):
        solver, actions, states = build_problem(len(model.ROUTE))
        oracle = PuzzleScriptOracle(3, model.ROWS)
        for i, action in enumerate(model.ROUTE):
            solver.add(actions[i]['UDLRA'.index(action)])
            alive, won = oracle.step(action)
            self.assertTrue(alive)
            self.assertEqual(won, i == len(model.ROUTE) - 1)
            solver.add(*[var == value for var, value in zip(states[i + 1], model.oracle_state(oracle))])
        solver.set(timeout=60000)
        self.assertEqual(solver.check(), z3.sat)
        assignment = solver.model()
        recorded = {(x, y) for y, row in enumerate(EXPECTED_ROWS) for x, cell in enumerate(row)
                    if cell == '#' and z3.is_true(assignment.eval(z3.Bool(f'origin_seen_43_{x}_{y}')))}
        self.assertEqual(recorded, {(0,4), (0,3), (0,2), (0,1), (2,0), (3,0), (4,0), (5,0), (6,0)})
        flags = [z3.Bool(f'origin_seen_43_{x}_{y}') for y, row in enumerate(EXPECTED_ROWS) for x, cell in enumerate(row) if cell == '#']
        solver.add(z3.PbLe([(flag, 1) for flag in flags], 8))
        self.assertEqual(solver.check(), z3.unsat)

    def test_invalid_horizons(self):
        for value in (-1, 1.5, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_problem(value)

    def test_baseline_and_small_seeded_samples(self):
        report = calibrate(5, 5)
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(report['baseline']['first_win'], 48)
        self.assertIn(43, report['baseline']['door_open_steps'])
        self.assertEqual(report['initial_random']['surviving_and_matched'], 4)
        self.assertEqual(report['baseline_prefix_random']['surviving_and_matched'], 5)


if __name__ == '__main__':
    unittest.main()
