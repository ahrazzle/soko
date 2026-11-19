"""End-to-end verification tests for v0.4.0 Two-Way Foundation-0 Synthesis upgrades."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import unittest

from soko_mcp.engine_bridge import get_capabilities, prove_floor_verified, verify_tcb_lock
from soko_mcp.oracle import FRONTIER_ROOMS
from soko_mcp.server import dispatch_tool_call

REPO_ROOT = Path(__file__).resolve().parent.parent


# Coupled two-resource pipeline system where pointwise single-resource Quotient `max` is strictly weaker
# than `Foundation-0/gfq-codes` Exact Rational Cost-Partitioned Quotients and Operator-Counting LP Dual!
DUAL_RESOURCE_SPEC = """
def initial_state():
    # (r1_done: 0..4, r2_done: 0..3, sync_locked: bool)
    return (0, 0, False)

def actions(s):
    r1, r2, locked = s
    acts = []
    if not locked:
        if r1 < 4:
            acts.append("WORK_R1")
        if r2 < 3:
            acts.append("WORK_R2")
        if r1 < 4 and r2 < 3:
            acts.append("JOINT_BOOST")
        if r1 == 4 and r2 == 3:
            acts.append("FINAL_LOCK")
    return tuple(acts)

def step(s, a):
    r1, r2, locked = s
    if a == "WORK_R1" and not locked and r1 < 4:
        return (r1 + 1, r2, False)
    if a == "WORK_R2" and not locked and r2 < 3:
        return (r1, r2 + 1, False)
    if a == "JOINT_BOOST" and not locked and r1 < 4 and r2 < 3:
        return (r1 + 1, r2 + 1, False)
    if a == "FINAL_LOCK" and not locked and r1 == 4 and r2 == 3:
        return (4, 3, True)
    return None

def step_cost(s, a, ns):
    if a == "WORK_R1":
        return 3
    if a == "WORK_R2":
        return 4
    if a == "JOINT_BOOST":
        return 6
    if a == "FINAL_LOCK":
        return 2
    return 1

def is_goal(s):
    return s == (4, 3, True)

def project_obs(s):
    return s
"""

# Independent bit-packed integer implementation (distinct alpha-normalized AST skeleton!)
DUAL_RESOURCE_IMPL = """
def initial_state():
    return 0

def actions(code):
    c1 = code & 7
    c2 = (code >> 3) & 7
    lk = (code >> 6) & 1
    if lk == 1:
        return ()
    out = []
    if c1 <= 3:
        out.append("WORK_R1")
    if c2 <= 2:
        out.append("WORK_R2")
    if c1 <= 3 and c2 <= 2:
        out.append("JOINT_BOOST")
    if c1 == 4 and c2 == 3:
        out.append("FINAL_LOCK")
    return tuple(out)

def step(code, op):
    c1 = code & 7
    c2 = (code >> 3) & 7
    lk = (code >> 6) & 1
    if lk != 0:
        return None
    if op == "WORK_R1" and c1 <= 3:
        return (c1 + 1) | (c2 << 3)
    if op == "WORK_R2" and c2 <= 2:
        return c1 | ((c2 + 1) << 3)
    if op == "JOINT_BOOST" and c1 <= 3 and c2 <= 2:
        return (c1 + 1) | ((c2 + 1) << 3)
    if op == "FINAL_LOCK" and c1 == 4 and c2 == 3:
        return 4 | (3 << 3) | (1 << 6)
    return None

def step_cost(code, op, nxt):
    costs = {"WORK_R1": 3, "WORK_R2": 4, "JOINT_BOOST": 6, "FINAL_LOCK": 2}
    return costs[op]

def is_goal(code):
    return code == (4 | (3 << 3) | (1 << 6))

def project_obs(code):
    return (code & 7, (code >> 3) & 7, bool((code >> 6) & 1))
