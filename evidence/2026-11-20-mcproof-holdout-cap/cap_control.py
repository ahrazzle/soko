"""Positive control for the 512-token holdout cap: grade public gold answers whole and cut at 512 tokens."""
import json, os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tiktoken
DS = Path(sys.argv[1]); OUT = Path(sys.argv[2]); CAP = int(sys.argv[3]) if len(sys.argv) > 3 else 512
enc = tiktoken.get_encoding("cl100k_base"); RATIO = 32216 / 30873  # Qwen3.5 tokens per cl100k token, from mcproof's own spec measurement
rows = [json.loads(l) for fn in ("compile.jsonl", "validation.jsonl") for l in open(DS / fn) if l.strip()]
rows = [r for r in rows if r["family"] in ("B", "C")]
def grade(item_id, text):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(text); p = f.name
    try:
        out = subprocess.run([sys.executable, "scripts/grade_item.py", "--id", item_id, "--input", p], cwd=DS, capture_output=True, text=True, timeout=600).stdout
        d = json.loads(out); return bool(d.get("passed")), [x.get("rule") for x in d.get("findings", [])][:3]
    finally:
        os.unlink(p)
def job(r):
    gold = r["positive_completion"]; toks = enc.encode(gold); qwen = round(len(toks) * RATIO)
    keep = int(CAP / RATIO); cut = enc.decode(toks[:keep]) if len(toks) > keep else gold
    full = grade(r["id"], gold); trunc = grade(r["id"], cut) if cut != gold else full
    return {"id": r["id"], "family": r["family"], "qwen_tokens_est": qwen, "over_cap": cut != gold, "gold_passed": full[0], "gold_findings": full[1], "cut_passed": trunc[0], "cut_findings": trunc[1]}
with ThreadPoolExecutor(4) as ex: res = list(ex.map(job, rows))
OUT.write_text(json.dumps({"cap_tokens": CAP, "ratio": RATIO, "items": res}, indent=1) + "\n")
for fam in "BC":
    it = [x for x in res if x["family"] == fam]
    print(fam, "items", len(it), "| gold passes", sum(x["gold_passed"] for x in it), "| over cap", sum(x["over_cap"] for x in it),
          "| gold cut at cap passes", sum(x["cut_passed"] for x in it), "| over-cap items that still pass when cut", sum(x["cut_passed"] for x in it if x["over_cap"]))
