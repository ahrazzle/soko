#!/usr/bin/env python3
"""Reproduce the campaign's intermediate III-14 hypothesis, without searching.

This uses the local Python oracle, not the original game engine. It deliberately
checks the complete route as well as the tempting intermediate key saving.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from soko_mcp.oracle import PuzzleScriptOracle

GRID = [
    "###############",
    "#.............#",
    "#.5.}}}.]]]]].#",
    "#...}}}.]G.G].#",
    "#.D.}}}.]]]]].#",
    "#.............#",
    "###############",
]
REFERENCE = "LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR"
ALTERNATE_PREFIX = "LLULULULURURURURU"


def run(route: str) -> dict:
    oracle = PuzzleScriptOracle(3, GRID)
    alive = True
    first_win = None
    executed = 0
    for executed, key in enumerate(route, 1):
        alive, won = oracle.step(key)
        if won and first_win is None:
            first_win = executed
        if not alive or won:
            break
    locations = lambda chars: [[x, y] for y, row in enumerate(oracle.obj)
                               for x, char in enumerate(row) if char is not None and char in chars]
    return {
        "route": route,
        "keys": len(route),
        "steps_executed": executed,
        "alive": alive,
        "first_win": first_win,
        "valid_winning_route": alive and first_win == len(route),
        "crate_positions_xy_zero_based": locations("*"),
        "bard_positions_xy_zero_based": locations("B5"),
        "druid_positions_xy_zero_based": locations("D6"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, help="Optional result path; otherwise print JSON")
    args = ap.parse_args()
    cases = {
        "reference_prefix": run(REFERENCE[:18]),
        "alternate_prefix": run(ALTERNATE_PREFIX),
        "reference_complete": run(REFERENCE),
        "alternate_with_unmodified_reference_suffix": run(ALTERNATE_PREFIX + REFERENCE[18:]),
    }
    expected = (
        len(cases["reference_prefix"]["crate_positions_xy_zero_based"]) == 9
        and len(cases["alternate_prefix"]["crate_positions_xy_zero_based"]) == 9
        and cases["reference_complete"]["valid_winning_route"]
        and not cases["alternate_with_unmodified_reference_suffix"]["valid_winning_route"]
    )
    problem = {"part": 3, "grid": GRID}
    result = {
        "schema_version": 1,
        "scope": "Local-oracle intermediate-hypothesis reproduction; no original-engine or proof claim",
        "problem": problem,
        "problem_sha256": hashlib.sha256(json.dumps(problem, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "oracle_sha256": hashlib.sha256((ROOT / "soko_mcp/oracle.py").read_bytes()).hexdigest(),
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cases": cases,
        "expected_observations_reproduced": expected,
        "verified_complete_route_improvement": False,
    }
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return 0 if expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
