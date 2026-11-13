"""Offline tests for `experiments.transport_relaxation.phase_window_witness`."""

from __future__ import annotations

import unittest

from experiments.transport_relaxation.phase_window_witness import (
    certify_phase_window_transport,
    verify_phase_window_certificate,
    _canon_sha256,
)

# Static union routes all 3 crates, but no single phase does:
# crates 0,1 reach goals {0,1} only in phase [0,4], crates also reach {1,2} only in [6,10].
PHASE_DISJOINT_WINDOWS = [
    (0, 0, 0, 4),
    (1, 0, 0, 4),
    (1, 1, 0, 4),
    (2, 1, 0, 4),
    (0, 1, 6, 10),
    (1, 1, 6, 10),
    (1, 2, 6, 10),
    (2, 2, 6, 10),
]


def _cert():
    return certify_phase_window_transport(
        n_crates=3,
        n_targets=3,
        window_edges=PHASE_DISJOINT_WINDOWS,
        phase_min=0,
        phase_max=10,
    )


class PhaseWindowWitnessTests(unittest.TestCase):
    def test_static_union_feasible_but_no_single_phase_routes(self) -> None:
        cert = _cert()
        self.assertEqual(cert["static_union_flow"], 3)
        self.assertTrue(cert["static_union_feasible"])
        self.assertEqual(cert["max_phase_flow"], 2)
        self.assertFalse(cert["phase_window_feasible"])
        self.assertTrue(cert["static_union_false_feasibility_caught"])

    def test_verifier_accepts_honest_certificate(self) -> None:
        ok, msg = verify_phase_window_certificate(_cert())
        self.assertTrue(ok, msg)
        self.assertEqual(msg, "verified")

    def test_verifier_rejects_inflated_knot_flow_with_valid_hash(self) -> None:
        cert = _cert()
        cert["knot_witnesses"][0]["max_flow"] = 3
        cert["certificate_sha256"] = _canon_sha256(cert)
        ok, msg = verify_phase_window_certificate(cert)
        self.assertFalse(ok)
        self.assertTrue(msg.startswith("flow_recomputation_mismatch"), msg)

    def test_verifier_rejects_dropped_window_with_valid_hash(self) -> None:
        cert = _cert()
        cert["window_edges_q"] = cert["window_edges_q"][:-1]
        cert["certificate_sha256"] = _canon_sha256(cert)
        ok, msg = verify_phase_window_certificate(cert)
        self.assertFalse(ok)

    def test_fully_overlapping_windows_are_feasible(self) -> None:
        cert = certify_phase_window_transport(
            n_crates=2,
            n_targets=2,
            window_edges=[(0, 0, 0, 10), (1, 1, 0, 10)],
            phase_min=0,
            phase_max=10,
        )
        self.assertTrue(cert["phase_window_feasible"])
        self.assertEqual(cert["max_phase_flow"], 2)
        ok, _ = verify_phase_window_certificate(cert)
        self.assertTrue(ok)

    def test_knot_witnesses_cover_exactly_the_interval_endpoints(self) -> None:
        cert = _cert()
        phases = [w["phase_q"] for w in cert["knot_witnesses"]]
        self.assertEqual(phases, ["0/1", "4/1", "6/1", "10/1"])
        ok, _ = verify_phase_window_certificate(cert)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
