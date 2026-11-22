"""Task 2. Winding of the activation order vs count of A presses, on catalog routes of Part III.
Acting sequence: active hero at each non-A key, consecutive repeats collapsed (start = initially active hero).
Winding W = sum over consecutive acting heroes of the cyclic distance among heroes alive at that moment.
Identity checked: presses == W (no wasted loop, none after the last action). Also reported per route."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
CYC = ["F", "T", "W", "P", "B", "D"]
def alive(o):
    return [h for h in CYC if h in hero_pos(o)]
def analyse(part, grid, route, start_from=0):
    o = PuzzleScriptOracle(part, grid)
    for k in route[:start_from]:
        o.step(k)
    cur = active(o)
    presses = 0; winding = 0; presses_since = 0; trans = []; bad = []; acting = [cur]
    for i, k in enumerate(route[start_from:], start_from + 1):
        if k == "A":
            presses += 1; presses_since += 1
            o.step(k)
            continue
        act = active(o)
        if act is None:
            bad.append((i, 'dead', None, 0, 0)); break
        if act != acting[-1]:
            al = alive(o)
            d = (al.index(act) - al.index(acting[-1])) % len(al)
            winding += d
            if d != presses_since: bad.append((i, acting[-1], act, d, presses_since))
            acting.append(act)
        elif presses_since:
            bad.append((i, act, act, 0, presses_since))
        presses_since = 0
        o.step(k)
    tail = presses_since
    return {"presses": presses, "winding": winding, "tail_presses_after_last_action": tail,
            "transitions": len(acting) - 1, "mismatched_transitions": bad[:5], "n_mismatch": len(bad),
            "identity_holds": presses == winding and tail == 0 and not bad, "won": o.check_win()}
if __name__ == "__main__":
    cat = json.loads((SOKO / "soko_mcp/data/catalog.json").read_text(encoding="utf-8"))
    res = {}
    for r in cat["rooms"]:
        if r["part"] != 3: continue
        a = analyse(3, r["grid"], r["reference_route"])
        res[r["id"]] = a
        print(r["id"], len(r["reference_route"]), a["presses"], a["winding"], a["identity_holds"], a["won"], a["n_mismatch"])
    r21 = [r for r in cat["rooms"] if r["id"] == "III-21"][0]
    suf = analyse(3, r21["grid"], r21["reference_route"], 195)
    print("III-21 suffix after key 195:", suf)
    res["III-21-suffix-195"] = suf
    # must-fail control: a route with one extra loop of presses must break the identity
    rt = r21["reference_route"]
    i = rt.index("A")
    bad_route = rt[:i] + "AAAAAA" + rt[i:]
    ctrl = analyse(3, r21["grid"], bad_route)
    print("control (6 extra presses inserted):", ctrl["presses"], ctrl["winding"], ctrl["identity_holds"])
    if ctrl["identity_holds"]:
        raise SystemExit("CONTROL FAILED: identity did not break")
    # second control: drop one A
    j = rt.index("A"); ctrl2 = analyse(3, r21["grid"], rt[:j] + rt[j+1:])
    print("control (one A removed):", ctrl2["presses"], ctrl2["winding"], ctrl2["identity_holds"], ctrl2["won"])
    if ctrl2["identity_holds"] and ctrl2["won"]:
        raise SystemExit("CONTROL 2 FAILED")
    (HERE.parent / "out/winding_identity.json").write_text(json.dumps(res, indent=1))
    failing = [k for k, v in res.items() if not v["identity_holds"]]
    print("identity fails on:", failing)
