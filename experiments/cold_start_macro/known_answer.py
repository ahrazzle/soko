#!/usr/bin/env python3
"""Known-answer test: does a stalled local optimizer say anything about the optimum?

For each closed Part III room (Frontier floor equals the shortest known route):
  1. Build a poor seed route with the cold-start search (strat.cpp). It never reads
     a reference route.
  2. Run `soko_mcp optimize` on the seed, then on its own output, until it reports
     no improvement (a fixed point) or the round limit is reached.
  3. Null control: run the optimizer on the proven-optimal reference route.
Report the fixed point, the proven optimum and the gap.

The claim under test: the optimizer's "no improvement" verdict is the same whether
the route is optimal or far from optimal. If that holds on even one room, then a
stall from a seeded start is evidence about the seed's neighbourhood only.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ROOMS = ["III-10", "III-12", "III-13", "III-15", "III-16"]


def room(rid: str) -> dict:
    out = subprocess.check_output([sys.executable, "-m", "soko_mcp", "get-room", "--room", rid], cwd=ROOT)
    return json.loads(out)


def optimize(rid: str, route: str, budget: int) -> dict:
    out = subprocess.run([sys.executable, "-m", "soko_mcp", "optimize", "--room", rid, "--route", route,
                          "--budget-sec", str(budget)], cwd=ROOT, capture_output=True, text=True)
    return json.loads(out.stdout)


def cold_seed(binary: Path, rid: str, k: int, seconds: int) -> str:
    r = room(rid)
    grid = r["grid"]
    stdin = f"{len(grid[0])} {len(grid)}\n" + "\n".join(grid) + "\n"
    out = subprocess.run([str(binary), "--K", str(k), "--nov", "1", "--time", str(seconds)], input=stdin,
                         capture_output=True, text=True).stdout
    routes = [line.split()[1] for line in out.splitlines() if line.startswith("ROUTE ")]
    if not routes:
        raise RuntimeError(f"cold search found no route for {rid}")
    return routes[-1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rooms", nargs="*", default=ROOMS)
    ap.add_argument("--k", type=int, default=4, help="states kept per progress cell in the cold search")
    ap.add_argument("--cold-seconds", type=int, default=80)
    ap.add_argument("--budget", type=int, default=60, help="optimizer budget per round, seconds")
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    tcb = subprocess.run(["sha256sum", "-c", "--quiet", "SHA256SUMS"], cwd=ROOT, capture_output=True, text=True)
    if tcb.returncode != 0:
        print("SHA256SUMS does not verify; the optimizer would reject every route.\n" + tcb.stdout, file=sys.stderr)
        return 2
    binary = Path("/tmp/soko-cold-strat")
    subprocess.check_call(["g++", "-O2", "-std=c++20", str(HERE / "strat.cpp"), "-o", str(binary)])

    rows = []
    for rid in args.rooms:
        r = room(rid)
        if r.get("proven_floor") != r.get("shortest_known"):
            print(f"skip {rid}: not closed", file=sys.stderr)
            continue
        opt = r["shortest_known"]
        seed = cold_seed(binary, rid, args.k, args.cold_seconds)
        trail, route = [len(seed)], seed
        stalled = False
        for _ in range(args.rounds):
            res = optimize(rid, route, args.budget)
            if "error" in res:
                raise RuntimeError(f"{rid}: {res['error']}")
            if not res["improved"]:
                stalled = True
                break
            route = res["best_route"]
            trail.append(len(route))
        null = optimize(rid, r["reference_route"], args.budget)
        rows.append({
            "room": rid, "proven_optimum": opt, "cold_seed_len": len(seed), "trail": trail,
            "final_len": len(route), "stalled_at_fixed_point": stalled, "gap_at_stop": len(route) - opt,
            "null_control_improved": null.get("improved"), "null_control_len": null.get("best_len"),
            "cold_seed": seed, "final_route": route,
        })
        print(json.dumps({k: rows[-1][k] for k in ("room", "proven_optimum", "trail", "stalled_at_fixed_point",
                                                    "gap_at_stop", "null_control_improved")}))
    args.output.write_text(json.dumps(rows, indent=2) + "\n")
    false_stalls = [r["room"] for r in rows if r["stalled_at_fixed_point"] and r["gap_at_stop"] > 0]
    print(f"false stalls (no-improvement verdict above the proven optimum): {false_stalls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
