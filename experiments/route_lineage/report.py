#!/usr/bin/env python3
"""Print the lineage tables from lineage.py output.

1. Plan families: single-linkage clusters of routes whose milestone sets overlap
   (Jaccard) at or above each threshold.
2. Each record against the record it replaced: milestone overlap, order agreement,
   shared exact states, and whether the milestone set is unchanged.
3. The opening: the key at which a chosen milestone first happens (default: the
   III-21 goblin-pair kill, ``kill 13,9``), and the share of states before it that
   an earlier public route already visited.
"""
from __future__ import annotations

import argparse
import functools
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from soko_mcp.oracle import PuzzleScriptOracle  # noqa: E402

SEED = 0xCBF29CE484222325


def families(rs: list[dict], t: float) -> list[list[dict]]:
    sets = {r["id"]: {e[1] for e in r["milestones"]} for r in rs}
    parent = {r["id"]: r["id"] for r in rs}

    def find(i):
        while parent[i] != i:
            i = parent[i]
        return i

    for a in rs:
        for b in rs:
            sa, sb = sets[a["id"]], sets[b["id"]]
            if a["id"] < b["id"] and len(sa & sb) / len(sa | sb) >= t:
                parent[find(a["id"])] = find(b["id"])
    groups: dict = {}
    for r in rs:
        groups.setdefault(find(r["id"]), []).append(r)
    return sorted(groups.values(), key=lambda g: min(len(r["keys"]) for r in g))


@functools.lru_cache(maxsize=None)
def grid(room: str) -> tuple[str, ...]:
    return tuple(json.loads(subprocess.check_output([sys.executable, "-m", "soko_mcp", "get-room", "--room", room], cwd=ROOT))["grid"])


def states(room: str, keys: str) -> list[int]:
    g = list(grid(room))
    o = PuzzleScriptOracle(room.split("-")[0].count("I"), g)
    out = []
    for c in keys:
        o.step(c)
        out.append(o.fold_canonical_digest(SEED))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lineage", type=Path)
    ap.add_argument("--room", default="III-21")
    ap.add_argument("--opening", default="kill 13,9", help="milestone that ends the opening")
    args = ap.parse_args()
    d = json.loads(args.lineage.read_text())
    rs = sorted([r for r in d["routes"] if r["room"] == args.room], key=lambda r: r["at"])
    pairs = {(p["a"], p["b"]): p for p in d["pairs"]}

    print(f"## {args.room}: {len(rs)} routes, {len({r['handle'] for r in rs})} authors\n")
    print("### Plan families\n\n| Threshold | Families (shortest-longest keys, routes, authors) |\n| ---: | --- |")
    for t in (0.6, 0.7, 0.75, 0.8):
        fam = families(rs, t)
        desc = "; ".join(f"{min(len(r['keys']) for r in f)}-{max(len(r['keys']) for r in f)}, {len(f)}, {len({r['handle'] for r in f})}" for f in fam)
        print(f"| {t} | {len(fam)}: {desc} |")

    print("\n### Each record against the one it replaced\n")
    print("| Before | After | Saved | Authors | Milestones | Order | States | Same milestones |\n| ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |")
    for a, b in zip(rs, rs[1:]):
        p = pairs.get((a["id"], b["id"])) or pairs.get((b["id"], a["id"]))
        same = {e[1] for e in a["milestones"]} == {e[1] for e in b["milestones"]}
        who = a["handle"] if a["handle"] == b["handle"] else f"{a['handle']} -> {b['handle']}"
        print(f"| {len(a['keys'])} | {len(b['keys'])} | {len(a['keys']) - len(b['keys'])} | {who} | {p['events']:.2f} | {p['order']} | {p['states']:.2f} | {'yes' if same else 'no'} |")

    if not any(e[1] == args.opening for r in rs for e in r["milestones"]):
        return 0
    print(f"\n### The opening (keys before the first `{args.opening}`)\n")
    print("| Route | Keys | Author | Opening ends at key | Opening states seen on earlier routes |\n| ---: | ---: | --- | ---: | ---: |")
    seen: set[int] = set()
    for r in rs:
        s = states(r["room"], r["keys"])
        hits = [e[0] for e in r["milestones"] if e[1] == args.opening]
        if hits:
            op = s[: hits[0]]
            share = sum(1 for x in op if x in seen) / len(op)
            print(f"| {r['id']} | {len(r['keys'])} | {r['handle']} | {hits[0]} | {share:.2f} |")
        seen |= set(s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
