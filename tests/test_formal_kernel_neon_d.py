"""Regression tests for cross-model audit findings NEON-D1, NEON-D2 and NEON-D4 in formal_kernel.

- D1: under exact_arithmetic_only=True, `2 ** -1` produced a float, a NaN potential slipped
  through every `>` comparison, and `inductive_potential` returned PROVEN for OPT >= 10**18 on a
  system whose optimum is 1. Negative or non-literal exponents and float-producing builtins are
  now rejected statically, and every potential value must be an exact int or Fraction at runtime.
- D2: `exact_dijkstra` with a small `max_states` dropped the cheap branch and reported a cost-100
  goal as PROVEN optimal when the optimum is 2. A popped goal is now PROVEN only when no state
  dropped by the state budget could reach it more cheaply.
- D4: a constant `project_obs` deduplicated away a successor whose IMPL invariant disagreed with
  SPEC, so the system locked. Every edge now checks successor invariant and action-set parity.
  The quotient lower bound used a finite `INF = 10**15` sentinel and reported a reachable goal at
  cost 10**15 as UNREACHABLE_INF; unreachable states are now absent from the distance table.
"""
from __future__ import annotations

import unittest
from fractions import Fraction

from soko_mcp.formal_kernel import (
    FORMAL_REGISTRY,
    certify_formal_lower_bound,
    define_formal_system,
    solve_formal_system,
    validate_pure_ast,
)

ONE_STEP_SPEC = """
def initial_state(): return 0
def actions(s): return ('go',) if s == 0 else ()
def step(s, a): return 1 if (s == 0 and a == 'go') else None
def is_goal(s): return s == 1
"""
ONE_STEP_IMPL = """
def initial_state(): return (0,)
def actions(s): return ('go',) if s[0] == 0 else ()
def step(s, a):
    if s[0] == 0 and a == 'go':
        return (1,)
    return None
def is_goal(s): return s[0] == 1
def project_obs(s): return s[0]
"""


def _define(sid: str, spec: str, impl: str, trace, must_fail) -> dict:
    FORMAL_REGISTRY.pop(sid, None)
    return define_formal_system(
        sid,
        spec,
        impl,
        positive_witnesses=[{"name": "w", "trace": trace, "expect_goal": True}],
        must_fail_controls=[{"name": "neg", "trace": must_fail}],
        exact_arithmetic_only=True,
        strict_bar=True,
    )


