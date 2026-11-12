"""Projection checks for the III-14 transport relaxation."""
from dataclasses import asdict, replace
import unittest

import z3

from experiments.transport_relaxation.project import (
    H, W, SWITCHES, pin_projection, project,
)


def set_item(values, index, value):
    result = list(values)
    result[index] = value
    return tuple(result)


class ProjectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from experiments.transport_relaxation.model import build_problem
        cls.projection = project()
        cls.solver, cls.actions, cls.frames = build_problem(len(cls.projection.route))

    def check_projection(self, projection, expected):
        self.solver.push()
        try:
            pin_projection(self.solver, self.actions, self.frames, projection)
            self.assertEqual(self.solver.check(), expected)
        finally:
            self.solver.pop()

    def check_step(self, before, after, key, expected):
        from experiments.transport_relaxation.model import (
            frame_constraints, new_frame, transition_constraints,
        )
        left, right = new_frame(100), new_frame(101)
        solver = z3.Solver()
        solver.add(*transition_constraints(left, right, key))
        solver.add(*frame_constraints(left, asdict(before)))
        solver.add(*frame_constraints(right, asdict(after)))
        self.assertEqual(solver.check(), expected)

    def test_reference_material_identity_and_model_witness(self):
        p = self.projection
        self.assertEqual(len(p.route), 48)
        self.assertEqual(len(p.frames), 49)
        self.assertEqual(p.landmark, 43)
        self.assertEqual(len(set(p.origins)), 9)
        self.assertTrue(all(x in (0, W - 1) or y in (0, H - 1) for x, y in p.origins))
        f = p.frames[p.landmark]
        self.assertEqual(tuple(zip(f.token_x, f.token_y)), SWITCHES)
        self.assertTrue(all(f.harvested))
        self.assertFalse(p.frames[42].landmark_seen)
        self.assertTrue(f.landmark_seen)
        self.check_projection(p, z3.sat)

    def test_model_rejects_remote_bard_carry(self):
        # At input 20 Bard moves down. Token 2 is harvested but is four
        # columns away, so it cannot be carried down with him.
        before, after = self.projection.frames[20:22]
        self.assertTrue(before.active and before.harvested[2])
        self.assertGreater(max(abs(before.bard_x - before.token_x[2]),
                               abs(before.bard_y - before.token_y[2])), 2)
        self.check_step(before, after, "D", z3.sat)
        invalid = replace(after, token_y=set_item(after.token_y, 2, before.token_y[2] + 1))
        self.check_step(before, invalid, "D", z3.unsat)

    def test_model_rejects_unharvested_move(self):
        # Token 1 moves during this Bard step. Suppressing its harvest flag
        # makes the same movement illegal.
        before, after = self.projection.frames[20:22]
        self.assertNotEqual((before.token_x[1], before.token_y[1]), (after.token_x[1], after.token_y[1]))
        before = replace(before, harvested=set_item(before.harvested, 1, False))
        after = replace(after, harvested=set_item(after.harvested, 1, False))
        self.check_step(before, after, "D", z3.unsat)

    def test_model_rejects_hero_off_board(self):
        before, after = self.projection.frames[20:22]
        self.check_step(before, replace(after, bard_x=W), "D", z3.unsat)

    def test_winning_frame_absorbs_further_inputs(self):
        won = self.projection.frames[-1]
        self.check_step(won, won, "L", z3.sat)
        self.check_step(won, replace(won, bard_x=won.bard_x - 1), "L", z3.unsat)

    def test_incomplete_reference_route_rejected(self):
        with self.assertRaises(ValueError):
            project(self.projection.route[:-1])


if __name__ == '__main__':
    unittest.main()
