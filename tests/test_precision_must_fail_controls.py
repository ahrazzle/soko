"""One-millionth precision must-fail controls for the exact certificate checkers.

Each control is a certificate that is valid except for one change of 1/1,000,000
(or one silently dropped state). The checker must reject it. Each unperturbed
certificate is also checked, so a rejection cannot come from a broken fixture.

Covered: `cost_partitioned_quotients`, `rational_lp_dual` and `inductive_potential`
in `soko_mcp.formal_kernel`, the `universe_code` closure check, and the exact
assignment dual checker in `experiments/landmark_dual_bounds`.
"""
from __future__ import annotations

import dataclasses
import sys
import unittest
from fractions import Fraction
from pathlib import Path

from soko_mcp import formal_kernel as fk
from tests.test_v04_foundation0_synthesis import DUAL_RESOURCE_IMPL, DUAL_RESOURCE_SPEC

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "experiments") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "experiments"))

from landmark_dual_bounds import hero_assignment_bounds as hab  # noqa: E402

EPS = "Fraction(1, 1000000)"
SYSTEM = "precision_must_fail_controls"

COST_PARTITION = '''
def p1(s): return (s[0], s[2])
def w1(s, a, ns):
    if a == "WORK_R1": return 3
    if a == "WORK_R2": return 0
    if a == "JOINT_BOOST": return Fraction(5, 2)
    return 1
def p2(s): return (s[1], s[2])
def w2(s, a, ns):
    if a == "WORK_R1": return 0
    if a == "WORK_R2": return 4
    if a == "JOINT_BOOST": return Fraction(7, 2)
    return 1
def projections(): return (("q1", p1, w1), ("q2", p2, w2))
'''

LP_DUAL = '''
def features(s): return (s[0], s[1], 1 if s[2] else 0)
def goal_rhs(): return (4, 3, 1)
def dual_y(): return (Fraction(5, 2), Fraction(7, 2), 2)
'''

POTENTIAL = "Fraction(5,2)*(4-s[0]) + Fraction(7,2)*(3-s[1]) + 2*(0 if s[2] else 1)"

FULL_UNIVERSE = (
    "def enumerate_states():\n"
    "    return [(a, b, False) for a in range(5) for b in range(4)] + [(4, 3, True)]\n"
)
UNIVERSE_DROPS_STATE = (
    "def enumerate_states():\n"
    "    out = [(a, b, False) for a in range(5) for b in range(4)] + [(4, 3, True)]\n"
    "    return [s for s in out if s != (2, 2, False)]\n"
)


def potential_code(extra: str = "") -> str:
    return f"def potential(s):\n    return {POTENTIAL}{extra}\n"


class FormalKernelPrecisionControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = fk.define_formal_system(
            SYSTEM,
            DUAL_RESOURCE_SPEC,
            DUAL_RESOURCE_IMPL,
            "precision must-fail controls",
            positive_witnesses=[
                {"name": "opt", "trace": ["JOINT_BOOST"] * 3 + ["WORK_R1", "FINAL_LOCK"], "expect_goal": True}
            ],
            must_fail_controls=[
                {"name": "no_lock", "trace": ["JOINT_BOOST"] * 3 + ["WORK_R1"]},
                {"name": "early_lock", "trace": ["JOINT_BOOST", "FINAL_LOCK"]},
            ],
        )
        if not result.get("tcb_locked"):
            raise RuntimeError(f"fixture system did not lock: {result}")

    def status(self, mode, code, bound, **kwargs):
        return fk.certify_formal_lower_bound(SYSTEM, mode, code, bound, **kwargs)["epistemic_status"]

    def test_unperturbed_certificates_are_proven(self):
        self.assertEqual(self.status("cost_partitioned_quotients", COST_PARTITION, 23), "PROVEN")
        self.assertEqual(self.status("rational_lp_dual", LP_DUAL, 23), "PROVEN")
        self.assertEqual(self.status("inductive_potential", potential_code(), 22), "PROVEN")
        self.assertEqual(
            self.status("cost_partitioned_quotients", COST_PARTITION, 23, universe_code=FULL_UNIVERSE),
            "PROVEN",
        )

    def test_cost_partition_overspent_by_one_millionth(self):
        # JOINT_BOOST: 5/2 + 7/2 + 1/1e6 exceeds its cost of 6.
        over_joint = COST_PARTITION.replace("Fraction(7, 2)", f"Fraction(7, 2) + {EPS}")
        self.assertEqual(
            self.status("cost_partitioned_quotients", over_joint, 23), "REJECTED_COST_PARTITION_OVERFLOW"
        )
        # WORK_R1: 3 + 1/1e6 exceeds its cost of 3.
        over_work = COST_PARTITION.replace("return 3\n", f"return 3 + {EPS}\n", 1)
        self.assertIn(f"return 3 + {EPS}", over_work)
        self.assertEqual(
            self.status("cost_partitioned_quotients", over_work, 23), "REJECTED_COST_PARTITION_OVERFLOW"
        )

    def test_lp_dual_infeasible_by_one_millionth(self):
        for old, new in (
            ("Fraction(7, 2)", f"Fraction(7, 2) + {EPS}"),
            ("Fraction(7, 2), 2)", f"Fraction(7, 2), 2 + {EPS})"),
        ):
            code = LP_DUAL.replace(old, new, 1)
            self.assertNotEqual(code, LP_DUAL)
            self.assertEqual(self.status("rational_lp_dual", code, 23), "REJECTED_DUAL_OPERATOR_INFEASIBLE")

    def test_inductive_potential_off_by_one_millionth(self):
        for state in ("(1, 1, False)", "(0, 0, False)"):
            code = potential_code(f" + ({EPS} if s == {state} else 0)")
            self.assertEqual(
                self.status("inductive_potential", code, 22), "REJECTED_STEP_CONSISTENCY_VIOLATION", state
            )

    def test_universe_that_drops_a_state_is_rejected(self):
        self.assertEqual(
            self.status("cost_partitioned_quotients", COST_PARTITION, 23, universe_code=UNIVERSE_DROPS_STATE),
            "REJECTED_DOMAIN_NOT_INDUCTIVELY_CLOSED",
        )


class HeroAssignmentDualPrecisionControls(unittest.TestCase):
    COST = [[4, 2, 8], [4, 3, 7], [3, 1, 6]]

    def setUp(self):
        self.cert = hab.solve_exact_bipartite_assignment(self.COST)
        self.eps = Fraction(1, 1000000)

    def test_unperturbed_dual_is_valid(self):
        self.assertTrue(hab.verify_bipartite_assignment_dual(self.COST, self.cert)["valid"])

    def test_sum_preserving_shift_breaks_feasibility_only(self):
        # Raise u[0] and lower one v[k] by the same 1/1e6. The dual objective and the
        # primal cost are unchanged, so only the edge feasibility check can reject it.
        k = next(j for j in range(3) if j != self.cert.assignment[0])
        dual_u = (self.cert.dual_u[0] + self.eps,) + self.cert.dual_u[1:]
        dual_v = tuple(x - self.eps if j == k else x for j, x in enumerate(self.cert.dual_v))
        bad = dataclasses.replace(self.cert, dual_u=dual_u, dual_v=dual_v)
        self.assertEqual(sum(bad.dual_u) + sum(bad.dual_v), self.cert.dual_objective)
        verdict = hab.verify_bipartite_assignment_dual(self.COST, bad)
        self.assertFalse(verdict["valid"])
        self.assertTrue(verdict["reason"].startswith("dual_infeasible_at_0_"), verdict)


if __name__ == "__main__":
    unittest.main()
