"""Local differential replay, canonical input validation, and bounded exact BFS.

Route agreement, exhaustive local search and source integrity are distinct evidence
levels. None establishes a kernel-checked proof or independent specification approval.
"""
from __future__ import annotations

from collections import deque
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from .flat_oracle import replay_flat_oracle
from .evidence import digest, normalize_route, problem_identity, validate_room
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
        "cpp_soko_engine_src_sha256": _file_sha256(CPP_SRC),
        "cpp_soko_engine_bin_sha256": _file_sha256(CPP_BIN),
        "formal_kernel_py_sha256": _file_sha256(pkg_dir / "formal_kernel.py"),
    }


def _required_checker_pins_ok(pins: Dict[str, Optional[str]], require_cpp: bool = False) -> bool:
    """Shipped checker artifacts must hash before any VERIFIED certificate."""
    for key in (
        "oracle_py_sha256",
        "flat_oracle_py_sha256",
        "engine_bridge_py_sha256",
        "evidence_py_sha256",
    ):
        if not pins.get(key):
            return False
    return not require_cpp or bool(pins.get("cpp_soko_engine_src_sha256") and pins.get("cpp_soko_engine_bin_sha256"))


def verify_tcb_lock() -> Dict[str, Any]:
    """Check the portable source manifest; report the local binary hash separately.

    A matching manifest establishes consistency with committed source hashes,
    not independent review, binary reproducibility, or formal verification.
    No compilation is required merely to inspect source integrity.
    """
    from .integrity import verify_source_manifest

    report = verify_source_manifest(REPO_ROOT, SHA256SUMS_PATH)
    pins = get_soko_checker_pins()
    ok = report["source_integrity_verified"]
    return {
        **report,
        "epistemic_status": "VERIFIED" if ok else "TAMPERED_OR_UNLOCKED",
        "tcb_locked": ok,
        "lock_scope": "source_manifest",
        "checker_pins_ok": _required_checker_pins_ok(pins),
        "cpp_engine_compiled": CPP_BIN.is_file(),
        "checker_pins": pins,
        "compiled_binary": {
            "sha256": pins["cpp_soko_engine_bin_sha256"],
            "verified_by_manifest": False,
        },
    }


def resolve_room_input(
    room_id: Optional[str] = None,
    part: Optional[int] = None,
    grid: Optional[List[str]] = None,
) -> Tuple[Optional[str], int, List[str], Optional[Dict[str, Any]]]:
    if room_id:
        key = room_id.strip()
        if key not in FRONTIER_ROOMS:
            raise ValueError(f"Unknown room_id {key!r}. Available built-in rooms: {sorted(FRONTIER_ROOMS)}")
        meta = FRONTIER_ROOMS[key]
        return key, int(meta["part"]), list(meta["grid"]), meta
    if part is None or not grid:
        raise ValueError("Provide either a built-in room_id (e.g. 'III-20') or both 'part' (1..3) and 'grid' (list of ASCII rows).")
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
    cmd = [compiler, "-O3", "-pthread", "-std=c++20", str(CPP_SRC), "-o", str(CPP_BIN)]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        return None
    return CPP_BIN


