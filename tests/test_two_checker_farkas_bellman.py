"""Unit tests for two-checker min-cut, Farkas LP, and Bellman quotient-PDB verifiers."""
from __future__ import annotations

from fractions import Fraction
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments" / "transport_relaxation"))
from two_checker_farkas_bellman import (  # noqa: E402
    verify_farkas_lp_infeasibility,
    verify_mincut_certificate,
    verify_quotient_pdb_bellman,
)


class TestTwoCheckerFarkasBellman(unittest.TestCase):
    def test_mincut_certificate_soundness_and_tamper_rejection(self) -> None:
        edges = [(0, 1 + i, 1) for i in range(9)] + [(1 + i, 10, 1) for i in range(5)]
        cert = verify_mincut_certificate(0, 10, edges, range(0, 10), reported_flow=5)
        self.assertTrue(cert.valid)
        self.assertFalse(verify_mincut_certificate(0, 10, edges, range(0, 10), reported_flow=4).valid)
        self.assertFalse(verify_mincut_certificate(0, 10, edges, range(0, 11), reported_flow=5).valid)

    def test_bellman_quotient_pdb_catches_overestimate_and_hash_collision(self) -> None:
        pdb_ok = {("q", 0): 2, ("q", 1): 1, ("q", 2): 0}
        edges = [(("q", 0), ("q", 1), 1), (("q", 1), ("q", 2), 1)]
        audit_ok = verify_quotient_pdb_bellman(
            pdb_ok, [("q", 2)], edges, hash64_fn=lambda s: 42 if s[1] in (0, 1) else 99
        )
        self.assertTrue(audit_ok.admissible)
        self.assertEqual(audit_ok.hash64_collisions_detected, 1)
        audit_bad = verify_quotient_pdb_bellman({("q", 0): 4, ("q", 1): 1, ("q", 2): 0}, [("q", 2)], edges)
        self.assertFalse(audit_bad.admissible)

    def test_exact_rational_farkas_infeasibility_witness(self) -> None:
        a = [[Fraction(-1), Fraction(-1)], [Fraction(1), Fraction(1)]]
        self.assertTrue(verify_farkas_lp_infeasibility(a, [Fraction(-1), Fraction(1, 2)], [Fraction(1), Fraction(1)]))
        self.assertFalse(verify_farkas_lp_infeasibility(a, [Fraction(0), Fraction(1, 2)], [Fraction(1), Fraction(1)]))


if __name__ == "__main__":
    unittest.main()
