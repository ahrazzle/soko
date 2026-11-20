import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
from sample_handoffs import bfs
r = ROOM["reference_route"]
var = r[:102] + "DLU" + r[103:]
out = []
for k0, depth, cap in ((192, 16, 900000),):
    t = time.time()
    f, ns, n = bfs(var[:k0], depth, cap)
    print(f"variant start {k0} depth {depth}: states {ns} expansions {n} handoffs {len(f)} {time.time()-t:.0f}s", flush=True)
    out += f
from collections import Counter
print(Counter((x["t"], x["actor"], x["entrance"]) for x in out))
Path(__file__).resolve().parent.parent.joinpath("out/handoff_sample_lower_raw.json").write_text(json.dumps(out))
