#!/usr/bin/env python3
"""Try shorter W-escape sequences from cut 246 using PR 8 oracle."""
import sys
sys.path.insert(0, "/workspace/soko-pr8")
from soko_mcp.catalog import load_catalog
from soko_mcp.oracle import PuzzleScriptOracle

cat = load_catalog()
room = cat["III-21"]
route = room["reference_route"]
ACTIVE=set("FTWPBD"); SLEEP={"1":"F","2":"T","3":"W","4":"P","5":"B","6":"D"}

def play(prefix, extra, label, show=True):
    sim = PuzzleScriptOracle(room["part"], room["grid"])
    keys = prefix + extra
    for i,k in enumerate(keys,1):
        alive,won=sim.step(k)
        if not alive:
            if show:
                print(f"{label}: DEAD at {i} key={k}")
                print(sim.render_ascii())
            return sim, False, i
        if won:
            if show:
                print(f"{label}: WIN at {i} (prefix {len(prefix)} extra {len(extra)})")
                print(sim.render_ascii())
            return sim, True, i
    if show:
        h={}
        crates=[]
        for y,row in enumerate(sim.obj):
            for x,c in enumerate(row):
                if c in ACTIVE: h[c]=(x,y)
                elif c in SLEEP: h[SLEEP[c]]=(x,y)
                elif c=='*': crates.append((x,y))
        print(f"\n======= {label} n={len(keys)} (+{len(extra)} from {len(prefix)}) act={sim.find_active()} notes={sim.notes} =======")
        print(sim.render_ascii())
        print("heroes", h)
        print("crates", sorted(crates))
    return sim, True, len(keys)

base246 = route[:246]
# Record escape
play(base246, route[246:280], "RECORD 280")

# After 7L + A: D active, try compact convert
# LLLLLLL A DD  = 7+1+2 convert (1,8)
play(base246, "LLLLLLLADD", "after DD convert 1,8")

# Try: LLLLLLL A DD AAAAA (to Bard) and see board
# Cycle from D: A=F, A=T, A=W, A=P, A=B
play(base246, "LLLLLLLADDAAAAA", "D converted, 5A to Bard")

# Maybe D DDRD (record first convert both walls) then AAAAA to B
play(base246, "LLLLLLLADDRDAAAAA", "DDRD + 5A Bard")

# After LLLLLLL, Bard is still... wait A already switched to D. 
# Could Bard do more L's? Already at (3,6). 
# What if we A to D earlier, after only enough L's to have D at (1,7) or (1,6)?
# After 6 L's (not 7): from start D(8,6) P(9,6) B(10,6)
# L: D7,P8,B9
# L: D6,P7,B8
# L: D5,P6,B7  -- D ON DEATH CELL (5,6) with P at (6,6) healing
# L: D4,P5,B6  -- P on death cell, safe
# L: D3,P4,B5
# L: D2,P3,B4
# L: D1,P2,B3  -- 7th L
# After 6 L's: D(2,6), P(3,6), B(4,6). Then A to D, D L to (1,6), D D to (1,7)...
# That's similar length.

# Try converting (1,8) then moving D away and using Thief?
# Or after DD, D moves R (out), AAAAA Bard charms crate U or L
play(base246, "LLLLLLLADDR", "DDR (D at 2,7, crate 1,8)")
