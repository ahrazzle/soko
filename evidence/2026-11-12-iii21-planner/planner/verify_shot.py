#!/usr/bin/env python3
"""Dual-oracle check of planner candidates, using PR 8."""
import sys
from pathlib import Path

sys.path.insert(0, "/workspace/soko-pr8")
from soko_mcp.catalog import load_catalog
from soko_mcp.engine_bridge import verify_route_dual

def load_route(path: Path) -> tuple[str, str]:
    name, route = path.stem, ""
    for line in path.read_text().splitlines():
        if line.startswith("name="):
            name = line[5:]
        elif line.startswith("route="):
            route = line[6:].strip()
    return name, route

def main():
    cat = load_catalog()
    room = cat["III-21"]
    grid, part = room["grid"], room["part"]
    args = sys.argv[1:]
    if not args:
        args = ["planner/runs/candidates.txt"]
    routes = []
    for a in args:
        p = Path(a)
        if not p.exists():
            print(f"missing {p}")
            continue
        if p.name == "candidates.txt":
            for line in p.read_text().splitlines():
                parts = line.split()
                if len(parts) >= 4:
                    q = Path(parts[-1])
                    routes.append(q if q.is_absolute() or q.exists() else p.parent / q)
        else:
            routes.append(p)
    if not routes:
        print("no candidates")
        return
    for rp in routes:
        name, route = load_route(rp)
        if not route:
            print(f"{name} EMPTY")
            continue
        v = verify_route_dual(part, grid, route)
        ok = v.get("valid_winning_route") and v.get("exact_win")
        print(
            f"{name} len={len(route)} valid={ok} "
            f"sha12={v.get('route_sha256_12')} "
            f"differential={v.get('differential_match')} "
            f"premature={v.get('premature_win')}"
        )
        if ok and len(route) < 316:
            print(f"  SHORTER THAN 316: {len(route)}")

if __name__ == "__main__":
    main()
