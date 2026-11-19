"""Deterministic-seed NRPA (`soko#53` C1) runner and dual-oracle verification harness for 15x7 `III-14`.

Compiles `iii14_nrpa_search.cpp` with a standard C++20 compiler (`clang++` or `g++`), executes
deterministic-seed Nested Rollout Policy Adaptation (`NRPA`, zero `h`-pruning bias, sparse quotient-state
keying per `soko#46`), and verifies every discovered winning rollout in BOTH `PuzzleScriptOracle` and
`FlatBitmaskOracle` (`mde guard --code-audit` clean, zero `float`, zero bare `assert`).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

from soko_mcp.flat_oracle import replay_flat_oracle
from soko_mcp.oracle import FRONTIER_ROOMS, replay_oracle

from .hero_assignment_bounds import load_strict_rational_json


def find_cpp20_compiler() -> str:
    for candidate in ("clang++", "g++-16", "g++-15", "g++-14", "g++", "c++"):
        exe = shutil.which(candidate)
        if exe is not None:
            return exe
    raise RuntimeError("No C++20 compiler (clang++ or g++) found on PATH")


def run_iii14_nrpa_experiment(
    *,
    seed: int = 20261119,
    level: int = 2,
    iterations: int = 60,
    restarts_prim: int = 10,
    restarts_open: int = 24,
    restarts_47: int = 16,
    horizon_open: int = 64,
    threads: int = 10,
) -> Dict[str, Any]:
    """Compile and execute deterministic-seed 2-arm NRPA on 15x7 `III-14`, then dual-verify every winning rollout."""
    cpp_src = Path(__file__).resolve().parent / "iii14_nrpa_search.cpp"
    src_sha256 = hashlib.sha256(cpp_src.read_bytes()).hexdigest()
    compiler = find_cpp20_compiler()
    grid: List[str] = FRONTIER_ROOMS["III-14-15x7"]["grid"]
    ref_r48: str = FRONTIER_ROOMS["III-14-15x7"]["reference_route"]

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        bin_path = tmp / "iii14_nrpa_search"
        raw_json_path = tmp / "nrpa_raw.json"
        compile_proc = subprocess.run(
            [compiler, "-O3", "-std=c++20", "-pthread", str(cpp_src), "-o", str(bin_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if compile_proc.returncode != 0:
            raise RuntimeError(f"Failed to compile iii14_nrpa_search.cpp: {compile_proc.stderr[:500]}")

        run_proc = subprocess.run(
            [
                str(bin_path),
                "--seed",
                str(seed),
                "--level",
                str(level),
                "--iterations",
                str(iterations),
                "--restarts-prim",
                str(restarts_prim),
                "--restarts-open",
                str(restarts_open),
                "--restarts-47",
                str(restarts_47),
                "--horizon-open",
                str(horizon_open),
                "--threads",
                str(threads),
                "--json-out",
                str(raw_json_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if run_proc.returncode != 0:
            raise RuntimeError(f"iii14_nrpa_search execution failed: {run_proc.stderr[:500]}")

        raw_data = load_strict_rational_json(raw_json_path.read_text(encoding="utf-8"))

    verified_wins: List[Dict[str, Any]] = []
    dual_mismatches = 0
    for item in raw_data["restarts"]:
        if not item["won"]:
            continue
        route = str(item["route"])
        ps_rep = replay_oracle(3, grid, route)
        fl_rep = replay_flat_oracle(3, grid, route)
        ok_dual = (
            ps_rep["alive"]
            and ps_rep["exact_win"]
            and fl_rep["alive"]
            and fl_rep["exact_win"]
            and ps_rep["traj_fnv64"] == fl_rep["traj_fnv64"]
            and len(route) == int(item["win_len"])
        )
        if not ok_dual:
            dual_mismatches += 1
        verified_wins.append({
            "restart_id": int(item["restart_id"]),
            "arm": str(item["arm"]),
            "seed": int(item["seed"]),
            "horizon": int(item["horizon"]),
            "length": len(route),
            "route": route,
            "route_sha256": hashlib.sha256(route.encode("utf-8")).hexdigest(),
            "traj_fnv64": ps_rep["traj_fnv64"],
            "dual_oracle_verified": ok_dual,
        })

    if dual_mismatches != 0:
        raise RuntimeError(f"NRPA produced {dual_mismatches} rollout(s) that failed dual-oracle verification")

    # Non-tautological `must_fail` controls on dual-oracle winning-route verification:
    # 1) Reference R48 truncated to 47 keys (`ref_r48[:-1]`) MUST fail `exact_win` in BOTH oracles!
    trunc47_ps = replay_oracle(3, grid, ref_r48[:-1])
    trunc47_fl = replay_flat_oracle(3, grid, ref_r48[:-1])
    must_fail_trunc47_rejected = (not trunc47_ps["exact_win"]) and (not trunc47_fl["exact_win"])

    # 2) Reference R48 with 1 extra post-win key (`ref_r48 + "L"`) MUST fail `exact_win` (`premature_win == True`)!
    extra49_ps = replay_oracle(3, grid, ref_r48 + "L")
    extra49_fl = replay_flat_oracle(3, grid, ref_r48 + "L")
    must_fail_extra49_rejected = (
        (not extra49_ps["exact_win"])
        and extra49_ps["premature_win"]
        and (not extra49_fl["exact_win"])
        and extra49_fl["premature_win"]
    )
    if not (must_fail_trunc47_rejected and must_fail_extra49_rejected):
        raise RuntimeError("C1 dual-oracle must_fail controls failed")

    shortest_len = int(raw_data["shortest_nrpa_win_len"])
    reproduced_48 = (shortest_len == 48)
    beat_48 = (0 < shortest_len < 48)
    # Honest epistemic tier: `VERIFIED` if winning routes are dual-oracle verified, `TESTED` if 0 wins found
    status = "VERIFIED" if verified_wins else "TESTED"

    summary = {
        "epistemic_status": status,
        "task_ref": "ahrazzle/soko#53 C1 (Deterministic-Seed Unseeded NRPA on 15x7 III-14)",
        "nrpa_source_sha256": src_sha256,
        "base_seed": int(raw_data["base_seed"]),
        "nrpa_level": int(raw_data["nrpa_level"]),
        "iterations_per_level": int(raw_data["iterations_per_level"]),
        "restarts_primitive_open": int(raw_data["restarts_primitive_open"]),
        "restarts_open_horizon": int(raw_data["restarts_open_horizon"]),
        "open_horizon_cap": int(raw_data["open_horizon_cap"]),
        "restarts_sub48_probe": int(raw_data["restarts_sub48_probe"]),
        "total_rollouts_executed": int(raw_data["total_rollouts_executed"]),
        "primitive_wins_count": int(raw_data["primitive_wins_count"]),
        "macro_wins_count": int(raw_data["macro_wins_count"]),
        "winning_restarts_count": len(verified_wins),
        "wins_at_or_below_47": int(raw_data["wins_at_or_below_47"]),
        "reproduced_48_from_scratch": reproduced_48,
        "found_sub_48_route": beat_48,
        "shortest_nrpa_win_len": shortest_len,
        "shortest_nrpa_win_route": str(raw_data["shortest_nrpa_win_route"]),
        "verified_winning_rollouts": verified_wins,
        "must_fail_controls": {
            "truncated_47_prefix_rejected": must_fail_trunc47_rejected,
            "post_win_49_extra_key_rejected": must_fail_extra49_rejected,
        },
    }
    load_strict_rational_json(json.dumps(summary))
    return summary