"""


class Foundation0SynthesisV04Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        reg = dispatch_tool_call(
            "formal_define_system",
            {
                "system_id": "f0_dual_resource_v04",
                "description": "Two-resource pipeline with coupled JOINT_BOOST action testing rational cost partitioning & LP duals.",
                "spec_code": DUAL_RESOURCE_SPEC,
                "impl_code": DUAL_RESOURCE_IMPL,
                "positive_witnesses": [
                    {
                        "name": "opt_23_witness",
                        "trace": ["JOINT_BOOST", "JOINT_BOOST", "JOINT_BOOST", "WORK_R1", "FINAL_LOCK"],
                        "expect_goal": True,
                    }
                ],
                "must_fail_controls": [
                    {"name": "missing_lock", "trace": ["JOINT_BOOST", "JOINT_BOOST", "JOINT_BOOST", "WORK_R1"]},
                    {"name": "premature_lock", "trace": ["JOINT_BOOST", "FINAL_LOCK"]},
                ],
            },
        )
        assert reg["epistemic_status"] == "VERIFIED" and reg["tcb_locked"], reg

    def test_01_capabilities_and_17_tools_v040(self) -> None:
        caps = get_capabilities()
        self.assertEqual(caps["version"], "0.4.0")
        self.assertIn("formal_audit_checkers", caps["formal_systems"]["tools"])
        if caps["cpp_engine_ready"]:
            # RowStripQuotientPDB lives only in the standalone III-14 prover, not in cpp/soko_engine.cpp.
            self.assertNotIn("RowStripQuotientPDB", caps["lower_bound_proving"]["abstractions"])

    def test_02_gfq_codes_cost_partitioned_quotients_beats_pointwise_max(self) -> None:
        # Optimal cost is 3*6 + 3 + 2 = 23.
        # Single-resource Quotient 1 (projecting only r1, locked) gets only 4*3 + 2 = 14 (or with JOINT_BOOST=6, min(3,6)*4=12+2=14).
        # Single-resource Quotient 2 (projecting only r2, locked) gets only 3*4 + 2 = 14.
        # Pointwise max(14, 14) = 14 < 23!
        # With exact rational cost-partitioning:
        #   w1: WORK_R1 -> 3, WORK_R2 -> 0, JOINT_BOOST -> Fraction(5, 2), FINAL_LOCK -> 1
        #   w2: WORK_R1 -> 0, WORK_R2 -> 4, JOINT_BOOST -> Fraction(7, 2), FINAL_LOCK -> 1
        # Note w1 + w2 == step_cost on every action!
        # Quotient 1 exact shortest path = 3*(5/2) + 3 + 1 = 23/2
        # Quotient 2 exact shortest path = 3*(7/2) + 1     = 23/2
        # Sum = 23/2 + 23/2 = 23 -> PROVEN exact optimum LB == UB == 23!
        q1_single = dispatch_tool_call(
            "formal_certify_lower_bound",
            {
                "system_id": "f0_dual_resource_v04",
                "proof_mode": "quotient_homomorphism",
                "certificate_code": "def project(s):\n    return (s[0], s[2])\n",
                "claimed_lower_bound": 14,
            },
        )
        self.assertEqual(q1_single["epistemic_status"], "PROVEN")
        self.assertEqual(q1_single["quotient_exact_bound"], 14)

        cp_cert_code = """
def p1(s):
    return (s[0], s[2])

def w1(s, a, ns):
    if a == "WORK_R1":
        return 3
    if a == "WORK_R2":
        return 0
    if a == "JOINT_BOOST":
        return Fraction(5, 2)
    return 1

def p2(s):
    return (s[1], s[2])

def w2(s, a, ns):
    if a == "WORK_R1":
        return 0
    if a == "WORK_R2":
        return 4
    if a == "JOINT_BOOST":
        return Fraction(7, 2)
    return 1

def projections():
    return (("r1_quotient", p1, w1), ("r2_quotient", p2, w2))
"""
        cp_res = dispatch_tool_call(
            "formal_certify_lower_bound",
            {
                "system_id": "f0_dual_resource_v04",
                "proof_mode": "cost_partitioned_quotients",
                "certificate_code": cp_cert_code,
                "claimed_lower_bound": 23,
            },
        )
        self.assertEqual(cp_res["epistemic_status"], "PROVEN")
        self.assertEqual(cp_res["ceil_integer_bound"], 23)
        self.assertEqual(cp_res["exact_rational_sum"], "45/2")

        # Negative control: overflowing partition weights (w1 + w2 > step_cost) MUST fail closed!
        bad_cp = cp_cert_code.replace("Fraction(7, 2)", "Fraction(8, 2)")
        bad_res = dispatch_tool_call(
            "formal_certify_lower_bound",
            {
                "system_id": "f0_dual_resource_v04",
                "proof_mode": "cost_partitioned_quotients",
                "certificate_code": bad_cp,
                "claimed_lower_bound": 23,
            },
        )
        self.assertEqual(bad_res["epistemic_status"], "REJECTED_COST_PARTITION_OVERFLOW")

    def test_03_gfq_codes_rational_lp_dual_farkas_certificate_and_rejection(self) -> None:
        # Exact Farkas state-equation dual multipliers y = (Fraction(5, 2), Fraction(7, 2), 2)
        # Check operator gains y^T (F(ns) - F(s)):
        #   WORK_R1:     5/2 <= 3
        #   WORK_R2:     7/2 <= 4
        #   JOINT_BOOST: 5/2 + 7/2 = 6 <= 6
        #   FINAL_LOCK:  2 <= 2
        # Initial objective y^T (b - F(s0)) = (5/2)*4 + (7/2)*3 + 2*1 = 10 + 21/2 + 2 = 45/2 -> ceil(45/2) = 23!
        lp_code = """
