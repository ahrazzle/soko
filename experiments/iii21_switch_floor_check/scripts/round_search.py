"""Task 3. Bounded exact searches with the real oracle from a handoff position (the record's key-195 state).
 S1: first Druid visit. 5 presses to reach D, then every state reachable by Druid-only keys (free closure).
     Report state count, whether closure is exhausted, and the least count of Druid cuts (repo bound) reached.
 S2: press-layered search: states reachable with at most p presses (moves free), layer by layer, until a state cap.
     Report states per layer, whether a win was seen, and the best progress (fewest unfinished heroes, lowest H_OC)."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
MOVES = "UDLR"
def closure(starts, cap):
    """All states reachable from starts by direction keys only (the active hero stays the same). Returns list, exhausted flag."""
    seen = {}
    stack = []
    for s in starts:
        sig = s.state_signature()
        if sig not in seen: seen[sig] = s; stack.append(s)
    while stack:
        s = stack.pop()
        for k in MOVES:
            c = s.clone(); c.step(k)
            sig = c.state_signature()
            if sig in seen: continue
            seen[sig] = c; stack.append(c)
            if len(seen) > cap: return list(seen.values()), False
    return list(seen.values()), True
def druid_cuts(o):
    return H.evaluate_operator_counting_bound(o).disjoint_druid_cuts
def run(prefix, label, cap1, cap2, maxp):
    o = new_oracle()
    for k in prefix: o.step(k)
    print(f"== {label}: active {active(o)}, keys {len(prefix)}", flush=True)
    # S1: Druid first
    s = o
    for _ in range((CYC_IDX["D"] - CYC_IDX[active(o)]) % 6):
        s = s.clone(); s.step("A")
    assert active(s) == "D", active(s)
    t = time.time()
    states, ex = closure([s], cap1)
    best = min(druid_cuts(x) for x in states)
    print(f"S1 Druid-first visit: {len(states)} states, exhausted={ex}, druid_cuts at start={druid_cuts(s)}, least reached={best}, {time.time()-t:.0f}s", flush=True)
    res = {"label": label, "S1_states": len(states), "S1_exhausted": ex, "S1_cuts_start": druid_cuts(s), "S1_cuts_least": best}
    # S2: press layer 0 (F alone, free moves) exhaustively, then estimate layer 1 from a sample
    t = time.time()
    cl0, ex0 = closure([o], cap2)
    win0 = any(x.check_win() for x in cl0)
    print(f"S2 layer p=0 (active hero alone): {len(cl0)} states, exhausted={ex0}, win={win0}, {time.time()-t:.0f}s", flush=True)
    import random
    random.seed(1)
    samp = random.sample(cl0, 8)
    sizes = []
    for x in samp:
        c = x.clone(); c.step("A")
        cl1, ex1 = closure([c], 30000)
        sizes.append((len(cl1), ex1))
        print(f"  sample layer-1 closure (next hero alone): {len(cl1)} states, exhausted={ex1}", flush=True)
    res.update({"S2_layer0_states": len(cl0), "S2_layer0_exhausted": ex0, "S2_layer0_win": win0, "S2_layer1_samples": sizes})
    return res
CYC_IDX = {h: i for i, h in enumerate(ORDER)}
if __name__ == "__main__":
    r = ROOM["reference_route"]
    out = [run(r[:195], "record handoff key 195", 400000, 400000, 0)]
    (HERE.parent / "out/round_search.json").write_text(json.dumps(out, indent=1))