class D1ExactPotentialTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sid = "neon_d1_one_step"
        reg = _define(self.sid, ONE_STEP_SPEC, ONE_STEP_IMPL, ["go"], [])
        self.assertTrue(reg["tcb_locked"], reg)

    def tearDown(self) -> None:
        FORMAL_REGISTRY.pop(self.sid, None)

    def test_negative_exponent_nan_exploit_rejected(self) -> None:
        cert = (
            "def potential(s):\n"
            "    half = 2 ** -1\n"
            "    inf_val = (10 ** 308) * half * 10\n"
            "    nan_val = inf_val - inf_val\n"
            "    if s == 0:\n"
            "        return 10 ** 18\n"
            "    return nan_val\n"
        )
        with self.assertRaises(ValueError):
            certify_formal_lower_bound(self.sid, proof_mode="inductive_potential",
                                       certificate_code=cert, claimed_lower_bound=10 ** 18)

    def test_static_rejections(self) -> None:
        for code in (
            "def f(n): return 2 ** n\n",
            "def f(n): return 2 ** -1\n",
            "def f(n):\n    x = 2\n    x **= -1\n    return x\n",
            "def f(n): return pow(2, -1)\n",
            "def f(n): return float(n)\n",
            "def f(n): return Fraction(2) ** Fraction(1, 2)\n",
            "class FakeInt(int):\n    pass\n",
            "def __gt__(a, b): return False\n",
        ):
            with self.assertRaises(ValueError, msg=code):
                validate_pure_ast(code, "neon_d1", exact_arithmetic_only=True)
        validate_pure_ast("def f(n): return n ** 2 + 10 ** 18\n", "neon_d1_ok", exact_arithmetic_only=True)
        validate_pure_ast("def f(n): return 2 ** n\n", "neon_d1_relaxed", exact_arithmetic_only=False)

    def test_runtime_bool_and_nan_potential_rejected(self) -> None:
        cert_bool = "def potential(s):\n    return True if s == 0 else 0\n"
        with self.assertRaises(TypeError):
            certify_formal_lower_bound(self.sid, proof_mode="inductive_potential",
                                       certificate_code=cert_bool, claimed_lower_bound=1)
        # Even when exact_arithmetic_only=False, NaN/inf potentials must still be rejected at runtime.
        relaxed_id = "neon_d1_relaxed_nan"
        FORMAL_REGISTRY.pop(relaxed_id, None)
        try:
            reg = define_formal_system(
                relaxed_id,
                ONE_STEP_SPEC,
                ONE_STEP_IMPL,
                positive_witnesses=[{"name": "w", "trace": ["go"], "expect_goal": True}],
                must_fail_controls=[{"name": "neg", "trace": []}],
                exact_arithmetic_only=False,
                strict_bar=True,
            )
            self.assertTrue(reg["tcb_locked"], reg)
            cert_nan = (
                "def potential(s):\n"
                "    inf_val = 1e308 * 10.0\n"
                "    return 10 ** 18 if s == 0 else (inf_val - inf_val)\n"
            )
            with self.assertRaises(TypeError):
                certify_formal_lower_bound(relaxed_id, proof_mode="inductive_potential",
                                           certificate_code=cert_nan, claimed_lower_bound=10 ** 18)
        finally:
            FORMAL_REGISTRY.pop(relaxed_id, None)

    def test_float_claim_rejected(self) -> None:
        with self.assertRaises(TypeError):
            certify_formal_lower_bound(self.sid, proof_mode="inductive_potential",
                                       certificate_code="def potential(s):\n    return 0\n",
                                       claimed_lower_bound=float("nan"))  # type: ignore[arg-type]

    def test_honest_potential_still_proven(self) -> None:
        cert = "def potential(s):\n    return Fraction(1, 1) if s == 0 else 0\n"
        res = certify_formal_lower_bound(self.sid, proof_mode="inductive_potential",
                                         certificate_code=cert, claimed_lower_bound=1)
        self.assertEqual(res["epistemic_status"], "PROVEN", res)
        over = certify_formal_lower_bound(self.sid, proof_mode="inductive_potential",
                                          certificate_code="def potential(s):\n    return 2 if s == 0 else 0\n",
                                          claimed_lower_bound=2)
        self.assertNotEqual(over["epistemic_status"], "PROVEN", over)


DIJKSTRA_SPEC = """
def initial_state(): return 'S'
def actions(s):
    if s == 'S': return ('slow', 'dead', 'fast')
    if s == 'F': return ('finish',)
    return ()
def step(s, a):
    if s == 'S' and a == 'slow': return 'G'
    if s == 'S' and a == 'dead': return 'D'
    if s == 'S' and a == 'fast': return 'F'
    if s == 'F' and a == 'finish': return 'G'
    return None
def step_cost(s, a, ns):
    return 100 if a == 'slow' else 1
def is_goal(s): return s == 'G'
"""
DIJKSTRA_IMPL = """
def initial_state(): return 0
def actions(s):
    table = {0: ('slow', 'dead', 'fast'), 2: ('finish',)}
    return table.get(s, ())
def step(s, a):
    trans = {(0, 'slow'): 3, (0, 'dead'): 1, (0, 'fast'): 2, (2, 'finish'): 3}
    return trans.get((s, a), None)
def step_cost(s, a, ns):
    return 100 if (s == 0 and ns == 3) else 1
def is_goal(s): return s == 3
def project_obs(s):
    return ('S', 'D', 'F', 'G')[s]
"""


