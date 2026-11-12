#!/usr/bin/env python3
"""Exact shortest-win BFS from prefixes of known III-14 routes."""
from __future__ import annotations
import sys, time, os
from collections import deque
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/workspace/soko")
import iii14_search as m
from soko_mcp.engine_bridge import verify_route_dual

MOVES = "UDLRA"

def vis_key(s: m.S):
    # notes and doors are derived
    return (s.walls, s.crates, s.bx, s.by, s.dx, s.dy, s.bard_active)

def exact_from(prefix: str, start: m.S, max_depth: int, time_budget: float, label: str):
    t0 = time.perf_counter()
    q = deque()
    q.append((vis_key(start), start, ""))
    seen = {vis_key(start): 0}
    wins = []
    expanded = 0
    while q:
        if time.perf_counter() - t0 > time_budget:
            break
        key, st, path = q.popleft()
        d = len(path)
        if d >= max_depth:
            continue
        expanded += 1
        for mv in MOVES:
            ns = m.step(st, mv)
            if ns is None:
                continue
            np = path + mv
            if ns.win():
                cand = prefix + np
                wins.append(cand)
                max_depth = len(np) - 1  # stricter
                print(f"  [{label}] WIN {len(cand)} (suffix {len(np)}) {cand}  t={time.perf_counter()-t0:.1f}s exp={expanded}", flush=True)
                continue
            if len(np) >= max_depth:
                continue
            k = vis_key(ns)
            if k in seen:
                continue
            seen[k] = len(np)
            q.append((k, ns, np))
    dt = time.perf_counter() - t0
    best = min(wins, key=len) if wins else None
    print(f"[{label}] done t={dt:.1f}s expanded={expanded} seen={len(seen)} queue={len(q)} "
          f"best={len(best) if best else 'none'} max_d={max_depth}", flush=True)
    return best

def main():
    cuts = [18, 19, 21, 25, 26, 28, 33, 34, 38, 40, 41]
    # also a couple mid points
    route = m.SEED
    states = m.traj_states(route)
    # time budgets: later cuts get exact full remaining; earlier get more time
    # remaining in 48-route at cut c is 48-c; we search up to (48-c-1) for improvement,
    # and also allow equal to report if 48 is already shortest from that cut.
    budgets = {
        18: 90.0, 19: 60.0, 21: 60.0,
        25: 90.0, 26: 60.0, 28: 60.0,
        33: 45.0, 34: 45.0, 38: 20.0, 40: 15.0, 41: 10.0,
    }
    results = []
    for c in cuts:
        s = m.S.unpack(states[c])
        remain = len(route) - c
        # search one less than current remaining to find improvements;
        # for late cuts also allow equal (prove minimality of suffix)
        max_d = remain - (0 if c >= 33 else 1)
        label = f"cut{c} remain{remain}"
        print(f"=== exact {label} max_d={max_d} budget={budgets[c]}s ===", flush=True)
        # dump a one-liner of the state
        sw = bin((s.crates | s.walls) & m.SWITCH_MASK).count("1")
        print(f"    B=({s.bx},{s.by}) D=({s.dx},{s.dy}) act={'B' if s.bard_active else 'D'} "
              f"crates={bin(s.crates).count('1')} sw={sw}/9", flush=True)
        best = exact_from(route[:c], s, max_d, budgets[c], label)
        if best:
            v = verify_route_dual(3, m.GRID, best)
            print(f"    verified={v['valid_winning_route']} len={len(best)} {best}", flush=True)
            if v["valid_winning_route"]:
                results.append(v["route"])

    # also exact from start with small depth just in case a very short exists (won't, need 9 transmutes + pack + enter)
    if results:
        best = min(results, key=len)
        print("BEST", len(best), best, flush=True)
        open("best.txt","w").write(f"{len(best)}\n{best}\n")
    else:
        print("NO IMPROVEMENT from exact BFS on 48-route cuts", flush=True)

if __name__ == "__main__":
    main()
