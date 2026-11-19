#!/usr/bin/env python3
"""Immutable Zero-Shared-Code Dual-Oracle Track Verifier for III-20 (Heroes of Sokoban III, Room 20 (Goblin Corridor — @a1kindus Chiral Record)).

Modeled on the `Foundation-0/incentre-lattices` locked-checker `tracks/` architecture:
replays candidate U/D/L/R/A routes through BOTH `PuzzleScriptOracle` and `FlatBitmaskOracle`,
verifies bit-exact 64-bit FNV-1a per-frame trajectory digest parity, and checks against
the current track best (84 keys).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from soko_mcp.flat_oracle import replay_flat_oracle
from soko_mcp.oracle import FRONTIER_ROOMS, replay_oracle

ROOM_ID = 'III-20'
PUBLISHED_FRONTIER_FLOOR = 74
REFERENCE_BEST_LEN = 84
REFERENCE_ROUTE = 'ADDDRRADAAADRULARADAAADDLLALAAAARRRRUULAAUALLRADRRRRADRULRURRRRRARRUURURAURRRDDRAUUR'


def verify_candidate(route: str = REFERENCE_ROUTE) -> dict:
    meta = FRONTIER_ROOMS[ROOM_ID]
    clean = route.strip().upper()
    spec_res = replay_oracle(int(meta["part"]), list(meta["grid"]), clean)
    flat_res = replay_flat_oracle(int(meta["part"]), list(meta["grid"]), clean)
    parity = (
        spec_res["alive"] == flat_res["alive"]
        and spec_res["exact_win"] == flat_res["exact_win"]
        and spec_res["premature_win"] == flat_res["premature_win"]
        and spec_res["traj_fnv64"] == flat_res["traj_fnv64"]
        and spec_res["final_ascii"] == flat_res["final_ascii"]
    )
    valid = bool(parity and spec_res["exact_win"] and not spec_res["premature_win"])
    return {
        "epistemic_status": "VERIFIED" if valid else "REJECTED",
        "room_id": ROOM_ID,
        "valid_winning_route": valid,
        "dual_oracle_parity": parity,
        "route_len": len(clean),
        "beats_reference_best": valid and len(clean) < REFERENCE_BEST_LEN,
        "published_frontier_floor": PUBLISHED_FRONTIER_FLOOR,
        "route_sha256_12": hashlib.sha256(clean.encode("utf-8")).hexdigest()[:12],
        "traj_fnv64": spec_res["traj_fnv64"],
    }


if __name__ == "__main__":
    cand = sys.argv[1] if len(sys.argv) > 1 else REFERENCE_ROUTE
    rep = verify_candidate(cand)
    print(json.dumps(rep, indent=2))
    raise SystemExit(0 if rep["valid_winning_route"] else 1)
