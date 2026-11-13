"""Prefix facts require fresh full-material replay, rather than claimed states."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import z3

from experiments.causal_solver import master as causal, refinement as r
from experiments.transport_relaxation import global_master
from experiments.transport_relaxation.diagnostic import shortened_heroes, hero_mappings


def projection(horizon):
    """Free hero projection: expose precisely which guarded facts are added."""
    result = SimpleNamespace(horizon=horizon, solver=z3.Solver(),
        actions=[[z3.Bool(f'prefix_action_{t}_{key}') for key in r.KEYS]
                 for t in range(horizon)],
        frames=[SimpleNamespace(**{
            **{f'{hero}_{axis}': z3.Int(f'prefix_{t}_{hero}_{axis}')
               for hero in ('bard', 'druid') for axis in ('x', 'y')},
            'active': z3.Bool(f'prefix_active_{t}')}) for t in range(horizon + 1)])
    for row in result.actions:
        result.solver.add(z3.PbEq([(a, 1) for a in row], 1))
    return result


def short_certificate(horizon=2):
    descriptors = [('action', 0, 'U'), ('hero', 1, 'druid', 3, 4)]
    return r._certificate(r._metadata(horizon, 'compact'), descriptors, descriptors,
                          'deterministic_prefix')


def rehash(certificate):
    certificate['payload_sha256'] = r._digest({k: certificate[k] for k in (
        'kind', 'metadata', 'core', 'origin_assumptions_sha256')})
    return certificate


class PrefixFrameLearningTests(unittest.TestCase):
    def test_complete_frame_excludes_each_wrong_hero_component_and_active(self):
        master = projection(2)
        result = r.add_core_cut(master, short_certificate(), learn_prefix_frames=True)
        self.assertTrue(result['added'], result)
        self.assertEqual(result['prefix_frames_learned'], 2)
        self.assertEqual(result['prefix_max_depth'], 1)
        frame = master.frames[1]
        for wrong in (frame.bard_x != 2, frame.bard_y != 2,
                      frame.druid_x != 2, frame.druid_y != 3, frame.active):
            with self.subTest(wrong=wrong):
                master.solver.push()
                master.solver.add(master.actions[0][0], wrong)
                self.assertEqual(master.solver.check(), z3.unsat)
                master.solver.pop()
        master.solver.add(master.actions[0][0], frame.druid_y == 3)
        self.assertEqual(master.solver.check(), z3.sat)

    def test_different_prefix_and_unchecked_suffix_remain_free(self):
        master = projection(2)
        r.add_core_cut(master, short_certificate(), learn_prefix_frames=True)
        frame = master.frames[1]
        master.solver.add(master.actions[0][r.KEYS.index('R')],
                          frame.bard_x == 8, frame.bard_y == 6,
                          frame.druid_x == 9, frame.druid_y == 5, frame.active,
                          master.frames[2].bard_x == 11)
        self.assertEqual(master.solver.check(), z3.sat)

    def test_default_keeps_only_original_nogood(self):
        master = projection(2)
        result = r.add_core_cut(master, short_certificate())
        self.assertTrue(result['added'])
        self.assertEqual(result['prefix_frames_learned'], 0)
        self.assertIsNone(result['prefix_max_depth'])
        self.assertEqual(len(master.solver.assertions()), 3)  # two action rows + nogood
        master.solver.add(master.actions[0][0], master.frames[1].bard_x == 8,
                          master.frames[1].druid_x == 2)
        self.assertEqual(master.solver.check(), z3.sat)

    def test_illegal_loss_learns_only_surviving_frames(self):
        core = [('action', 0, 'U'), ('action', 1, 'U')]
        certificate = r._certificate(r._metadata(2, 'compact'), core, core,
                                     'deterministic_prefix')
        master = projection(2)
        result = r.add_core_cut(master, certificate, learn_prefix_frames=True)
        self.assertTrue(result['added'], result)
        self.assertEqual(result['prefix_frames_learned'], 2)
        self.assertEqual(result['prefix_max_depth'], 1)
        master.solver.add(master.actions[0][0], master.actions[1][0])
        self.assertEqual(master.solver.check(), z3.unsat)

    def test_reference_retained_and_spurious_projection_excluded(self):
        route, heroes = shortened_heroes()
        spurious = {'route': route, 'heroes': list(hero_mappings(heroes)), 'landmark': 42}
        checked = r.ExactRefiner(47).check(spurious)
        master = causal.build_master(47, use_events=False)
        global_master.pin_assignment(master, spurious)
        result = r.add_core_cut(master, checked['certificate'], learn_prefix_frames=True)
        self.assertTrue(result['added'], result)
        self.assertGreater(result['prefix_max_depth'], 0)
        self.assertEqual(master.solver.check(), z3.unsat)

        reference = causal.reference_assignment(48)
        self.assertEqual(r.ExactRefiner(48).check(reference)['status'], 'sat')
        padded = {**spurious, 'route': route + 'A',
                  'heroes': spurious['heroes'] + [dict(spurious['heroes'][-1])]}
        certificate = r.ExactRefiner(48).check(padded)['certificate']
        master = causal.build_master(48, use_events=False)
        global_master.pin_assignment(master, reference)
        self.assertTrue(r.add_core_cut(master, certificate, learn_prefix_frames=True)['added'])
        self.assertEqual(master.solver.check(), z3.sat)

    def test_absorbing_goal_keeps_activity_and_positions_after_padding(self):
        reference = causal.reference_assignment(50)
        reference['route'] = reference['route'][:48] + 'AU'
        reference['heroes'][-1]['active'] = not reference['heroes'][-1]['active']
        checked = r.ExactRefiner(50).check(reference)
        self.assertEqual(checked['frame'], 50)
        master = projection(50)
        result = r.add_core_cut(master, checked['certificate'],
                                learn_prefix_frames=True, timeout_seconds=10)
        self.assertTrue(result['added'], result)
        self.assertEqual(result['prefix_frames_learned'], 51)
        self.assertEqual(result['prefix_max_depth'], 50)
        master.solver.add(*[master.actions[t][r.KEYS.index(key)]
                            for t, key in enumerate(reference['route'])])
        goal = reference['heroes'][48]
        for t in (49, 50):
            frame = master.frames[t]
            for wrong in (frame.active != goal['active'],
                          frame.bard_x != goal['bard_x'],
                          frame.druid_x != goal['druid_x']):
                master.solver.push()
                master.solver.add(wrong)
                self.assertEqual(master.solver.check(), z3.unsat)
                master.solver.pop()

    def test_metadata_payload_and_rehashed_satisfiable_tampering_add_nothing(self):
        variants = []
        for field in ('board_sha256', 'source_sha256', 'mechanics_sha256'):
            certificate = short_certificate()
            certificate['metadata'][field] = 'forged'
            variants.append(rehash(certificate))
        certificate = short_certificate()
        certificate['core'][-1][-1] = 5
        variants.append(certificate)
        certificate = short_certificate()
        certificate['core'][-1] = ['hero', 1, 'druid', 2, 3]
        variants.append(rehash(certificate))
        certificate = short_certificate()
        certificate['core'] = [['action', 1, 'U'], ['hero', 2, 'druid', 3, 4]]
        variants.append(rehash(certificate))  # missing initial action is open
        for certificate in variants:
            with self.subTest(certificate=certificate):
                master = projection(2)
                before = tuple(master.solver.assertions())
                result = r.add_core_cut(master, certificate, learn_prefix_frames=True)
                self.assertFalse(result['added'], result)
                self.assertEqual(result['prefix_frames_learned'], 0)
                self.assertEqual(tuple(master.solver.assertions()), before)

    def test_forged_validation_facts_are_ignored(self):
        certificate = short_certificate()
        certificate['validation'] = {'verified': True, 'checked_frames': [
            [1, [8, 6], [9, 5], True]]}
        master = projection(2)
        result = r.add_core_cut(master, certificate, learn_prefix_frames=True)
        self.assertTrue(result['added'], result)
        self.assertNotIn('checked_frames', result['certificate']['validation'])
        master.solver.add(master.actions[0][0], master.frames[1].bard_x == 8)
        self.assertEqual(master.solver.check(), z3.unsat)

    def test_zero_and_partial_replay_timeout_add_nothing(self):
        for timeout in (0, 1e-12):
            master = projection(2)
            before = tuple(master.solver.assertions())
            result = r.add_core_cut(master, short_certificate(), timeout_seconds=timeout,
                                    learn_prefix_frames=True)
            self.assertFalse(result['added'], result)
            self.assertEqual(result['prefix_frames_learned'], 0)
            self.assertEqual(tuple(master.solver.assertions()), before)
        for initial_ticks in (3, 5):
            master = projection(2)
            before = tuple(master.solver.assertions())
            # Expire either after collecting frame 0 or after successful replay
            # while constructing the implications. Neither may install facts.
            clock = iter([0.] * initial_ticks + [20.] * 10)
            with patch.object(r.time, 'perf_counter', side_effect=lambda: next(clock)):
                result = r.add_core_cut(master, short_certificate(), timeout_seconds=10,
                                        learn_prefix_frames=True)
            self.assertFalse(result['added'], result)
            self.assertEqual(tuple(master.solver.assertions()), before)

    def test_oracle_disagreement_after_collected_frame_adds_nothing(self):
        actual = r.mechanics.oracle_state
        count = 0
        def disagree_on_second_frame(oracle):
            nonlocal count
            count += 1
            state = actual(oracle)
            return state if count == 1 else (*state[:4], not state[4], *state[5:])
        master = projection(2)
        before = tuple(master.solver.assertions())
        with patch.object(r.mechanics, 'oracle_state', side_effect=disagree_on_second_frame):
            result = r.add_core_cut(master, short_certificate(), learn_prefix_frames=True)
        self.assertFalse(result['added'], result)
        self.assertIn('oracle mismatch', result['reason'])
        self.assertEqual(tuple(master.solver.assertions()), before)

    def test_smt_core_installs_only_nogood(self):
        certificate = r._certificate(r._metadata(0, 'compact'),
            [('active', 0, True)], [('active', 0, True)], 'smt_core')
        # A real horizon-zero exact check has a false terminal goal.
        master = projection(0)
        result = r.add_core_cut(master, certificate, learn_prefix_frames=True)
        self.assertTrue(result['added'], result)
        self.assertEqual(result['prefix_frames_learned'], 0)
        self.assertEqual(len(master.solver.assertions()), 1)


if __name__ == '__main__':
    unittest.main()
