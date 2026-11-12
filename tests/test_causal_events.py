import itertools
import unittest
from unittest.mock import patch

import z3

from experiments.causal_solver import events
from experiments.causal_solver import master as causal_master
from experiments.exact_frontier import iii14_smt as reference


class CausalEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trace = events.extract_events(reference.ROUTE)

    def _pinned_master(self, route=None, *, symmetry=False):
        trace = self.trace if route is None else events.extract_events(route)
        master = causal_master.build_master(len(trace['route']), use_events=False)
        metadata = events.add_master_constraints(master, symmetry=symmetry)
        for row, key in zip(master.actions, trace['route']):
            master.solver.add(row[events.KEYS.index(key)])
        for frame, state in zip(master.frames, trace['states']):
            bard, druid = events._concrete_points(state)
            master.solver.add(frame.bard_x == bard[0], frame.bard_y == bard[1],
                              frame.druid_x == druid[0], frame.druid_y == druid[1],
                              frame.active == state[4])
        master.solver.add(master.landmarks[trace['material_landmarks'][0] - 1])
        return master, metadata

    def test_known48_independent_counts_and_master(self):
        trace = self.trace
        self.assertEqual(trace['first_win'], 48)
        self.assertGreaterEqual(len(trace['history'][-1]['actual_seen']), 9)
        landmark = trace['material_landmarks'][0]
        self.assertGreaterEqual(len(trace['history'][landmark]['actual_seen']), 9)
        master, metadata = self._pinned_master(symmetry=True)
        self.assertEqual(master.solver.check(), z3.sat)
        solution = master.solver.model()
        for t, history in enumerate(trace['history']):
            self.assertEqual(solution.eval(metadata['seen_count'][t]).as_long(), len(history['seen']))
            self.assertLessEqual(solution.eval(metadata['joint_prefix'][t]).as_long(), t)
            self.assertTrue(any(solution.eval(v).as_long() <= 48 - t
                                for v in metadata['suffix'][t]))
        for row, observed in zip(metadata['release'], trace['events']):
            selected = [origin for origin, predicate in zip(events.ORIGINS, row)
                        if z3.is_true(solution.eval(predicate))]
            self.assertEqual(selected, [] if observed['origin'] is None else [observed['origin']])

    def test_planted_early_origin_and_event_claims_rejected(self):
        master, metadata = self._pinned_master()
        self.assertEqual(master.solver.check(), z3.sat)
        for false_claim in (metadata['seen'][0][0], metadata['release'][0][0],
                            metadata['landmark_ready'][1]):
            master.solver.push()
            master.solver.add(false_claim)
            self.assertEqual(master.solver.check(), z3.unsat)
            master.solver.pop()

    def test_exact_adapter_concrete_frames_and_event_guards(self):
        trace = self.trace
        solver = z3.Solver()
        states = [tuple(z3.BoolVal(v) if type(v) is bool else reference.BV(v) for v in state)
                  for state in trace['states']]
        actions = [tuple(z3.BoolVal(key == candidate) for candidate in events.KEYS)
                   for key in trace['route']]
        metadata = events.add_exact_constraints(solver, actions, states, symmetry=True)
        self.assertEqual(solver.check(), z3.sat)
        solution = solver.model()
        for t, history in enumerate(trace['history']):
            self.assertEqual(solution.eval(metadata['seen_count'][t]).as_long(),
                             len(history['actual_seen']))
        solver.add(metadata['release'][0][0])
        self.assertEqual(solver.check(), z3.unsat)

    def test_joint_distance_exhaustive_tiny_board_one_step(self):
        points = tuple(itertools.product(range(2), repeat=2))
        for before in itertools.product(points, repeat=2):
            for dx, dy in events.geometry.DIRECTIONS.values():
                for moved in itertools.product((False, True), repeat=2):
                    after = tuple((p[0] + dx * change, p[1] + dy * change)
                                  for p, change in zip(before, moved))
                    if any(p not in points for p in after):
                        continue
                    for goals in itertools.product(points, repeat=2):
                        self.assertLessEqual(events.joint_distance(before, goals) -
                                             events.joint_distance(after, goals), 1)
        # Both heroes moving right costs one input, not two Manhattan units.
        self.assertEqual(events.joint_distance(((0, 0), (0, 1)), ((1, 0), (1, 1))), 1)
        # Conflicting horizontal movement requires two different directions.
        self.assertEqual(events.joint_distance(((0, 0), (1, 1)), ((1, 0), (0, 1))), 2)

    def test_joint_distance_wide_integer_arithmetic(self):
        before = ((z3.BitVecVal(14, 4), z3.BitVecVal(6, 3)),
                  (z3.BitVecVal(14, 4), z3.BitVecVal(6, 3)))
        self.assertEqual(z3.simplify(events.joint_distance(before, ((0, 0), (0, 0)))).as_long(), 20)

    def test_full_key_preserves_notes_activity_doors_and_material_kind(self):
        state = self.trace['states'][0]
        key = events.canonical_full_state_key(state)
        self.assertEqual(key, state)
        for field in range(7):
            modified = list(state)
            modified[field] = not modified[field] if field in (4, 6) else modified[field] ^ 1
            self.assertNotEqual(key, events.canonical_full_state_key(modified))
        with self.assertRaises(ValueError):
            events.canonical_full_state_key((*state[:6], 0))

    def test_normalization_exhaustive_short_traces(self):
        for keys in itertools.product(events.KEYS, repeat=3):
            route = ''.join(keys)
            try:
                original = events.extract_events(route)
            except ValueError:
                continue
            normalized = events.normalize_route(route)
            replay = events.extract_events(normalized)
            self.assertEqual(original['states'][-1], replay['states'][-1])
            self.assertLessEqual(len(normalized), len(route))
            self.assertNotIn('AA', normalized)
            self.assertTrue(all(a != b for a, b in zip(replay['states'], replay['states'][1:])))

    def test_aa_identity_under_settled_state_invariant(self):
        # This proof quantifies over masks, rather than assuming arbitrary
        # notes/door state. AA is not an identity on arbitrary stale states.
        wall, crates, bard, druid = z3.BitVecs('aa_w aa_c aa_b aa_d', reference.N)
        active = z3.Bool('aa_active')
        notes = z3.If(active, reference.area(bard) & (crates | druid), reference.Z)
        opened = ((wall | crates | bard | druid) & reference.BV(reference.SW)) == reference.BV(reference.SW)
        state = (wall, crates, bard, druid, active, notes, opened)
        after_one, legal_one = reference.trans(state, 'A')
        after_two, legal_two = reference.trans(after_one, 'A')
        solver = z3.Solver()
        solver.set(timeout=5000)
        solver.add(z3.Or(z3.Not(legal_one), z3.Not(legal_two),
                         *[a != b for a, b in zip(state, after_two)]))
        self.assertEqual(solver.check(), z3.unsat)
        for state in self.trace['states']:
            wall, crates, bard, druid, active, notes, opened = state
            expected_notes = z3.simplify(reference.area(reference.BV(bard))).as_long() & (crates | druid)
            self.assertEqual(notes, expected_notes if active else 0)
            self.assertEqual(opened, (wall | crates | bard | druid) & reference.SW == reference.SW)

    def test_normalized_win_and_terminal_padding(self):
        route = 'AA' + reference.ROUTE
        normalized = events.normalize_route(route)
        self.assertEqual(normalized, reference.ROUTE)
        self.assertEqual(events.extract_events(normalized)['first_win'], 48)
        # Root's absorbing master allows arbitrary actions after first win.
        padded = normalized + 'AAU'
        trace = events.extract_events(padded)
        self.assertEqual(trace['first_win'], 48)
        self.assertEqual(trace['states'][48:], (trace['states'][48],) * 4)
        self.assertTrue(all(not e['preterminal'] and e['origin'] is None
                            for e in trace['events'][48:]))
        master, _ = self._pinned_master(padded, symmetry=True)
        self.assertEqual(master.solver.check(), z3.sat)

    def test_source_guard_precedes_clauses(self):
        master = causal_master.build_master(1, use_events=False)
        count = len(master.solver.assertions())
        with patch.object(events.source, '_guard_current_source', side_effect=ValueError('guard')):
            with self.assertRaisesRegex(ValueError, 'guard'):
                events.add_master_constraints(master)
        self.assertEqual(len(master.solver.assertions()), count)


if __name__ == '__main__':
    unittest.main()
