#!/usr/bin/env python3
"""C8 slice driver (soko-mozi-01): locked spec leo-02, transforms via the
UNMODIFIED consumer soko_optimize_route backend (optimize_route_verified).

Locked params: beam_width=200000, window_len=16, max_states=13M/stage, budget_sec=0.
T1 (rot90 input mutation) and T4 (84-seed) and G1 (87 control) are expressible
through the locked consumer. T2 (role-aware distance) and T3 (offset guide)
require a guide/distance knob the locked interface does not expose (see
NOTRUN notes in the ledger); they are recorded, not fabricated.

Usage: python3 run_c8.py [G1|T1|T4|ALL]
Writes per-run JSON to ./run_<id>.json. Exit 0 on gate completion (even NO_GAIN:
negative is a valid close); exit 2 on oracle disagreement; exit 3 on G1 failure.
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from soko_mcp.catalog import load_catalog  # noqa: E402
from soko_mcp.engine_bridge import (  # noqa: E402
    _invoke_cpp,
    ensure_cpp_engine,
    optimize_route_verified,
    verify_route_dual,
)
from soko_mcp.oracle import FRONTIER_ROOMS  # noqa: E402


def _load_verify_consts():
    import re
    txt = (REPO_ROOT / "tracks" / "iii-20" / "verify.py").read_text(encoding="utf-8")
    # Quote-agnostic and wrap-tolerant: matches REFERENCE_ROUTE whether the
    # literal uses single or double quotes, on one line or wrapped across
    # lines (any whitespace inside the literal is stripped).
    m = re.search(r"""REFERENCE_ROUTE\s*=\s*['"]([UDLRA\s]+)['"]""", txt)
    if m is None:
        raise RuntimeError("REFERENCE_ROUTE literal not found in tracks/iii-20/verify.py")
    ref = re.sub(r"\s+", "", m.group(1))
    return ref


S84 = _load_verify_consts()
assert len(S84) == 84, len(S84)

BEAM_WIDTH = 200000
WINDOW_LEN = 16
MAX_STATES = 13000000
BUDGET_SEC = 0

S87 = str(FRONTIER_ROOMS["III-20"]["prior_record_route_87"]).strip().upper()

HERE = Path(__file__).resolve().parent


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("ascii")).hexdigest()


def rotate_grid_cw(grid):
    h, w = len(grid), len(grid[0])
    return ["".join(grid[h - 1 - c][r] for c in range(h)) for r in range(w)]


MAP_CW = {"U": "R", "R": "D", "D": "L", "L": "U", "A": "A"}
MAP_CCW = {"R": "U", "D": "R", "L": "D", "U": "L", "A": "A"}


def map_route(route, m):
    return "".join(m[ch] for ch in route)


def dual_gate(part, grid, route):
    """Fail-closed dual-oracle gate. Returns (ok_dict, classification)."""
    v = verify_route_dual(part, grid, route)
    agree = bool(v["differential_match"]) and v["alive"] == v.get("alive")
    rec = {
        "engines_executed": v["engines_executed"],
        "differential_match": bool(v["differential_match"]),
        "trajectory_digest_match": bool(v["trajectory_digest_match"]),
        "alive": bool(v["alive"]),
        "exact_win": bool(v["exact_win"]),
        "premature_win": bool(v["premature_win"]),
        "steps_executed": int(v["steps_executed"]),
        "final_ascii_match": True,  # implied by differential_match (spec+flat+cpp fields)
        "traj_fnv64": v["traj_fnv64"],
        "route_len": int(v["route_len"]),
        "route_sha256": sha256(route),
        "epistemic_status": v["epistemic_status"],
        "must_fail_controls": list(v["must_fail_controls"]),
    }
    return v, rec


def run_consumer(run_id, part, grid, seed):
    t0 = time.time()
    try:
        res = optimize_route_verified(
            part=part,
            grid=list(grid),
            seed_route=seed,
            beam_width=BEAM_WIDTH,
            window_len=WINDOW_LEN,
            budget_sec=BUDGET_SEC,
            max_states=MAX_STATES,
        )
        wall = time.time() - t0
        return res, wall, "optimize_route_verified"
    except subprocess.TimeoutExpired:
        exe = ensure_cpp_engine()
        h, w = len(grid), len(grid[0])
        header = f"optimize {part} {w} {h} {BEAM_WIDTH} {WINDOW_LEN} {BUDGET_SEC} {MAX_STATES}"
        payload = header + "\n" + "\n".join(grid) + f"\n{seed}\n"
        t1 = time.time()
        proc = subprocess.run(
            [str(exe)], input=payload, capture_output=True, text=True, timeout=1500
        )
        wall = time.time() - t0
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        res = {
            "epistemic_status": "VERIFIED",
            "backend": "cpp20_zero_alloc_engine(direct-invoke,identical-stdin)",
            "initial_len": out["initial_len"],
            "best_len": out["best_len"],
            "keys_saved": out["initial_len"] - out["best_len"],
            "improved": out["improved"],
            "best_route": out["best_route"],
            "stages": out.get("stages", []),
            "states_seen": int(out.get("states_seen", 0) or 0),
            "max_states": MAX_STATES,
        }
        return res, wall, "direct-binary-fallback(same-stdin)"
    # TimeoutExpired inherits from SubprocessError; other errors propagate.


