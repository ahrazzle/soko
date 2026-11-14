"""Left-right mirror analysis for III-21 (23x13).

Checks the static board (walls, goals, crates, monsters) for exact
left-right mirror symmetry with heroes stripped, computes the hero
permutation the mirror induces, and tests whether that permutation
commutes with the fixed hero-switch cycle. A mirror that preserved both
the board and the cycle would transport routes; III-21's does not,
because the permutation swaps hero *roles* (Fighter<->Priest,
Thief<->Bard, Wizard<->Druid). The result is therefore a geometry-only
symmetry, stated with its exact breaking cells, plus what it does and
does not license for search.

Usage (from the repo root):
  python3 evidence/2026-11-13-iii21-autopsy/mirror.py
Writes mirror.json next to itself.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

# Slot numbers follow the A-cycle order 1->2->3->4->5->6->1.
# Grid symbols: Fighter is 'F', the other heroes are their slot digits.
SLOT = {"F": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6}
ROLE = {1: "Fighter", 2: "Thief", 3: "Wizard",
        4: "Priest", 5: "Bard", 6: "Druid"}


def main():
    room = json.loads(subprocess.check_output(
        [sys.executable, "-m", "soko_mcp", "get-room", "--room", "III-21"],
        cwd=str(ROOT), text=True))
    grid = room["grid"]
    h, w = len(grid), len(grid[0])
    stripped = ["".join("." if c in "F123456" else c for c in row)
                for row in grid]
    mirrored = [row[::-1] for row in stripped]
    mismatches = [{"x": x, "y": y, "cell": stripped[y][x],
                   "mirror_cell": mirrored[y][x]}
                  for y in range(h) for x in range(w)
                  if stripped[y][x] != mirrored[y][x]]
    per_row = {y: sum(1 for m in mismatches if m["y"] == y) for y in range(h)}

    heroes = {}
    for y, row in enumerate(grid):
        for x, c in enumerate(row):
            if c in "F123456":
                heroes[c] = (x, y)
    # Mirror-x hero permutation, in slot numbers (F is slot 1).
    perm = {}
    for c, (x, y) in heroes.items():
        target = grid[y][w - 1 - x]
        perm[SLOT[c]] = SLOT[target]
    cycle = {1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 1}
    commutes = all(perm[cycle[s]] == cycle[perm[s]] for s in range(1, 7))
    role_preserving = all(perm[s] == s for s in range(1, 7))

    result = {
        "room": "III-21",
        "board": {"width": w, "height": h},
        "mirror_x_static_mismatches": len(mismatches),
        "mismatches_per_row": per_row,
        "mismatch_cells": mismatches,
        "symmetric_rows": [y for y in range(h) if per_row[y] == 0],
        "breaking_rows": [y for y in range(h) if per_row[y] > 0],
        "hero_permutation_slots": {str(k): v for k, v in perm.items()},
        "hero_permutation_roles": {
            ROLE[s]: ROLE[perm[s]] for s in range(1, 7)},
        "permutation_commutes_with_cycle": commutes,
        "permutation_preserves_roles": role_preserving,
        "conclusion": (
            "Left-right mirror is exact on the static board for rows "
            "0-6, 8 and 12 and breaks only in rows 7, 9, 10, 11 "
            "(16 cells, all in the Wizard/Druid chamber and its ceiling). "
            "The induced hero permutation commutes with the A-cycle but "
            "swaps every hero role, so the mirror is a geometry-only "
            "symmetry: it does NOT transport routes. It licenses "
            "geometry-equivalent single-hero sub-tasks in the symmetric "
            "bands and a symmetry-breaking search constraint, not a "
            "mirrored route."),
    }
    (HERE / "mirror.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
