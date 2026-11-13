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


def _rehash(cert):
    cert["certificate_sha256"] = _canon_sha256(cert)
    return cert


class PhaseWindowWitnessForgeryTests(unittest.TestCase):
    """Regression tests for grk-proof review 5887432722 on PR #45."""

    def test_forged_max_phase_q_off_knot_is_rejected(self) -> None:
        cert = _cert()
        cert["max_phase_q"] = "5/1"  # not a knot; no window is open at 5
        ok, msg = verify_phase_window_certificate(_rehash(cert))
        self.assertFalse(ok)
        self.assertEqual(msg, "max_phase_q_mismatch")

    def test_forged_max_phase_q_zero_on_non_argmax_knot_is_rejected(self) -> None:
        cert = certify_phase_window_transport(
            n_crates=2,
            n_targets=2,
            window_edges=[(0, 0, 0, 10), (1, 1, 6, 10)],
            phase_min=0,
            phase_max=10,
        )
        self.assertEqual(cert["max_phase_q"], "6/1")
        self.assertEqual(cert["knot_witnesses"][0]["phase_q"], "0/1")
        self.assertEqual(cert["knot_witnesses"][0]["max_flow"], 1)
        self.assertTrue(verify_phase_window_certificate(cert)[0])
        cert["max_phase_q"] = "0/1"
        ok, msg = verify_phase_window_certificate(_rehash(cert))
        self.assertFalse(ok)
        self.assertEqual(msg, "max_phase_q_mismatch")

    def test_swapped_source_side_is_rejected(self) -> None:
        cert = _cert()
        kws = cert["knot_witnesses"]
        self.assertNotEqual(kws[0]["source_side"], kws[2]["source_side"])
        kws[0]["source_side"], kws[2]["source_side"] = kws[2]["source_side"], kws[0]["source_side"]
        ok, msg = verify_phase_window_certificate(_rehash(cert))
        self.assertFalse(ok)
        self.assertEqual(msg, "source_side_mismatch")

    def test_replaced_source_side_is_rejected(self) -> None:
        cert = _cert()
        cert["knot_witnesses"][1]["source_side"] = ["src"]
        ok, msg = verify_phase_window_certificate(_rehash(cert))
        self.assertFalse(ok)
        self.assertEqual(msg, "source_side_mismatch")

    def _assert_index_attack_rejected(self, edge_pos: int, slot: int, value: int) -> None:
        # Rewrite one window and every knot's matching active edge, so the
        # forged certificate is self-consistent apart from the index itself.
        # With -1 on an edge whose real index is n-1, flows and cuts are
        # unchanged under Python's negative-index aliasing.
        cert = _cert()
        orig = cert["window_edges_q"][edge_pos][:2]
        cert["window_edges_q"][edge_pos][slot] = value
        forged = cert["window_edges_q"][edge_pos][:2]
        for kw in cert["knot_witnesses"]:
            kw["active_edges"] = [forged if e == orig else e for e in kw["active_edges"]]
        ok, msg = verify_phase_window_certificate(_rehash(cert))
        self.assertFalse(ok)
        self.assertEqual(msg, "window_index_out_of_range")

    def test_crate_minus_one_is_rejected(self) -> None:
        self._assert_index_attack_rejected(3, 0, -1)  # (2, 1) -> (-1, 1)

    def test_crate_n_is_rejected(self) -> None:
        self._assert_index_attack_rejected(0, 0, 3)

    def test_target_minus_one_is_rejected(self) -> None:
        self._assert_index_attack_rejected(6, 1, -1)  # (1, 2) -> (1, -1)

    def test_target_n_is_rejected(self) -> None:
        self._assert_index_attack_rejected(0, 1, 3)

    def test_crate_minus_one_false_feasibility_is_rejected(self) -> None:
        # Review 5887432722 shape: crate 1 has no window at all, but naming
        # crate -1 aliased it and produced a feasible, passing certificate.
        cert = certify_phase_window_transport(
            n_crates=2, n_targets=2,
            window_edges=[(0, 0, 0, 10), (1, 1, 0, 10)],
            phase_min=0, phase_max=10,
        )
        self.assertTrue(cert["phase_window_feasible"])
        cert["window_edges_q"][1][0] = -1
        for kw in cert["knot_witnesses"]:
            kw["active_edges"] = [[-1, 1] if e == [1, 1] else e for e in kw["active_edges"]]
        ok, msg = verify_phase_window_certificate(_rehash(cert))
        self.assertFalse(ok)
        self.assertEqual(msg, "window_index_out_of_range")

    def test_certifier_refuses_out_of_range_indices(self) -> None:
        for edge in [(-1, 0, 0, 10), (3, 0, 0, 10), (0, -1, 0, 10), (0, 3, 0, 10)]:
            with self.assertRaises(ValueError):
                certify_phase_window_transport(
                    n_crates=3, n_targets=3,
                    window_edges=PHASE_DISJOINT_WINDOWS + [edge],
                    phase_min=0, phase_max=10,
                )


