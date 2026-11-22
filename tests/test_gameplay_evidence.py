"""Positive and adversarial tests for the gameplay-evidence/v0.1 Soko adapter."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from soko_mcp.gameplay_evidence import (
    EvidenceExportError,
    artifact_digest,
    export_bytes,
    export_file,
    json_sha256,
    parse_certificate,
    validate_artifact,
)

ROOT = Path(__file__).resolve().parents[1]
CERTIFICATE = ROOT / "evidence/2026-11-22-gameplay-evidence/heroes-rr-three-engine-certificate.json"
SIMGRAMMAR = Path("/tmp/rmmz-converge.awcxGe/simgrammar")
REVISION = "41b6f9ca54cc24954adcd3e88149c2371a4478e6"


def _resign(artifact: dict) -> dict:
    artifact["artifact_sha256"] = artifact_digest(artifact)
    return artifact


def _recommit_payload(artifact: dict) -> dict:
    payload = artifact["payload"]
    payload["model_sha256"] = json_sha256(payload["model"])
    payload["initial_state_sha256"] = json_sha256(payload["initial_state"])
    payload["actions_sha256"] = json_sha256(payload["actions"])
    payload["trajectory_sha256"] = json_sha256(payload["trajectory"])
    for check in artifact["evidence"]["checks"]:
        check["initial_state_sha256"] = payload["initial_state_sha256"]
        check["actions_sha256"] = payload["actions_sha256"]
        check["trajectory_sha256"] = payload["trajectory_sha256"]
    return _resign(artifact)


class GameplayEvidenceExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = CERTIFICATE.read_bytes()
        cls.cert = parse_certificate(cls.raw)
        cls.artifact = export_file(
            CERTIFICATE, revision=REVISION, simgrammar_root=SIMGRAMMAR
        )
        validate_artifact(cls.artifact, reverify=True)

    def test_positive_preserves_source_and_replay_only_semantics(self) -> None:
        artifact = self.artifact
        self.assertEqual(artifact["schema"], "gameplay-evidence/v0.1")
        self.assertEqual(artifact["source"]["raw"].encode("utf-8"), self.raw)
        self.assertEqual(artifact["source"]["raw_sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(artifact["artifact_sha256"], artifact_digest(artifact))
        self.assertEqual(artifact["payload"]["initial_state_sha256"], self.cert["instance_sha256"])
        outcome = artifact["payload"]["outcome"]
        self.assertEqual(outcome["source_route_sha256"], self.cert["route_sha256"])
        self.assertEqual(outcome["source_trajectory_fnv64"], self.cert["traj_fnv64"])
        self.assertEqual(outcome["source_certificate_sha256"], self.cert["certificate_sha256"])
        self.assertEqual(outcome["source_checker_pins"], self.cert["checker_pins"])
        self.assertEqual(outcome["source_epistemic_status"], "VERIFIED")
        self.assertEqual(len(artifact["evidence"]["checks"]), 1)
        check = artifact["evidence"]["checks"][0]
        self.assertEqual(check["kind"], "model_replay")
        self.assertNotEqual(check["kind"], "model_proof")
        self.assertEqual(check["status"], "PASS")
        self.assertEqual(check["source_labels"], ["VERIFIED", "differential_replay"])
        self.assertEqual(
            [control["name"] for control in artifact["evidence"]["negative_controls"]],
            self.cert["must_fail_controls"],
        )
        self.assertTrue(all(control["passed"] for control in artifact["evidence"]["negative_controls"]))
        self.assertEqual(artifact["mechanics"], [])
        self.assertIn("agent-pathfinding.yaml was inspected but not pinned", artifact["evidence"]["limitations"][-1])

    def test_missing_simgrammar_root_is_explicitly_unbound(self) -> None:
        for root in (None, Path("/definitely/not/a/simgrammar/root")):
            with self.subTest(root=root):
                artifact = export_bytes(self.raw, revision=REVISION, simgrammar_root=root)
                self.assertEqual(artifact["mechanics"], [])
                self.assertTrue(artifact["evidence"]["limitations"][-1].startswith("SimGrammar unbound:"))
                validate_artifact(artifact)

    def test_raw_source_tamper_fails_even_after_artifact_resigning(self) -> None:
        artifact = copy.deepcopy(self.artifact)
        artifact["source"]["raw"] += "\n"
        _resign(artifact)
        with self.assertRaisesRegex(EvidenceExportError, "raw_sha256"):
            validate_artifact(artifact)

    def test_payload_outcome_tamper_fails_after_resigning(self) -> None:
        artifact = copy.deepcopy(self.artifact)
        artifact["payload"]["outcome"]["exact_win"] = False
        _resign(artifact)
        with self.assertRaisesRegex(EvidenceExportError, "source projection"):
            validate_artifact(artifact)

    def test_action_and_trajectory_tamper_fail_after_full_recommitment(self) -> None:
        for field in ("actions", "trajectory"):
            with self.subTest(field=field):
                artifact = copy.deepcopy(self.artifact)
                if field == "actions":
                    artifact["payload"]["actions"][1]["key"] = "L"
                else:
                    artifact["payload"]["trajectory"][1]["ascii"] = "XXX"
                _recommit_payload(artifact)
                with self.assertRaisesRegex(EvidenceExportError, "source projection"):
                    validate_artifact(artifact)

    def test_source_label_and_model_proof_promotion_fail(self) -> None:
        promoted = copy.deepcopy(self.cert)
        promoted["epistemic_status"] = "PROVEN"
        promoted["certificate_sha256"] = json_sha256(
            {key: value for key, value in promoted.items() if key != "certificate_sha256"}
        )
        raw = json.dumps(promoted, indent=2).encode("utf-8")
        with self.assertRaisesRegex(EvidenceExportError, "VERIFIED"):
            export_bytes(raw, revision=REVISION)

        artifact = copy.deepcopy(self.artifact)
        artifact["evidence"]["checks"][0]["source_labels"] = ["PROVEN"]
        _resign(artifact)
        with self.assertRaisesRegex(EvidenceExportError, "source projection"):
            validate_artifact(artifact)

        artifact = copy.deepcopy(self.artifact)
        artifact["evidence"]["checks"][0]["kind"] = "model_proof"
        _resign(artifact)
        with self.assertRaisesRegex(EvidenceExportError, "source projection"):
            validate_artifact(artifact)

    def test_dropped_source_or_exported_controls_fail(self) -> None:
        dropped = copy.deepcopy(self.cert)
        dropped["must_fail_controls"].pop()
        dropped["certificate_sha256"] = json_sha256(
            {key: value for key, value in dropped.items() if key != "certificate_sha256"}
        )
        raw = json.dumps(dropped, indent=2).encode("utf-8")
        with self.assertRaisesRegex(EvidenceExportError, "controls"):
            export_bytes(raw, revision=REVISION)

        artifact = copy.deepcopy(self.artifact)
        artifact["evidence"]["negative_controls"].pop()
        _resign(artifact)
        with self.assertRaisesRegex(EvidenceExportError, "source projection"):
            validate_artifact(artifact)

    def test_certificate_digest_mismatch_fails_before_export(self) -> None:
        tampered = copy.deepcopy(self.cert)
        tampered["certificate_sha256"] = "a" * 64
        raw = json.dumps(tampered, indent=2).encode("utf-8")
        with self.assertRaisesRegex(EvidenceExportError, "CERTIFICATE_HASH_MISMATCH"):
            export_bytes(raw, revision=REVISION)

    def test_cli_round_trip_without_mcproof(self) -> None:
        from soko_mcp.gameplay_evidence import main

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "artifact.json"
            code = main([
                "export", "--certificate", str(CERTIFICATE), "--output", str(output),
                "--revision", REVISION, "--simgrammar-root", str(SIMGRAMMAR),
            ])
            self.assertEqual(code, 0)
            self.assertEqual(main(["validate", str(output), "--reverify"]), 0)
            artifact = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(artifact["artifact_sha256"], self.artifact["artifact_sha256"])


if __name__ == "__main__":
    unittest.main()
