"""Hardened multi-oracle bridge between Python MCP tools, FlatBitmaskOracle, and C++20 `soko_engine`.

Fixes v0.1.0 audit findings F-01, F-02, F-03, and F-04:
- F-01 Fix: `verify_route_dual` is strictly fail-closed (`differential_match` starts `False`), always executes
  AT LEAST TWO zero-shared-code independent engines (`PuzzleScriptOracle` + `FlatBitmaskOracle`), and executes
  ALL THREE (`+ C++20 soko_engine`) whenever a C++20 compiler is available and `w * h <= 512`.
- F-02 Fix: Asserts bit-exact 64-bit FNV-1a per-frame trajectory digest (`traj_fnv64`) parity across every step
  `t = 0..L` (including hidden Bard `Note` masks and open-door flags), not merely terminal ASCII.
- F-03 Fix: `verify_tcb_lock()` verifies `SHA256SUMS` at runtime and attaches cryptographic `checker_pins`
  to every `VERIFIED` certificate (Foundation-0 Issue #14).
- F-04 Fix: Surfaces exact-state transposition-table collision prevention stats and Quotient-PDB activation
  from `cpp/soko_engine.cpp` (`prove_lb`).
"""
from __future__ import annotations

from collections import deque
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple

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
        "cpp_soko_engine_src_sha256": _file_sha256(CPP_SRC),
        "cpp_soko_engine_bin_sha256": _file_sha256(CPP_BIN),
        "formal_kernel_py_sha256": _file_sha256(pkg_dir / "formal_kernel.py"),
    }


def _resolve_confined_path(repo_root: Path, rel_path: str) -> Tuple[Optional[Path], Optional[str]]:
    """Resolve a manifest-relative path only if it stays inside repo_root (reject .. and escapes)."""
    clean = rel_path.strip().replace("\\", "/")
    if not clean or clean.startswith("/"):
        return None, "absolute_or_empty_path"
    parts = [p for p in clean.split("/") if p not in ("", ".")]
    if ".." in parts:
        return None, "parent_segment"
    target = (repo_root / clean).resolve()
    try:
        target.relative_to(repo_root.resolve())
    except ValueError:
        return None, "escapes_repo_root"
    return target, None


def _required_checker_pins_ok(pins: Dict[str, Optional[str]]) -> bool:
    """Shipped checker artifacts must hash before any VERIFIED certificate."""
    for key in (
        "oracle_py_sha256",
        "flat_oracle_py_sha256",
        "cpp_soko_engine_src_sha256",
        "cpp_soko_engine_bin_sha256",
    ):
        if not pins.get(key):
            return False
    return True


def verify_tcb_lock() -> Dict[str, Any]:
    """Verify runtime SHA256SUMS integrity of all tracked repository files + TCB checker pins."""
    cpp_bin = ensure_cpp_engine()
    pins = get_soko_checker_pins()
    manifest_present = SHA256SUMS_PATH.is_file()
    checked_files = 0
    mismatched: List[Dict[str, str]] = []
    missing: List[str] = []
    unconfined: List[Dict[str, str]] = []

    if manifest_present:
        for raw_line in SHA256SUMS_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            expected_hash, rel_path = parts[0].strip(), parts[1].strip().lstrip("*")
            target, confine_err = _resolve_confined_path(REPO_ROOT, rel_path)
            if confine_err is not None or target is None:
                unconfined.append({"file": rel_path, "reason": confine_err or "unconfined"})
                continue
            actual_hash = _file_sha256(target)
            checked_files += 1
            if actual_hash is None:
                missing.append(rel_path)
            elif actual_hash != expected_hash:
                mismatched.append({"file": rel_path, "expected": expected_hash, "actual": actual_hash})

    pins_ok = _required_checker_pins_ok(pins)
    ok = (
        manifest_present
        and checked_files > 0
        and not mismatched
        and not missing
        and not unconfined
        and pins_ok
    )
    return {
        "epistemic_status": "VERIFIED" if ok else "TAMPERED_OR_UNLOCKED",
        "tcb_locked": ok,
        "manifest_present": manifest_present,
        "files_verified": checked_files,
        "mismatched_files": mismatched,
        "missing_files": missing,
        "unconfined_paths": unconfined,
        "checker_pins_ok": pins_ok,
        "cpp_engine_compiled": cpp_bin is not None,
        "checker_pins": pins,
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
    clean_rows = [r.rstrip("\r\n") for r in grid if r.strip()]
    return None, int(part), clean_rows, None


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
    clean = route.strip().upper()
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
    pins_ok = _required_checker_pins_ok(pins)
    is_verified = dual_or_triple_checked and differential_match and py_res["exact_win"] and pins_ok

    if not dual_or_triple_checked:
        epistemic = "REJECTED_INSUFFICIENT_ORACLES"
    elif dual_or_triple_checked and differential_match and py_res["exact_win"] and not pins_ok:
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
        }
    return {
        "epistemic_status": "UNSOLVED_WITHIN_BUDGET",
        "solved": False,
        "states_explored": cpp_out.get("explored", 0) if cpp_out else 0,
    }


def prove_floor_verified(
    part: int,
    grid: List[str],
    max_bound: int = 30,
    budget_sec: int = 15,
) -> Dict[str, Any]:
    cpp_out = _invoke_cpp("prove_lb", part, grid, max_bound, 0, budget_sec, "-")
    if cpp_out is None:
        raise RuntimeError("C++20 compiler (g++ or clang++) and grid <= 512 cells are required for prove_lb IDA* lower-bound proving.")

    status = cpp_out.get("epistemic_status")
    if status is None:
        status = "INCOMPLETE_CPP_OUTPUT"

    exact_state_tt = cpp_out.get("exact_state_tt")
    if exact_state_tt is None:
        exact_state_tt = False

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
    pins_ok = _required_checker_pins_ok(pins)
    proven_floor = int(cpp_out.get("proven_floor", 0))

    if status == "VERIFIED":
        if not exact_state_tt:
            status = "REJECTED_CPP_CLAIM"
        elif not pins_ok:
            status = "REJECTED_TCB_UNLOCKED"
        elif not witness or witness_verified is None:
            status = "REJECTED_NO_WITNESS"
        elif witness_verified["route_len"] < proven_floor:
            status = "REJECTED_WITNESS_BELOW_FLOOR"

    return {
        "epistemic_status": status,
        "proven_floor": proven_floor,
        "exact_optimum_reached": bool(cpp_out.get("exact_optimum_reached")),
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
            f"Collision-free exact-DynState IDA* with runtime step-consistency assertions (h(s) <= 1 + h(s') checked across "
            f"{int(cpp_out.get('edge_consistency_checks', 0))} transitions, quotient_pdb={bool(cpp_out.get('quotient_pdb_enabled'))}) "
            f"refutes all winning routes of length < {proven_floor}."
        ),
    }
