"""Controls for benchmark trust boundaries and scheduling decisions."""
import unittest

from experiments.causal_solver.backends import check_clauses, check_witness
from experiments.causal_solver.benchmark import allocation, bounded


class BenchmarkTests(unittest.TestCase):
    def test_clause_model_validation(self):
        self.assertTrue(check_clauses([[1, -2], [2]], [1, 2]))
        self.assertFalse(check_clauses([[1], [2]], [1, -2]))
        self.assertFalse(check_clauses([[1]], [1, -1]))
        self.assertFalse(check_clauses([[]], []))
        self.assertFalse(check_clauses([[1, 2]], [1], 2))
        self.assertFalse(check_clauses([[1]], [1, 1], 2))
        self.assertFalse(check_clauses([[1]], [1, -2, 3], 2))

    def test_goal_witness_is_trimmed_and_requires_win(self):
        class Oracle:
            def __init__(self, *args): self.i = 0
            def step(self, key):
                self.i += 1
                return (self.i <= 1, self.i == 1)
        class Room:
            PuzzleScriptOracle = Oracle
            ROWS = []
            @staticmethod
            def validate(route): return route == 'A'
        self.assertEqual(check_witness('AU', 'goal', Room), 'A')
        with self.assertRaises(ValueError): check_witness('AU', 'transition', Room)
        class NoWin(Oracle):
            def step(self, key): return True, False
        class NoWinRoom(Room): PuzzleScriptOracle = NoWin
        with self.assertRaises(ValueError): check_witness('A', 'goal', NoWinRoom)

    def test_timeout_stays_unknown(self):
        case = dict(horizon=0, pins='', mode='goal', events=False, encoding='compact', backend='z3')
        result = bounded(case, 0.001)
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(result['reason'], 'wall_timeout')

    def test_allocation_requires_repetition_and_distinguishes_workloads(self):
        def row(backend, t, status='sat', horizon=1):
            return {'case': dict(horizon=horizon, pins='A', mode='transition', encoding='compact', backend=backend, events=False), 'status': status, 'wall_seconds': t, 'budget_seconds': 10}
        self.assertEqual(allocation([row('z3', 1), row('pysat', 3)])[0]['decision'], 'inconclusive')
        rows = [row('z3', 1)] * 3 + [row('pysat', 3)] * 3
        self.assertEqual(allocation(rows)[0]['backend'], 'z3')
        self.assertEqual(allocation([row('z3', 1)] * 3 + [row('pysat', 3, 'unknown')] * 3)[0]['decision'], 'inconclusive')
        self.assertEqual(allocation([row('z3', 1)] * 3 + [row('pysat', 3, horizon=2)] * 3)[0]['decision'], 'inconclusive')


if __name__ == '__main__': unittest.main()
