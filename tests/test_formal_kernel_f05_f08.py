"""Regression tests for F-05 through F-08 formal_kernel soundness fixes.

Covers the four open certificate/ledger boundary defects documented in the
2026-11-12 formal-systems experience report:
- F-05: Truncated `inductive_potential` lower bounds (`max_concrete_states` <
  reachable graph) must fail closed rather than certifying false bounds above
  the true shortest-path cost.
- F-06: `PROVEN` certificates in `solve_formal_system`,
  `certify_formal_lower_bound`, and `synthesize_formal_invariant` (both
  `formal_kernel` and `invariant_synth`, under reachable BFS and explicit
  `universe_code`) must enforce full `SPEC`/`IMPL` parity (`project_obs`,
  `invariant`, `is_goal`, `actions`, survival, `step_cost`), including when
  `project_obs` is coarse or `SPEC` collapses distinct `IMPL` trajectories.
- F-07: `triage_formal_portfolio` must not stamp `VERIFIED` on unverified
  caller-supplied floor integers and must reject contradictory bounds.
- F-08: `export_formal_ledger` must enforce 64-hex SHA-256 digests and bind
  `VERIFIED` / `PROVEN` external claims to registered kernel artifacts.
"""
from __future__ import annotations

import unittest

from soko_mcp import formal_kernel, invariant_synth
from soko_mcp.formal_kernel import (
    FORMAL_REGISTRY,
    certify_formal_lower_bound,
    define_formal_system,
    export_formal_ledger,
    solve_formal_system,
    triage_formal_portfolio,
    verify_formal_trace,
)


class F05TruncatedPotentialTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sys_id = "f05_jump_chain_20"
        FORMAL_REGISTRY.pop(self.sys_id, None)
        spec_code = """
def initial_state():
    return 0

def actions(s):
    return ("step",) if s < 20 else ()

def step(s, a):
    return 20 if s == 10 else s + 1

def is_goal(s):
    return s == 20

def step_cost(s, a, ns):
    return 0 if s == 10 else 1
"""
        impl_code = """
def initial_state():
    return (0,)

def actions(s):
    return () if s[0] >= 20 else ("step",)

def step(s, a):
    return (20,) if s[0] == 10 else (s[0] + 1,)

def is_goal(s):
    return s[0] == 20

def step_cost(s, a, ns):
    return 0 if s[0] == 10 else 1

def project_obs(s):
    return s[0]
"""
        reg = define_formal_system(
            self.sys_id,
            spec_code=spec_code,
            impl_code=impl_code,
            must_fail_controls=[{"name": "one_step_not_goal", "trace": ["step"]}],
            bounded_fuzz_nodes=25,
        )
        self.assertEqual(reg["epistemic_status"], "VERIFIED")

    def test_truncated_inductive_potential_fails_closed(self) -> None:
        opt = solve_formal_system(self.sys_id, mode="reach_goal", strategy="exact_dijkstra")
        self.assertEqual(opt["epistemic_status"], "PROVEN")
        self.assertEqual(opt["optimal_cost"], 10)

        false_potential = "def potential(s):\n    return 20 - s\n"
        truncated = certify_formal_lower_bound(
            self.sys_id,
            proof_mode="inductive_potential",
            certificate_code=false_potential,
            claimed_lower_bound=15,
            max_concrete_states=6,
        )
        self.assertEqual(truncated["epistemic_status"], "REJECTED_INCOMPLETE_CONCRETE_GRAPH_FOR_POTENTIAL")
        self.assertIsNone(truncated["certified_lower_bound"])
        self.assertFalse(truncated["complete_domain_closed"])

        full_false = certify_formal_lower_bound(
            self.sys_id,
            proof_mode="inductive_potential",
            certificate_code=false_potential,
            claimed_lower_bound=15,
            max_concrete_states=25,
        )
        self.assertEqual(full_false["epistemic_status"], "REJECTED_STEP_CONSISTENCY_VIOLATION")

        sound_potential = "def potential(s):\n    return 0 if s >= 10 else 10 - s\n"
        full_sound = certify_formal_lower_bound(
            self.sys_id,
            proof_mode="inductive_potential",
            certificate_code=sound_potential,
            claimed_lower_bound=10,
            max_concrete_states=25,
        )
        self.assertEqual(full_sound["epistemic_status"], "PROVEN")
        self.assertEqual(full_sound["certified_lower_bound"], 10)


