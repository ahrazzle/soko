"""An empty or unknown certificate must not come back VERIFIED.

The auditor used to return VERIFIED whenever it found no red-flag field.
A certificate with no status has no such field, so `{}` passed. The same
path relabeled REJECTED and CONJECTURE as VERIFIED, and PROVEN as VERIFIED.
CONJECTURE still needs no pins. Every recognized status that passes keeps
its own name.
"""

from __future__ import annotations

import unittest

from mde_soko.domain_oracle import audit_soko_certificate

HEX64 = "a" * 64


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class AuditStatusFailClosedTests(unittest.TestCase):
    def test_empty_certificate_is_rejected(self) -> None:
        result = audit_soko_certificate({})
        _require(not bool(result["passed"]), f"empty certificate passed: {result}")
        self.assertEqual(result["epistemic_status"], "REJECTED")
        self.assertIn("F00_STATUS_ABSENT", {f["rule"] for f in result["findings"]})

    def test_unknown_status_is_rejected(self) -> None:
        result = audit_soko_certificate({"epistemic_status": "BANANA"})
        _require(not bool(result["passed"]), f"unknown status passed: {result}")
        self.assertEqual(result["epistemic_status"], "REJECTED")
        self.assertIn("F00_STATUS_UNKNOWN", {f["rule"] for f in result["findings"]})

    def test_rejected_and_conjecture_are_not_relabeled_verified(self) -> None:
        rejected = audit_soko_certificate({"epistemic_status": "REJECTED"})
        _require(bool(rejected["passed"]), f"a plain rejection is not an illegal claim: {rejected}")
        self.assertEqual(rejected["epistemic_status"], "REJECTED")

        conjecture = audit_soko_certificate({"epistemic_status": "CONJECTURE"})
        _require(bool(conjecture["passed"]), f"CONJECTURE does not require pins: {conjecture}")
        self.assertEqual(conjecture["epistemic_status"], "CONJECTURE")

    def test_verified_with_pins_still_passes(self) -> None:
        cert = {
            "epistemic_status": "VERIFIED",
            "tcb_pins": {
                "tcb_manifest_verified": True,
                "checker_auditor_py_sha256": HEX64,
            },
            "witness_or_proof_sha256": "b" * 64,
        }
        result = audit_soko_certificate(cert)
        _require(bool(result["passed"]), f"pinned VERIFIED certificate rejected: {result}")
        self.assertEqual(result["epistemic_status"], "VERIFIED")

    def test_pinned_proven_keeps_its_own_status(self) -> None:
        cert = {
            "epistemic_status": "PROVEN",
            "tcb_pins": {
                "tcb_manifest_verified": True,
                "checker_auditor_py_sha256": HEX64,
            },
            "witness_or_proof_sha256": "b" * 64,
        }
        result = audit_soko_certificate(cert)
        _require(bool(result["passed"]), f"pinned PROVEN certificate rejected: {result}")
        self.assertEqual(result["epistemic_status"], "PROVEN")

    def test_every_passing_recognized_status_keeps_its_name(self) -> None:
        pins = {"tcb_manifest_verified": True, "checker_auditor_py_sha256": HEX64}
        for status in ("VERIFIED", "PROVEN", "LOWER_BOUND"):
            result = audit_soko_certificate(
                {"epistemic_status": status, "tcb_pins": pins, "witness_or_proof_sha256": "b" * 64}
            )
            _require(bool(result["passed"]), f"{status} with pins rejected: {result}")
            self.assertEqual(result["epistemic_status"], status)
        for status in ("CONJECTURE", "REJECTED", "LINT_PASS", "LOWER_BOUND_UNWITNESSED", "UNVERIFIED_CALLER_BOUNDS"):
            result = audit_soko_certificate({"epistemic_status": status})
            self.assertEqual(result["epistemic_status"], status)
        bounded = audit_soko_certificate(
            {"epistemic_status": "VERIFIED_ON_BOUNDED_REACHABLE_SUBGRAPH", "complete_space": True}
        )
        self.assertEqual(bounded["epistemic_status"], "VERIFIED_ON_BOUNDED_REACHABLE_SUBGRAPH")

    def test_bare_proven_is_still_rejected(self) -> None:
        result = audit_soko_certificate({"epistemic_status": "PROVEN"})
        _require(not bool(result["passed"]), f"bare PROVEN passed: {result}")
        self.assertEqual(result["epistemic_status"], "REJECTED")


if __name__ == "__main__":
    unittest.main()
