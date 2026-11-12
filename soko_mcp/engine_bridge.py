"""Hardened multi-oracle bridge between Python MCP tools, FlatBitmaskOracle, and C++20 `soko_engine`.

v0.3.0 Soundness & Capability Guarantees:
- F-01 Fix: `verify_route_dual` is strictly fail-closed (`differential_match` starts `False`), always executes
  AT LEAST TWO zero-shared-code independent engines (`PuzzleScriptOracle` + `FlatBitmaskOracle`), and executes
  ALL THREE (`+ C++20 soko_engine`) whenever a C++20 compiler is available and `w * h <= 512`.
- F-02 Fix: Asserts bit-exact 64-bit FNV-1a per-frame trajectory digest (`traj_fnv64`) parity across every step
  `t = 0..L` (including hidden Bard `Note` masks and open-door flags), not merely terminal ASCII.
- F-03 / F-08 Fix: `verify_tcb_lock()` enforces `REPO_ROOT` path confinement (`unconfined_paths` check), verifies
  `SHA256SUMS` at runtime, and attaches cryptographic `checker_pins` to every `VERIFIED` certificate.
- F-04 / F-09 / F-10 Fix: Surfaces exact-state deduplication stats, `PairAtomQuotientPDB` + `BardDruidQuotientPDB`
  activation, Wizard-ray lower bounds, and strict fail-closed C++ epistemic & witness checks in `prove_floor_verified`.
- Capabilities Contract: `get_capabilities()` reports executable backend readiness honestly, distinguishing missing
  backends (`BACKEND_UNAVAILABLE`) from search budget exhaustion (`UNSOLVED_WITHIN_BUDGET`).
"""
from __future__ import annotations

from collections import deque
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from .catalog import get_room, load_catalog
from .evidence import digest, problem_identity, validate_room
from .flat_oracle import replay_flat_oracle
from .oracle import FRONTIER_ROOMS, PuzzleScriptOracle, replay_oracle

REPO_ROOT = Path(__file__).resolve().parent.parent
CPP_SRC = REPO_ROOT / "cpp" / "soko_engine.cpp"
CPP_BIN_DIR = REPO_ROOT / "cpp" / "build"
CPP_BIN = CPP_BIN_DIR / ("soko_engine.exe" if os.name == "nt" else "soko_engine")
SHA256SUMS_PATH = REPO_ROOT / "SHA256SUMS"


