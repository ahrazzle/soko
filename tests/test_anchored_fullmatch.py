"""Anchored patterns must reject a trailing newline.

`$` matches before a final newline, so `re.match` accepted `3/4\\n` and a
64-hex digest with the same extra byte. `fullmatch` does not.
"""

from __future__ import annotations

import unittest

from experiments.landmark_dual_bounds.hero_assignment_bounds import parse_strict_fraction
from mde_soko.domain_oracle import audit_soko_certificate

HEX64 = "a" * 64


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _verified() -> dict:
    return {
        "epistemic_status": "VERIFIED",
        "tcb_pins": {
            "tcb_manifest_verified": True,
            "checker_auditor_py_sha256": HEX64,
        },
        "witness_or_proof_sha256": "b" * 64,
    }


class AnchoredFullmatchTests(unittest.TestCase):
    def test_canonical_fraction_still_parses(self) -> None:
        self.assertEqual(parse_strict_fraction("3/4").numerator, 3)
        self.assertEqual(parse_strict_fraction("-5"), -5)

    def test_fraction_trailing_newline_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_strict_fraction("3/4\n")

    def test_digest_trailing_newline_rejected(self) -> None:
        clean = audit_soko_certificate(_verified())
        _require(bool(clean["passed"]), f"control certificate rejected: {clean}")
        bad_witness = _verified()
        bad_witness["witness_or_proof_sha256"] = "b" * 64 + "\n"
        res_w = audit_soko_certificate(bad_witness)
        _require(
            (not bool(res_w["passed"]))
            and any(str(f["rule"]).startswith("F08") for f in res_w["findings"]),
            f"trailing newline on the witness digest was accepted: {res_w}",
        )
        bad_pin = _verified()
        bad_pin["tcb_pins"] = {
            "tcb_manifest_verified": True,
            "checker_auditor_py_sha256": HEX64 + "\n",
        }
        res_p = audit_soko_certificate(bad_pin)
        _require(
            (not bool(res_p["passed"]))
            and any(str(f["rule"]).startswith("F03") for f in res_p["findings"]),
            f"trailing newline on the checker digest was accepted: {res_p}",
        )


if __name__ == "__main__":
    unittest.main()
