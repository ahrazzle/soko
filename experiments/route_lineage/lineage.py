#!/usr/bin/env python3
"""Are published routes independent attempts, or one plan polished many times?

For each route, replay it in the spec oracle and record its *milestones*: the
irreversible changes to the board, in the order they first happen.

- ``open x,y``: an interior wall cell stops being a wall (the Druid turned it into a crate).
- ``wall x,y``: a cell that was not a wall becomes one (crate set as wall, petrified hero).
- ``kill x,y``: the goblin that *started* at (x,y) dies.
- ``petrify x,y``: the goblin that started at (x,y) is turned into a wall.

Goblins carry an identity through every push, pull, swap and carry: each one is a
``str`` subclass equal to ``"O"``, so the oracle moves it unchanged. A death is
recorded where the oracle removes goblins (``_run_late``), so a goblin pushed or
swapped along is never mistaken for a dead one. (Before 2026-11-20 the labels
were guessed from board differences, which invented kills on chain pushes, Wizard
swaps and petrifications.)

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


class _Goblin(str):
    """A goblin that remembers its starting cell. Equal to "O" everywhere the oracle looks."""

    def __new__(cls, start: tuple[int, int]):
        g = super().__new__(cls, "O")
        g.start = start
        return g

    __hash__ = str.__hash__


class _TrackedOracle(PuzzleScriptOracle):
    """Records which goblins the late phase removes (deaths), by identity."""

    def _run_late(self) -> bool:
        before = _goblins(self)
        alive = super()._run_late()
        after = _goblins(self)
        self.deaths = getattr(self, "deaths", []) + [g for g in before if g not in after]
        return alive


def _goblins(o: PuzzleScriptOracle) -> dict[tuple[int, int], tuple[int, int]]:
    """Map each goblin's starting cell to its current cell."""
    return {o.obj[y][x].start: (x, y) for y in range(o.h) for x in range(o.w) if isinstance(o.obj[y][x], _Goblin)}


def cells(o: PuzzleScriptOracle, ch: str) -> set[tuple[int, int]]:
    return {(x, y) for y in range(o.h) for x in range(o.w) if o.obj[y][x] == ch}


def milestones(room: str, keys: str) -> dict:
    g = grid(room)
    o = _TrackedOracle(int(room.split("-")[0].count("I")), g)
    for y in range(o.h):
        for x in range(o.w):
            if o.obj[y][x] == "O":
                o.obj[y][x] = _Goblin((x, y))
    walls = cells(o, "#")
    seen: dict[tuple, int] = {}
    events: list[list] = []
    states = {o.fold_canonical_digest(0xCBF29CE484222325)}

    def note(kind: str, c: tuple[int, int], t: int) -> None:
        key = (kind, c)
        seen[key] = seen.get(key, 0) + 1
        label = f"{kind} {c[0]},{c[1]}" + (f" #{seen[key]}" if seen[key] > 1 else "")
        events.append([t, label])

    for t, k in enumerate(keys, 1):
        before = _goblins(o)
        o.deaths = []
        o.step(k)
        states.add(o.fold_canonical_digest(0xCBF29CE484222325))
        after, w = _goblins(o), cells(o, "#")
        petrified = set()
        for start, c in sorted(before.items()):
            if start in after:
                continue
            if start in o.deaths:
                note("kill", start, t)
            elif c in w:
                note("petrify", start, t)
                petrified.add(c)
            else:
                raise RuntimeError(f"goblin from {start} vanished at key {t} without dying or petrifying")
        for c in sorted(walls - w):
            note("open", c, t)
        for c in sorted(w - walls - petrified):
            note("wall", c, t)
        walls = w
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
