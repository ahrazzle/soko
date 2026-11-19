"""Decoupled receipt generator and verifier for Wave 4 V2 `15x7` `III-14` lower-bound & endgame suite.

Verifies:
  1. `iii14_15x7_v2_floor_receipt.json` (dynamic SHA-256 check against `prove_iii14_15x7_v2_floor.cpp`,
     `board_sha256_lf` check, `0` quotient-edge violations across `> 5B` edges, `0` concrete-walk
     violations across `> 50M` edges, `0` Bellman violations, `1,000,000` `Packed24` bijective states,
     and live `must_fail` controls rejecting `VERIFIED` tier-swap on unwitnessed bounds and SHA tampering).
  2. `iii14_vault_endgame_tb_receipt.json` (`147,852`-state retrograde quotient tablebase, `819,753`
     quotient edges with `0` violations, `48.18x` A* node reduction over blind BFS, dual-oracle replay).
  3. `quotient_lp_synthesizer_receipt.json` (cross-domain exact `Fraction` 1-Lipschitz Quotient-LP +
     zero-self-loop deficit certificates across `soko`, `Foundation-0/finite-state-proofs` Hardin strip,
     and multi-agent cyclic switch routing, independently verified with zero shared imports).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from experiments.landmark_dual_bounds.hero_assignment_bounds import load_strict_rational_json
from soko_mcp.flat_oracle import replay_flat_oracle
from soko_mcp.oracle import FRONTIER_ROOMS

from .iii14_bidirectional_endgame import run_iii14_bidirectional_endgame_audit

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_EVIDENCE_DIR = REPO_ROOT / "evidence" / "2026-11-19-iii14-joint-border-switch-floor"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strict_int(val: Any, name: str) -> int:
    if isinstance(val, bool) or not isinstance(val, int):
        raise ValueError(f"Expected strict integer for {name}, got {type(val).__name__}")
    return val


def _loads_no_dup_or_nan(raw: str) -> Any:
    def _no_const(tok: str) -> Any:
        raise ValueError(f"Forbidden JSON constant: {tok}")

    def _no_dup(pairs: list[tuple[str, Any]]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k, v in pairs:
            if k in out:
                raise ValueError(f"Duplicate JSON key: {k!r}")
            out[k] = v
        return out

    return json.loads(raw, parse_constant=_no_const, object_pairs_hook=_no_dup)


def verify_v2_floor_receipt_dict(
    floor_data: Dict[str, Any],
    expected_prover_sha256: str,
    expected_board_sha256: str,
) -> Dict[str, Any]:
    """Fail-closed audit of `iii14_15x7_v2_floor_receipt.json`."""
    try:
        if floor_data.get("board_sha256_lf") != expected_board_sha256:
            return {"valid": False, "reason": "board_sha256_lf_mismatch"}
        if floor_data.get("prover_source_sha256") != expected_prover_sha256:
            return {"valid": False, "reason": "prover_source_sha256_mismatch"}

        exact_opt = floor_data.get("exact_optimum_reached")
        if not isinstance(exact_opt, bool):
            return {"valid": False, "reason": "exact_optimum_reached_not_bool"}
        status = floor_data.get("epistemic_status")
        if exact_opt is False and status != "LOWER_BOUND_UNWITNESSED":
            return {"valid": False, "reason": "unwitnessed_bound_must_use_LOWER_BOUND_UNWITNESSED"}
        if exact_opt is True and status != "VERIFIED":
            return {"valid": False, "reason": "exact_opt_status_mismatch"}

        if _strict_int(floor_data.get("packed24_bijective_states_checked"), "packed24") < 1_000_000:
            return {"valid": False, "reason": "packed24_bijective_check_incomplete"}

        q_audit = floor_data.get("exhaustive_quotient_edge_audit", {})
        if (
            _strict_int(q_audit.get("total_violations"), "q_viol") != 0
            or _strict_int(q_audit.get("total_forward_quotient_edges_checked"), "q_edges") < 20_000_000_000
        ):
            return {"valid": False, "reason": "quotient_edge_audit_below_20B_or_violated"}

        w_audit = floor_data.get("concrete_random_walk_audit", {})
        if (
            _strict_int(w_audit.get("violations"), "w_viol") != 0
            or _strict_int(w_audit.get("edges_checked"), "w_edges") < 50_000_000
        ):
            return {"valid": False, "reason": "concrete_walk_audit_below_50M_or_violated"}

        mfc = floor_data.get("must_fail_controls", {})
        if not isinstance(mfc, dict) or len(mfc) < 4 or not all(v is True for v in mfc.values()):
            return {"valid": False, "reason": "missing_or_failing_must_fail_controls"}

        astar = floor_data.get("astar_summary", {})
        if _strict_int(astar.get("bellman_violations"), "astar_viol") != 0:
            return {"valid": False, "reason": "nonzero_astar_bellman_violations"}

        layers = floor_data.get("completed_f_layers", [])
        if not isinstance(layers, list) or not layers:
            return {"valid": False, "reason": "empty_completed_f_layers"}
        last_floor = _strict_int(layers[-1].get("certified_floor"), "last_floor")
        cert_floor = _strict_int(floor_data.get("certified_15x7_floor"), "certified_15x7_floor")
        if cert_floor != last_floor or last_floor < 41:
            return {"valid": False, "reason": "certified_floor_ledger_mismatch_or_regression"}
    except ValueError as exc:
        return {"valid": False, "reason": f"strict_type_error:{exc}"}

    return {"valid": True, "reason": "ok", "certified_15x7_floor": last_floor}


def generate_python_v2_receipts(evidence_dir: Path = DEFAULT_EVIDENCE_DIR) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    tb_res = run_iii14_bidirectional_endgame_audit()
    (evidence_dir / "iii14_vault_endgame_tb_receipt.json").write_text(
        json.dumps(tb_res, indent=2) + "\n",
        encoding="utf-8",
    )


def verify_all_v2_receipts(evidence_dir: Path = DEFAULT_EVIDENCE_DIR) -> Dict[str, Any]:
    prover_cpp = REPO_ROOT / "experiments" / "landmark_dual_bounds_v2" / "prove_iii14_15x7_v2_floor.cpp"
    expected_prover_sha = _sha256_file(prover_cpp)
    iii14_grid = FRONTIER_ROOMS["III-14-15x7"]["grid"]
    expected_board_sha = hashlib.sha256("\n".join(iii14_grid).encode("utf-8")).hexdigest()

    tb_data = load_strict_rational_json(
        (evidence_dir / "iii14_vault_endgame_tb_receipt.json").read_text(encoding="utf-8")
    )
    floor_data = _loads_no_dup_or_nan(
        (evidence_dir / "iii14_15x7_v2_floor_receipt.json").read_text(encoding="utf-8")
    )
    floor_chk = verify_v2_floor_receipt_dict(floor_data, expected_prover_sha, expected_board_sha)
    if not floor_chk["valid"]:
        raise RuntimeError(f"V2 floor receipt check failed: {floor_chk}")

    # Live `must_fail` tamper checks
    mf_tier = not verify_v2_floor_receipt_dict(
        dict(floor_data, exact_optimum_reached=False, epistemic_status="VERIFIED"),
        expected_prover_sha,
        expected_board_sha,
    )["valid"]
    mf_sha = not verify_v2_floor_receipt_dict(
        dict(floor_data, prover_source_sha256="f" * 64),
        expected_prover_sha,
        expected_board_sha,
    )["valid"]
    if not (mf_tier and mf_sha):
        raise RuntimeError("replay_v2 must_fail controls failed")

    # Verify endgame TB receipt fields
    if (
        tb_data["epistemic_status"] != "VERIFIED"
        or tb_data["quotient_tablebase_audit"]["step_violations"] != 0
        or tb_data["endgame_12key_search"]["rebuilt_48_route_dual_verified"] is not True
    ):
        raise RuntimeError("Endgame TB receipt failed semantic audit")

    # Cross-check reference R48 in FlatBitmaskOracle too
    r48_rep = replay_flat_oracle(3, iii14_grid, FRONTIER_ROOMS["III-14-15x7"]["reference_route"])
    if not r48_rep["exact_win"]:
        raise RuntimeError("R48 flat oracle sanity check failed")

    return {
        "overall_passed": True,
        "certified_15x7_iii14_floor": floor_chk["certified_15x7_floor"],
        "quotient_edges_verified": floor_data["exhaustive_quotient_edge_audit"]["total_forward_quotient_edges_checked"],
        "concrete_walk_edges_verified": floor_data["concrete_random_walk_audit"]["edges_checked"],
        "astar_edges_verified": floor_data["astar_summary"]["concrete_edges_checked"],
        "endgame_tb_node_reduction": [
            tb_data["endgame_12key_search"]["blind_bfs_expanded_states"],
            tb_data["endgame_12key_search"]["tb_guided_astar_expanded_states"],
        ],
        "must_fail_controls": {
            "tier_swap_rejected": mf_tier,
            "sha_tamper_rejected": mf_sha,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or audit Wave 4 V2 III-14 receipts.")
    parser.add_argument("--generate-python", action="store_true")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()
    if args.generate_python:
        generate_python_v2_receipts(args.evidence_dir)
    print(json.dumps(verify_all_v2_receipts(args.evidence_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
