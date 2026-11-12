"""Fixed-hero token-allocation controls and diagnostic checks."""
from dataclasses import replace
import unittest

from experiments.transport_relaxation.diagnostic import (
    baseline_heroes, check_witness, compare_original_heroes, hero_mappings, possible_landmarks, shortened_heroes,
)
from experiments.transport_relaxation.project import SWITCHES
from experiments.transport_relaxation import allocation


class AllocationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.route, cls.heroes = baseline_heroes()
        cls.maps = hero_mappings(cls.heroes)
        cls.result = allocation.allocate(cls.route, cls.maps, 43)

    def test_known_reference_all_nine_switches_and_model_witness(self):
        r = self.result
        self.assertEqual(r['status'], 'feasible')
        self.assertEqual(r['landmark_frame'], 43)
        self.assertEqual(len(r['origins']), 9)
        self.assertEqual(len({tuple(p) for p in r['origins']}), 9)
        frame = r['frames'][43]
        self.assertEqual(tuple(zip(frame['token_x'], frame['token_y'])), SWITCHES)
        self.assertTrue(all(frame['harvested']))
        self.assertEqual(check_witness(self.route, r)['status'], 'sat')

    def test_remote_boundary_origin_cannot_be_harvested(self):
        # After the first L, Druid is at (1,4) and has not yet faced (0,4).
        states = allocation.reachable_token_states(self.route[:1], self.maps[:2], (0, 4), 1)
        self.assertTrue(states)
        self.assertFalse(any(state['harvested'] for state in states))
        # On the second L, Druid stays at (1,4), facing that origin.
        states = allocation.reachable_token_states(self.route[:2], self.maps[:3], (0, 4), 2)
        self.assertTrue(any(state['harvested'] for state in states))

    def test_illegal_hero_trajectory_rejected(self):
        broken = list(self.heroes)
        broken[5] = replace(broken[5], bard=(14, 6))
        result = allocation.allocate(self.route, hero_mappings(broken), 43)
        self.assertEqual(result['status'], 'invalid_trajectory')

    def test_short_schedule_has_abstract_witness_but_original_does_not_win(self):
        route, heroes = shortened_heroes()
        result = allocation.allocate(route, hero_mappings(heroes), 42)
        self.assertEqual(result['status'], 'feasible')
        self.assertEqual(check_witness(route, result)['status'], 'sat')
        replay = compare_original_heroes(route, heroes)
        self.assertFalse(replay['winning'])
        self.assertEqual(replay['first_hero_mismatch']['frame'], 26)

    def test_hall_obstruction_is_a_real_neighbor_deficiency(self):
        route, heroes = shortened_heroes()
        result = allocation.allocate(route, hero_mappings(heroes), 31)
        self.assertEqual(result['status'], 'infeasible')
        hall = result['hall_obstruction']
        neighbors = set().union(*(set(result['edges'][i]['origin_indices'])
                                  for i in hall['switch_indices']))
        self.assertEqual(neighbors, set(hall['origin_indices']))
        self.assertLess(len(neighbors), len(hall['switch_indices']))
        self.assertEqual(hall['deficiency'], len(hall['switch_indices']) - len(neighbors))

    def test_shortened_hero_schedule_and_landmark_filter(self):
        route, heroes = shortened_heroes()
        self.assertEqual(len(route), 47)
        self.assertEqual(heroes[17].druid, (5, 1))
        self.assertEqual({heroes[-1].bard, heroes[-1].druid}, {(9, 3), (11, 3)})
        self.assertEqual(possible_landmarks(route, heroes), tuple(range(17, 48)))
        self.assertTrue(all({h.bard, h.druid} != {(9, 3), (11, 3)} for h in heroes[:-1]))


if __name__ == '__main__':
    unittest.main()
