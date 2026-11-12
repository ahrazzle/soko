"""Check bounded game controls and their ability to catch faulty transitions."""
import unittest
from unittest.mock import patch

from experiments.causal_solver import controls
from experiments.exact_frontier import iii14_smt as model


class CausalControlsTests(unittest.TestCase):
    def test_reference_and_spurious_routes(self):
        reference = controls.replay(model.ROUTE)
        self.assertEqual(reference['outcome'], 'won')
        self.assertEqual(reference['step'], 48)
        short, heroes = controls.shortened_heroes()
        self.assertEqual(len(short), 47)
        self.assertEqual(controls.replay(short)['outcome'], 'not_won')
        comparison = controls.compare_original_heroes(short, heroes)
        self.assertFalse(comparison['winning'])
        self.assertEqual(comparison['first_hero_mismatch']['frame'], 26)

    def test_exhaustive_and_loss_semantics(self):
        counts = controls.exhaustive(3)
        self.assertEqual(counts['transitions'], 150)
        self.assertEqual(counts['loss_pruned'], 1)
        self.assertEqual(controls.replay('UU')['outcome'], 'loss_pruned')

    def test_all_mechanics_mutants_are_detected(self):
        cases = controls.planted_errors()
        self.assertEqual(len(cases), 10)
        self.assertTrue(all(result['detected'] for result in cases.values()))
        for name, case in cases.items():
            if name != 'corrupt_source_pin':
                self.assertNotEqual(case['correct'], case['mutant'], name)

    def test_controls_reject_corrupted_transition(self):
        transition = controls.transition
        def broken(state, key):
            result, legal = transition(state, key)
            result = list(result)
            result[5] = 0  # Erase notes after activation.
            return tuple(result), legal
        with patch.object(controls, 'transition', broken):
            with self.assertRaisesRegex(AssertionError, 'disagrees with oracle'):
                controls.checked_step(controls.fixture(active='D', objects=[(5, 5, '*')]), 'A')

    def test_invalid_exhaustive_depth(self):
        for depth in (-1, True, 5):
            with self.assertRaises(ValueError):
                controls.exhaustive(depth)


if __name__ == '__main__':
    unittest.main()
