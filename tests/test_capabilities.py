"""Capability surface and honest backend-unavailable vs budget-exhausted status tests."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import soko_mcp.engine_bridge as eb  # noqa: E402
from soko_mcp.oracle import FRONTIER_ROOMS  # noqa: E402
from soko_mcp.server import dispatch_tool_call  # noqa: E402


class CapabilityContractTests(unittest.TestCase):
    def test_soko_capabilities_reports_honest_runtime_readiness(self) -> None:
        caps = dispatch_tool_call("soko_capabilities", {})
        self.assertEqual(caps["version"], "0.3.0")
        self.assertTrue(caps["cpp_engine_ready"])
        self.assertIsNone(caps["cpp_unavailable_reason"])
        self.assertEqual(caps["route_verification"]["total_oracles"], 3)
        self.assertIn("PairAtomQuotientPDB", caps["lower_bound_proving"]["abstractions"])
        self.assertIn("WizardRayGoalBound", caps["lower_bound_proving"]["abstractions"])
        self.assertIn("formal_synthesize_invariant", caps["formal_systems"]["tools"])

    def test_solve_room_distinguishes_backend_unavailable_from_budget_exhaustion(self) -> None:
        g20 = FRONTIER_ROOMS["III-20"]["grid"]

        with patch.object(eb, "ensure_cpp_engine", return_value=None):
            no_cpp = eb.solve_room_verified(3, g20, max_depth=5, beam_width=2000, budget_sec=2)
            self.assertEqual(no_cpp["epistemic_status"], "BACKEND_UNAVAILABLE")
            self.assertFalse(no_cpp["solved"])
            self.assertIsNotNone(no_cpp["unavailable_reason"])

            caps_no_cpp = eb.get_capabilities()
            self.assertFalse(caps_no_cpp["cpp_engine_ready"])
            self.assertFalse(caps_no_cpp["solve_from_scratch"]["available"])
            self.assertEqual(caps_no_cpp["route_verification"]["total_oracles"], 2)

        budget_out = eb.solve_room_verified(3, g20, max_depth=2, beam_width=2000, budget_sec=2)
        self.assertEqual(budget_out["epistemic_status"], "UNSOLVED_WITHIN_BUDGET")
        self.assertFalse(budget_out["solved"])

    def test_catalog_capability_surface(self) -> None:
        caps = dispatch_tool_call("soko_capabilities", {})
        self.assertIn("catalog", caps)
        self.assertEqual(caps["catalog"]["original_rooms"], 66)


if __name__ == "__main__":
    unittest.main()
