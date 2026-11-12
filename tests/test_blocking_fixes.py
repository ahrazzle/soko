"""Regression tests for PR #1 review blocking fixes (I-1 9-step route, TCB path confinement, fail-closed prove_floor)."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import soko_mcp.engine_bridge as eb  # noqa: E402
from soko_mcp.oracle import FRONTIER_ROOMS, run_planted_bug_audit  # noqa: E402


class BlockingFixesRegressionTests(unittest.TestCase):
    def test_i1_metadata_and_9_step_route_verified(self) -> None:
        meta = FRONTIER_ROOMS["I-1"]
        self.assertEqual(meta["proven_floor"], 9)
        self.assertEqual(meta["shortest_known"], 9)
        self.assertEqual(meta["frontier_record"], 9)
        self.assertEqual(meta["reference_route"], "RRRRRRRRR")

        ok9 = eb.verify_route_dual(1, meta["grid"], "RRRRRRRRR")
        self.assertEqual(ok9["epistemic_status"], "VERIFIED")
        self.assertTrue(ok9["valid_winning_route"])
        self.assertEqual(ok9["route_len"], 9)

        short8 = eb.verify_route_dual(1, meta["grid"], "RRRRRRRR")
        self.assertEqual(short8["epistemic_status"], "REJECTED")
        self.assertFalse(short8["valid_winning_route"])

        audit = run_planted_bug_audit()
        self.assertEqual(audit["epistemic_status"], "VERIFIED")
        self.assertEqual(audit["planted_bugs_caught"], 10)

    def test_verify_tcb_lock_rejects_unconfined_paths_and_missing_pins(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fake_manifest = Path(td) / "SHA256SUMS"
            fake_manifest.write_text(
                "0" * 64 + "  ../outside_escape.txt\n"
                + "1" * 64 + "  /etc/hosts\n",
                encoding="utf-8",
            )
            with patch.object(eb, "SHA256SUMS_PATH", fake_manifest):
                res = eb.verify_tcb_lock()
                self.assertFalse(res["tcb_locked"])
                self.assertEqual(res["epistemic_status"], "TAMPERED_OR_UNLOCKED")
                self.assertEqual(len(res["unconfined_paths"]), 2)

        with patch.object(
            eb,
            "get_soko_checker_pins",
            return_value={
                "oracle_py_sha256": None,
                "flat_oracle_py_sha256": "abc",
                "cpp_soko_engine_src_sha256": "def",
                "cpp_soko_engine_bin_sha256": None,
                "formal_kernel_py_sha256": "ghi",
            },
        ):
            res_pin = eb.verify_tcb_lock()
            self.assertFalse(res_pin["tcb_locked"])
            self.assertFalse(res_pin["checker_pins_ok"])

    def test_prove_floor_verified_fails_closed_on_malformed_or_unwitnessed_cpp_output(self) -> None:
        grid = FRONTIER_ROOMS["I-1"]["grid"]

        # 1. Missing epistemic_status must NEVER default to VERIFIED
        with patch.object(eb, "_invoke_cpp", return_value={"proven_floor": 9, "exact_state_tt": True, "nodes_expanded": 5, "edge_consistency_checks": 10}):
            r1 = eb.prove_floor_verified(1, grid, max_bound=10, budget_sec=2)
            self.assertEqual(r1["epistemic_status"], "INCOMPLETE_CPP_OUTPUT")
            self.assertEqual(r1["proven_floor"], 0)

        # 2. Lossy TT must fail closed
        with patch.object(eb, "_invoke_cpp", return_value={"epistemic_status": "VERIFIED", "proven_floor": 9, "exact_state_tt": False, "nodes_expanded": 5, "edge_consistency_checks": 10}):
            r2 = eb.prove_floor_verified(1, grid, max_bound=10, budget_sec=2)
            self.assertEqual(r2["epistemic_status"], "REJECTED_LOSSY_TT")
            self.assertEqual(r2["proven_floor"], 0)

        # 3. exact_optimum_reached=True without winning_witness must fail closed
        with patch.object(
            eb,
            "_invoke_cpp",
            return_value={
                "epistemic_status": "VERIFIED",
                "proven_floor": 9,
                "exact_optimum_reached": True,
                "exact_state_tt": True,
                "winning_witness": "",
                "nodes_expanded": 5,
                "edge_consistency_checks": 10,
            },
        ):
            r3 = eb.prove_floor_verified(1, grid, max_bound=10, budget_sec=2)
            self.assertEqual(r3["epistemic_status"], "REJECTED_NO_WITNESS")
            self.assertEqual(r3["proven_floor"], 0)

        # 4. exact_optimum_reached=True with invalid/mismatched witness must fail closed
        with patch.object(
            eb,
            "_invoke_cpp",
            return_value={
                "epistemic_status": "VERIFIED",
                "proven_floor": 9,
                "exact_optimum_reached": True,
                "exact_state_tt": True,
                "winning_witness": "RRRRRRRR",
                "nodes_expanded": 5,
                "edge_consistency_checks": 10,
            },
        ):
            r4 = eb.prove_floor_verified(1, grid, max_bound=10, budget_sec=2)
            self.assertEqual(r4["epistemic_status"], "REJECTED_INVALID_WITNESS")
            self.assertEqual(r4["proven_floor"], 0)


if __name__ == "__main__":
    unittest.main()
