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
from .evidence import digest, normalize_route, problem_identity, validate_room
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
        "checker_auditor_py_sha256": _file_sha256(pkg_dir / "checker_auditor.py"),
    }


_PYTHON_TCB_PINS = (
    "oracle_py_sha256",
    "flat_oracle_py_sha256",
    "engine_bridge_py_sha256",
    "evidence_py_sha256",
    "formal_kernel_py_sha256",
    "checker_auditor_py_sha256",
)


def _required_checker_pins_ok(pins: Dict[str, Optional[str]], require_cpp: bool = True) -> bool:
    """Python checker pins are always required; native pins only when native output is relied on."""
    if not all(pins.get(key) for key in _PYTHON_TCB_PINS):
        return False
    return not require_cpp or bool(pins.get("cpp_soko_engine_src_sha256") and pins.get("cpp_soko_engine_bin_sha256"))


def _runtime_tcb_locked() -> Tuple[bool, Dict[str, Any]]:
    lock = verify_tcb_lock()
    return bool(lock.get("tcb_locked")), lock


def verify_tcb_lock() -> Dict[str, Any]:
    """Check the portable source manifest; report the local binary hash separately.

    A matching manifest shows the checker sources equal the committed hashes. It is
    not independent review, binary reproducibility, or a proof of correctness, and
    inspecting it never compiles anything. The compiled engine is machine-specific,
    so it is observed (hashed) but never accepted as a manifest entry.
    """
    from .integrity import verify_source_manifest

    report = verify_source_manifest(REPO_ROOT, SHA256SUMS_PATH)
    pins = get_soko_checker_pins()
    pins_ok = _required_checker_pins_ok(pins, require_cpp=False)
    ok = bool(report["source_integrity_verified"]) and pins_ok
    return {
        **report,
        "epistemic_status": "VERIFIED" if ok else "TAMPERED_OR_UNLOCKED",
        "tcb_locked": ok,
        "lock_scope": "source_manifest",
        "checker_pins_ok": pins_ok,
        "cpp_engine_compiled": CPP_BIN.is_file(),
        "checker_pins": pins,
        "compiled_binary": {
            "sha256": pins.get("cpp_soko_engine_bin_sha256"),
            "verified_by_manifest": False,
        },
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
        "version": "0.4.0",
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
                "formal_audit_checkers",
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


def _cpp_bin_stamp() -> Path:
    return CPP_BIN.with_name(CPP_BIN.name + ".src-sha256")


def ensure_cpp_engine() -> Optional[Path]:
    """Compile cpp/soko_engine.cpp on demand if g++ or clang++ is available.

    The binary is reused only when a stamp beside it records the SHA-256 of the exact
    source it was built from. File timestamps are not trusted: a fresh clone or an
    unpacked archive can make old source look older than an existing binary.
    """
    if not CPP_SRC.is_file():
        return None
    src_sha = _file_sha256(CPP_SRC)
    stamp = _cpp_bin_stamp()
    try:
        if CPP_BIN.is_file() and stamp.read_text(encoding="ascii").strip() == src_sha:
            return CPP_BIN
    except OSError:
        pass
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
        stamp_tmp = Path(temporary) / stamp.name
        stamp_tmp.write_text(f"{src_sha}\n", encoding="ascii")
        stamp_tmp.replace(stamp)
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
    """Fail-closed multi-oracle route verifier (PuzzleScriptOracle + FlatBitmaskOracle + C++20 engine).

    Malformed rooms and routes are rejected before any interpreter or native code runs.
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
        # Lead with the verifier's status: a seed can be a real win and still be rejected,
        # e.g. REJECTED_TCB_UNLOCKED, and the alive/win triple alone hides that (#49).
        raise ValueError(
            f"seed_route (len={len(clean_seed)}) was rejected by the verifier: "
            f"epistemic_status={seed_check['epistemic_status']}, alive={seed_check['alive']}, "
            f"exact_win={seed_check['exact_win']}, premature_win={seed_check['premature_win']}, "
            f"differential_match={seed_check['differential_match']}"
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


def _shortest_known_route_len(part: int, grid: List[str]) -> Optional[int]:
    """Length of the shortest reference route for this exact board that replays as a win."""
    candidates = set()
    for meta in FRONTIER_ROOMS.values():
        if meta.get("part") == part and list(meta.get("grid", [])) == list(grid) and meta.get("reference_route"):
            candidates.add(str(meta["reference_route"]))
    try:
        for meta in load_catalog().values():
            if meta.get("part") == part and list(meta.get("grid", [])) == list(grid) and meta.get("reference_route"):
                candidates.add(str(meta["reference_route"]))
    except Exception:  # catalog data is optional for this cross-check
        pass
    best: Optional[int] = None
    for route in candidates:
        py_res = replay_oracle(part, grid, route)
        flat_res = replay_flat_oracle(part, grid, route)
        if py_res.get("exact_win") and flat_res.get("exact_win"):
            n = len(route.strip())
            best = n if best is None else min(best, n)
    return best


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
            "guarantee": None,
            "checker_pins": get_soko_checker_pins(),
            "tcb_lock_report": tcb_report,
        }
    cpp_out = _invoke_cpp("prove_lb", part, grid, max_bound, 0, budget_sec, "-")
    if cpp_out is None:
        raise RuntimeError("C++20 compiler (g++ or clang++) and grid <= 512 cells are required for prove_lb lower-bound proving.")

    def _count(key: str) -> int:
        try:
            return int(cpp_out.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0

    def _rejected(status: str, **extra: Any) -> Dict[str, Any]:
        # A rejected claim keeps only the trivial floor 0 and never carries a guarantee.
        out = {
            "epistemic_status": status,
            "proven_floor": 0,
            "exact_optimum_reached": False,
            "guarantee": None,
            "nodes_expanded": _count("nodes_expanded"),
            "edge_consistency_checks": _count("edge_consistency_checks"),
            "checker_pins": get_soko_checker_pins(),
        }
        out.update(extra)
        return out

    raw_status = cpp_out.get("epistemic_status")
    if not isinstance(raw_status, str) or not raw_status:
        return _rejected("INCOMPLETE_CPP_OUTPUT")
    # The native prover reports VERIFIED only with a witness and EXHAUSTIVE_LOWER_BOUND otherwise.
    if raw_status not in ("VERIFIED", "EXHAUSTIVE_LOWER_BOUND"):
        return _rejected(raw_status)
    if not cpp_out.get("exact_state_tt", False):
        return _rejected("REJECTED_LOSSY_TT")

    exact_opt = bool(cpp_out.get("exact_optimum_reached", False))
    if raw_status != "VERIFIED" and exact_opt:
        return _rejected("REJECTED_INCONSISTENT_STATUS")
    witness = str(cpp_out.get("winning_witness", "") or "")
    witness_verified = None

    try:
        claimed_floor = int(cpp_out.get("proven_floor", 0))
    except (TypeError, ValueError):
        return _rejected("INCOMPLETE_CPP_OUTPUT")

    # F-04: a search capped at max_bound refutes routes shorter than max_bound + 1 at most.
    # A larger unwitnessed floor rests on the start heuristic alone (e.g. I-1 with max_bound=1
    # reported floor 9 with 0 nodes and 0 edges), so it is rejected.
    if not exact_opt and claimed_floor > int(max_bound) + 1:
        return _rejected("REJECTED_FLOOR_EXCEEDS_MAX_BOUND", claimed_floor=claimed_floor, max_bound=int(max_bound))
    # An inexact floor can refute at most the routes up to the deepest completed layer.
    if not exact_opt and "completed_depth" in cpp_out:
        try:
            completed = int(cpp_out["completed_depth"])
        except (TypeError, ValueError):
            return _rejected("INCOMPLETE_CPP_OUTPUT")
        if claimed_floor > completed + 1:
            return _rejected("REJECTED_FLOOR_EXCEEDS_COMPLETED_DEPTH", claimed_floor=claimed_floor, completed_depth=completed)

    if exact_opt:
        if not witness and claimed_floor > 0:
            return _rejected("REJECTED_NO_WITNESS")
        w_check = verify_route_dual(part, grid, witness)
        if w_check["valid_winning_route"] and w_check["route_len"] != claimed_floor:
            return _rejected(
                "REJECTED_WITNESS_FLOOR_MISMATCH",
                claimed_floor=claimed_floor,
                witness_len=w_check["route_len"],
            )
        if not w_check["valid_winning_route"]:
            return _rejected("REJECTED_INVALID_WITNESS")
        witness_verified = {
            "route": witness,
            "route_len": w_check["route_len"],
            "route_sha256_12": w_check["route_sha256_12"],
            "traj_fnv64": w_check["traj_fnv64"],
        }

    # F-04: checked after the witness, so an equal-length detour (DRRRRRRRRRU at floor 11 on I-1)
    # is still caught. A lower bound can never exceed the length of a known winning route on the same board.
    known_len = _shortest_known_route_len(part, grid)
    if known_len is not None and claimed_floor > known_len:
        return _rejected(
            "REJECTED_FLOOR_EXCEEDS_KNOWN_ROUTE",
            claimed_floor=claimed_floor,
            shortest_known_route_len=known_len,
        )

    search_strategy = cpp_out.get("search_strategy", "exact_state_ida_star")
    search_fields = {
        "completed_depth": cpp_out.get("completed_depth"),
        "termination_reason": cpp_out.get("termination_reason"),
        "timed_out": cpp_out.get("timed_out"),
    }

    # F-04: VERIFIED is reserved for an exact optimum bound to a dual-oracle-checked witness on a board
    # with a reference route to cross-check. Without a reference route nothing outside the engine's
    # exact flag refutes a shorter win (a hall where RR wins in 2 accepted floor 4 with witness URRD),
    # so that case is reported as WITNESS_MATCHES_CLAIM_UNREFERENCED, without a floor or guarantee.
    if exact_opt and witness_verified is not None and known_len is None:
        return {
            "epistemic_status": "WITNESS_MATCHES_CLAIM_UNREFERENCED",
            "optimality_proven": False,
            "proven_floor": None,
            "claimed_floor": claimed_floor,
            "exact_optimum_reached": exact_opt,
            "search_strategy": search_strategy,
            "exact_state_tt": True,
            "nodes_expanded": _count("nodes_expanded"),
            "edge_consistency_checks": _count("edge_consistency_checks"),
            **search_fields,
            "winning_witness": witness_verified,
            "checker_pins": get_soko_checker_pins(),
            "verification_note": (
                "The dual-oracle-checked witness matches the claimed floor, but no reference route was available "
                "for this board to check optimality. Shorter winning routes are not refuted, so it is not VERIFIED."
            ),
            "guarantee": None,
        }

    # Otherwise an inexact or unwitnessed floor is reported as an unwitnessed lower bound.
    status = "VERIFIED" if (exact_opt and witness_verified is not None) else "LOWER_BOUND_UNWITNESSED"
    edges = _count("edge_consistency_checks")
    return {
        "epistemic_status": status,
        "optimality_proven": bool(exact_opt and witness_verified is not None),
        "proven_floor": claimed_floor,
        "exact_optimum_reached": exact_opt,
        "search_strategy": search_strategy,
        "quotient_pdb_enabled": bool(cpp_out.get("quotient_pdb_enabled", False)),
        "pair_atom_pdb_enabled": bool(cpp_out.get("pair_atom_pdb_enabled", False)),
        "wizard_ray_bound_enabled": bool(cpp_out.get("wizard_ray_bound_enabled", False)),
        "exact_state_tt": True,
        "exact_tt_prunes": _count("exact_tt_prunes"),
        "hash_collisions_prevented": _count("hash_collisions_prevented"),
        "nodes_expanded": _count("nodes_expanded"),
        "edge_consistency_checks": edges,
        **search_fields,
        "winning_witness": witness_verified,
        "checker_pins": get_soko_checker_pins(),
        "verification_note": (
            None if status == "VERIFIED" else
            "Lower bound from the engine's runtime-checked search; no optimal witness, so it is not VERIFIED."
        ),
        "guarantee": (
            None if claimed_floor <= 0 else
            f"Exact-state deduplicated search ({search_strategy}) refutes all winning routes of length "
            f"< {claimed_floor}, provided its heuristic (quotient_pdb={cpp_out.get('quotient_pdb_enabled', False)}, "
            f"pair_atom_pdb={cpp_out.get('pair_atom_pdb_enabled', False)}) is admissible. The runtime check "
            f"h(s) <= 1 + h(s') covered the {edges} transitions it expanded, not pruned branches."
        ),
    }