class F06DualCheckerParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.inv_sys = "f06_coarse_obs_inv_divergence"
        self.split_sys = "f06_spec_collapse_impl_split"
        FORMAL_REGISTRY.pop(self.inv_sys, None)
        FORMAL_REGISTRY.pop(self.split_sys, None)

        spec_inv = """
def initial_state():
    return 0

def actions(s):
    return ("inc",) if s < 3 else ()

def step(s, a):
    return s + 1

def is_goal(s):
    return False

def invariant(s):
    return True

def project_obs(s):
    return 0
"""
        impl_inv = """
def initial_state():
    return (0, True)

def actions(s):
    return () if s[0] >= 3 else ("inc",)

def step(s, a):
    return (s[0] + 1, s[0] + 1 < 2)

def is_goal(s):
    return False

def invariant(s):
    return s[1]

def project_obs(s):
    return 0
"""
        reg = define_formal_system(
            self.inv_sys,
            spec_code=spec_inv,
            impl_code=impl_inv,
            must_fail_controls=[{"name": "no_goal_step", "trace": ["inc"]}],
            bounded_fuzz_nodes=1,
        )
        self.assertTrue(reg["tcb_locked"])

    def test_dijkstra_lower_bound_and_houdini_reject_impl_invariant_divergence(self) -> None:
        sol = solve_formal_system(
            self.inv_sys,
            mode="find_invariant_violation",
            strategy="exact_dijkstra",
        )
        self.assertEqual(sol["epistemic_status"], "REJECTED_DIFFERENTIAL_MISMATCH")

        lb_bfs = certify_formal_lower_bound(
            self.inv_sys,
            proof_mode="inductive_potential",
            certificate_code="def potential(s):\n    return 0\n",
            claimed_lower_bound=0,
        )
        self.assertEqual(lb_bfs["epistemic_status"], "REJECTED_DIFFERENTIAL_MISMATCH")

        universe = "def enumerate_states():\n    return (0, 1, 2, 3)\n"
        lb_univ = certify_formal_lower_bound(
            self.inv_sys,
            proof_mode="inductive_potential",
            certificate_code="def potential(s):\n    return 0\n",
            claimed_lower_bound=0,
            universe_code=universe,
        )
        self.assertEqual(lb_univ["epistemic_status"], "REJECTED_DIFFERENTIAL_MISMATCH")

        cands = 'def predicates():\n    return {"triv": lambda s: True}\n'
        for mod in (formal_kernel, invariant_synth):
            with self.subTest(module=mod.__name__, scope="reachable"):
                h_bfs = mod.synthesize_formal_invariant(self.inv_sys, cands, synthesis_mode="houdini_safety")
                self.assertEqual(h_bfs["epistemic_status"], "REJECTED_DIFFERENTIAL_MISMATCH")
            with self.subTest(module=mod.__name__, scope="universe"):
                h_univ = mod.synthesize_formal_invariant(
                    self.inv_sys,
                    cands,
                    synthesis_mode="houdini_safety",
                    universe_code=universe,
                )
                self.assertEqual(h_univ["epistemic_status"], "REJECTED_DIFFERENTIAL_MISMATCH")

        proven_certs = [
            c for c in FORMAL_REGISTRY[self.inv_sys].certificates if c.get("epistemic_status") == "PROVEN"
        ]
        self.assertEqual(proven_certs, [])

    def test_spec_collapsed_state_does_not_mask_impl_branch_divergence(self) -> None:
        spec_split = """
def initial_state():
    return 0

def actions(s):
    if s == 0:
        return ("a", "b")
    if s == 1:
        return ("c",)
    return ()

def step(s, act):
    if s == 0:
        return 1
    return 2

def is_goal(s):
    return False

def invariant(s):
    return True

def project_obs(s):
    return s
"""
        impl_split = """
def initial_state():
    return (0, 0)

def actions(s):
    if s[0] == 0:
        return ("a", "b")
    if s[0] == 1:
        return ("c",)
    return ()

def step(s, act):
    if s[0] == 0:
        return (1, 0 if act == "a" else 1)
    return (2, s[1])

def is_goal(s):
    return False

def invariant(s):
    return not (s[0] == 2 and s[1] == 1)

def project_obs(s):
    return s[0]
"""
        reg = define_formal_system(
            self.split_sys,
            spec_code=spec_split,
            impl_code=impl_split,
            must_fail_controls=[{"name": "safe_branch", "trace": ["a", "c"]}],
            bounded_fuzz_nodes=1,
        )
        self.assertTrue(reg["tcb_locked"])

        sol = solve_formal_system(
            self.split_sys,
            mode="find_invariant_violation",
            strategy="exact_dijkstra",
        )
        self.assertEqual(sol["epistemic_status"], "REJECTED_DIFFERENTIAL_MISMATCH")