def _file_sha256(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def get_soko_checker_pins() -> Dict[str, Optional[str]]:
    pkg_dir = Path(__file__).resolve().parent
    return {
        "oracle_py_sha256": _file_sha256(pkg_dir / "oracle.py"),
        "flat_oracle_py_sha256": _file_sha256(pkg_dir / "flat_oracle.py"),
        "engine_bridge_py_sha256": _file_sha256(pkg_dir / "engine_bridge.py"),
        "evidence_py_sha256": _file_sha256(pkg_dir / "evidence.py"),
        "integrity_py_sha256": _file_sha256(pkg_dir / "integrity.py"),
        "catalog_py_sha256": _file_sha256(pkg_dir / "catalog.py"),
        "cpp_soko_engine_src_sha256": _file_sha256(CPP_SRC),
        "cpp_soko_engine_bin_sha256": _file_sha256(CPP_BIN),
        "formal_kernel_py_sha256": _file_sha256(pkg_dir / "formal_kernel.py"),
    }


def _required_checker_pins_ok(pins: Dict[str, Optional[str]]) -> bool:
    for key in (
        "oracle_py_sha256",
        "flat_oracle_py_sha256",
        "engine_bridge_py_sha256",
        "evidence_py_sha256",
        "cpp_soko_engine_src_sha256",
        "cpp_soko_engine_bin_sha256",
        "formal_kernel_py_sha256",
    ):
        if not pins.get(key):
            return False
    return True


def _runtime_tcb_locked() -> Tuple[bool, Dict[str, Any]]:
    lock = verify_tcb_lock()
    return bool(lock.get("tcb_locked")), lock


def _is_confined_to_repo(rel_path: str) -> Tuple[bool, Optional[Path]]:
    raw_p = Path(rel_path)
    if raw_p.is_absolute() or ".." in raw_p.parts:
        return False, None
    root_resolved = REPO_ROOT.resolve()
    candidate = (REPO_ROOT / raw_p).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        return False, None
    return True, candidate


def verify_tcb_lock() -> Dict[str, Any]:
    """Verify runtime SHA256SUMS integrity with strict REPO_ROOT confinement + TCB checker pins."""
    cpp_bin = ensure_cpp_engine()
    pins = get_soko_checker_pins()
    required_pin_keys = (
        "oracle_py_sha256",
        "flat_oracle_py_sha256",
        "cpp_soko_engine_src_sha256",
        "formal_kernel_py_sha256",
    )
    checker_pins_ok = all(bool(pins.get(k)) for k in required_pin_keys)

    manifest_present = SHA256SUMS_PATH.is_file()
    checked_files = 0
    mismatched: List[Dict[str, str]] = []
    missing: List[str] = []
    unconfined_paths: List[str] = []

    if manifest_present:
        for raw_line in SHA256SUMS_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) != 2:
                unconfined_paths.append(line)
                continue
            expected_hash, rel_path = parts[0].strip(), parts[1].strip().lstrip("*")
            confined, target = _is_confined_to_repo(rel_path)
            if not confined or target is None:
                unconfined_paths.append(rel_path)
                continue
            actual_hash = _file_sha256(target)
            checked_files += 1
            if actual_hash is None:
                missing.append(rel_path)
            elif actual_hash != expected_hash:
                mismatched.append({"file": rel_path, "expected": expected_hash, "actual": actual_hash})

    ok = (
        manifest_present
        and checked_files > 0
        and checker_pins_ok
        and not unconfined_paths
        and not mismatched
        and not missing
    )
    return {
        "epistemic_status": "VERIFIED" if ok else "TAMPERED_OR_UNLOCKED",
        "tcb_locked": ok,
        "manifest_present": manifest_present,
        "checker_pins_ok": checker_pins_ok,
        "files_verified": checked_files,
        "unconfined_paths": unconfined_paths,
        "mismatched_files": mismatched,
        "missing_files": missing,
        "cpp_engine_compiled": cpp_bin is not None,
        "checker_pins": pins,
    }


def get_capabilities() -> Dict[str, Any]:
    """Report executable runtime capabilities honestly, separating backend availability from search budgets."""
    cpp_bin = ensure_cpp_engine()
    cpp_ready = cpp_bin is not None
    reason: Optional[str] = None
    if not cpp_ready:
        reason = "missing_cpp_source" if not CPP_SRC.is_file() else "cpp_compile_unavailable_or_failed"
    pkg_dir = Path(__file__).resolve().parent
    formal_present = (pkg_dir / "formal_kernel.py").is_file()
    from .original import capability as original_capability

    return {
        "version": "0.3.0",
        "cpp_engine_ready": cpp_ready,
        "cpp_unavailable_reason": reason,
        "route_verification": {
            "available": True,
            "python_oracles": 2,
            "total_oracles": 3 if cpp_ready else 2,
        },
        "route_optimization": {
            "available": True,
            "backend": "cpp20_zero_alloc_lns_and_chiral_beam" if cpp_ready else "python_fallback_window_bfs",
        },
        "solve_from_scratch": {
            "available": cpp_ready,
            "unavailable_reason": reason,
        },
        "lower_bound_proving": {
            "available": cpp_ready,
            "unavailable_reason": reason,
            "abstractions": [
                "BardDruidQuotientPDB",
                "PairAtomQuotientPDB",
                "WizardRayGoalBound",
                "ExactBucketedAStar",
                "ExactDynStateIDAStar",
            ] if cpp_ready else [],
        },
        "formal_systems": {
            "available": formal_present,
            "unavailable_reason": None if formal_present else "missing_formal_kernel",
            "tools": [
                "formal_define_system",
                "formal_verify_trace",
                "formal_solve_system",
                "formal_certify_lower_bound",
                "formal_synthesize_invariant",
                "formal_triage_portfolio",
                "formal_export_ledger",
            ] if formal_present else [],
        },
        "catalog": {
            "original_rooms": len(load_catalog()),
            "parts": [1, 2, 3],
            "offline": True,
            "legacy_fixture_prefix": "fixture:",
        },
        "original_engine": original_capability(),
        "tcb_manifest_present": SHA256SUMS_PATH.is_file(),
        "checker_pins": get_soko_checker_pins(),
    }


