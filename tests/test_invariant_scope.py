"""Finite-state regression tests for invariant synthesis proof boundaries."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from soko_mcp import formal_kernel, invariant_synth


class SmallSystem:
    code_sha256 = "test-system"

    def initial_state(self):
        return 0

    def actions(self, state):
        return ("advance",)

    def step(self, state, action):
        return {0: 1, 1: 1, 2: 3, 3: 3}[state]

    def project_obs(self, state):
        return state

    def invariant(self, state):
        return (True, "")

    def is_goal(self, state):
        return state == 3


class InvariantScopeTest(unittest.TestCase):
    def run_synthesis(self, module, candidates, **kwargs):
        system = SmallSystem()
        reg = SimpleNamespace(spec=system, impl=system, exact_only=True,
                              system_id="test", certificates=[])
        with patch.object(module, "_get_locked_system", return_value=reg):
            result = module.synthesize_formal_invariant("test", candidates, **kwargs)
        return result, reg

    def test_cap_excludes_successor_without_claiming_closure(self):
        candidates = 'def predicates():\n    return {"always": lambda s: True}\n'
        for module in (formal_kernel, invariant_synth):
            for mode in ("houdini_safety", "deadlock_trap"):
                with self.subTest(module=module.__name__, mode=mode):
                    result, reg = self.run_synthesis(module, candidates, synthesis_mode=mode,
                                                     max_concrete_states=1)
                    self.assertEqual(result["epistemic_status"], "VERIFIED_ON_BOUNDED_REACHABLE_SUBGRAPH")
                    self.assertEqual(result["proof_scope"], "explored_reachable_subgraph")
                    self.assertEqual(result["open_transitions"], 1)
                    self.assertFalse(result["complete_domain_closed"])
                    self.assertEqual(result["transitions_checked"], 0)
                    self.assertEqual(reg.certificates, [])

    def test_reachable_trap_is_not_a_global_predicate(self):
        candidates = 'def predicates():\n    return {"candidate": lambda s: s == 1 or s == 2}\n'
        universe = 'def enumerate_states():\n    return (0, 1, 2, 3)\n'
        for module in (formal_kernel, invariant_synth):
            with self.subTest(module=module.__name__):
                reachable, _ = self.run_synthesis(module, candidates, synthesis_mode="deadlock_trap")
                self.assertEqual(reachable["epistemic_status"], "PROVEN")
                self.assertEqual(reachable["proof_scope"], "complete_reachable_states")
                self.assertEqual(reachable["synthesized_traps"], ["candidate"])
                self.assertEqual(reachable["open_transitions"], 0)
                closed, _ = self.run_synthesis(module, candidates, synthesis_mode="deadlock_trap",
                                               universe_code=universe)
                self.assertEqual(closed["proof_scope"], "enumerated_closed_domain")
                self.assertEqual(closed["epistemic_status"], "REJECTED_NO_SOUND_TRAP_FOUND")
                self.assertEqual(closed["synthesized_traps"], [])


if __name__ == "__main__":
    unittest.main()
