"""Canonical input boundary and identity for empirical Sokoban evidence."""
from __future__ import annotations

import hashlib
import json


def validate_room(part: int, grid: list[str]) -> None:
    """Reject malformed/vacuous starts before any interpreter or native code runs.

    This flat ASCII format cannot represent a hero initially on a goal. It is
    deliberately a canonical starting-room interface, not a saved-state format.
    """
    if type(part) is not int or part not in (1, 2, 3):
        raise ValueError("part must be an integer in 1, 2, 3")
    if not isinstance(grid, list) or not grid or not all(isinstance(row, str) and row for row in grid):
        raise ValueError("grid must contain nonempty text rows")
    if any(len(row) != len(grid[0]) for row in grid):
        raise ValueError("grid must be rectangular")
    if len(grid) * len(grid[0]) > 512:
        raise ValueError("grid must contain at most 512 cells")
    if any(ch not in ".#*GFTWPBD123456OLRM[]{}" for row in grid for ch in row):
        raise ValueError("grid contains an unsupported symbol")
    active = "FTWPBD"
    identities = {hero: str(i + 1) for i, hero in enumerate(active)}
    heroes = [identities.get(ch, ch) for row in grid for ch in row if ch in active + "123456"]
    if sum(ch in active for row in grid for ch in row) < 1 or len(set(heroes)) != len(heroes):
        raise ValueError("canonical starting rooms require at least one active hero and distinct hero identities")
    if sum(row.count("G") for row in grid) != len(heroes):
        raise ValueError("canonical starting rooms require one goal per hero")


def normalize_route(route: str) -> str:
    if not isinstance(route, str):
        raise ValueError("route must be text")
    clean = route.strip().upper()
    if any(ch not in "UDLRA" for ch in clean):
        raise ValueError("route must contain only U D L R A")
    return clean


def digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def problem_identity(part: int, grid: list[str]) -> dict:
    problem = {
        "adapter": "heroes-of-sokoban-ascii-v1", "part": part, "grid": grid,
        "goal": "heroes occupy exactly the goal cells",
        "termination": "alive and first win on final key", "cost": "number of UDLRA keys",
    }
    return {"problem": problem, "instance_sha256": digest(problem)}


def must_fail(name: str, predicate_holds: bool, log: list[str]) -> None:
    """Record a must-fail negative control (modeled on Foundation-0 certlib.must_fail).

    `predicate_holds` is the checker's acceptance verdict on a deliberately broken
    or tautological input. The control passes only when `predicate_holds` is False.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("must_fail control name must be a non-empty string")
    if bool(predicate_holds):
        raise ValueError(f"must_fail control '{name}' was wrongly accepted")
    log.append(name.strip())


def verify_certificate_gate(cert: dict) -> dict:
    """Fail-closed certificate gate enforcing `must_fail_controls`, hash integrity, and anti-tier-swap rules."""
    if not isinstance(cert, dict):
        return {"passed": False, "epistemic_status": "REJECTED_MALFORMED_CERTIFICATE", "reason": "certificate must be a dict"}

    if "certificate_sha256" in cert:
        expected_hash = digest({k: v for k, v in cert.items() if k != "certificate_sha256"})
        if cert.get("certificate_sha256") != expected_hash:
            return {
                "passed": False,
                "epistemic_status": "REJECTED_CERTIFICATE_HASH_MISMATCH",
                "reason": "certificate_sha256 does not match canonical payload digest",
            }

    status = str(cert.get("epistemic_status", "")).strip()
    if not status:
        return {"passed": False, "epistemic_status": "REJECTED_MISSING_STATUS", "reason": "missing epistemic_status"}

    controls = cert.get("must_fail_controls")
    if status in ("PROVEN", "VERIFIED", "LOWER_BOUND", "LOWER_BOUND_UNWITNESSED"):
        if (
            not isinstance(controls, list)
            or len(controls) == 0
            or any(not isinstance(c, str) or not c.strip() for c in controls)
            or len(set(controls)) != len(controls)
        ):
            return {
                "passed": False,
                "epistemic_status": "REJECTED_MISSING_MUST_FAIL_CONTROLS",
                "reason": "certificate must carry a non-empty list of distinct must_fail_controls names",
            }

    # Anti-tier-swap checks (LOWER_BOUND / LINT_PASS / bounded-subgraph promoted to VERIFIED or PROVEN)
    kind = str(cert.get("certificate_kind", ""))
    claim_kind = str(cert.get("claim_kind", "")).lower()
    if status == "VERIFIED":
        if cert.get("mode") in ("single_checker", "dual_checker"):
            return {
                "passed": False,
                "epistemic_status": "REJECTED_TIER_SWAP",
                "reason": "static AST lint report cannot claim VERIFIED (must be LINT_PASS)",
            }
        if claim_kind in ("lower_bound", "bound") and not cert.get("exact_optimum_reached", False):
            return {
                "passed": False,
                "epistemic_status": "REJECTED_TIER_SWAP",
                "reason": "lower-bound claim without exact optimal witness cannot be promoted to VERIFIED",
            }
        if "proven_floor" in cert and "exact_optimum_reached" in cert:
            witness = cert.get("winning_witness")
            if (
                not bool(cert.get("exact_optimum_reached"))
                or cert.get("optimality_proven") is False
                or (int(cert.get("proven_floor") or 0) > 0 and not isinstance(witness, dict))
                or (isinstance(witness, dict) and witness.get("route_len") != cert.get("proven_floor"))
            ):
                return {
                    "passed": False,
                    "epistemic_status": "REJECTED_TIER_SWAP",
                    "reason": "unwitnessed or non-exact floor bound cannot be promoted to VERIFIED",
                }
        if kind.endswith("_LOWER_BOUND") and not cert.get("winning_witness"):
            return {
                "passed": False,
                "epistemic_status": "REJECTED_TIER_SWAP",
                "reason": f"lower-bound certificate ({kind}) without matching primal witness cannot claim VERIFIED",
            }
        if "valid_winning_route" in cert and cert.get("valid_winning_route") is not True:
            return {
                "passed": False,
                "epistemic_status": "REJECTED_TIER_SWAP",
                "reason": "rejected route certificate cannot be promoted to VERIFIED",
            }

    if status == "PROVEN":
        if cert.get("complete_domain_closed") is False:
            return {
                "passed": False,
                "epistemic_status": "REJECTED_TIER_SWAP",
                "reason": "bounded-subgraph check (complete_domain_closed=False) cannot be promoted to PROVEN",
            }
        if "proven_floor" in cert and not cert.get("formal_proof_checked", False):
            return {
                "passed": False,
                "epistemic_status": "REJECTED_TIER_SWAP",
                "reason": "empirical search floor without formal proof cannot be promoted to PROVEN",
            }

    return {"passed": True, "epistemic_status": status, "must_fail_controls": list(controls or [])}