class D2DijkstraBudgetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sid = "neon_d2_dijkstra"
        reg = _define(self.sid, DIJKSTRA_SPEC, DIJKSTRA_IMPL, ["fast", "finish"], ["dead"])
        self.assertTrue(reg["tcb_locked"], reg)

    def tearDown(self) -> None:
        FORMAL_REGISTRY.pop(self.sid, None)

    def test_state_budget_never_proves_suboptimal_goal(self) -> None:
        res = solve_formal_system(self.sid, mode="reach_goal", strategy="exact_dijkstra", max_states=3)
        self.assertNotEqual(res["epistemic_status"], "PROVEN", res)
        self.assertEqual(res["epistemic_status"], "VERIFIED_FEASIBLE_NOT_PROVEN_OPTIMAL", res)
        self.assertEqual(res["best_found_cost"], 100)
        self.assertEqual(res["unexplored_lower_bound"], 1)
        self.assertIsNone(res["optimal_cost"])

    def test_full_budget_proves_true_optimum(self) -> None:
        res = solve_formal_system(self.sid, mode="reach_goal", strategy="exact_dijkstra", max_states=50)
        self.assertEqual(res["epistemic_status"], "PROVEN", res)
        self.assertEqual(res["optimal_cost"], 2)

    def test_cost_budget_alone_keeps_optimality(self) -> None:
        # max_cost prunes only the cost-100 branch; the cost-2 goal is still provably optimal.
        res = solve_formal_system(self.sid, mode="reach_goal", strategy="exact_dijkstra", max_cost=10)
        self.assertEqual(res["epistemic_status"], "PROVEN", res)
        self.assertEqual(res["optimal_cost"], 2)


