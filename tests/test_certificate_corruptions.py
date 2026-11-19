"""Certificate `must_fail` control and tier-swap corruption regression tests (#53 A6, A7).

Modeled on `Foundation-0/incentre-lattices` `certlib.must_fail` and
`Foundation-0/f0` `tests/run_gate_corruptions.py`:
  1. Every issued route, optimization, solver, floor, and track certificate carries a
     non-empty list of distinct `must_fail_controls` names and passes `verify_certificate_gate`.
  2. Stripping, emptying, or duplicating `must_fail_controls` fails closed.
  3. Promoting a `LOWER_BOUND` / `LOWER_BOUND_UNWITNESSED` claim (or static `LINT_PASS`
     checker audit, or bounded-subgraph result) to `VERIFIED` or `PROVEN` fails closed
     (`REJECTED_TIER_SWAP`), even if `certificate_sha256` is recomputed.
  4. A tautological negative control (such as seeding an improvement control with an
     already-passing target) raises `ValueError` immediately in `must_fail`.
"""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest

from soko_mcp.checker_auditor import audit_builtin_soko_oracles, audit_dual_checkers
from soko_mcp.engine_bridge import (
    ensure_cpp_engine,
    optimize_route_verified,
    prove_floor_verified,
    solve_room_verified,
    verify_route_dual,
)
from soko_mcp.evidence import digest, must_fail, verify_certificate_gate
from soko_mcp.oracle import FRONTIER_ROOMS

REPO_ROOT = Path(__file__).resolve().parent.parent


def _resign(cert: dict) -> dict:
    mutated = copy.deepcopy(cert)
    mutated.pop("certificate_sha256", None)
    mutated["certificate_sha256"] = digest(mutated)
    return mutated


