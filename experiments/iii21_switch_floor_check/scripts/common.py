"""Shared helpers. Uses the repo clone at ../soko (read-only)."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
SOKO = next((q for q in HERE.parents if (q / "soko_mcp").is_dir()), HERE.parent / "soko")
OUT = HERE.parent / "out"
sys.path.insert(0, str(SOKO))
from soko_mcp.oracle import PuzzleScriptOracle, TO_INACTIVE  # noqa: E402
from experiments.landmark_dual_bounds import hero_assignment_bounds as H  # noqa: E402
_cat = json.loads((SOKO / "soko_mcp/data/catalog.json").read_text(encoding="utf-8"))
ROOM = next(r for r in _cat["rooms"] if r["id"] == "III-21")
W = 23
ORDER = ["F", "T", "W", "P", "B", "D"]
IDX = {h: i for i, h in enumerate(ORDER)}
MOUTHS = {248: "upper", 271: "lower"}
def new_oracle():
    return PuzzleScriptOracle(3, ROOM["grid"])
def hero_pos(o):
    inact = {v: k for k, v in TO_INACTIVE.items()}
    pos = {}
    for y in range(o.h):
        for x in range(o.w):
            c = o.obj[y][x]
            if c in IDX: pos[c] = (x, y)
            elif c in inact: pos[inact[c]] = (x, y)
    return pos
def active(o):
    a = o.find_active()
    return a[2] if a else None
def on_goal(o):
    return sorted(h for h, (x, y) in hero_pos(o).items() if o.floor[y][x] == "G")
