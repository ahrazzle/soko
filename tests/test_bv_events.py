import itertools
import unittest
from unittest.mock import patch

import z3

from experiments.causal_solver import bv_events, events, master
from experiments.transport_relaxation import global_master


class BitvectorEventTests(unittest.TestCase):
    def test_width_bounds(self):
        for horizon in (0, 1, 2, 45, 47, 48, 127, 1000):
            width = bv_events.arithmetic_width(horizon)
            signed_max = (1 << (width - 1)) - 1
            self.assertGreaterEqual(signed_max, horizon + len(events.ORIGINS) + 40 + 2)
            self.assertGreaterEqual(signed_max, 50)
        for invalid in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                bv_events.arithmetic_width(invalid)

    def test_joint_distance_against_integer_exhaustively(self):
        width = bv_events.arithmetic_width(48)
        points = tuple(itertools.product(range(2), repeat=2))
        for before in itertools.product(points, repeat=2):
            for after in itertools.product(points, repeat=2):
                self.assertEqual(z3.simplify(bv_events.joint_distance(before, after, width)).as_long(),
                                 events.joint_distance(before, after))
        # Exhaust every possible pair of signed displacements for each axis.
        for maximum in (14, 6):
            for a, b in itertools.product(range(-maximum, maximum + 1), repeat=2):
                av, bv = z3.BitVecVal(a, width), z3.BitVecVal(b, width)
                axis_cost = bv_events._max_zero(av, bv) + bv_events._max_zero(-av, -bv)
                self.assertEqual(z3.simplify(axis_cost).as_long(), max(0, a, b) + max(0, -a, -b))

    def test_complete_predicates_equal_wider_arithmetic(self):
        # Under the proved finite ranges, extra high bits must not change any
        # numeric expression or prefix/suffix predicate. Wide arithmetic is
        # itself below its signed limit, so both equal mathematical arithmetic.
        for horizon in (1, 2, 48):
            width = bv_events.arithmetic_width(horizon)
            wide = width + 3
            bx, by = z3.BitVec('eq_bx', 4), z3.BitVec('eq_by', 3)
            dx, dy = z3.BitVec('eq_dx', 4), z3.BitVec('eq_dy', 3)
            points = ((bx, by), (dx, dy))
            count, switches, elapsed = z3.BitVecs('eq_k eq_a eq_t', width)
            active = z3.Bool('eq_active')
            count_w, switches_w, elapsed_w = [z3.ZeroExt(3, v) for v in (count, switches, elapsed)]
            j = bv_events.joint_distance(events.STARTS, points, width)
            jw = bv_events.joint_distance(events.STARTS, points, wide)
            differences = [z3.ZeroExt(3, j) != jw,
                           (j + count + switches <= elapsed) !=
                           (jw + count_w + switches_w <= elapsed_w)]
            for goals in (events.GOALS, tuple(reversed(events.GOALS))):
                activation = z3.And(z3.Not(active), z3.Not(events._at(points[0], goals[0])))
                remaining = (bv_events.joint_distance(points, goals, width)
                             + z3.If(count < 9, 9 - count, z3.BitVecVal(0, width))
                             + z3.If(activation, z3.BitVecVal(1, width), z3.BitVecVal(0, width)))
                remaining_w = (bv_events.joint_distance(points, goals, wide)
                               + z3.If(count_w < 9, 9 - count_w, z3.BitVecVal(0, wide))
                               + z3.If(activation, z3.BitVecVal(1, wide), z3.BitVecVal(0, wide)))
                differences.extend([z3.ZeroExt(3, remaining) != remaining_w,
                                    (remaining <= horizon - elapsed) !=
                                    (remaining_w <= horizon - elapsed_w)])
            solver = z3.Solver()
            solver.set(timeout=10000)
            solver.add(z3.ULT(bx, 15), z3.ULT(dx, 15), z3.ULT(by, 7), z3.ULT(dy, 7),
                       z3.ULE(count, len(events.ORIGINS)), z3.ULE(switches, horizon),
                       z3.ULE(elapsed, horizon), z3.Or(*differences))
            self.assertEqual(solver.check(), z3.unsat, (horizon, solver.reason_unknown()))

    def test_population_count_no_overflow(self):
        for horizon in (1, 2, 48):
            width = bv_events.arithmetic_width(horizon)
            for size in (len(events.ORIGINS), horizon):
                for count in range(size + 1):
                    values = [z3.BoolVal(i < count) for i in range(size)]
                    self.assertEqual(z3.simplify(bv_events._sum_bools(values, width)).as_long(), count)

    def test_release_targeting_matches_integer_guard(self):
        # Exhaust full coordinate domains, including all original border cells.
        for x, y in itertools.product(range(15), range(7)):
            for dx, dy in events.geometry.DIRECTIONS.values():
                direct = {(x + dx, y + dy)} & set(events.ORIGINS)
                reversed_targets = {origin for origin in events.ORIGINS
                                    if 0 <= origin[0] - dx < 15
                                    and 0 <= origin[1] - dy < 7
                                    and (x, y) == (origin[0] - dx, origin[1] - dy)}
                self.assertEqual(direct, reversed_targets)

    def test_known_route_metadata_and_padding_match_integer_adapter(self):
        for horizon in (48, 51):
            assignment = master.reference_assignment(horizon)
            integer = master.build_master(horizon, use_events=False)
            bitvector = master.build_master(horizon, use_events=False)
            int_meta = events.add_master_constraints(integer, symmetry=True)
            bv_meta = bv_events.add_master_constraints(bitvector, symmetry=True)
            for problem in (integer, bitvector):
                global_master.pin_assignment(problem, assignment)
                self.assertEqual(problem.solver.check(), z3.sat)
            im, bm = integer.solver.model(), bitvector.solver.model()
            for field in ('seen_count', 'joint_prefix', 'landmark_ready', 'switches'):
                for a, b in zip(int_meta[field], bv_meta[field]):
                    va, vb = im.eval(a), bm.eval(b)
                    self.assertEqual(z3.is_true(va), z3.is_true(vb)) if z3.is_bool(va) else self.assertEqual(va.as_long(), vb.as_long())
            for a, b in zip(int_meta['suffix'], bv_meta['suffix']):
                self.assertEqual([im.eval(v).as_long() for v in a], [bm.eval(v).as_long() for v in b])

    def test_formula_is_pure_bool_bv_and_guarded(self):
        problem = master.build_master(2, use_events=False)
        bv_events.add_master_constraints(problem)
        pending, visited = list(problem.solver.assertions()), set()
        while pending:
            expression = pending.pop()
            if expression.get_id() in visited:
                continue
            visited.add(expression.get_id())
            self.assertIn(expression.sort().kind(), (z3.Z3_BOOL_SORT, z3.Z3_BV_SORT))
            pending.extend(expression.children())
        problem = master.build_master(1, use_events=False)
        count = len(problem.solver.assertions())
        with patch.object(events.source, '_guard_current_source', side_effect=ValueError('guard')):
            with self.assertRaisesRegex(ValueError, 'guard'):
                bv_events.add_master_constraints(problem)
        self.assertEqual(count, len(problem.solver.assertions()))


if __name__ == '__main__':
    unittest.main()
