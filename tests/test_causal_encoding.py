"""Exact causal factoring against the compact model and the game oracle."""
import unittest

import z3

from experiments.causal_solver import encoding
from experiments.exact_frontier import iii14_compact as compact
from experiments.exact_frontier import iii14_smt as model
from experiments.exact_frontier.check_compact_equivalence import symbolic_state
from soko_mcp.oracle import PuzzleScriptOracle


class CausalEncodingTests(unittest.TestCase):
    def test_arbitrary_state_one_step_equivalence(self):
        # Five fixed one-hot selections exhaust the action domain. No state
        # invariants are assumed, including on losing/illegal transitions.
        for key in 'UDLRA':
            with self.subTest(action=key):
                state = symbolic_state('causal_' + key)
                actions = [z3.BoolVal(key == k) for k in 'UDLRA']
                expected, expected_legal = compact.trans(state, actions)
                actual, actual_legal = encoding.trans(state, actions)
                solver = z3.Solver()
                solver.set(timeout=10000)
                solver.add(z3.Or(expected_legal != actual_legal,
                                 *[a != b for a, b in zip(expected, actual)]))
                self.assertEqual(solver.check(), z3.unsat, solver.reason_unknown())

    def test_reference_route_against_original_oracle(self):
        state = model.initial()
        oracle = PuzzleScriptOracle(3, model.ROWS)
        self.assertEqual(model.eval_state(state), model.oracle_state(oracle))
        for index, key in enumerate(model.ROUTE):
            actions = [z3.BoolVal(key == k) for k in 'UDLRA']
            state, legal = encoding.trans(state, actions)
            state = tuple(z3.simplify(value) for value in state)
            alive, won = oracle.step(key)
            self.assertTrue(alive, index)
            self.assertTrue(z3.is_true(z3.simplify(legal)), index)
            self.assertEqual(model.eval_state(state), model.oracle_state(oracle), index)
            self.assertEqual(won, index == len(model.ROUTE) - 1)

    def test_build_initial_state_and_action_constraints(self):
        solver, actions, states = encoding.build(1)
        self.assertEqual(len(states), 2)
        self.assertEqual(len(actions), 1)
        self.assertEqual([str(a) for a in actions[0]],
                         ['action_0_' + k for k in 'UDLRA'])
        # Drop only the final goal requirement to inspect original controls.
        assertions = solver.assertions()
        solver = z3.Solver()
        solver.add(*assertions[:-1])
        solver.add(actions[0][4])
        self.assertEqual(solver.check(), z3.sat)
        m = solver.model()
        self.assertEqual(tuple(m.eval(x, model_completion=True).as_long()
                               if z3.is_bv(x) else z3.is_true(m.eval(x))
                               for x in states[0]), model.eval_state(model.initial()))
        self.assertEqual(sum(z3.is_true(m.eval(a)) for a in actions[0]), 1)

    def test_goal_absorbs_actions(self):
        source, actions, states = encoding.build(1)
        # Replace the seven initial equalities with a goal state to exercise
        # absorption independently of the length of a full winning route.
        solver = z3.Solver()
        solver.add(*source.assertions()[7:])
        solver.add((states[0][2] | states[0][3]) == model.BV(model.GOAL))
        solver.add(actions[0][4])
        self.assertEqual(solver.check(), z3.sat)
        solver.add(z3.Or(*[a != b for a, b in zip(states[0], states[1])]))
        self.assertEqual(solver.check(), z3.unsat)

    def test_invalid_arguments(self):
        for horizon in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                encoding.build(horizon)
        with self.assertRaises(ValueError):
            encoding.trans(model.initial(), [])


if __name__ == '__main__':
    unittest.main()
