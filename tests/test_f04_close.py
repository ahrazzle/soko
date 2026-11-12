"""F-04 closure: floor witness binding, TCB gating, formal_kernel differential lock."""
from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
from unittest import mock

from soko_mcp.engine_bridge import (
    REPO_ROOT,
    SHA256SUMS_PATH,
    prove_floor_verified,
    verify_route_dual,
    verify_tcb_lock,
)
from soko_mcp.formal_kernel import define_formal_system
from soko_mcp.oracle import FRONTIER_ROOMS

_CHECKER_TEMPLATE = """
def initial_state():
    return 0

def actions(state):
    return (1,)

def step(state, action):
    return state + 1

def invariant(state):
    return True, ""

def step_cost(state, action, next_state):
    return 1

def project_obs(state):
    return 0
"""


class F04ProveFloorTests(unittest.TestCase):
    def test_honest_i1_prove_floor_verified(self) -> None:
        meta = FRONTIER_ROOMS["I-1"]
        out = prove_floor_verified(meta["part"], meta["grid"], max_bound=12, budget_sec=3)
        self.assertEqual(out["epistemic_status"], "VERIFIED")
        self.assertEqual(out["proven_floor"], 9)
        self.assertIsNotNone(out["winning_witness"])
        self.assertEqual(out["winning_witness"]["route_len"], 9)
        self.assertEqual(out["winning_witness"]["route"], "RRRRRRRRR")
        self.assertIsNotNone(out.get("guarantee"))

    def test_stub_floor_one_with_nine_step_witness_rejected(self) -> None:
        meta = FRONTIER_ROOMS["I-1"]
        fake = {
            "epistemic_status": "VERIFIED",
            "proven_floor": 1,
            "exact_optimum_reached": True,
            "exact_state_tt": True,
            "winning_witness": "RRRRRRRRR",
            "nodes_expanded": 1,
            "edge_consistency_checks": 0,
        }
        def _invoke_side_effect(mode: str, *args, **kwargs):
            if mode == "prove_lb":
                return fake
            return None

        with mock.patch("soko_mcp.engine_bridge._invoke_cpp", side_effect=_invoke_side_effect):
            out = prove_floor_verified(meta["part"], meta["grid"], max_bound=12, budget_sec=1)
        self.assertNotEqual(out["epistemic_status"], "VERIFIED")
        self.assertEqual(out["epistemic_status"], "REJECTED_WITNESS_FLOOR_MISMATCH")

    def test_stub_floor_ten_with_eleven_step_detour_rejected(self) -> None:
        meta = FRONTIER_ROOMS["I-1"]
        detour = "DRRRRRRRRRU"
        fake = {
            "epistemic_status": "VERIFIED",
            "proven_floor": 10,
            "exact_optimum_reached": True,
            "exact_state_tt": True,
            "winning_witness": detour,
            "nodes_expanded": 1,
            "edge_consistency_checks": 0,
        }

        def _invoke_side_effect(mode: str, *args, **kwargs):
            if mode == "prove_lb":
                return fake
            return None

        with mock.patch("soko_mcp.engine_bridge._invoke_cpp", side_effect=_invoke_side_effect):
            out = prove_floor_verified(meta["part"], meta["grid"], max_bound=12, budget_sec=1)
        self.assertNotEqual(out["epistemic_status"], "VERIFIED")
        self.assertEqual(out["epistemic_status"], "REJECTED_WITNESS_FLOOR_MISMATCH")

    def test_guarantee_absent_when_not_verified(self) -> None:
        meta = FRONTIER_ROOMS["I-1"]
        fake = {"proven_floor": 1, "nodes_expanded": 0, "edge_consistency_checks": 0}
        with mock.patch("soko_mcp.engine_bridge._invoke_cpp", return_value=fake):
            out = prove_floor_verified(meta["part"], meta["grid"], max_bound=12, budget_sec=1)
        self.assertEqual(out["epistemic_status"], "INCOMPLETE_CPP_OUTPUT")
        self.assertIsNone(out.get("guarantee"))


class F04TcbGatingTests(unittest.TestCase):
    def test_verify_route_dual_rejects_when_manifest_tampered(self) -> None:
        meta = FRONTIER_ROOMS["I-1"]
        oracle_path = REPO_ROOT / "soko_mcp" / "oracle.py"
        digest = hashlib.sha256(oracle_path.read_bytes()).hexdigest()
        tampered = SHA256SUMS_PATH.read_text(encoding="utf-8").replace(
            digest, "0" * 64, 1
        )
        original = SHA256SUMS_PATH.read_text(encoding="utf-8")
        SHA256SUMS_PATH.write_text(tampered, encoding="utf-8")
        self.addCleanup(lambda: SHA256SUMS_PATH.write_text(original, encoding="utf-8"))
        lock = verify_tcb_lock()
        self.assertFalse(lock["tcb_locked"])
        out = verify_route_dual(meta["part"], meta["grid"], meta["reference_route"])
        self.assertEqual(out["epistemic_status"], "REJECTED_TCB_UNLOCKED")

    def test_prove_floor_rejects_after_tcb_lock_failed(self) -> None:
        meta = FRONTIER_ROOMS["I-1"]
        fake = {
            "epistemic_status": "VERIFIED",
            "proven_floor": 1,
            "exact_optimum_reached": True,
            "exact_state_tt": True,
            "winning_witness": "RRRRRRRRR",
            "nodes_expanded": 1,
            "edge_consistency_checks": 0,
        }
        original = SHA256SUMS_PATH.read_text(encoding="utf-8")
        SHA256SUMS_PATH.write_text("deadbeef\n  ../etc/passwd\n", encoding="utf-8")
        self.addCleanup(lambda: SHA256SUMS_PATH.write_text(original, encoding="utf-8"))
        def _invoke_side_effect(mode: str, *args, **kwargs):
            if mode == "prove_lb":
                return fake
            return None

        with mock.patch("soko_mcp.engine_bridge._invoke_cpp", side_effect=_invoke_side_effect):
            out = prove_floor_verified(meta["part"], meta["grid"], max_bound=12, budget_sec=1)
        self.assertNotEqual(out["epistemic_status"], "VERIFIED")
        self.assertEqual(out["epistemic_status"], "REJECTED_TCB_UNLOCKED")


class F04FormalKernelTests(unittest.TestCase):
    def test_disagreeing_goal_on_hidden_state_not_verified_locked(self) -> None:
        spec = _CHECKER_TEMPLATE + "\ndef is_goal(state):\n    return state >= 3\n"
        impl = _CHECKER_TEMPLATE + "\ndef is_goal(state):\n    return state == 1 or state >= 3\n"
        out = define_formal_system(
            "f04_goal_mismatch",
            spec_code=spec,
            impl_code=impl,
            description="F-04 review counterexample",
            must_fail_controls=[{"name": "two_steps_no_goal", "trace": [1, 1]}],
            positive_witnesses=[{"name": "three_steps", "trace": [1, 1, 1], "expect_goal": True}],
            strict_bar=True,
            bounded_fuzz_nodes=16,
        )
        self.assertNotEqual(out.get("epistemic_status"), "VERIFIED")
        self.assertFalse(out.get("tcb_locked"))


if __name__ == "__main__":
    unittest.main()