def get_capabilities() -> Dict[str, Any]:
    """Report executable capabilities, not features promised by documentation."""
    cpp_ready = ensure_cpp_engine() is not None
    reason = None if cpp_ready else (
        "missing_cpp_source" if not CPP_SRC.is_file() else "cpp_compile_unavailable_or_failed"
    )
    return {
        "cpp_engine_ready": cpp_ready,
        "cpp_unavailable_reason": reason,
        "route_verification": {"available": True, "python_oracles": 2},
        "route_optimization": {
            "available": True,
            "backend": "cpp20_bounded_exact_bfs" if cpp_ready else "python_fallback_window_bfs",
        },
        "solve_from_scratch": {"available": cpp_ready, "unavailable_reason": reason},
        "lower_bound_proving": {"available": cpp_ready, "unavailable_reason": reason},
        "formal_systems": {"available": False, "unavailable_reason": "not_implemented"},
        "tcb_manifest_present": SHA256SUMS_PATH.is_file(),
    }


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
        timeout=max(30, p3 + 25),
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
    """Fail-closed multi-oracle route verifier (PuzzleScriptOracle + FlatBitmaskOracle + C++20 engine).

    Eliminates F-01 & F-02:
    - Never defaults `differential_match = True`; requires >= 2 independent engines to execute and match
      on survival, exact final-step win, step count, final ASCII, AND per-frame 64-bit FNV-1a trajectory digest!
    """
    validate_room(part, grid)
    clean = normalize_route(route)
    py_res = replay_oracle(part, grid, clean)
    flat_res = None if _skip_flat_for_test else replay_flat_oracle(part, grid, clean)
    cpp_res = None if _skip_cpp_for_test else _invoke_cpp("verify", part, grid, 0, 0, 5, clean or "-")

    engines_executed = ["python_spec_oracle"]
    if flat_res is not None:
        engines_executed.append("python_flat_bitmask_oracle")
    if cpp_res is not None:
        engines_executed.append("cpp20_soko_engine")

    # Fail-closed: require at least 2 independent checkers (and C++ if explicitly mandated)
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
    pins_ok = _required_checker_pins_ok(pins, require_cpp=cpp_res is not None)
    is_verified = dual_or_triple_checked and differential_match and py_res["exact_win"] and pins_ok

    if not dual_or_triple_checked:
        epistemic = "REJECTED_INSUFFICIENT_ORACLES"
    elif dual_or_triple_checked and differential_match and py_res["exact_win"] and not pins_ok:
        epistemic = "REJECTED_TCB_UNLOCKED"
    else:
        epistemic = "VERIFIED" if is_verified else "REJECTED"

    result = {
        "epistemic_status": epistemic,
        "evidence_level": "differential_replay",
        "formal_proof_checked": False,
        "external_spec_pinned": False,
        "source_lock_asserted": False,
        **problem_identity(part, grid),
        "route_sha256": hashlib.sha256(clean.encode("ascii")).hexdigest(),
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
    result["certificate_sha256"] = digest(result)
    return result


def _python_window_shortcut(part: int, grid: List[str], route: str, win_len: int = 10, budget_sec: int = 35) -> str:
    """Pure-Python BFS fallback optimizer when no C++20 compiler is present."""
    best = route.strip().upper()
    deadline = time.monotonic() + max(0, budget_sec)
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
            if time.monotonic() >= deadline:
                return best
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
    clean_seed = normalize_route(seed_route)
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
        backend = "cpp20_bounded_exact_bfs"
    else:
        cand_route = _python_window_shortcut(part, grid, clean_seed, min(10, window_len), budget_sec)
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
        "verification": cand_check,
        "search": cpp_out,
    }


def solve_room_verified(
    part: int,
    grid: List[str],
    max_depth: int = 120,
    beam_width: int = 40000,
    budget_sec: int = 20,
) -> Dict[str, Any]:
    validate_room(part, grid)
    capabilities = get_capabilities()
    if not capabilities["solve_from_scratch"]["available"]:
        return {
            "epistemic_status": "UNAVAILABLE_BACKEND",
            "solved": False,
            "search_performed": False,
            "states_explored": 0,
            "unavailable_reason": capabilities["cpp_unavailable_reason"],
        }
    cpp_out = _invoke_cpp("solve", part, grid, max_depth, beam_width, budget_sec, "-")
    if cpp_out is not None and cpp_out.get("solved"):
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
            "verification": v,
            "search": cpp_out,
        }
    return {
        "epistemic_status": "UNSOLVED_WITHIN_BUDGET" if cpp_out is not None else "BACKEND_FAILED",
        "solved": False,
        "search_performed": cpp_out is not None,
        "states_explored": cpp_out.get("explored", 0) if cpp_out else 0,
        "search": cpp_out,
    }


