#!/usr/bin/env python3
"""III-21 delivery and topology timeline, PR 8 official oracle."""
import sys, json
from collections import defaultdict
sys.path.insert(0, "/workspace/soko-pr8")
from soko_mcp.catalog import load_catalog
from soko_mcp.oracle import PuzzleScriptOracle
from soko_mcp.engine_bridge import verify_route_dual

ACTIVE = set("FTWPBD")
SLEEP = {"1": "F", "2": "T", "3": "W", "4": "P", "5": "B", "6": "D"}
ALLH = "FTWPBD"

def scan(sim):
    heroes = {}
    crates = []
    goblins = []
    walls_extra = []  # not needed
    for y, row in enumerate(sim.obj):
        for x, c in enumerate(row):
            if c in ACTIVE:
                heroes[c] = (x, y)
            elif c in SLEEP:
                heroes[SLEEP[c]] = (x, y)
            elif c == "*":
                crates.append((x, y))
            elif c == "O":
                goblins.append((x, y))
    goals = []
    hog_who = []
    for y, row in enumerate(sim.floor):
        for x, c in enumerate(row):
            if c == "G":
                goals.append((x, y))
                h = None
                o = sim.obj[y][x]
                if o in ACTIVE:
                    h = o
                elif o in SLEEP:
                    h = SLEEP[o]
                if h:
                    hog_who.append((h, (x, y)))
    act = sim.find_active()
    active = act[2] if act else None
    return heroes, tuple(sorted(crates)), tuple(sorted(goblins)), tuple(goals), hog_who, active, act

def ascii(sim):
    return sim.render_ascii()

cat = load_catalog()
room = cat["III-21"]
grid, part, route = room["grid"], room["part"], room["reference_route"]
v = verify_route_dual(part, grid, route)
assert v["valid_winning_route"] and v["exact_win"] and v["route_len"] == 316
print(f"VERIFIED 316 sha12={v['route_sha256_12']} differential={v['differential_match']}")

sim = PuzzleScriptOracle(part, grid)
h, cr, gb, goals, hog, active, act = scan(sim)
print("GOALS", goals)
print(f"k=0 active={active} heroes={h} crates={cr} goblins={gb} hog={hog}")

events = []
prev = (h, cr, gb, hog, active)
# stretches
stretches = []
cur_h = active
cur_start = 0
n_A = 0

for i, k in enumerate(route, 1):
    if k == "A":
        n_A += 1
    alive, won = sim.step(k)
    h, cr, gb, goals, hog, active, act = scan(sim)
    ph, pcr, pgb, phog, pact = prev
    notes = []
    if k == "A" or active != pact:
        notes.append(f"active {pact}->{active}")
        if pact != cur_h:
            pass
        # close stretch on switch completed (A is the switch key)
        stretches.append((cur_start, i, pact, cur_h if k=="A" else active))
        # actually: before A, pact was acting; after A, active is new
        # stretch of pact is cur_start .. i-1, then A at i
    if h != ph:
        moved = []
        for name in ALLH:
            if h.get(name) != ph.get(name):
                moved.append(f"{name}{ph.get(name)}->{h.get(name)}")
        notes.append("MOVE " + " ".join(moved))
    if cr != pcr:
        notes.append(f"CRATES {pcr} -> {cr}")
    if gb != pgb:
        dead = set(pgb) - set(gb)
        new = set(gb) - set(pgb)
        notes.append(f"GOBLINS dead={sorted(dead)} new={sorted(new)}")
    if hog != phog:
        notes.append(f"HOG {len(phog)}->{len(hog)} {hog}")
    if not alive:
        notes.append("DEAD")
    if won:
        notes.append("WIN")
    if notes:
        events.append((i, k, active, notes, h, hog, len(gb), len(cr)))
    prev = (h, cr, gb, hog, active)
    if k == "A":
        cur_h = active
        cur_start = i  # stretch starts after A? or including? work starts next key
        cur_start = i + 1 if i < len(route) else i

print(f"\n=== EVENTS ({len(events)}) A-count={n_A} final active={active} won={won} alive={alive} ===")
print(f"FINAL heroes={h}")
print(f"FINAL hog={hog}")
print(f"FINAL crates={cr}")
print(f"FINAL goblins={gb}")
print()

# Print compact event log (skip pure MOVEs that aren't hog/crate/goblin/switch-with-context)
# We'll print all switches + topology + hog, and first arrival of each hero on any goal.
first_goal = {}
for i, k, active, notes, h, hog, ng, nc in events:
    for who, pos in hog:
        if who not in first_goal:
            first_goal[who] = (i, pos)
    flag = any(n.startswith(("CRATES","GOBLINS","HOG","WIN","DEAD","active")) for n in notes)
    if flag:
        short = "; ".join(notes)
        print(f"{i:3d} {k} act={active} {short}")

print("\n=== FIRST GOAL ARRIVAL ===")
for who, (i, pos) in first_goal.items():
    print(f"  {who} at key {i} on {pos}")

print("\n=== FINAL ASSIGNMENT ===")
assignment = {who: pos for who, pos in hog}
print(assignment)

# Reconstruct stretches properly: consecutive non-A keys for same hero
print("\n=== HERO STRETCHES (len>=3 or topology) ===")
sim = PuzzleScriptOracle(part, grid)
active0 = scan(sim)[5]
start = 0
hero = active0
# After each A, hero changes
idx = 0
while idx < len(route):
    # collect until A or end
    j = idx
    keys = []
    while j < len(route) and route[j] != "A":
        keys.append(route[j])
        j += 1
    # keys[0:j-idx] is work; then maybe AAAA
    work = "".join(keys)
    nA = 0
    while j < len(route) and route[j] == "A":
        nA += 1
        j += 1
    print(f"  keys {idx+1}-{idx+len(work)} {hero} {work}  then {nA}A" if work or nA else "")
    for _ in range(len(work) + nA):
        if idx < len(route):
            sim.step(route[idx])
            idx += 1
    hero = scan(sim)[5]

# hog over time (every time it changes, already printed)
# assignment-manhattan at end
print("\n=== ASCII every 20 keys and at hog changes ===")
sim = PuzzleScriptOracle(part, grid)
prev_hog_n = 0
for i, k in enumerate(route, 1):
    sim.step(k)
    h, cr, gb, goals, hog, active, act = scan(sim)
    if len(hog) != prev_hog_n or i in (29, 57, 137, 182, 246, 262, 289, 296, 302, 312, 316) or i % 50 == 0:
        print(f"\n--- after key {i} '{k}' active={active} hog={len(hog)} {hog} crates={len(cr)} goblins={len(gb)} ---")
        print(sim.render_ascii())
        print("heroes", h)
        prev_hog_n = len(hog)
