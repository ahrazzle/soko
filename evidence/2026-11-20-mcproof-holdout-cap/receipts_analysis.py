"""Read mcproof's published holdout receipts and report three things.

1. Holdout items whose error list is identical in every arm.
2. Per-family answer times, to show which arms ran into the 512-token cap.
3. The answer-length cap each run used, from the validation scorecard and the scoring script.

Usage: python3 receipts_analysis.py /path/to/mcproof   (checked out at adea9b6)
"""
import collections
import json
import re
import statistics as st
import sys
from pathlib import Path

R = Path(sys.argv[1])
V = R / "verification"
arms = {"B0": json.loads((V / "vault_arm_b0.json").read_text())["private_holdout"],
        "B1": json.loads((V / "vault_arm_b1.json").read_text())["private_holdout"]}
for name, a in json.loads((V / "vault_arms_adapters.json").read_text())["arms"].items():
    if "private_holdout" in a:
        arms[name] = a["private_holdout"]
items = {a: {it["id"]: it for it in h["items"]} for a, h in arms.items()}
ids = sorted(items["B0"])
same = [i for i in ids if len({tuple(sorted(items[a][i]["error_categories"])) for a in arms}) == 1]
print(f"arms: {len(arms)}; passes: {', '.join(f'{a} {h['total_passed']}/{h['total_count']}' for a, h in arms.items())}")
print(f"items with the identical error list in all {len(arms)} arms: {len(same)}: {same}")
fam_b = [i for i in ids if i.startswith("HOLD-B-")]
print("Family B error lists:", collections.Counter(tuple(sorted(items[a][i]["error_categories"])) for a in arms for i in fam_b))

ad = json.loads((V / "vault_arms_adapters.json").read_text())["arms"]["P2-B"]
for split, key, cap in (("private_holdout", "family", 512), ("general_retention", "domain", 384)):
    by = collections.defaultdict(list)
    for it in ad[split]["items"]:
        by[it[key]].append(it["elapsed_ms"] / 1000)
    print(f"P2-B {split} (cap {cap} tokens), seconds min/median/max:",
          {k: (round(min(v), 1), round(st.median(v), 1), round(max(v), 1)) for k, v in sorted(by.items())})

vs = json.loads((R / "compile/artifacts/evaluation/validation_scorecard.json").read_text())
print("validation scorecard decoding:", vs["decoding"])
print("holdout receipt decoding:", json.loads((V / "vault_arm_b0.json").read_text())["decoding"])
src = (V / "score_arms_against_vault.py").read_text()
print("holdout n_predict in score_arms_against_vault.py:", sorted(set(re.findall(r"query_split\(base_url, holdout_rows[^)]*max_tokens=(\d+)", src))))
print("validation by family:", {a: {f: x["passed"] for f, x in v["by_family"].items()} for a, v in vs["arms"].items()})