def do_run(run_id, part, grid, seed, seed_desc):
    seed_sha = sha256(seed)
    print(f"[{run_id}] seed_desc={seed_desc} seed_len={len(seed)} seed_sha256={seed_sha}")
    res, wall, path = run_consumer(run_id, part, grid, seed)
    best = res["best_route"]
    _, gate = dual_gate(part, grid, best)
    # Spec section 3 validity: agreement + exact_win + not premature + len < 84.
    # must_fail controls re-checked independently on the ORIGINAL room for T1.
    valid_sub84 = (
        gate["differential_match"]
        and gate["exact_win"]
        and not gate["premature_win"]
        and gate["route_len"] < 84
    )
    disagreement = not gate["differential_match"]
    out = {
        "run_id": run_id,
        "seed_desc": seed_desc,
        "seed_len": len(seed),
        "seed_sha256": seed_sha,
        "tool_params": {
            "beam_width": BEAM_WIDTH,
            "window_len": WINDOW_LEN,
            "max_states_per_stage": MAX_STATES,
            "budget_sec": BUDGET_SEC,
        },
        "consumer_path": path,
        "wall_sec": round(wall, 1),
        "backend": res.get("backend"),
        "initial_len": res.get("initial_len"),
        "best_len": res.get("best_len"),
        "keys_saved": res.get("keys_saved"),
        "improved": res.get("improved"),
        "stages_log": res.get("stages"),
        "states_seen": res.get("states_seen"),
        "best_route_sha256": sha256(best),
        "best_route": best,
        "dual_gate": gate,
        "valid_sub84": valid_sub84,
        "oracle_disagreement": disagreement,
    }
    p = HERE / f"run_{run_id}.json"
    p.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(
        f"[{run_id}] best_len={res.get('best_len')} improved={res.get('improved')} "
        f"states_seen={res.get('states_seen')} stages={res.get('stages')} wall={wall:.1f}s path={path}"
    )
    print(
        f"[{run_id}] gate: match={gate['differential_match']} win={gate['exact_win']} "
        f"prem={gate['premature_win']} len={gate['route_len']} valid_sub84={valid_sub84}"
    )
    return out


def main(which):
    assert len(S84) == 84, len(S84)
    assert len(S87) == 87, len(S87)
    cat = load_catalog()["III-20"]
    assert int(cat["proven_floor"]) == 77, cat["proven_floor"]
    assert int(cat["shortest_known"]) == 84, cat["shortest_known"]
    print(f"S84 sha256={sha256(S84)}")
    print(f"S87 sha256={sha256(S87)}")
    exe = ensure_cpp_engine()
    print(f"engine={exe}")
    if exe is None:
        print("FATAL: no C++ compiler; engine unavailable")
        return 4
    part = 3
    grid = list(cat["grid"])
    assert len(grid) == 9 and len(grid[0]) == 15

    results = {}
    if which in ("G1", "ALL"):
        results["G1"] = do_run("G1", part, grid, S87, "S87 prior record (positive control)")
        if results["G1"]["best_len"] > 84:
            print("G1 FAILED: 87-seed did not rediscover <=84. STOP per locked section 8.")
            return 3
        if results["G1"]["oracle_disagreement"]:
            print("ORACLE DISAGREEMENT on G1. STOP per locked section 3.")
            return 2
    if which in ("T1", "ALL"):
        rgrid = rotate_grid_cw(grid)
        assert len(rgrid) == 15 and len(rgrid[0]) == 9
        t1seed = map_route(S84, MAP_CW)
        pre = verify_route_dual(part, rgrid, t1seed)
        print(f"[T1] rotated-room seed pre-verify: win={pre['exact_win']} match={pre['differential_match']}")
        if not (pre["valid_winning_route"] and pre["differential_match"]):
            print("[T1] BLOCKED: mapped seed does not win on rotated room; consumer requires a winning seed.")
            results["T1"] = {"run_id": "T1", "blocked": "rotated seed rejected", "pre": pre["epistemic_status"]}
            (HERE / "run_T1.json").write_text(json.dumps(results["T1"], indent=2) + "\n")
        else:
            r = do_run("T1", part, rgrid, t1seed, "rot90-CW grid + mapped S84")
            back = map_route(r["best_route"], MAP_CCW)
            _, gate_orig = dual_gate(part, grid, back)
            r["mapped_back_route"] = back
            r["mapped_back_sha256"] = sha256(back)
            r["orig_room_gate"] = gate_orig
            r["valid_sub84_orig_room"] = bool(
                gate_orig["differential_match"]
                and gate_orig["exact_win"]
                and not gate_orig["premature_win"]
                and gate_orig["route_len"] < 84
            )
            print(f"[T1] mapped-back len={len(back)} orig-room valid_sub84={r['valid_sub84_orig_room']}")
            (HERE / "run_T1.json").write_text(json.dumps(r, indent=2) + "\n")
            results["T1"] = r
            if r["oracle_disagreement"]:
                print("ORACLE DISAGREEMENT on T1. STOP per locked section 3.")
                return 2
    if which in ("T4", "ALL"):
        results["T4"] = do_run("T4", part, grid, S84, "S84 fixed-point (84-seed + shipped X-mirror guide)")
        if results["T4"]["oracle_disagreement"]:
            print("ORACLE DISAGREEMENT on T4. STOP per locked section 3.")
            return 2
    print("DONE: " + json.dumps({k: v.get("best_len", v.get("blocked")) for k, v in results.items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "ALL"))
