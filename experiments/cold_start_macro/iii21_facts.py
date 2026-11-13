#!/usr/bin/env python3
"""Recompute the counts in docs/iii21-anatomy.md from the pinned grid and the record route."""
import itertools
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from soko_mcp.oracle import PuzzleScriptOracle  # noqa: E402

ORDER = "FTWPBD"
STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def main() -> None:
    d = json.loads(subprocess.check_output([sys.executable, "-m", "soko_mcp", "get-room", "--room", "III-21"], cwd=ROOT))
    g, route = d["grid"], d["reference_route"]
    w, h = len(g[0]), len(g)

    # Laps: hero segments in the record and wraps around the fixed switch order.
    o, seq = PuzzleScriptOracle(3, g), []
    moves = dict.fromkeys(ORDER, 0)
    for is_a, grp in itertools.groupby(route, key=lambda c: c == "A"):
        keys = "".join(grp)
        if not is_a:
            seq.append(o.find_active()[2])
            moves[seq[-1]] += len(keys)
        for c in keys:
            o.step(c)
    wraps = sum(1 for a, b in zip(seq, seq[1:]) if ORDER.index(b) <= ORDER.index(a))
    print(f"record: {len(route)} keys, {route.count('A')} A, {len(seq)} segments, {wraps} wraps, moves {moves}")
    print(f"A mod 6 = {route.count('A') % 6}; (end - start) mod 6 = {(ORDER.index(seq[-1]) - ORDER.index(seq[0])) % 6}")

    # Walkable cells per hero at the start, never stopping next to a goblin.
    gob = {(x, y) for y in range(h) for x in range(w) if g[y][x] == "O"}
    goals = {(x, y) for y in range(h) for x in range(w) if g[y][x] == "G"}
    safe = lambda p: all((p[0] + dx, p[1] + dy) not in gob for dx, dy in STEPS)  # noqa: E731
    for y in range(h):
        for x in range(w):
            if g[y][x] in "F23456":
                seen, q = {(x, y)}, [(x, y)]
                for p in q:
                    for dx, dy in STEPS:
                        n = (p[0] + dx, p[1] + dy)
                        if n not in seen and g[n[1]][n[0]] in ".G" and safe(n):
                            seen.add(n)
                            q.append(n)
                print(f"hero {g[y][x]} at {(x, y)}: {len(seen)} walkable cells, exits reachable {sorted(seen & goals)}")

    # One-wall breaches: an interior wall whose opposite neighbours lie in different non-wall regions.
    comp, cid = {}, 0
    for y in range(h):
        for x in range(w):
            if g[y][x] != "#" and (x, y) not in comp:
                cid += 1
                comp[(x, y)], q = cid, [(x, y)]
                for p in q:
                    for dx, dy in STEPS:
                        n = (p[0] + dx, p[1] + dy)
                        if 0 <= n[0] < w and 0 <= n[1] < h and g[n[1]][n[0]] != "#" and n not in comp:
                            comp[n] = cid
                            q.append(n)
    breaches = [(x, y) for y in range(1, h - 1) for x in range(1, w - 1) if g[y][x] == "#"
                for a, b in (((x - 1, y), (x + 1, y)), ((x, y - 1), (x, y + 1)))
                if a in comp and b in comp and comp[a] != comp[b]]
    print(f"{cid} non-wall regions; {len(breaches)} one-wall breaches: {breaches}")


if __name__ == "__main__":
    main()
