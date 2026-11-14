"""CI gate: floor claims in the READMEs must be ones this repository reproduces.

Two checks:

1. Static. No README may call a numeric floor "proven" unless that
   (room, floor) pair is listed in REPRODUCED_FLOORS below. A floor reported
   by the live Frontier is an external claim; write it as such, not as proven.
2. Reproduction (``--reproduce``). For each entry in REPRODUCED_FLOORS whose
   README text is present, run ``python -m soko_mcp prove-floor`` and require
   the returned proven_floor to reach the stated value.

Run from the repository root:
  python tools/check_readme_floors.py              # static check only
  python tools/check_readme_floors.py --reproduce  # static + reproduction
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READMES = [ROOT / "README.md", ROOT / "experiments" / "width_search" / "README.md"]

# room -> (floor, README phrase that states it, prove-floor max_bound, budget_sec)
REPRODUCED_FLOORS = {
    "III-20": (48, "`>= 48`", 75, 60),
}

# "proven minimum 76", "proven minimum `44`", "a proven 44", "proven floor of 50"
_PROVEN_NUMBER = re.compile(
    r"\bproven(?:\s+(?:minimum|floor|lower\s+bound))?(?:\s+(?:is|of))?\s*`?(\d+)`?",
    re.IGNORECASE,
)


def static_check() -> list[str]:
    allowed = {floor for floor, _, _, _ in REPRODUCED_FLOORS.values()}
    problems = []
    for path in READMES:
        if not path.is_file():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for m in _PROVEN_NUMBER.finditer(line):
                if int(m.group(1)) not in allowed:
                    problems.append(
                        f"{path.relative_to(ROOT)}:{lineno}: '{m.group(0)}' states a proven floor "
                        "this repository does not reproduce"
                    )
    return problems


def reproduce() -> list[str]:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    problems = []
    for room, (floor, phrase, max_bound, budget) in REPRODUCED_FLOORS.items():
        if phrase not in readme:
            continue
        proc = subprocess.run(
            [sys.executable, "-m", "soko_mcp", "prove-floor", "--room", room,
             "--max-bound", str(max_bound), "--budget-sec", str(budget)],
            cwd=ROOT, capture_output=True, text=True, timeout=budget + 120,
        )
        try:
            out = json.loads(proc.stdout)
        except json.JSONDecodeError:
            problems.append(f"{room}: prove-floor did not return JSON (rc={proc.returncode}): {proc.stderr[-400:]}")
            continue
        got = out.get("proven_floor")
        status = out.get("epistemic_status")
        print(f"{room}: README states {phrase}; prove-floor returned {status} proven_floor={got}")
        if not isinstance(got, int) or got < floor:
            problems.append(f"{room}: README states {phrase} but prove-floor returned {status} proven_floor={got}")
    return problems


def main(argv: list[str]) -> int:
    problems = static_check()
    if "--reproduce" in argv:
        problems += reproduce()
    for p in problems:
        print(p, file=sys.stderr)
    if not problems:
        print("README floor claims: ok")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