def resolve_room_input(
    room_id: Optional[str] = None,
    part: Optional[int] = None,
    grid: Optional[List[str]] = None,
) -> Tuple[Optional[str], int, List[str], Optional[Dict[str, Any]]]:
    if room_id:
        key = room_id.strip()
        if key.startswith("fixture:"):
            fixture = key.removeprefix("fixture:")
            if fixture not in FRONTIER_ROOMS:
                raise ValueError(f"Unknown fixture {fixture!r}")
            import copy

            meta = copy.deepcopy(FRONTIER_ROOMS[fixture])
            meta.update(
                id=key,
                room_id=key,
                is_fixture=True,
                source={"kind": "legacy_repository_fixture", "original_instance_asserted": False},
            )
        else:
            if key == "III-14-15x7":
                key = "III-14"
            try:
                meta = get_room(key)
            except KeyError:
                raise ValueError(
                    f"Unknown room_id {key!r}; use soko_list_rooms for the original catalog."
                ) from None
        return key, int(meta["part"]), list(meta["grid"]), meta
    if part is None or not grid:
        raise ValueError(
            "Provide an original room_id (I-1..III-22), an explicit fixture: ID, or both part and grid."
        )
    validate_room(part, grid)
    return None, part, list(grid), None


def ensure_cpp_engine() -> Optional[Path]:
    """Compile cpp/soko_engine.cpp on demand if g++ or clang++ is available."""
    if not CPP_SRC.is_file():
        return None
    if CPP_BIN.is_file() and CPP_BIN.stat().st_mtime >= CPP_SRC.stat().st_mtime:
        return CPP_BIN
    compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        return None
    CPP_BIN_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="compile-", dir=CPP_BIN_DIR) as temporary:
        candidate = Path(temporary) / CPP_BIN.name
        cmd = [compiler, "-O3", "-pthread", "-std=c++20", str(CPP_SRC), "-o", str(candidate)]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if res.returncode != 0:
            return None
        candidate.replace(CPP_BIN)
    return CPP_BIN


