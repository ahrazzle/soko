"""Task 1. For sampled real handoff positions compute
 (a) least total of per-hero solo move keys over the 720 hero->exit assignments (repo: solo_walk_plus_wall_convert_matrix + enumerate_all_goal_bijections),
 (b) least switch presses: three readings of who must act,
 (c) a + b, and the repo's own h_OC, and compare with the published floors 74 (lower) / 75 (F upper) / 76 (T upper)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
CYC = ["F", "T", "W", "P", "B", "D"]
FLOOR = {("F", "lower"): 74, ("T", "lower"): 74, ("F", "upper"): 75, ("T", "upper"): 76}
def cyc_dist(a, b): return (CYC.index(b) - CYC.index(a)) % 6
def metrics(o):
    labels, goals, mat = H.solo_walk_plus_wall_convert_matrix(o)
    rows = H.enumerate_all_goal_bijections(labels, goals, mat)
    assert len(rows) == 720
    a = rows[0]["solo_sum_cost"]
    act = active(o); ong = on_goal(o)
    need = [h for h in CYC if h not in ong]
    b_strict = max([cyc_dist(act, h) for h in need] + [0])
    b_druid = cyc_dist(act, "D") if "D" in need else 0
    b_none = 0
    oc = H.evaluate_operator_counting_bound(o)
    # a restricted to heroes that actually need to move: same assignment, heroes already on an exit still cost 0 only if they keep their own exit
    return {"active": act, "on_goal": ong, "need_strict": need, "a_min_assignment_sum": a,
            "best_perm": rows[0]["perm"], "b_strict_all_unfinished_act": b_strict, "b_druid_only": b_druid,
            "c_strict": a + b_strict, "c_druid": a + b_druid, "h_OC": str(oc.exact_rational_bound), "H_OC": oc.ceil_integer_bound}
if __name__ == "__main__":
    route = ROOM["reference_route"]
    raw = json.loads((HERE.parent / "out/handoff_sample_raw.json").read_text()) + json.loads((HERE.parent / "out/handoff_sample_lower_raw.json").read_text())
    samples = [{"prefix": route[:195], "t": 195, "actor": "F", "entrance": "upper", "note": "record route"}] + raw
    seen = set(); table = []
    for s in samples:
        o = new_oracle()
        for k in s["prefix"]: o.step(k)
        sig = o.state_signature()
        if sig in seen: continue
        seen.add(sig)
        m = metrics(o)
        fl = FLOOR[(s["actor"], s["entrance"])]
        row = {"t": s["t"], "actor": s["actor"], "entrance": s["entrance"], "published_floor": fl, **m,
               "gap_to_floor_a": fl - m["a_min_assignment_sum"], "gap_to_floor_c_strict": fl - m["c_strict"],
               "prefix_sha": __import__("hashlib").sha256(s["prefix"].encode()).hexdigest()[:12], "prefix": s["prefix"]}
        table.append(row)
    # keep a compact, diverse sample for display
    print("t actor ent floor | a(720-min) b_strict b_druid | a+b_strict a+b_druid | H_OC | on_goal | active")
    for r in table:
        print(r["t"], r["actor"], r["entrance"], r["published_floor"], "|", r["a_min_assignment_sum"], r["b_strict_all_unfinished_act"], r["b_druid_only"], "|", r["c_strict"], r["c_druid"], "|", r["H_OC"], "|", r["on_goal"], "|", r["active"], r["prefix_sha"])
    (HERE.parent / "out/floor_compare.json").write_text(json.dumps(table, indent=1))
    # must-fail control: a handoff-looking matrix with one hero moved to a goal must change a
    o = new_oracle()
    for k in route[:195]: o.step(k)
    base = metrics(o)["a_min_assignment_sum"]
    o2 = new_oracle()
    for k in route[:246]: o2.step(k)
    later = metrics(o2)["a_min_assignment_sum"]
    print("control: a at key 195 =", base, " a at key 246 =", later)
    if not later < base: raise SystemExit("CONTROL FAILED: metric does not fall as the route progresses")
