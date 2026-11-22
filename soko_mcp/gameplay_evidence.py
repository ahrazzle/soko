"""Export a verified three-engine Soko route as ``gameplay-evidence/v0.1``.

The adapter uses only the Python standard library and the repository's existing
Soko verifier. It never imports or executes mcproof. A source ``VERIFIED`` route
is differential model replay, not a model proof or live original-engine replay.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from .engine_bridge import verify_route_dual
from .evidence import verify_certificate_gate
from .oracle import PuzzleScriptOracle

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CERTIFICATE = (
    REPO_ROOT
    / "evidence"
    / "2026-11-22-gameplay-evidence"
    / "heroes-rr-three-engine-certificate.json"
)
ADAPTER = "python3 -m soko_mcp.gameplay_evidence export"
SCHEMA = "gameplay-evidence/v0.1"
SOURCE_ADAPTER = "heroes-of-sokoban-ascii-v1"
EXPECTED_ENGINES = [
    "python_spec_oracle",
    "python_flat_bitmask_oracle",
    "cpp20_soko_engine",
]
HEX_40 = re.compile(r"[0-9a-f]{40}")
HEX_64 = re.compile(r"[0-9a-f]{64}")


class EvidenceExportError(ValueError):
    """A source certificate or exported envelope failed a closed validation gate."""


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceExportError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise EvidenceExportError(f"non-finite JSON number: {value}")


def parse_certificate(raw: bytes) -> dict[str, Any]:
    """Parse exact UTF-8 source bytes while rejecting duplicate keys and NaN."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvidenceExportError("source certificate is not exact UTF-8") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_json_object,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, EvidenceExportError) as exc:
        raise EvidenceExportError(f"invalid source JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceExportError("source certificate must be a JSON object")
    return value


def _check_canonical(value: Any) -> None:
    if value is None or isinstance(value, str) or type(value) is bool:
        return
    if type(value) is int:
        if not -(2**63) <= value < 2**63:
            raise EvidenceExportError("integer outside signed 64-bit range")
        return
    if type(value) is float:
        raise EvidenceExportError("floating-point values are forbidden by the exchange contract")
        return
    if isinstance(value, list):
        for item in value:
            _check_canonical(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise EvidenceExportError("non-string JSON object key")
            _check_canonical(item)
        return
    raise EvidenceExportError(f"non-JSON value: {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    _check_canonical(value)
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def json_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def artifact_digest(artifact: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in artifact.items() if key != "artifact_sha256"}
    return json_sha256(unsigned)


def _certificate_semantics(cert: dict[str, Any]) -> None:
    """Accept only the genuine verified three-engine RR source shape."""
    gate = verify_certificate_gate(cert)
    if not gate.get("passed"):
        raise EvidenceExportError(
            f"source certificate gate failed: {gate.get('epistemic_status')}: {gate.get('reason')}"
        )
    if cert.get("epistemic_status") != "VERIFIED":
        raise EvidenceExportError("source status must remain exactly VERIFIED")
    problem = cert.get("problem")
    if not isinstance(problem, dict) or problem.get("adapter") != SOURCE_ADAPTER:
        raise EvidenceExportError(f"source problem.adapter must be {SOURCE_ADAPTER}")
    if problem.get("part") != 1 or problem.get("grid") != ["F.G"]:
        raise EvidenceExportError("source is not the repository's minimal F.G instance")
    if cert.get("route") != "RR" or cert.get("route_len") != 2:
        raise EvidenceExportError("source route must be exactly RR")
    true_fields = (
        "valid_winning_route",
        "trajectory_digest_match",
        "alive",
        "exact_win",
        "dual_engine_checked",
        "triple_oracle_checked",
        "differential_match",
        "checker_pins_ok",
    )
    if any(cert.get(field) is not True for field in true_fields):
        raise EvidenceExportError("source lacks a passing three-engine differential replay")
    if cert.get("premature_win") is not False or cert.get("formal_proof_checked") is not False:
        raise EvidenceExportError("source has invalid termination or proof semantics")
    if cert.get("external_spec_pinned") is not False or cert.get("source_lock_asserted") is not False:
        raise EvidenceExportError("source external-spec/lock limitations were changed")
    if cert.get("engines_executed") != EXPECTED_ENGINES or cert.get("engines_count") != 3:
        raise EvidenceExportError("exactly the three pinned Soko engines are required")
    controls = cert.get("must_fail_controls")
    expected_controls = [
        "rejected_route_promoted_to_verified",
        "truncated_prefix_rejected",
        "post_win_extra_key_rejected",
    ]
    if controls != expected_controls:
        raise EvidenceExportError("source must-fail controls are missing or reordered")
    pins = cert.get("checker_pins")
    if not isinstance(pins, dict) or not pins or any(
        not isinstance(value, str) or HEX_64.fullmatch(value) is None for value in pins.values()
    ):
        raise EvidenceExportError("three-engine source requires complete non-null checker pins")
    if HEX_64.fullmatch(str(cert.get("route_sha256", ""))) is None:
        raise EvidenceExportError("source route digest is malformed")
    if cert.get("route_sha256") != hashlib.sha256(b"RR").hexdigest():
        raise EvidenceExportError("source route digest does not commit to raw RR")
    if not isinstance(cert.get("traj_fnv64"), str) or not re.fullmatch(
        r"[0-9a-f]{16}", cert["traj_fnv64"]
    ):
        raise EvidenceExportError("source trajectory FNV-1a digest is malformed")


def reverify_source(cert: dict[str, Any]) -> dict[str, Any]:
    """Run the existing certificate gate and a fresh required-C++ replay."""
    _certificate_semantics(cert)
    problem = cert["problem"]
    fresh = verify_route_dual(1, problem["grid"], cert["route"], require_cpp=True)
    fresh_gate = verify_certificate_gate(fresh)
    if not fresh_gate.get("passed") or fresh.get("epistemic_status") != "VERIFIED":
        raise EvidenceExportError(
            f"fresh three-engine verifier rejected the route: {fresh.get('epistemic_status')}"
        )
    if fresh != cert:
        raise EvidenceExportError(
            "source differs from fresh verifier output (payload, checker pins, controls, or digest)"
        )
    return fresh


def _trajectory(cert: dict[str, Any]) -> list[dict[str, Any]]:
    problem = cert["problem"]
    simulation = PuzzleScriptOracle(problem["part"], problem["grid"])
    states: list[dict[str, Any]] = [{"step": 0, "ascii": simulation.render_ascii()}]
    for index, key in enumerate(cert["route"], 1):
        alive, winning = simulation.step(key)
        states.append(
            {
                "step": index,
                "key": key,
                "ascii": simulation.render_ascii(),
                "alive": bool(alive),
                "winning": bool(winning),
            }
        )
    if states[-1]["ascii"] != cert["final_ascii"]:
        raise EvidenceExportError("reconstructed trajectory does not match source final_ascii")
    return states


def _negative_controls(cert: dict[str, Any]) -> list[dict[str, Any]]:
    observations = {
        "rejected_route_promoted_to_verified": (
            "An invalid route promoted to VERIFIED",
            "verify_certificate_gate returned REJECTED_TIER_SWAP",
        ),
        "truncated_prefix_rejected": (
            "The final route key was dropped, leaving R",
            "python_spec_oracle and python_flat_bitmask_oracle both returned exact_win=false",
        ),
        "post_win_extra_key_rejected": (
            "An extra U key was appended after the winning RR route",
            "python_spec_oracle and python_flat_bitmask_oracle both returned exact_win=false",
        ),
    }
    return [
        {
            "name": name,
            "mutation": observations[name][0],
            "observed": observations[name][1],
            "passed": True,
        }
        for name in cert["must_fail_controls"]
    ]


def _mechanics_binding(simgrammar_root: Path | None) -> tuple[list[dict[str, Any]], str]:
    """Bind no search mechanic to a replay-only certificate.

    In particular, SimGrammar's agent-pathfinding definition requires route
    search/least-cost routing. This RR certificate only replays supplied keys,
    so pinning that YAML would claim semantics the source never checked.
    """
    if simgrammar_root is None:
        return [], (
            "SimGrammar unbound: no root was supplied; mechanics=[] and no mechanic "
            "identity or pin was inferred."
        )
    candidate = simgrammar_root / "data" / "mechanics" / "agent-pathfinding.yaml"
    try:
        raw = candidate.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeError):
        return [], (
            "SimGrammar unbound: the supplied root or agent-pathfinding candidate is "
            "unavailable/unreadable; mechanics=[] and no pins were fabricated."
        )
    if not text.startswith("id: agent-pathfinding\n"):
        return [], (
            "SimGrammar unbound: agent-pathfinding.yaml has an unexpected identity; "
            "mechanics=[] and no pins were fabricated."
        )
    return [], (
        "SimGrammar unbound: agent-pathfinding.yaml was inspected but not pinned because "
        "it owns agent route search and least-cost routing; this source only replays "
        "supplied RR keys and establishes neither route search nor minimality; mechanics=[]."
    )


def _base_limitations() -> list[str]:
    return [
        "VERIFIED is differential model_replay only; it is not model_proof and no formal proof or route minimality is claimed.",
        "The three local engines can share a mistaken interpretation; external_spec_pinned=false and no live original-engine execution is claimed.",
        "source_lock_asserted=false; checker pins preserve implementation/binary hashes but are not independent authenticity or correctness proofs.",
        "The source trajectory commitment is its original 64-bit FNV-1a digest; the exported ASCII trajectory does not reconstruct hidden per-frame state for other boards.",
        "Structural envelope validation alone does not independently accept the domain verdict; consumers must trust or independently rerun the pinned Soko verifier.",
    ]


def _build_artifact(
    cert: dict[str, Any],
    raw: bytes,
    producer: dict[str, str],
    mechanics: list[dict[str, Any]],
    mechanics_limitation: str,
) -> dict[str, Any]:
    _certificate_semantics(cert)
    if mechanics:
        raise EvidenceExportError("this replay-only adapter cannot emit SimGrammar mechanic pins")
    problem = cert["problem"]
    actions = [{"step": index, "key": key} for index, key in enumerate(cert["route"], 1)]
    trajectory = _trajectory(cert)
    initial_state_sha256 = json_sha256(problem)
    actions_sha256 = json_sha256(actions)
    trajectory_sha256 = json_sha256(trajectory)
    if initial_state_sha256 != cert["instance_sha256"]:
        raise EvidenceExportError("initial-state commitment differs from source instance_sha256")
    checker_bundle = {
        "engines_executed": cert["engines_executed"],
        "checker_pins": cert["checker_pins"],
    }
    outcome = {
        "alive": cert["alive"],
        "exact_win": cert["exact_win"],
        "premature_win": cert["premature_win"],
        "steps_executed": cert["steps_executed"],
        "final_ascii": cert["final_ascii"],
        "source_epistemic_status": cert["epistemic_status"],
        "source_evidence_level": cert["evidence_level"],
        "source_formal_proof_checked": cert["formal_proof_checked"],
        "source_external_spec_pinned": cert["external_spec_pinned"],
        "source_lock_asserted": cert["source_lock_asserted"],
        "source_certificate_sha256": cert["certificate_sha256"],
        "source_route_sha256": cert["route_sha256"],
        "source_route_sha256_12": cert["route_sha256_12"],
        "source_trajectory_fnv64": cert["traj_fnv64"],
        "source_trajectory_digest_match": cert["trajectory_digest_match"],
        "source_engines_executed": cert["engines_executed"],
        "source_checker_pins": copy.deepcopy(cert["checker_pins"]),
    }
    artifact: dict[str, Any] = {
        "schema": SCHEMA,
        "artifact_sha256": "",
        "producer": copy.deepcopy(producer),
        "claim": {
            "id": "soko-heroes-rr-three-engine-route",
            "kind": "route",
            "statement": (
                "On the heroes-of-sokoban-ascii-v1 F.G instance, the supplied RR route "
                "reaches exact_win alive on the final key in three matching local model replays."
            ),
        },
        "mechanics": copy.deepcopy(mechanics),
        "payload": {
            "domain": SOURCE_ADAPTER,
            "model": {
                "adapter": SOURCE_ADAPTER,
                "transition_semantics": "UDLRA keys; alive; first win required on the final key",
                "cost_semantics": "number of UDLRA keys; no minimality claim",
                "source_instance_sha256": cert["instance_sha256"],
                "source_evidence_level": cert["evidence_level"],
                "engines_executed": cert["engines_executed"],
            },
            "model_sha256": "",
            "initial_state": copy.deepcopy(problem),
            "initial_state_sha256": initial_state_sha256,
            "actions": actions,
            "actions_sha256": actions_sha256,
            "trajectory": trajectory,
            "trajectory_sha256": trajectory_sha256,
            "outcome": outcome,
        },
        "evidence": {
            "checks": [
                {
                    "kind": "model_replay",
                    "status": "PASS",
                    "checker": {
                        "name": "soko_mcp.engine_bridge.verify_route_dual+soko_mcp.evidence.verify_certificate_gate",
                        "revision": producer["revision"],
                        "artifact_sha256": json_sha256(checker_bundle),
                    },
                    "source_labels": [cert["epistemic_status"], cert["evidence_level"]],
                    "initial_state_sha256": initial_state_sha256,
                    "actions_sha256": actions_sha256,
                    "trajectory_sha256": trajectory_sha256,
                }
            ],
            "negative_controls": _negative_controls(cert),
            "limitations": _base_limitations() + [mechanics_limitation],
        },
        "source": {
            "media_type": "application/json",
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "raw": raw.decode("utf-8"),
        },
    }
    artifact["payload"]["model_sha256"] = json_sha256(artifact["payload"]["model"])
    artifact["artifact_sha256"] = artifact_digest(artifact)
    return artifact


def _producer(revision: str) -> dict[str, str]:
    if HEX_40.fullmatch(revision) is None:
        raise EvidenceExportError("producer/checker revision must be 40 lowercase hex characters")
    return {"repository": "ahrazzle/soko", "revision": revision, "adapter": ADAPTER}


def export_bytes(
    raw: bytes,
    *,
    revision: str,
    simgrammar_root: Path | None = None,
) -> dict[str, Any]:
    """Verify and export exact source bytes. No output is returned on rejection."""
    if not isinstance(raw, bytes):
        raise EvidenceExportError("raw source must be bytes to preserve its exact encoding")
    cert = parse_certificate(raw)
    reverify_source(cert)
    mechanics, mechanics_limitation = _mechanics_binding(simgrammar_root)
    return _build_artifact(
        cert, raw, _producer(revision), mechanics, mechanics_limitation
    )


def export_file(
    certificate: Path = DEFAULT_CERTIFICATE,
    *,
    revision: str,
    simgrammar_root: Path | None = None,
) -> dict[str, Any]:
    return export_bytes(
        certificate.read_bytes(), revision=revision, simgrammar_root=simgrammar_root
    )


def validate_artifact(artifact: dict[str, Any], *, reverify: bool = False) -> None:
    """Fail closed on envelope tampering, source-label promotion, or dropped controls.

    Validation reconstructs the deterministic projection from the parsed source;
    therefore recomputing digests after a mutation does not make it acceptable.
    """
    if not isinstance(artifact, dict):
        raise EvidenceExportError("artifact must be a JSON object")
    expected_top = {
        "schema", "artifact_sha256", "producer", "claim", "mechanics", "payload", "evidence", "source"
    }
    if set(artifact) != expected_top or artifact.get("schema") != SCHEMA:
        raise EvidenceExportError("invalid gameplay-evidence/v0.1 top-level envelope")
    if artifact.get("artifact_sha256") != artifact_digest(artifact):
        raise EvidenceExportError("artifact_sha256 mismatch")
    payload = artifact.get("payload")
    if not isinstance(payload, dict):
        raise EvidenceExportError("payload must be an object")
    expected_payload = {
        "domain", "model", "model_sha256", "initial_state", "initial_state_sha256",
        "actions", "actions_sha256", "trajectory", "trajectory_sha256", "outcome",
    }
    if set(payload) != expected_payload:
        raise EvidenceExportError("payload has missing or unknown keys")
    for field, digest_field in (
        ("model", "model_sha256"),
        ("initial_state", "initial_state_sha256"),
        ("actions", "actions_sha256"),
        ("trajectory", "trajectory_sha256"),
    ):
        if payload[digest_field] != json_sha256(payload[field]):
            raise EvidenceExportError(f"payload {digest_field} mismatch")
    if not isinstance(payload["actions"], list) or not isinstance(payload["trajectory"], list):
        raise EvidenceExportError("actions and trajectory must be arrays")
    source = artifact.get("source")
    if not isinstance(source, dict) or set(source) != {"media_type", "raw_sha256", "raw"}:
        raise EvidenceExportError("invalid source envelope")
    if not isinstance(source["raw"], str):
        raise EvidenceExportError("source.raw must be text")
    raw = source["raw"].encode("utf-8")
    if source["raw_sha256"] != hashlib.sha256(raw).hexdigest():
        raise EvidenceExportError("source.raw_sha256 mismatch")
    cert = parse_certificate(raw)
    if reverify:
        reverify_source(cert)
    mechanics_limitations = [
        item for item in artifact.get("evidence", {}).get("limitations", [])
        if isinstance(item, str) and item.startswith("SimGrammar unbound:")
    ]
    if len(mechanics_limitations) != 1:
        raise EvidenceExportError("exactly one explicit SimGrammar unbound limitation is required")
    expected = _build_artifact(
        cert,
        raw,
        artifact["producer"],
        artifact["mechanics"],
        mechanics_limitations[0],
    )
    expected["artifact_sha256"] = artifact["artifact_sha256"]
    if artifact != expected:
        raise EvidenceExportError(
            "artifact differs from the verified source projection (payload, checks, controls, labels, or limits)"
        )


def _head_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _load_artifact(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_json_object, parse_constant=_reject_json_constant
        )
    except (UnicodeError, json.JSONDecodeError, EvidenceExportError) as exc:
        raise EvidenceExportError(f"invalid artifact JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceExportError("artifact must be a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    export = subparsers.add_parser("export", help="Reverify RR and emit gameplay-evidence/v0.1")
    export.add_argument("--certificate", type=Path, default=DEFAULT_CERTIFICATE)
    export.add_argument("--output", type=Path, help="Output JSON path; omit for stdout")
    export.add_argument("--simgrammar-root", type=Path)
    export.add_argument("--revision", help="40-hex producer/checker source commit (default: git HEAD)")
    validate = subparsers.add_parser("validate", help="Validate an exported artifact without mcproof")
    validate.add_argument("artifact", type=Path)
    validate.add_argument(
        "--reverify", action="store_true", help="Also rerun the required three-engine source verifier"
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            artifact = export_file(
                args.certificate,
                revision=args.revision or _head_revision(),
                simgrammar_root=args.simgrammar_root,
            )
            validate_artifact(artifact, reverify=False)
            encoded = json.dumps(artifact, indent=2, ensure_ascii=True) + "\n"
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(encoded, encoding="utf-8", newline="")
                print(json.dumps({"status": "EXPORTED", "output": str(args.output),
                                  "artifact_sha256": artifact["artifact_sha256"]}, indent=2))
            else:
                sys.stdout.write(encoded)
        else:
            artifact = _load_artifact(args.artifact)
            validate_artifact(artifact, reverify=args.reverify)
            print(json.dumps({"status": "VALID", "artifact_sha256": artifact["artifact_sha256"],
                              "source_reverified": args.reverify}, indent=2))
    except (EvidenceExportError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "REJECTED", "error": str(exc)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