class F07F08PortfolioAndLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sys_id = "f07_f08_verified_chain"
        FORMAL_REGISTRY.pop(self.sys_id, None)
        spec_code = """
def initial_state():
    return 0

def actions(s):
    return ("r",) if s < 3 else ()

def step(s, a):
    return s + 1

def is_goal(s):
    return s == 3
"""
        impl_code = """
def initial_state():
    return (0,)

def actions(s):
    return () if s[0] >= 3 else ("r",)

def step(s, a):
    return (s[0] + 1,)

def is_goal(s):
    return s[0] == 3

def project_obs(s):
    return s[0]
"""
        define_formal_system(
            self.sys_id,
            spec_code=spec_code,
            impl_code=impl_code,
            positive_witnesses=[{"name": "three_r", "trace": ["r", "r", "r"], "expect_goal": True}],
            must_fail_controls=[{"name": "two_r", "trace": ["r", "r"]}],
            bounded_fuzz_nodes=8,
        )

    def test_triage_portfolio_distinguishes_unverified_and_contradictory_bounds(self) -> None:
        unverified = triage_formal_portfolio(
            [{"id": "UNREGISTERED-ROOM", "proven_floor": 42, "shortest_known": 48, "live_record": 50}]
        )
        self.assertEqual(unverified["epistemic_status"], "UNVERIFIED_CALLER_BOUNDS")
        self.assertFalse(unverified["caller_bounds_verified"])
        self.assertFalse(unverified["ranked_portfolio"][0]["bounds_verified_in_registry"])

        contradictory = triage_formal_portfolio(
            [{"id": "BAD-BOUNDS", "proven_floor": 50, "shortest_known": 48, "live_record": 48}]
        )
        self.assertEqual(contradictory["epistemic_status"], "REJECTED_INCONSISTENT_PORTFOLIO_BOUNDS")

        sol = solve_formal_system(self.sys_id, mode="reach_goal", strategy="exact_dijkstra")
        self.assertEqual(sol["epistemic_status"], "PROVEN")
        verified = triage_formal_portfolio(
            [{"id": self.sys_id, "proven_floor": 3, "shortest_known": 3, "live_record": 3}]
        )
        self.assertEqual(verified["epistemic_status"], "VERIFIED")
        self.assertTrue(verified["caller_bounds_verified"])
        self.assertTrue(verified["ranked_portfolio"][0]["bounds_verified_in_registry"])

    def test_export_ledger_enforces_64_hex_sha256_and_registry_binding(self) -> None:
        with self.assertRaises(ValueError):
            export_formal_ledger(
                [{"claim_id": "short-hash", "epistemic_status": "VERIFIED", "witness_or_proof_sha256": "ab"}]
            )

        with self.assertRaises(ValueError):
            export_formal_ledger(
                [{"claim_id": "unregistered-64", "epistemic_status": "VERIFIED", "witness_or_proof_sha256": "0" * 64}]
            )

        tr = verify_formal_trace(self.sys_id, ["r", "r", "r"], verification_goal="goal_witness")
        tr_sha = tr["transcript_sha256"]

        with self.assertRaises(ValueError):
            export_formal_ledger(
                [{"claim_id": "trace-not-proven", "epistemic_status": "PROVEN", "witness_or_proof_sha256": tr_sha}]
            )

        led_ver = export_formal_ledger(
            [
                {"claim_id": "trace-verified", "epistemic_status": "VERIFIED", "witness_or_proof_sha256": tr_sha},
                {"claim_id": "ext-known", "epistemic_status": "KNOWN", "witness_or_proof_sha256": "f" * 64},
            ]
        )
        self.assertEqual(len(led_ver["external_claims"]), 2)
        self.assertEqual(led_ver["external_claims"][0]["epistemic_status"], "VERIFIED")

        cert_lb = certify_formal_lower_bound(
            self.sys_id,
            proof_mode="inductive_potential",
            certificate_code="def potential(s):\n    return 3 - s\n",
            claimed_lower_bound=3,
        )
        cert_sha = cert_lb["checker_pins"]["certificate_sha256"]
        led_prov = export_formal_ledger(
            [{"claim_id": "lb-proven", "epistemic_status": "PROVEN", "witness_or_proof_sha256": cert_sha}]
        )
        self.assertEqual(led_prov["external_claims"][0]["epistemic_status"], "PROVEN")


if __name__ == "__main__":
    unittest.main()
