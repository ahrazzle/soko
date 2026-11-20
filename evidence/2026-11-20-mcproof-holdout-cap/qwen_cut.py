"""Cap control with the real Qwen3.5 tokenizer: grade public gold whole and cut at CAP tokens.

Usage (from anywhere): python3 qwen_cut.py CAP FAMILIES TOKENIZER_JSON MCPROOF_ROOT
  e.g. python3 qwen_cut.py 512 BC /path/to/Qwen3.5-4B/tokenizer.json /path/to/mcproof
Needs the `tokenizers` package and MCPROOF_MDE_ROOT for Family B. Written by the second reviewer, 2026-11-20.
"""
import json, os, subprocess, sys, tempfile
from tokenizers import Tokenizer
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
tok = Tokenizer.from_file(sys.argv[3])
ROOT = Path(sys.argv[4])
DS = ROOT / "datasets"
spec = (ROOT / "spec" / "plane1_formal_spec.md").read_text()
print("spec qwen tokens:", len(tok.encode(spec, add_special_tokens=False).ids))
CAP = int(sys.argv[1]) if len(sys.argv) > 1 else 512
rows = [json.loads(l) for fn in ("compile.jsonl", "validation.jsonl") for l in open(DS / fn) if l.strip()]
def grade(iid, text):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(text); p = f.name
    try:
        out = subprocess.run([sys.executable, "scripts/grade_item.py", "--id", iid, "--input", p], cwd=DS, capture_output=True, text=True, timeout=600).stdout
        d = json.loads(out); return bool(d.get("passed")), [x.get("rule") for x in d.get("findings", [])][:3]
    finally:
        os.unlink(p)
def job(r):
    g = r["positive_completion"]; enc = tok.encode(g, add_special_tokens=False)
    n = len(enc.ids)
    if n > CAP:
        end = enc.offsets[CAP - 1][1]; cut = g[:end]
    else:
        cut = g
    res = grade(r["id"], cut) if cut != g else (True, [])
    return r["id"], r["family"], n, n > CAP, res
fams = sys.argv[2] if len(sys.argv) > 2 else "BC"
with ThreadPoolExecutor(4) as ex:
    out = list(ex.map(job, [r for r in rows if r["family"] in fams]))
for f in fams:
    it = [o for o in out if o[1] == f]
    print(f, "n", len(it), "over cap", sum(o[3] for o in it), "cut fails", sum(not o[4][0] for o in it))
for o in sorted(out, key=lambda o: -o[2]):
    if o[2] > CAP - 60: print(o)
lens = {f: sorted(o[2] for o in out if o[1] == f) for f in fams}
print({f: (v[0], v[len(v)//2], v[-1]) for f, v in lens.items()})
