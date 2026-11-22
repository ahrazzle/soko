"""Task 4. Recompute the layer table from the published handoff tables.
Group (t, hero, entrance) with n positions must be excluded for target T when floor+k+t <= T-1.
Source claims: floors (verdict.json) and counts (handoffs.tsv). Arithmetic verified here."""
import csv, json, sys
from pathlib import Path
W = Path(__file__).resolve().parent.parent / "web"
FLOORS = {("Fighter","upper"):75,("Fighter","lower"):74,("Thief","upper"):76,("Thief","lower"):74}
def load(p):
    with open(p) as fh:
        return [(int(r["keys_spent"]), r["hero"], r["entrance"], int(r["starting_positions"]))
                for r in csv.DictReader(fh, delimiter="\t")]
def check(cond, msg):
    if not cond:
        raise SystemExit("CHECK FAILED: " + msg)
def pick(*names):
    return next(W / n for n in names if (W / n).exists())
P269 = pick("iii-21-h269/handoffs.tsv", "h269_handoffs.tsv"); P268 = pick("iii-21-h268/handoffs.tsv", "h268_handoffs.tsv")
PV = pick("iii-21-h269/verdict.json", "h269_verdict.json")
t269 = load(P269); t268 = load(P268)
with open(PV) as fh:
    v = json.load(fh)
vf = {("Fighter" if k.split("_")[1]=="0" else "Thief", "upper" if k.endswith("248") else "lower"): x for k, x in v["universal_entrance_floors"].items()}
check(vf == FLOORS, "floors differ from verdict.json %s" % vf)
check(sum(r[3] for r in t269) == 47644 and len(t269) == 25, "h269 total")
check(sum(r[3] for r in t268) == 18198 and len(t268) == 21, "h268 total")
tmin = {h: min(r[0] for r in t269 if r[1] == h) for h in ("Fighter", "Thief")}
tmax_pub = max(r[0] for r in t269)
pub = {(r[0], r[1], r[2]): r[3] for r in t269}
def needed(T, k):
    out = []
    for (h, e), f in FLOORS.items():
        for t in range(tmin[h], T - (f + k)):  # t + f + k <= T-1
            out.append((t, h, e))
    return out
rows = []
for T in (270, 271, 272):
    for k in range(7):
        g = needed(T, k)
        known = [x for x in g if x in pub]
        unk = sorted(x for x in g if x not in pub)
        rows.append({"target": T, "k": k, "groups": len(g), "published_groups": len(known),
                     "positions_published": sum(pub[x] for x in known),
                     "groups_beyond_published_table": len(unk),
                     "first_unpublished": [f"{t} {h[0]} {e}" for t, h, e in unk[:4]]})
# must-fail controls: the function must reproduce both published totals, and must change if a floor is wrong
r270 = [r for r in rows if r["target"] == 270 and r["k"] == 0][0]
check(r270["positions_published"] == 47644 and r270["groups"] == 25 and r270["groups_beyond_published_table"] == 0, "270,k=0 does not reproduce 47,644")
FLOORS_SAVE = dict(FLOORS)
FLOORS[("Fighter","lower")] = 75
check(sum(pub.get(x, 0) for x in needed(270, 0)) != 47644, "control: wrong floor must change the total")
FLOORS.update(FLOORS_SAVE)
# 269 table is the T=269,k=0 case: check it reproduces 18,198 from the h268 floors? (h268 used the same floors) 
g268 = [x for x in needed(269, 0)]
check(sum(pub[x] for x in g268 if x in pub) == 18198, "269 target should give the h268 total 18,198")
check(all(x in pub for x in g268), "269 groups all published")
pure = {k: min(tmin[h] + f + k for (h, e), f in FLOORS.items()) for k in range(7)}
check(pure[0] == 262 and pure[9 - 9] == 262, "pure floor bound at k=0 should be 188+74")
print("pure floor bound (earliest handoff + floor + k), no search:", pure, "; k=9 gives", min(tmin[h] + f + 9 for (h, e), f in FLOORS.items()))
print(json.dumps(rows, indent=1))
with open(Path(__file__).resolve().parent.parent/"out/layer_table.json", "w") as fh:
    json.dump(rows, fh, indent=1)
print("\ntarget k  groups pub_positions  beyond_table")
for r in rows: print(r["target"], r["k"], r["groups"], r["positions_published"], r["groups_beyond_published_table"])
