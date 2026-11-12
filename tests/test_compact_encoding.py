"""Guard the encoding refactor against semantic and certificate regressions."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import z3

from experiments.exact_frontier import iii14_compact as compact
from experiments.exact_frontier import iii14_smt as legacy
from experiments.exact_frontier.check_compact_equivalence import check, difference
from experiments.exact_frontier.iii14_problem import build_problem
from soko_mcp.oracle import PuzzleScriptOracle


class CompactEncodingTests(unittest.TestCase):
    def test_all_action_transitions_match_on_arbitrary_states(self):
        for key in 'UDLRA':
            with self.subTest(action=key):
                solver = z3.Solver()
                solver.set(timeout=10000)
                solver.add(difference(key))
                self.assertEqual(solver.check(), z3.unsat)

    def test_difference_query_detects_planted_semantic_bugs(self):
        for component in ('legal', 'active', 'notes', 'door'):
            with self.subTest(component=component):
                def mutant(state, actions):
                    values, legal = compact.trans(state, actions)
                    values = list(values)
                    if component == 'legal':
                        legal = z3.Not(legal)
                    elif component == 'active':
                        values[4] = z3.Not(values[4])
                    elif component == 'notes':
                        values[5] = legacy.Z
                    else:
                        values[6] = z3.Not(values[6])
                    return values, legal
                solver = z3.Solver()
                solver.set(timeout=10000)
                solver.add(difference('A', mutant))
                self.assertEqual(solver.check(), z3.sat)

    def test_known_win_is_absorbing_with_extra_inputs(self):
        route = legacy.ROUTE + 'UL'
        solver, actions, states = build_problem(len(route))
        oracle = PuzzleScriptOracle(3, legacy.ROWS)
        for i, key in enumerate(route):
            solver.add(actions[i]['UDLRA'.index(key)])
            if i < len(legacy.ROUTE):
                alive, won = oracle.step(key)
                self.assertTrue(alive)
                self.assertEqual(won, i == len(legacy.ROUTE) - 1)
            solver.add(*[var == value for var, value in
                         zip(states[i + 1], legacy.oracle_state(oracle))])
        solver.set(timeout=60000)
        self.assertEqual(solver.check(), z3.sat)

    def test_equivalence_timeout_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
            'experiments.exact_frontier.check_compact_equivalence.solve_cnf',
            return_value={'status': 'unknown', 'checker_status': 'not_run'}
        ):
            report = check(Path(tmp))
        self.assertEqual(report['status'], 'inconclusive')
        self.assertEqual(len(report['cases']), 1)
        self.assertFalse(report['original_game_equivalence_proved'])

    def test_unchecked_unsat_does_not_claim_checked_certificates(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
            'experiments.exact_frontier.check_compact_equivalence.solve_cnf',
            return_value={'status': 'unsat', 'checker_status': 'unchecked'}
        ):
            report = check(Path(tmp))
        self.assertEqual(report['status'], 'unchecked_encoding_equivalence')
        self.assertEqual(len(report['cases']), 5)

    def test_invalid_encoding_rejected(self):
        with self.assertRaisesRegex(ValueError, 'encoding'):
            build_problem(1, encoding='unrecognized')


if __name__ == '__main__':
    unittest.main()
