import random
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import z3

from experiments.transport_relaxation import global_master as gm, model
from experiments.transport_relaxation.diagnostic import baseline_heroes, hero_mappings
from experiments.transport_relaxation.project import project


class GlobalMasterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        route, frames = baseline_heroes()
        cls.assignment = {'route': route, 'heroes': list(hero_mappings(frames)),
                          'landmark': project().landmark}

    def test_reference_and_padding_decode(self):
        a = self.assignment
        self.assertEqual(len(a['route']), 48)
        for padding in (0, 1):
            assignment = {'route': 'U' * padding + a['route'],
                          'heroes': [a['heroes'][0]] * padding + a['heroes'],
                          'landmark': a['landmark'] + padding}
            master = gm.build_master(len(assignment['route']))
            gm.pin_assignment(master, assignment)
            self.assertEqual(master.solver.check(), z3.sat)
            self.assertEqual(gm.decode(master, master.solver.model()), assignment)

    def test_zero_and_invalid_horizons_and_guard(self):
        self.assertEqual(gm.build_master(0).solver.check(), z3.unsat)
        for h in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                gm.build_master(h)
        with patch.object(model.exact, '_guard_current_source', side_effect=RuntimeError('guard')):
            with self.assertRaisesRegex(RuntimeError, 'guard'):
                gm.build_master(1)

    def test_capacities_agree_with_universal_flow(self):
        from experiments.transport_relaxation import universal_flow as uf
        master = gm.build_master(48)
        gm.pin_assignment(master, self.assignment)
        self.assertEqual(master.solver.check(), z3.sat)
        solution = master.solver.model()
        universe = uf.build_universe(48)
        rng = random.Random(9)
        for arc in rng.sample(list(universe.edges), 1000):
            with self.subTest(kind=arc.kind, params=arc.params):
                symbolic = z3.is_true(solution.eval(gm.symbolic_capacity(master, arc), model_completion=True))
                self.assertEqual(int(symbolic), uf.capacity(arc, self.assignment))

    def test_cut_counts_each_arc_even_with_same_predicate(self):
        from experiments.transport_relaxation import universal_flow as uf
        master = gm.build_master(48)
        gm.pin_assignment(master, self.assignment)
        t = self.assignment['landmark']
        arcs = [uf.Arc(i, 'a', 'b', 'landmark', (t,)) for i in range(9)]
        predicate = gm.symbolic_capacity(master, arcs[0])
        self.assertIs(gm.symbolic_capacity(master, arcs[1]), predicate)
        self.assertEqual(len(master.capacity_cache), 1)
        gm.add_cut(master, SimpleNamespace(edges=arcs), range(9))
        self.assertEqual(len(master.capacity_cache), 1)
        self.assertEqual(master.solver.check(), z3.sat)
        gm.add_cut(master, SimpleNamespace(edges=arcs), range(8))
        self.assertEqual(master.solver.check(), z3.unsat)


if __name__ == '__main__':
    unittest.main()
