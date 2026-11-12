"""Completion cores are executable recipes and never trusted status strings."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import z3

from experiments.causal_solver import refinement as r
from experiments.exact_frontier import iii14_smt as game
from experiments.transport_relaxation.diagnostic import (
    baseline_heroes, shortened_heroes, hero_mappings,
)


def tiny_problem(horizon, encoding):
    """A small deterministic transition harness for core/cut protocol tests."""
    solver = z3.Solver()
    states = [(z3.BitVecVal(0, game.N), z3.BitVecVal(0, game.N),
               z3.BitVec(f'tiny_b{t}', game.N), z3.BitVec(f'tiny_d{t}', game.N),
               z3.Bool(f'tiny_active{t}'), z3.BitVecVal(0, game.N), z3.BoolVal(False))
              for t in range(horizon + 1)]
    actions = [[z3.Bool(f'tiny_{t}_{k}') for k in r.KEYS] for t in range(horizon)]
    solver.add(states[0][2] == game.BV(1 << 32),
               states[0][3] == game.BV(1 << 62), z3.Not(states[0][4]))
    for t, row in enumerate(actions):
        solver.add(z3.PbEq([(a, 1) for a in row], 1))
        solver.add(states[t + 1][2] == states[t][2])
        solver.add(states[t + 1][4] == z3.Xor(states[t][4], row[4]))
        moved = states[t][3]
        for a, key in zip(row[:4], 'UDLR'):
            moved = z3.If(z3.And(a, z3.Not(states[t][4])), game.shift(states[t][3], key), moved)
        solver.add(states[t + 1][3] == moved)
    return solver, actions, states


def tiny_master(horizon=2):
    return SimpleNamespace(horizon=horizon, solver=z3.Solver(),
        actions=[[z3.Bool(f'master_{t}_{k}') for k in r.KEYS] for t in range(horizon)],
        frames=[SimpleNamespace(**{**{f'{hero}_{coord}': z3.Int(f'master_{t}_{hero}_{coord}')
                                      for hero in ('bard', 'druid') for coord in ('x', 'y')},
                                   'active': z3.Bool(f'master_active_{t}')})
                for t in range(horizon + 1)])


class SmallCoreTests(unittest.TestCase):
    def setUp(self):
        self.patch = patch.object(r, '_build', side_effect=tiny_problem)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        lemmas = patch.object(r, '_prefix_lemmas')
        lemmas.start()
        self.addCleanup(lemmas.stop)
        self.refiner = r.ExactRefiner(2)

    def test_wrong_initial_hero_has_independently_checked_core(self):
        result = self.refiner.check_assumptions([('hero', 0, 'bard', 3, 2)])
        self.assertEqual(result['status'], 'unsat')
        self.assertEqual(result['core'], [['hero', 0, 'bard', 3, 2]])
        self.assertFalse(result['verified'])
        checked = self.refiner.check_certificate(result['certificate'])
        self.assertTrue(checked['verified'])
        self.assertEqual(checked['recheck_status'], 'unsat')

    def test_partial_core_excludes_multiple_complete_assignments(self):
        descriptors = [('action', 0, 'U'), ('hero', 1, 'druid', 3, 4)]
        result = self.refiner.check_assumptions(descriptors)
        self.assertEqual(result['status'], 'unsat')
        self.assertEqual({tuple(x) for x in result['core']}, set(descriptors))
        master = tiny_master()
        cut = r.add_core_cut(master, result['certificate'])
        self.assertTrue(cut['added'])
        for unrelated_key in ('L', 'R'):
            master.solver.push()
            master.solver.add(master.actions[0][0], master.actions[1][r.KEYS.index(unrelated_key)],
                              master.frames[1].druid_x == 3, master.frames[1].druid_y == 4)
            self.assertEqual(master.solver.check(), z3.unsat)
            master.solver.pop()
        for action, x, y in [('U', 2, 3), ('R', 3, 4)]:
            master.solver.push()
            master.solver.add(*[a == (k == action) for k, a in zip(r.KEYS, master.actions[0])],
                              master.frames[1].druid_x == x, master.frames[1].druid_y == y)
            self.assertEqual(master.solver.check(), z3.sat)
            master.solver.pop()

    def test_certificates_are_json_roundtrippable(self):
        import json
        result = self.refiner.check_assumptions([('active', 0, True)])
        certificate = json.loads(json.dumps(result['certificate']))
        self.assertTrue(self.refiner.check_certificate(certificate)['verified'])

    def test_corrupted_payload_metadata_and_unknown_cannot_cut(self):
        certificate = self.refiner.check_assumptions([('active', 0, True)])['certificate']
        variants = []
        for key, value in [('horizon', 1), ('encoding', 'legacy'), ('source_sha256', 'bad'),
                           ('board_sha256', 'bad'), ('mechanics_sha256', {})]:
            changed = deepcopy(certificate)
            changed['metadata'][key] = value
            variants.append(changed)
        changed = deepcopy(certificate)
        changed['core'][0][-1] = False
        variants.append(changed)
        changed = deepcopy(certificate)
        changed['unrecognized'] = True
        variants.append(changed)
        for changed in variants:
            with self.subTest(certificate=changed):
                master = tiny_master()
                before = tuple(master.solver.assertions())
                self.assertFalse(r.add_core_cut(master, changed)['added'])
                self.assertEqual(tuple(master.solver.assertions()), before)
        certificate['validation'] = {'status': 'verified', 'verified': True}
        master = tiny_master()
        self.assertFalse(r.add_core_cut(master, certificate, timeout_seconds=0)['added'])
        self.assertEqual(len(master.solver.assertions()), 0)
        self.assertEqual(self.refiner.check_assumptions([], timeout_seconds=0)['status'], 'unknown')

    def test_rehashed_satisfiable_core_and_forged_verified_status_rejected(self):
        certificate = self.refiner.check_assumptions([('active', 0, True)])['certificate']
        certificate['core'] = [['active', 0, False]]
        payload = {k: certificate[k] for k in ('kind', 'metadata', 'core', 'origin_assumptions_sha256')}
        certificate['payload_sha256'] = r._digest(payload)
        certificate['validation'] = {'status': 'verified', 'verified': True}
        result = r.add_core_cut(tiny_master(), certificate)
        self.assertEqual(result['status'], 'rejected')
        self.assertFalse(result['added'])
        self.assertEqual(result['recheck_status'], 'sat')

    def test_candidate_assumptions_do_not_leak_between_checks(self):
        self.assertEqual(self.refiner.check_assumptions([('active', 0, True)])['status'], 'unsat')
        self.assertEqual(self.refiner.check_assumptions([('active', 0, False)])['status'], 'sat')

    def test_malformed_assumptions_and_assignment_rejected(self):
        for d in [('action', 2, 'U'), ('action', 0, 'UD'), ('hero', 0, 'bard', True, 2),
                  ('active', 0, 1), ('landmark', 1), ('hero', 0, 'bard', 15, 2)]:
            with self.subTest(descriptor=d), self.assertRaises(ValueError):
                self.refiner.check_assumptions([d])
        with self.assertRaises(ValueError):
            self.refiner.check({'route': 'UU', 'heroes': []})
        with self.assertRaises(ValueError):
            self.refiner.check_assumptions([], timeout_seconds=float('inf'))


class FullMaterialControls(unittest.TestCase):
    def test_petrifying_bard_is_verified_loss_even_if_oracle_alive_is_true(self):
        initial = {'bard_x': 2, 'bard_y': 2, 'druid_x': 2, 'druid_y': 4, 'active': False}
        next_frame = {**initial, 'druid_y': 3}
        refiner = r.ExactRefiner(2)
        result = refiner.check({'route': 'UU', 'heroes': [initial, next_frame, next_frame]})
        self.assertEqual(result['status'], 'unsat')
        self.assertEqual(result['contradiction'], 'illegal_hero_loss')
        self.assertTrue(refiner.check_certificate(result['certificate'])['verified'])

    def test_known_48_key_original_route_retained(self):
        route, heroes = baseline_heroes()
        self.assertEqual(len(route), 48)
        refiner = r.ExactRefiner(len(route))
        result = refiner.check({'route': route, 'heroes': hero_mappings(heroes)}, timeout_seconds=30)
        self.assertEqual(result['status'], 'sat', result)
        self.assertEqual(result['route'], route)

    def test_absorbing_goal_preserves_active_on_action_padding(self):
        route, heroes = baseline_heroes()
        frames = list(hero_mappings(heroes))
        padded = {'route': route + 'AU', 'heroes': frames + [dict(frames[-1]), dict(frames[-1])]}
        refiner = r.ExactRefiner(len(padded['route']))
        self.assertEqual(refiner.check(padded)['status'], 'sat')
        padded['heroes'][-2]['active'] = not frames[-1]['active']
        result = refiner.check(padded)
        self.assertEqual(result['status'], 'unsat')
        self.assertEqual(result['frame'], 49)
        self.assertTrue(refiner.check_certificate(result['certificate'])['verified'])

    def test_deterministic_certificate_tampering_and_timeout_cannot_cut(self):
        route, heroes = shortened_heroes()
        refiner = r.ExactRefiner(len(route))
        certificate = refiner.check({'route': route, 'heroes': hero_mappings(heroes)})['certificate']
        master = tiny_master(len(route))
        certificate['validation'] = {'status': 'verified', 'verified': True}
        self.assertFalse(r.add_core_cut(master, certificate, timeout_seconds=0)['added'])
        self.assertEqual(len(master.solver.assertions()), 0)
        certificate['core'] = [['active', 0, False]]
        payload = {k: certificate[k] for k in ('kind', 'metadata', 'core', 'origin_assumptions_sha256')}
        certificate['payload_sha256'] = r._digest(payload)
        self.assertFalse(r.add_core_cut(master, certificate)['added'])
        self.assertEqual(len(master.solver.assertions()), 0)

    def test_constructed_47_key_spurious_projection_rejected_and_core_rechecked(self):
        route, heroes = shortened_heroes()
        self.assertEqual(len(route), 47)
        refiner = r.ExactRefiner(len(route))
        result = refiner.check({'route': route, 'heroes': hero_mappings(heroes)}, timeout_seconds=30)
        self.assertEqual(result['status'], 'unsat', result)
        checked = refiner.check_certificate(result['certificate'], timeout_seconds=30)
        self.assertTrue(checked['verified'], checked)


if __name__ == '__main__':
    unittest.main()