def prove_floor_verified(
    part: int,
    grid: List[str],
    max_bound: int = 30,
    budget_sec: int = 15,
) -> Dict[str, Any]:
    validate_room(part, grid)
    cpp_out = _invoke_cpp("prove_lb", part, grid, max_bound, 0, budget_sec, "-")
    if cpp_out is None:
        raise RuntimeError("C++20 compiler (g++ or clang++) and grid <= 512 cells are required for exhaustive lower-bound search.")

    status = cpp_out.get("epistemic_status")
    if status is None:
        status = "INCOMPLETE_CPP_OUTPUT"

    exact_state_tt = cpp_out.get("exact_state_tt") is True

    witness = str(cpp_out.get("winning_witness") or "")
    witness_verified = None
    if witness:
        w_check = verify_route_dual(part, grid, witness)
        if not w_check["valid_winning_route"]:
            raise RuntimeError("prove_lb witness failed multi-oracle differential verification!")
        witness_verified = {
            "route": witness,
            "route_len": w_check["route_len"],
            "route_sha256_12": w_check["route_sha256_12"],
            "traj_fnv64": w_check["traj_fnv64"],
        }

    pins = get_soko_checker_pins()
    pins_ok = _required_checker_pins_ok(pins, require_cpp=True)
    reported_floor = cpp_out.get("proven_floor")
    proven_floor = reported_floor if type(reported_floor) is int else 0

    if status == "VERIFIED":
        if not exact_state_tt:
            status = "REJECTED_CPP_CLAIM"
        elif not pins_ok:
            status = "REJECTED_TCB_UNLOCKED"
        elif not witness or witness_verified is None:
            status = "REJECTED_NO_WITNESS"
        elif witness_verified["route_len"] != proven_floor:
            status = "REJECTED_WITNESS_BELOW_FLOOR"

    completed = cpp_out.get("completed_depth")
    accepted = status in ("VERIFIED", "EXHAUSTIVE_LOWER_BOUND")
    if accepted and (
        not exact_state_tt or not pins_ok or type(reported_floor) is not int
        or cpp_out.get("search_algorithm") != "exact_bfs"
        or type(completed) is not int or completed < -1
        or proven_floor != completed + 1
        or proven_floor > max_bound + 1
        or (status == "VERIFIED" and cpp_out.get("exact_optimum_reached") is not True)
        or (status == "EXHAUSTIVE_LOWER_BOUND" and (witness or cpp_out.get("exact_optimum_reached")))
    ):
        status = "REJECTED_CPP_CLAIM"
    accepted = status in ("VERIFIED", "EXHAUSTIVE_LOWER_BOUND")

    return {
        "epistemic_status": status,
        "proven_floor": proven_floor if accepted else None,
        "reported_floor": reported_floor,
        "exact_optimum_reached": accepted and status == "VERIFIED",
        "evidence_level": "bounded_exhaustive_search" if accepted else "rejected_search_claim",
        "formal_proof_checked": False,
        "external_spec_pinned": False,
        "source_lock_asserted": False,
        **problem_identity(part, grid),
        "search": cpp_out,
        "quotient_pdb_enabled": bool(cpp_out.get("quotient_pdb_enabled")),
        "exact_state_tt": exact_state_tt,
        "exact_tt_prunes": int(cpp_out.get("exact_tt_prunes", 0)),
        "hash_collisions_prevented": int(cpp_out.get("hash_collisions_prevented", 0)),
        "nodes_expanded": int(cpp_out.get("nodes_expanded", 0)),
        "edge_consistency_checks": int(cpp_out.get("edge_consistency_checks", 0)),
        "winning_witness": witness_verified,
        "checker_pins": pins,
        "checker_pins_ok": pins_ok,
        "guarantee": (
            f"Exact-state BFS under the local C++ transition rules ruled out winning routes shorter than {proven_floor} keys. "
            "The statement rests on that bounded search and any independently replayed witness."
        ) if accepted else None,
    }
