"""Generate real handoff positions: BFS (dedupe by oracle state signature) from record-route states,
collect states right after an F push / T pull moves the crate off a mouth cell (248 upper / 271 lower)
into the chamber cell next to it. Prints/writes the sample as route-prefix strings so any position can be replayed."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
KEYS = "UDLRA"
CH = {248: (19, 10), 271: (19, 11)}
def mouth_xy(m): return (m % W, m // W)
def bfs(prefix, depth, cap, label=""):
    o = new_oracle()
    for k in prefix: o.step(k)
    t0 = len(prefix)
    seen = {o.state_signature()}
    frontier = [(o, "")]
    found = []
    n = 0
    for d in range(1, depth + 1):
        nxt = []
        for s, path in frontier:
            for k in KEYS:
                c = s.clone()
                act = active(s)
                ok, won = c.step(k)
                n += 1
                if not ok if False else False: pass
                sig = c.state_signature()
                if sig in seen: continue
                seen.add(sig)
                nxt.append((c, path + k))
                if k != "A" and act in ("F", "T"):
                    for m, (cx, cy) in CH.items():
                        mx, my = mouth_xy(m)
                        if s.obj[my][mx] == "*" and c.obj[my][mx] != "*" and c.obj[cy][cx] == "*":
                            found.append({"prefix": prefix + path + k, "t": t0 + d, "actor": act,
                                          "mouth": m, "entrance": MOUTHS[m]})
            if len(seen) > cap: break
        frontier = nxt
        if len(seen) > cap: break
    return found, len(seen), n
if __name__ == "__main__":
    route = ROOM["reference_route"]
    out = []
    for k0, depth in ((194, 8), (192, 9), (190, 10), (186, 10)):
        t = time.time()
        f, ns, n = bfs(route[:k0], depth, 400000)
        print(f"start key {k0} depth {depth}: states {ns}, expansions {n}, handoffs {len(f)}, {time.time()-t:.0f}s", flush=True)
        out += f
    Path(__file__).resolve().parent.parent.joinpath("out/handoff_sample_raw.json").write_text(json.dumps(out))
    from collections import Counter
    print(Counter((x["t"], x["actor"], x["entrance"]) for x in out))