def _load_track_verifier(track_slug: str):
    path = REPO_ROOT / "tracks" / track_slug / "verify.py"
    spec = importlib.util.spec_from_file_location(f"track_{track_slug.replace('-', '_')}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class MustFailAndTierSwapCorruptionTests(unittest.TestCase):
    def test_must_fail_helper_rejects_passing_or_unnamed_controls(self) -> None:
        log: list[str] = []
        must_fail("truncated_route", False, log)
        self.assertEqual(log, ["truncated_route"])

        # Simulates seeding an 87 -> 84 control with 84 so the broken predicate holds (True):
        with self.assertRaisesRegex(ValueError, "wrongly accepted"):
            must_fail("seed_already_at_improved_len", True, log)

        for bad_name in ("", "   ", 123):  # type: ignore[list-item]
            with self.assertRaises(ValueError):
                must_fail(bad_name, False, log)  # type: ignore[arg-type]

    def test_builtin_and_dual_checker_auditor_return_lint_pass_not_verified(self) -> None:
        builtin = audit_builtin_soko_oracles()
        self.assertEqual(builtin["epistemic_status"], "LINT_PASS")
        self.assertEqual(builtin["verdict"], "PASS")

        single = audit_dual_checkers("def check(x: int) -> bool:\n    return x == 3\n")
        self.assertEqual(single["epistemic_status"], "LINT_PASS")
        self.assertEqual(single["verdict"], "PASS")

        # Promoting a static lint report to VERIFIED must fail closed as a tier swap:
        promoted_lint = _resign({**builtin, "epistemic_status": "VERIFIED", "must_fail_controls": ["dummy_ctrl"]})
        gate = verify_certificate_gate(promoted_lint)
        self.assertFalse(gate["passed"])
        self.assertEqual(gate["epistemic_status"], "REJECTED_TIER_SWAP")

    def test_all_live_certificates_carry_must_fail_controls_and_pass_gate(self) -> None:
        i1 = FRONTIER_ROOMS["I-1"]
        route_cert = verify_route_dual(i1["part"], i1["grid"], i1["reference_route"])
        self.assertEqual(route_cert["epistemic_status"], "VERIFIED")
        self.assertGreaterEqual(len(route_cert["must_fail_controls"]), 2)
        self.assertTrue(verify_certificate_gate(route_cert)["passed"])

        for slug in ("iii-14", "iii-20"):
            tmod = _load_track_verifier(slug)
            tcert = tmod.verify_candidate()
            self.assertEqual(tcert["epistemic_status"], "VERIFIED")
            self.assertIn("truncated_reference_prefix", tcert["must_fail_controls"])
            self.assertIn("extra_key_after_win", tcert["must_fail_controls"])
            self.assertTrue(verify_certificate_gate(tcert)["passed"])

        if ensure_cpp_engine() is not None:
            exact_floor = prove_floor_verified(i1["part"], i1["grid"], max_bound=12, budget_sec=30)
            self.assertEqual(exact_floor["epistemic_status"], "VERIFIED")
            self.assertTrue(verify_certificate_gate(exact_floor)["passed"])

            # Detour of length 11 on I-1 shortened back to 9 via deterministic window shortcut:
            opt_cert = optimize_route_verified(i1["part"], i1["grid"], "DRRRRRRRRRU", beam_width=2000, window_len=12, budget_sec=0, max_states=50000)
            self.assertEqual(opt_cert["epistemic_status"], "VERIFIED")
            self.assertEqual(opt_cert["best_len"], 9)
            self.assertIn("seed_already_at_improved_len", opt_cert["must_fail_controls"])
            self.assertTrue(verify_certificate_gate(opt_cert)["passed"])

            solved_cert = solve_room_verified(i1["part"], i1["grid"], max_depth=15, beam_width=2000, budget_sec=30)
            self.assertEqual(solved_cert["epistemic_status"], "VERIFIED")
            self.assertTrue(verify_certificate_gate(solved_cert)["passed"])

    def test_gate_corruptions_tier_swap_missing_controls_and_hash_tamper(self) -> None:
        i1 = FRONTIER_ROOMS["I-1"]
        base_route = verify_route_dual(i1["part"], i1["grid"], i1["reference_route"])
        self.assertTrue(verify_certificate_gate(base_route)["passed"])

        # Corruption 1: Tampered payload without updating certificate_sha256
        tampered_hash = copy.deepcopy(base_route)
        tampered_hash["route_len"] = 8
        g_hash = verify_certificate_gate(tampered_hash)
        self.assertFalse(g_hash["passed"])
        self.assertEqual(g_hash["epistemic_status"], "REJECTED_CERTIFICATE_HASH_MISMATCH")

        # Corruption 2: Empty, missing, or duplicate must_fail_controls
        for bad_controls in ([], None, [""], ["dup", "dup"]):
            corrupted = copy.deepcopy(base_route)
            if bad_controls is None:
                corrupted.pop("must_fail_controls", None)
            else:
                corrupted["must_fail_controls"] = bad_controls
            corrupted = _resign(corrupted)
            g_ctrl = verify_certificate_gate(corrupted)
            self.assertFalse(g_ctrl["passed"])
            self.assertEqual(g_ctrl["epistemic_status"], "REJECTED_MISSING_MUST_FAIL_CONTROLS")

        # Corruption 3: Tier swap — promoting LOWER_BOUND_UNWITNESSED / LOWER_BOUND to VERIFIED
        if ensure_cpp_engine() is not None:
            r20 = FRONTIER_ROOMS["III-20"]
            lb_cert = prove_floor_verified(3, r20["grid"], max_bound=12, budget_sec=30)
            self.assertEqual(lb_cert["epistemic_status"], "LOWER_BOUND_UNWITNESSED")
            self.assertTrue(verify_certificate_gate(lb_cert)["passed"])

            tier_swapped_floor = _resign({**lb_cert, "epistemic_status": "VERIFIED"})
            g_swap = verify_certificate_gate(tier_swapped_floor)
            self.assertFalse(g_swap["passed"])
            self.assertEqual(g_swap["epistemic_status"], "REJECTED_TIER_SWAP")

        # Synthetic LOWER_BOUND record promoted to VERIFIED (even when resigned):
        synthetic_lb = _resign({
            "epistemic_status": "VERIFIED",
            "claim_kind": "lower_bound",
            "proven_floor": 44,
            "exact_optimum_reached": False,
            "optimality_proven": False,
            "winning_witness": None,
            "must_fail_controls": ["unwitnessed_bound_promoted_to_verified"],
        })
        g_syn = verify_certificate_gate(synthetic_lb)
        self.assertFalse(g_syn["passed"])
        self.assertEqual(g_syn["epistemic_status"], "REJECTED_TIER_SWAP")

        # Formal lower-bound certificate promoted from PROVEN/LOWER_BOUND to VERIFIED without primal witness:
        formal_lb_swap = _resign({
            "epistemic_status": "VERIFIED",
            "certificate_kind": "QUOTIENT_HOMOMORPHISM_LOWER_BOUND",
            "certified_lower_bound": 14,
            "complete_domain_closed": True,
            "must_fail_controls": ["incomplete_concrete_graph_rejected"],
        })
        g_flb = verify_certificate_gate(formal_lb_swap)
        self.assertFalse(g_flb["passed"])
        self.assertEqual(g_flb["epistemic_status"], "REJECTED_TIER_SWAP")

        # Bounded subgraph certificate promoted to PROVEN:
        bounded_to_proven = _resign({
            "epistemic_status": "PROVEN",
            "certificate_kind": "HOUDINI_INDUCTIVE_SAFETY_INVARIANT",
            "complete_domain_closed": False,
            "must_fail_controls": ["non_inductive_conjuncts_pruned"],
        })
        g_b2p = verify_certificate_gate(bounded_to_proven)
        self.assertFalse(g_b2p["passed"])
        self.assertEqual(g_b2p["epistemic_status"], "REJECTED_TIER_SWAP")


if __name__ == "__main__":
    unittest.main()