def _invoke_cpp(mode: str, part: int, grid: List[str], p1: int, p2: int, p3: int, route: str = "-") -> Optional[Dict[str, Any]]:
    exe = ensure_cpp_engine()
    if exe is None:
        return None
    h, w = len(grid), len(grid[0])
    if w * h > 512:
        return None
    payload = f"{mode} {part} {w} {h} {p1} {p2} {p3}\n" + "\n".join(grid) + f"\n{route or '-'}\n"
    proc = subprocess.run(
        [str(exe)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=max(30, p3 + 30),
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return json.loads(proc.stdout.strip().splitlines()[-1])


def verify_route_dual(
    part: int,
    grid: List[str],
    route: str,
    require_cpp: bool = False,
    _skip_cpp_for_test: bool = False,
    _skip_flat_for_test: bool = False,
) -> Dict[str, Any]:
    """Fail-closed multi-oracle route verifier (PuzzleScriptOracle + FlatBitmaskOracle + C++20 engine)."""
    clean = route.strip().upper()
    py_res = replay_oracle(part, grid, clean)
    flat_res = None if _skip_flat_for_test else replay_flat_oracle(part, grid, clean)
    cpp_res = None if _skip_cpp_for_test else _invoke_cpp("verify", part, grid, 0, 0, 5, clean or "-")

    engines_executed = ["python_spec_oracle"]
    if flat_res is not None:
        engines_executed.append("python_flat_bitmask_oracle")
    if cpp_res is not None:
        engines_executed.append("cpp20_soko_engine")

    differential_match = False
    trajectory_digest_match = False

    if len(engines_executed) >= 2 and (not require_cpp or cpp_res is not None):
        py_flat_ok = True
        py_flat_traj_ok = True
        if flat_res is not None:
            py_flat_ok = (
                flat_res["alive"] == py_res["alive"]
                and flat_res["exact_win"] == py_res["exact_win"]
                and flat_res["premature_win"] == py_res["premature_win"]
                and flat_res["steps_executed"] == py_res["steps_executed"]
                and flat_res["final_ascii"] == py_res["final_ascii"]
            )
            py_flat_traj_ok = flat_res["traj_fnv64"] == py_res["traj_fnv64"]

        py_cpp_ok = True
        py_cpp_traj_ok = True
        if cpp_res is not None:
            py_cpp_ok = (
                cpp_res.get("alive") == py_res["alive"]
                and cpp_res.get("exact_win") == py_res["exact_win"]
                and cpp_res.get("premature_win") == py_res["premature_win"]
                and cpp_res.get("steps_executed") == py_res["steps_executed"]
                and cpp_res.get("final_ascii") == py_res["final_ascii"]
            )
            py_cpp_traj_ok = cpp_res.get("traj_fnv64") == py_res["traj_fnv64"]

        trajectory_digest_match = py_flat_traj_ok and py_cpp_traj_ok
        differential_match = py_flat_ok and py_cpp_ok and trajectory_digest_match

    dual_or_triple_checked = len(engines_executed) >= 2 and (not require_cpp or cpp_res is not None)
    pins = get_soko_checker_pins()
    pins_ok = _required_checker_pins_ok(pins)
    tcb_locked, _tcb_report = _runtime_tcb_locked()
    is_verified = (
        dual_or_triple_checked
        and differential_match
        and py_res["exact_win"]
        and pins_ok
        and tcb_locked
    )

    if not dual_or_triple_checked:
        epistemic = "REJECTED_INSUFFICIENT_ORACLES"
    elif dual_or_triple_checked and differential_match and py_res["exact_win"] and (not pins_ok or not tcb_locked):
        epistemic = "REJECTED_TCB_UNLOCKED"
    else:
        epistemic = "VERIFIED" if is_verified else "REJECTED"

    return {
        "epistemic_status": epistemic,
        "valid_winning_route": is_verified,
        "route_len": py_res["route_len"],
        "route_sha256_12": py_res["route_sha256_12"],
        "traj_fnv64": py_res["traj_fnv64"],
        "trajectory_digest_match": trajectory_digest_match,
        "alive": py_res["alive"],
        "exact_win": py_res["exact_win"],
        "premature_win": py_res["premature_win"],
        "steps_executed": py_res["steps_executed"],
        "engines_executed": engines_executed,
        "engines_count": len(engines_executed),
        "dual_engine_checked": dual_or_triple_checked,
        "triple_oracle_checked": len(engines_executed) == 3,
        "differential_match": differential_match,
        "checker_pins": pins,
        "checker_pins_ok": pins_ok,
        "final_ascii": py_res["final_ascii"],
        "route": clean,
    }


def _python_window_shortcut(part: int, grid: List[str], route: str, win_len: int = 10) -> str:
    """Pure-Python BFS fallback optimizer when no C++20 compiler is present."""
    best = route.strip().upper()
    sim = PuzzleScriptOracle(part, grid)
    traj = [sim.clone()]
    for ch in best:
        sim.step(ch)
        traj.append(sim.clone())
    n = len(best)
    for left in range(0, n, max(2, win_len // 2)):
        right = min(n, left + win_len)
        targets = {traj[k].state_signature(): k for k in range(left + 2, right + 1)}
        q = deque([(traj[left].clone(), "")])
        seen = {traj[left].state_signature()}
        max_d = (right - left) - 1
        while q and len(seen) < 15000:
            cur_s, path = q.popleft()
            if len(path) >= max_d:
                continue
            for mv in ("U", "D", "L", "R", "A"):
                ns = cur_s.clone()
                alive, won = ns.step(mv)
                if not alive:
                    continue
                np = path + mv
                if won and left + len(np) < n:
                    return best[:left] + np
                sig = ns.state_signature()
                if sig in targets and len(np) < (targets[sig] - left):
                    return best[:left] + np + best[targets[sig]:]
                if len(np) < max_d and sig not in seen:
                    seen.add(sig)
                    q.append((ns, np))
    return best


def optimize_route_verified(
    part: int,
    grid: List[str],
    seed_route: str,
    beam_width: int = 40000,
    window_len: int = 14,
    budget_sec: int = 35,
) -> Dict[str, Any]:
    clean_seed = seed_route.strip().upper()
    seed_check = verify_route_dual(part, grid, clean_seed)
    if not seed_check["valid_winning_route"]:
        raise ValueError(
            f"seed_route (len={len(clean_seed)}) is not a valid winning route for this room: "
            f"alive={seed_check['alive']}, exact_win={seed_check['exact_win']}, premature_win={seed_check['premature_win']}"
        )

    cpp_out = _invoke_cpp("optimize", part, grid, beam_width, window_len, budget_sec, clean_seed)
    if cpp_out is not None and "best_route" in cpp_out:
        cand_route = cpp_out["best_route"]
        stages = cpp_out.get("stages", [])
        backend = "cpp20_zero_alloc_engine"
    else:
        cand_route = _python_window_shortcut(part, grid, clean_seed, min(10, window_len))
        stages = ["python_fallback_window_bfs"] if len(cand_route) < len(clean_seed) else []
        backend = "python_fallback"

    cand_check = verify_route_dual(part, grid, cand_route)
    if not cand_check["valid_winning_route"]:
        raise RuntimeError("Optimizer produced a candidate route that failed multi-oracle differential verification!")

    return {
        "epistemic_status": "VERIFIED",
        "backend": backend,
        "initial_len": len(clean_seed),
        "best_len": cand_check["route_len"],
        "keys_saved": len(clean_seed) - cand_check["route_len"],
        "improved": cand_check["route_len"] < len(clean_seed),
        "best_route": cand_check["route"],
        "best_route_sha256_12": cand_check["route_sha256_12"],
        "traj_fnv64": cand_check["traj_fnv64"],
        "stages": stages,
        "dual_oracle_verified": True,
        "triple_oracle_checked": cand_check["triple_oracle_checked"],
        "differential_match": cand_check["differential_match"],
        "checker_pins": cand_check["checker_pins"],
    }


def solve_room_verified(
    part: int,
    grid: List[str],
    max_depth: int = 120,
    beam_width: int = 40000,
    budget_sec: int = 20,
) -> Dict[str, Any]:
    if len(grid) * len(grid[0]) > 512:
        return {
            "epistemic_status": "BACKEND_UNAVAILABLE",
            "solved": False,
            "unavailable_reason": "grid_exceeds_512_cells",
            "states_explored": 0,
        }
    if ensure_cpp_engine() is None:
        return {
            "epistemic_status": "BACKEND_UNAVAILABLE",
            "solved": False,
            "unavailable_reason": "missing_cpp_source" if not CPP_SRC.is_file() else "cpp_compile_unavailable_or_failed",
            "states_explored": 0,
        }
    cpp_out = _invoke_cpp("solve", part, grid, max_depth, beam_width, budget_sec, "-")
    if cpp_out is None:
        return {
            "epistemic_status": "BACKEND_UNAVAILABLE",
            "solved": False,
            "unavailable_reason": "cpp_invocation_failed",
            "states_explored": 0,
        }
    if cpp_out.get("solved"):
        route = cpp_out["route"]
        v = verify_route_dual(part, grid, route)
        if not v["valid_winning_route"]:
            raise RuntimeError("Solver candidate failed multi-oracle verification!")
        return {
            "epistemic_status": "VERIFIED",
            "solved": True,
            "route_len": v["route_len"],
            "route": v["route"],
            "route_sha256_12": v["route_sha256_12"],
            "traj_fnv64": v["traj_fnv64"],
            "states_explored": cpp_out.get("explored", 0),
            "dual_oracle_verified": True,
            "triple_oracle_checked": v["triple_oracle_checked"],
            "checker_pins": v["checker_pins"],
        }
    return {
        "epistemic_status": "UNSOLVED_WITHIN_BUDGET",
        "solved": False,
        "states_explored": cpp_out.get("explored", 0),
    }


def prove_floor_verified(
    part: int,
    grid: List[str],
    max_bound: int = 30,
    budget_sec: int = 15,
) -> Dict[str, Any]:
    validate_room(part, grid)
    tcb_locked, tcb_report = _runtime_tcb_locked()
    if not tcb_locked or not _required_checker_pins_ok(get_soko_checker_pins()):
        return {
            "epistemic_status": "REJECTED_TCB_UNLOCKED",
            "proven_floor": 0,
            "exact_optimum_reached": False,
            "checker_pins": get_soko_checker_pins(),
            "tcb_lock_report": tcb_report,
        }
    cpp_out = _invoke_cpp("prove_lb", part, grid, max_bound, 0, budget_sec, "-")
    if cpp_out is None:
        raise RuntimeError("C++20 compiler (g++ or clang++) and grid <= 512 cells are required for prove_lb lower-bound proving.")

    raw_status = cpp_out.get("epistemic_status")
    if not isinstance(raw_status, str) or not raw_status:
        return {
            "epistemic_status": "INCOMPLETE_CPP_OUTPUT",
            "proven_floor": 0,
            "exact_optimum_reached": False,
            "nodes_expanded": cpp_out.get("nodes_expanded", 0),
            "edge_consistency_checks": cpp_out.get("edge_consistency_checks", 0),
            "checker_pins": get_soko_checker_pins(),
        }
    if raw_status != "VERIFIED":
        return {
            "epistemic_status": raw_status,
            "proven_floor": 0,
            "exact_optimum_reached": False,
            "nodes_expanded": cpp_out.get("nodes_expanded", 0),
            "edge_consistency_checks": cpp_out.get("edge_consistency_checks", 0),
            "checker_pins": get_soko_checker_pins(),
        }

    if not cpp_out.get("exact_state_tt", False):
        return {
            "epistemic_status": "REJECTED_LOSSY_TT",
            "proven_floor": 0,
            "exact_optimum_reached": False,
            "nodes_expanded": cpp_out.get("nodes_expanded", 0),
            "edge_consistency_checks": cpp_out.get("edge_consistency_checks", 0),
            "checker_pins": get_soko_checker_pins(),
        }

    exact_opt = bool(cpp_out.get("exact_optimum_reached", False))
    witness = str(cpp_out.get("winning_witness", "") or "")
    witness_verified = None

    if exact_opt:
        if not witness and int(cpp_out.get("proven_floor", 0)) > 0:
            return {
                "epistemic_status": "REJECTED_NO_WITNESS",
                "proven_floor": 0,
                "exact_optimum_reached": False,
                "nodes_expanded": cpp_out.get("nodes_expanded", 0),
                "edge_consistency_checks": cpp_out.get("edge_consistency_checks", 0),
                "checker_pins": get_soko_checker_pins(),
            }
        w_check = verify_route_dual(part, grid, witness)
        if not w_check["valid_winning_route"] or w_check["route_len"] != int(cpp_out["proven_floor"]):
            return {
                "epistemic_status": "REJECTED_INVALID_WITNESS",
                "proven_floor": 0,
                "exact_optimum_reached": False,
                "nodes_expanded": cpp_out.get("nodes_expanded", 0),
                "edge_consistency_checks": cpp_out.get("edge_consistency_checks", 0),
                "checker_pins": get_soko_checker_pins(),
            }
        witness_verified = {
            "route": witness,
            "route_len": w_check["route_len"],
            "route_sha256_12": w_check["route_sha256_12"],
            "traj_fnv64": w_check["traj_fnv64"],
        }

    return {
        "epistemic_status": "VERIFIED",
        "optimality_proven": bool(exact_opt and witness_verified is not None),
        "proven_floor": int(cpp_out["proven_floor"]),
        "exact_optimum_reached": exact_opt,
        "search_strategy": cpp_out.get("search_strategy", "exact_state_ida_star"),
        "quotient_pdb_enabled": bool(cpp_out.get("quotient_pdb_enabled", False)),
        "pair_atom_pdb_enabled": bool(cpp_out.get("pair_atom_pdb_enabled", False)),
        "wizard_ray_bound_enabled": bool(cpp_out.get("wizard_ray_bound_enabled", False)),
        "exact_state_tt": True,
        "exact_tt_prunes": int(cpp_out.get("exact_tt_prunes", 0)),
        "hash_collisions_prevented": int(cpp_out.get("hash_collisions_prevented", 0)),
        "nodes_expanded": int(cpp_out["nodes_expanded"]),
        "edge_consistency_checks": int(cpp_out["edge_consistency_checks"]),
        "winning_witness": witness_verified,
        "checker_pins": get_soko_checker_pins(),
        "guarantee": (
            f"Exact-state deduplicated search ({cpp_out.get('search_strategy', 'exact_state_ida_star')}) with runtime "
            f"step-consistency assertions (h(s) <= 1 + h(s') checked across {cpp_out['edge_consistency_checks']} transitions, "
            f"quotient_pdb={cpp_out.get('quotient_pdb_enabled', False)}, pair_atom_pdb={cpp_out.get('pair_atom_pdb_enabled', False)}) "
            f"refutes all winning routes of length < {cpp_out['proven_floor']}."
        ),
    }