class D4ParityAndSentinelTests(unittest.TestCase):
    def tearDown(self) -> None:
        for sid in ("neon_d4_f07", "neon_d4_f07_2step", "neon_d4_inf", "neon_d4_cp_inf", "neon_d4_unreach"):
            FORMAL_REGISTRY.pop(sid, None)

    def test_coarse_obs_cannot_mask_impl_invariant(self) -> None:
        spec = """
def initial_state(): return 0
def actions(s): return ('step', 'win') if s < 2 else ()
def step(s, a):
    if a == 'step' and s == 0: return 1
    if a == 'win' and s == 0: return 2
    return None
def is_goal(s): return s == 2
def invariant(s): return True
def project_obs(s): return 0
"""
        impl = """
def initial_state(): return (0,)
def actions(s):
    if s[0] < 2:
        return ('step', 'win')
    return ()
def step(s, a):
    if a == 'step' and s[0] == 0:
        return (1,)
    if a == 'win' and s[0] == 0:
        return (2,)
    return None
def is_goal(s): return s[0] == 2
def invariant(s): return s[0] != 1
def project_obs(s): return 0
"""
        reg = _define("neon_d4_f07", spec, impl, ["win"], [])
        self.assertFalse(reg["tcb_locked"], reg)
        self.assertEqual(reg["epistemic_status"], "REJECTED_DIFFERENTIAL_MISMATCH")

    def test_coarse_obs_cannot_mask_2step_impl_invariant(self) -> None:
        spec = """
def initial_state(): return 0
def actions(s): return ('step', 'win') if s < 3 else ()
def step(s, a):
    if a == 'step' and s < 2: return s + 1
    if a == 'win' and s == 0: return 3
    return None
def is_goal(s): return s == 3
def invariant(s): return True
def project_obs(s): return 0
"""
        impl = """
def initial_state(): return (0,)
def actions(s): return ('step', 'win') if s[0] < 3 else ()
def step(s, a):
    if a == 'step' and s[0] < 2: return (s[0] + 1,)
    if a == 'win' and s[0] == 0: return (3,)
    return None
def is_goal(s): return s[0] == 3
def invariant(s): return s[0] != 2
def project_obs(s): return 0
"""
        reg = _define("neon_d4_f07_2step", spec, impl, ["win"], [])
        self.assertFalse(reg["tcb_locked"], reg)
        self.assertEqual(reg["epistemic_status"], "REJECTED_DIFFERENTIAL_MISMATCH")

    def test_large_finite_cost_is_not_unreachable(self) -> None:
        spec = """
def initial_state(): return 0
def actions(s): return ('pay',) if s == 0 else ()
def step(s, a): return 1 if (s == 0 and a == 'pay') else None
def step_cost(s, a, ns): return 10 ** 15
def is_goal(s): return s == 1
"""
        impl = """
def initial_state(): return (0,)
def actions(s): return ('pay',) if s[0] == 0 else ()
def step(s, a): return (1,) if (s[0] == 0 and a == 'pay') else None
def step_cost(s, a, ns): return 1000000000000000
def is_goal(s): return s[0] == 1
def project_obs(s): return s[0]
"""
        reg = _define("neon_d4_inf", spec, impl, ["pay"], [])
        self.assertTrue(reg["tcb_locked"], reg)
        res = certify_formal_lower_bound("neon_d4_inf", proof_mode="quotient_homomorphism",
                                         certificate_code="def project(s): return s\n",
                                         claimed_lower_bound=10 ** 15)
        self.assertEqual(res["epistemic_status"], "PROVEN", res)
        self.assertEqual(res["quotient_exact_bound"], 10 ** 15)
        too_big = certify_formal_lower_bound("neon_d4_inf", proof_mode="quotient_homomorphism",
                                             certificate_code="def project(s): return s\n",
                                             claimed_lower_bound=10 ** 15 + 1)
        self.assertEqual(too_big["epistemic_status"], "REJECTED_QUOTIENT_BOUND_TOO_WEAK", too_big)

    def test_large_finite_cost_partitioned_quotient(self) -> None:
        spec = """
def initial_state(): return 0
def actions(s): return ('pay',) if s == 0 else ()
def step(s, a): return 1 if (s == 0 and a == 'pay') else None
def step_cost(s, a, ns): return 10 ** 18
def is_goal(s): return s == 1
"""
        impl = """
def initial_state(): return (0,)
def actions(s): return ('pay',) if s[0] == 0 else ()
def step(s, a): return (1,) if (s[0] == 0 and a == 'pay') else None
def step_cost(s, a, ns): return 10 ** 18
def is_goal(s): return s[0] == 1
def project_obs(s): return s[0]
"""
        reg = _define("neon_d4_cp_inf", spec, impl, ["pay"], [])
        self.assertTrue(reg["tcb_locked"], reg)
        cert = (
            "def projections():\n"
            "    return (\n"
            "        ('p1', lambda s: s, lambda s, a, ns: Fraction(10 ** 18, 2)),\n"
            "        ('p2', lambda s: s, lambda s, a, ns: Fraction(10 ** 18, 2)),\n"
            "    )\n"
        )
        res = certify_formal_lower_bound("neon_d4_cp_inf", proof_mode="cost_partitioned_quotients",
                                         certificate_code=cert, claimed_lower_bound=10 ** 18)
        self.assertEqual(res["epistemic_status"], "PROVEN", res)
        self.assertEqual(res["ceil_integer_bound"], 10 ** 18)

    def test_genuinely_unreachable_goal_stays_unreachable_inf(self) -> None:
        spec = """
def initial_state(): return 0
def actions(s): return ('loop',)
def step(s, a): return 0
def is_goal(s): return s == 1
"""
        impl = """
def initial_state(): return (0,)
def actions(s): return ('loop',)
def step(s, a): return (0,)
def is_goal(s): return s[0] == 1
def project_obs(s): return s[0]
"""
        FORMAL_REGISTRY.pop("neon_d4_unreach", None)
        reg = define_formal_system(
            "neon_d4_unreach",
            spec,
            impl,
            must_fail_controls=[{"name": "loop", "trace": ["loop"]}],
            exact_arithmetic_only=True,
            strict_bar=True,
        )
        self.assertTrue(reg["tcb_locked"], reg)
        res_q = certify_formal_lower_bound("neon_d4_unreach", proof_mode="quotient_homomorphism",
                                           certificate_code="def project(s): return s\n",
                                           claimed_lower_bound=10 ** 20)
        self.assertEqual(res_q["epistemic_status"], "PROVEN", res_q)
        self.assertEqual(res_q["quotient_exact_bound"], "UNREACHABLE_INF")


if __name__ == "__main__":
    unittest.main()