def features(s):
    return (s[0], s[1], 1 if s[2] else 0)

def goal_rhs():
    return (4, 3, 1)

def dual_y():
    return (Fraction(5, 2), Fraction(7, 2), 2)
"""
        lp_res = dispatch_tool_call(
            "formal_certify_lower_bound",
            {
                "system_id": "f0_dual_resource_v04",
                "proof_mode": "rational_lp_dual",
                "certificate_code": lp_code,
                "claimed_lower_bound": 23,
            },
        )
        self.assertEqual(lp_res["epistemic_status"], "PROVEN")
        self.assertEqual(lp_res["exact_dual_objective"], "45/2")
        self.assertEqual(lp_res["ceil_integer_bound"], 23)

        # Dual multiplier violating JOINT_BOOST (3 + 4 = 7 > 6) MUST be rejected!
        bad_lp = lp_code.replace("Fraction(5, 2), Fraction(7, 2)", "3, 4")
        bad_res = dispatch_tool_call(
            "formal_certify_lower_bound",
            {
                "system_id": "f0_dual_resource_v04",
                "proof_mode": "rational_lp_dual",
                "certificate_code": bad_lp,
                "claimed_lower_bound": 23,
            },
        )
        self.assertEqual(bad_res["epistemic_status"], "REJECTED_DUAL_OPERATOR_INFEASIBLE")

        # A truncated concrete graph has unindexed successors; it must be rejected, not raise KeyError.
        trunc_res = dispatch_tool_call(
            "formal_certify_lower_bound",
            {
                "system_id": "f0_dual_resource_v04",
                "proof_mode": "rational_lp_dual",
                "certificate_code": lp_code,
                "claimed_lower_bound": 23,
                "max_concrete_states": 6,
            },
        )
        self.assertEqual(trunc_res["epistemic_status"], "REJECTED_INCOMPLETE_CONCRETE_GRAPH_FOR_QUOTIENT")

    def test_04_formal_audit_checkers_self_audit_and_hazard_detection(self) -> None:
        # 1. Built-in self-audit of oracle.py vs flat_oracle.py
        builtin_rep = dispatch_tool_call("formal_audit_checkers", {"builtin_soko_oracles": True})
        self.assertEqual(builtin_rep["epistemic_status"], "VERIFIED")
        self.assertEqual(builtin_rep["verdict"], "PASS")
        self.assertTrue(builtin_rep["distinct_alpha_skeleton"])

        # 2. Catches alpha-renamed copy-paste tautology + F-01 optimistic True
        taut_rep = dispatch_tool_call(
            "formal_audit_checkers",
            {
                "spec_code": "def check(s, a):\n    ok = True\n    if a > 0:\n        ok = (s == a)\n    return ok\n",
                "impl_code": "def verify(st, mv):\n    ok = True\n    if mv > 0:\n        ok = (st == mv)\n    return ok\n",
            },
        )
        self.assertEqual(taut_rep["verdict"], "FAIL")
        self.assertFalse(taut_rep["distinct_alpha_skeleton"])
        rules = {f["rule"] for f in taut_rep["spec_audit"]["findings"]}
        self.assertIn("OPTIMISTIC_TRUE_DEFAULT_F01", rules)

    def test_05_incentre_lattices_tracks_and_iii20_multicore_exact_astar(self) -> None:
        for track in ("iii-14", "iii-20"):
            script = REPO_ROOT / "tracks" / track / "verify.py"
            self.assertTrue(script.is_file())
            proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=30, check=True)
            self.assertIn('"epistemic_status": "VERIFIED"', proc.stdout)

        caps = get_capabilities()
        if caps["cpp_engine_ready"]:
            r20 = FRONTIER_ROOMS["III-20"]
            pf20 = prove_floor_verified(3, r20["grid"], max_bound=30, budget_sec=4)
            self.assertEqual(pf20["epistemic_status"], "LOWER_BOUND_UNWITNESSED")
            self.assertEqual(pf20["search_strategy"], "multicore_exact_bucketed_astar")
            self.assertGreaterEqual(pf20["proven_floor"], 18)

        tcb = verify_tcb_lock()
        self.assertEqual(tcb["epistemic_status"], "VERIFIED")
        self.assertTrue(tcb["tcb_locked"])


if __name__ == "__main__":
    unittest.main()