def _flow2():
    # Knot 0 has flow/capacity 1; static union and max phase flow are 2.
    return certify_phase_window_transport(
        n_crates=2,
        n_targets=2,
        window_edges=[(0, 0, 0, 10), (1, 1, 5, 10)],
        phase_min=0,
        phase_max=10,
    )


def _flow1():
    # Every knot has flow/capacity 1; max phase flow is 1.
    return certify_phase_window_transport(
        n_crates=2,
        n_targets=2,
        window_edges=[(0, 0, 0, 4), (0, 1, 0, 4), (1, 0, 6, 10), (1, 1, 6, 10)],
        phase_min=0,
        phase_max=10,
    )


class PhaseWindowWitnessTypeCheckTests(unittest.TestCase):
    """Regression tests for grk-proof review 5887628888 on PR #47."""

    def _assert_rehashed_malformed(self, cert) -> None:
        # Rehash first so a failure is from the type check, not the hash.
        try:
            ok, msg = verify_phase_window_certificate(_rehash(cert))
        except TypeError:
            self.fail("verifier raised TypeError; expected malformed_certificate")
        self.assertFalse(ok)
        self.assertEqual(msg, "malformed_certificate")

    def test_float_static_union_flow_is_malformed(self) -> None:
        cert = _flow2()
        self.assertEqual(cert["static_union_flow"], 2)
        cert["static_union_flow"] = 2.9
        self._assert_rehashed_malformed(cert)

    def test_float_max_phase_flow_is_malformed(self) -> None:
        cert = _flow2()
        self.assertEqual(cert["max_phase_flow"], 2)
        cert["max_phase_flow"] = 2.9
        self._assert_rehashed_malformed(cert)

    def test_float_knot_max_flow_is_malformed(self) -> None:
        cert = _flow2()
        self.assertEqual(cert["knot_witnesses"][0]["max_flow"], 1)
        cert["knot_witnesses"][0]["max_flow"] = 1.9
        self._assert_rehashed_malformed(cert)

    def test_float_knot_min_cut_capacity_is_malformed(self) -> None:
        cert = _flow2()
        self.assertEqual(cert["knot_witnesses"][0]["min_cut_capacity"], 1)
        cert["knot_witnesses"][0]["min_cut_capacity"] = 1.9
        self._assert_rehashed_malformed(cert)

    def test_string_knot_min_cut_capacity_is_malformed(self) -> None:
        cert = _flow2()
        self.assertEqual(cert["knot_witnesses"][0]["min_cut_capacity"], 1)
        cert["knot_witnesses"][0]["min_cut_capacity"] = "1"
        self._assert_rehashed_malformed(cert)

    def test_bool_knot_max_flow_is_malformed(self) -> None:
        cert = _flow1()
        self.assertEqual(cert["knot_witnesses"][0]["max_flow"], 1)
        cert["knot_witnesses"][0]["max_flow"] = True
        self._assert_rehashed_malformed(cert)

    def test_bool_knot_min_cut_capacity_is_malformed(self) -> None:
        cert = _flow1()
        self.assertEqual(cert["knot_witnesses"][0]["min_cut_capacity"], 1)
        cert["knot_witnesses"][0]["min_cut_capacity"] = True
        self._assert_rehashed_malformed(cert)

    def test_bool_max_phase_flow_is_malformed(self) -> None:
        cert = _flow1()
        self.assertEqual(cert["max_phase_flow"], 1)
        cert["max_phase_flow"] = True
        self._assert_rehashed_malformed(cert)

    def test_none_static_union_flow_is_malformed(self) -> None:
        cert = _flow2()
        cert["static_union_flow"] = None
        self._assert_rehashed_malformed(cert)

    def test_none_max_phase_flow_is_malformed(self) -> None:
        cert = _flow2()
        cert["max_phase_flow"] = None
        self._assert_rehashed_malformed(cert)

    def test_string_phase_window_feasible_is_malformed(self) -> None:
        cert = _flow2()
        self.assertTrue(cert["phase_window_feasible"])
        cert["phase_window_feasible"] = "false"
        self._assert_rehashed_malformed(cert)

    def test_int_static_union_feasible_is_malformed(self) -> None:
        cert = _flow2()
        self.assertTrue(cert["static_union_feasible"])
        cert["static_union_feasible"] = 1
        self._assert_rehashed_malformed(cert)

    def test_int_phase_window_feasible_zero_is_malformed(self) -> None:
        cert = _cert()
        self.assertFalse(cert["phase_window_feasible"])
        cert["phase_window_feasible"] = 0
        self._assert_rehashed_malformed(cert)

    def test_int_false_feasibility_caught_is_malformed(self) -> None:
        cert = _cert()
        self.assertTrue(cert["static_union_false_feasibility_caught"])
        cert["static_union_false_feasibility_caught"] = 1
        self._assert_rehashed_malformed(cert)

    def test_bool_standins_in_active_edges_are_malformed(self) -> None:
        cert = certify_phase_window_transport(
            n_crates=2,
            n_targets=2,
            window_edges=[(0, 0, 0, 10), (1, 1, 0, 10)],
            phase_min=0,
            phase_max=10,
        )
        self.assertEqual(cert["knot_witnesses"][0]["active_edges"], [[0, 0], [1, 1]])
        cert["knot_witnesses"][0]["active_edges"] = [[False, False], [True, True]]
        self._assert_rehashed_malformed(cert)

    def test_unserializable_index_is_malformed_not_raised(self) -> None:
        class _Unserializable:
            pass

        cert = _cert()
        cert["window_edges_q"][0][0] = _Unserializable()
        try:
            ok, msg = verify_phase_window_certificate(cert)
        except TypeError:
            self.fail("verifier raised TypeError; expected malformed_certificate")
        self.assertFalse(ok)
        self.assertEqual(msg, "malformed_certificate")

        try:
            import numpy as np
        except ImportError:
            return
        cert = _cert()
        cert["window_edges_q"][0][0] = np.int64(0)
        try:
            ok, msg = verify_phase_window_certificate(cert)
        except TypeError:
            self.fail("verifier raised TypeError on np.int64; expected malformed_certificate")
        self.assertFalse(ok)
        self.assertEqual(msg, "malformed_certificate")

    def test_certifier_rejects_non_int_n_crates_and_n_targets(self) -> None:
        bad_counts = [True, 1.0, "1"]
        try:
            import numpy as np
        except ImportError:
            np = None
        else:
            bad_counts.extend([np.int64(1), np.int32(1)])
        windows = [(0, 0, 0, 10)]
        for bad in bad_counts:
            with self.subTest(field="n_crates", value=repr(bad)):
                with self.assertRaises(ValueError):
                    certify_phase_window_transport(
                        n_crates=bad, n_targets=2, window_edges=windows,
                        phase_min=0, phase_max=10,
                    )
            with self.subTest(field="n_targets", value=repr(bad)):
                with self.assertRaises(ValueError):
                    certify_phase_window_transport(
                        n_crates=2, n_targets=bad, window_edges=windows,
                        phase_min=0, phase_max=10,
                    )

if __name__ == "__main__":
    unittest.main()
