import unittest

from pysat.solvers import Solver
from experiments.exact_frontier.action_priority import ActionPriority, action_preferences


class ActionPriorityTests(unittest.TestCase):
    def test_preference_order_and_validation(self):
        aliases = {f'action_0_{k}': i + 1 for i, k in enumerate('UDLRA')}
        self.assertEqual(action_preferences(aliases, 'L'), [3, -1, -2, -4, -5])
        with self.assertRaises(ValueError):
            action_preferences(aliases, 'X')
        aliases['action_0_U'] = 3
        with self.assertRaises(ValueError):
            action_preferences(aliases, 'L')

    def test_fixed_assignments_survive_backtracking(self):
        p = ActionPriority([1, -2, 3])
        p.on_new_level()
        p.on_assignment(1, False)
        p.on_assignment(1, True)
        p.on_assignment(-2, False)
        p.on_backtrack(0)
        self.assertEqual(p.values, {1: 1})
        self.assertEqual(p.decide(), -2)
        self.assertEqual(p.propagate(), [])
        self.assertFalse(p.has_clause())

    def test_sat_and_unsat_pigeonholes_exercise_backtracking(self):
        for pigeons in (4, 5):
            with self.subTest(pigeons=pigeons):
                size = 4
                variables = list(range(1, pigeons * size + 1))
                clauses = [[p * size + h + 1 for h in range(size)] for p in range(pigeons)]
                clauses += [[-(p * size + h + 1), -(q * size + h + 1)]
                            for p in range(pigeons) for q in range(p + 1, pigeons)
                            for h in range(size)]
                with Solver(name='cadical300', with_proof=True) as solver:
                    solver.configure({'lucky': 0, 'elim': 0, 'probe': 0})
                    engine = ActionPriority(variables)
                    solver.connect_propagator(engine)
                    for var in variables:
                        solver.observe(var)
                    for clause in clauses:
                        solver.add_clause(clause)
                    sat = solver.solve()
                    self.assertEqual(sat, pigeons == 4)
                    self.assertGreater(engine.decisions, 0)
                    self.assertGreater(engine.backtracks, 0)
                    if sat:
                        model = set(solver.get_model())
                        self.assertTrue(all(any(lit in model for lit in clause) for clause in clauses))
                    else:
                        self.assertTrue(solver.get_proof())


if __name__ == '__main__':
    unittest.main()
