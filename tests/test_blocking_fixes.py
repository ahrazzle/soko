"""Regression tests for F-03, F-04, I-1 registry, and TCB confinement (review 5874535099)."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from soko_mcp.engine_bridge import (
    REPO_ROOT,
    SHA256SUMS_PATH,
    get_soko_checker_pins,
    prove_floor_verified,
    verify_route_dual,
    verify_tcb_lock,
)
from soko_mcp.oracle import FRONTIER_ROOMS
from soko_mcp.server import TOOLS, dispatch_tool_call


class BlockingFixTests(unittest.TestCase):
    def test_tcb_lock_tool_wired(self) -> None:
        names = {t["name"] for t in TOOLS}
        self.assertIn("soko_verify_tcb_lock", names)
        out = dispatch_tool_call("soko_verify_tcb_lock", {})
        self.assertIn("tcb_locked", out)
        self.assertIn("checker_pins", out)

    def test_confined_manifest_rejects_parent_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "SHA256SUMS"
            digest = hashlib.sha256(b"probe").hexdigest()
            manifest.write_text(f"{digest}  ../outside.py\n")
            with mock.patch("soko_mcp.engine_bridge.SHA256SUMS_PATH", manifest):
                out = verify_tcb_lock()
        self.assertFalse(out["tcb_locked"])
        self.assertEqual(out["epistemic_status"], "TAMPERED_OR_UNLOCKED")
        self.assertTrue(out["unconfined_paths"])

    def test_manifest_verified_when_intact(self) -> None:
        out = verify_tcb_lock()
        self.assertTrue(SHA256SUMS_PATH.is_file())
        self.assertTrue(out["manifest_present"])
        self.assertGreater(out["files_verified"], 0)
        self.assertTrue(out["tcb_locked"], out)
        self.assertEqual(out["epistemic_status"], "VERIFIED")
        self.assertEqual(out["lock_scope"], "source_manifest")
        self.assertFalse(out["compiled_binary"]["verified_by_manifest"])

    def test_i1_registry_nine_step_route(self) -> None:
        meta = FRONTIER_ROOMS["I-1"]
        self.assertEqual(meta["proven_floor"], 9)
        self.assertEqual(meta["shortest_known"], 9)
        self.assertEqual(meta["reference_route"], "RRRRRRRRR")
        good = verify_route_dual(meta["part"], meta["grid"], meta["reference_route"])
        self.assertEqual(good["epistemic_status"], "VERIFIED")
        bad = verify_route_dual(meta["part"], meta["grid"], "RRRRRRRR")
        self.assertEqual(bad["epistemic_status"], "REJECTED")

    def test_prove_floor_rejects_missing_cpp_epistemic_default(self) -> None:
        meta = FRONTIER_ROOMS["I-1"]
        fake = {"proven_floor": 1, "exact_optimum_reached": False, "nodes_expanded": 0, "edge_consistency_checks": 0}
        with mock.patch("soko_mcp.engine_bridge._invoke_cpp", return_value=fake):
            out = prove_floor_verified(meta["part"], meta["grid"], max_bound=12, budget_sec=1)
        self.assertNotEqual(out["epistemic_status"], "VERIFIED")
        self.assertEqual(out["epistemic_status"], "INCOMPLETE_CPP_OUTPUT")

    def test_prove_floor_rejects_stub_verified_without_witness(self) -> None:
        meta = FRONTIER_ROOMS["I-1"]
        fake = {
            "epistemic_status": "VERIFIED",
            "proven_floor": 1,
            "exact_optimum_reached": True,
            "exact_state_tt": True,
            "winning_witness": "",
            "nodes_expanded": 1,
            "edge_consistency_checks": 0,
        }
        with mock.patch("soko_mcp.engine_bridge._invoke_cpp", return_value=fake):
            out = prove_floor_verified(meta["part"], meta["grid"], max_bound=12, budget_sec=1)
        self.assertEqual(out["epistemic_status"], "REJECTED_NO_WITNESS")

    def test_ledger_routes_still_verified(self) -> None:
        for rid in ("II-22", "III-14", "III-15", "III-20", "III-22"):
            meta = FRONTIER_ROOMS[rid]
            res = verify_route_dual(meta["part"], meta["grid"], meta["reference_route"])
            self.assertEqual(res["epistemic_status"], "VERIFIED", msg=rid)


if __name__ == "__main__":
    unittest.main()
