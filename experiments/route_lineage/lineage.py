#!/usr/bin/env python3
"""Are published routes independent attempts, or one plan polished many times?

For each route, replay it in the spec oracle and record its *milestones*: the
irreversible changes to the board, in the order they first happen.

- ``open x,y``: an interior wall cell stops being a wall (the Druid turned it into a crate).
- ``wall x,y``: a cell that was not a wall becomes one (petrified goblin or hero, crate set as wall).
- ``kill x,y``: a goblin dies; the cell is where it stood on the previous frame.

A route's plan is its milestone list. Two routes have the same plan when they
reach the same milestones in the same order. Two numbers compare routes A and B:

- ``events``: Jaccard overlap of the two milestone sets (1.0 = same milestones).
- ``order``: among milestones both routes reach, the fraction of pairs that occur
  in the same order (1.0 = same order; 0.5 = unrelated order).
- ``states``: Jaccard overlap of the sets of exact full board states visited.
  Independent searches rarely pass through the same exact states unless the room
  forces it, so a high value marks a copied or polished route.

Input: a JSON list of {"room", "id", "keys", ...}. Output: JSON with each route's
milestones and every pairwise comparison within a room.
"""
from __future__ import annotations

import argparse
import itertools
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from soko_mcp.oracle import PuzzleScriptOracle  # noqa: E402

_GRIDS: dict[str, list[str]] = {}


def grid(room: str) -> list[str]:
    if room not in _GRIDS:
        out = subprocess.check_output([sys.executable, "-m", "soko_mcp", "get-room", "--room", room], cwd=ROOT)
        _GRIDS[room] = json.loads(out)["grid"]
    return _GRIDS[room]


def cells(o: PuzzleScriptOracle, ch: str) -> set[tuple[int, int]]:
    return {(x, y) for y in range(o.h) for x in range(o.w) if o.obj[y][x] == ch}


def milestones(room: str, keys: str) -> dict:
    g = grid(room)
    o = PuzzleScriptOracle(int(room.split("-")[0].count("I")), g)
    walls0 = cells(o, "#")
    walls, gobs = set(walls0), cells(o, "O")
    seen: dict[tuple, int] = {}
    events: list[list] = []
    states = {o.fold_canonical_digest(0xCBF29CE484222325)}

    def note(kind: str, c: tuple[int, int], t: int) -> None:
        key = (kind, c)
        seen[key] = seen.get(key, 0) + 1
        label = f"{kind} {c[0]},{c[1]}" + (f" #{seen[key]}" if seen[key] > 1 else "")
        events.append([t, label])

    for t, k in enumerate(keys, 1):
        o.step(k)
        states.add(o.fold_canonical_digest(0xCBF29CE484222325))
        w, gb = cells(o, "#"), cells(o, "O")
        for c in sorted(walls - w):
            note("open", c, t)
        for c in sorted(w - walls):
            note("wall", c, t)
        # A goblin that left without a goblin appearing next to it died (pushes move one cell).
        appeared = gb - gobs
        for c in sorted(gobs - gb):
            near = [a for a in appeared if abs(a[0] - c[0]) + abs(a[1] - c[1]) == 1]
            if near:
                appeared.discard(near[0])
            else:
                note("kill", c, t)
        walls, gobs = w, gb
    return {"events": events, "won": o.check_win(), "states": states}


def compare(a: dict, b: dict) -> dict:
    ea = [e[1] for e in a["events"]]
    eb = [e[1] for e in b["events"]]
    sa, sb = set(ea), set(eb)
    common = [e for e in ea if e in sb]
    pos_b = {e: i for i, e in enumerate(eb)}
    pairs = list(itertools.combinations(common, 2))
    agree = sum(1 for x, y in pairs if pos_b[x] < pos_b[y])
    return {
        "events": round(len(sa & sb) / max(1, len(sa | sb)), 3),
        "order": round(agree / len(pairs), 3) if pairs else None,
        "states": round(len(a["states"] & b["states"]) / len(a["states"] | b["states"]), 3),
        "only_a": sorted(sa - sb),
        "only_b": sorted(sb - sa),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("routes", type=Path, help="JSON list of {room, id, keys}")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    routes = json.loads(args.routes.read_text())
    for r in routes:
        m = milestones(r["room"], r["keys"])
        r.update(won=m["won"], milestones=m["events"], _m=m)
        print(f"{r['room']} {r['id']} len={len(r['keys'])} won={m['won']} milestones={len(m['events'])}", file=sys.stderr)
    pairs = []
    for a, b in itertools.combinations(routes, 2):
        if a["room"] == b["room"]:
            pairs.append({"room": a["room"], "a": a["id"], "b": b["id"], **compare(a["_m"], b["_m"])})
    for r in routes:
        r.pop("_m")
    args.output.write_text(json.dumps({"routes": routes, "pairs": pairs}, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
