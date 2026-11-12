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
        outside = REPO_ROOT.parent / "escape_probe_blocking_fixes.txt"
        payload = b"probe"
        outside.write_bytes(payload)
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        digest = hashlib.sha256(payload).hexdigest()
        rel_escape = f"../{outside.name}"
        tampered = f"{digest}  {rel_escape}\n"
        original = SHA256SUMS_PATH.read_text(encoding="utf-8") if SHA256SUMS_PATH.is_file() else ""
        SHA256SUMS_PATH.write_text(tampered, encoding="utf-8")
        self.addCleanup(lambda: SHA256SUMS_PATH.write_text(original, encoding="utf-8") if original else SHA256SUMS_PATH.unlink(missing_ok=True))
        out = verify_tcb_lock()
        self.assertFalse(out["tcb_locked"])
        self.assertEqual(out["epistemic_status"], "TAMPERED_OR_UNLOCKED")
        self.assertTrue(out["unconfined_paths"])

    def test_manifest_verified_when_intact(self) -> None:
        out = verify_tcb_lock()
        self.assertTrue(SHA256SUMS_PATH.is_file())
        self.assertTrue(out["manifest_present"])
        self.assertGreater(out["files_verified"], 0)
        if out["checker_pins_ok"]:
            self.assertTrue(out["tcb_locked"])
            self.assertEqual(out["epistemic_status"], "VERIFIED")

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
