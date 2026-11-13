"""Route autopsy for the III-21 316-key Frontier record (futarchist).

Steps the official route through the repo's PuzzleScriptOracle, one key at
a time, and logs the active hero, its position, and the board band after
every key. Summarises: A-press count, per-hero key counts, per-band key
counts, hero-visit segments (a hero left and later returned to costs a full
A-cycle each way), band transitions, and goals covered over time.

Bands follow the board's three stacked chambers:
  top    y in 0..3   (Fighter / Priest, goals (10,1) (12,1))
  middle y in 4..8   (Thief / Bard,   goals (10,6) (12,6))
  bottom y in 9..12  (Wizard / Druid, goals (10,11) (12,11))

Usage (from the repo root):
  python3 evidence/2026-11-13-iii21-autopsy/autopsy.py
Writes autopsy.json and autopsy.md next to itself.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from soko_mcp.oracle import PuzzleScriptOracle  # noqa: E402

ROUTE = (
    "RRRDRRDRRRURRDRRUURRRRRLLLLDDAUAADLLULLLLLDDAAALLLULDDDRDLULDDLLUUAAAULLULAAUADLLLLL"
    "AAADLAAALDADRAAAALLDAULAALARUAAARRRRRAUAARDRAAARRDRRUADDRRDDRLAAUAAAULLRRURURDDAURUL"
    "DDRRRRLLLLAAUUAAARDDRRRDRRRRRAAAAAULLULULULLLDUURLDLLUALLLUUAAAALLLLLDLLLDULLULLLLL"
    "LLADDRDALDDAUAAALDURADDUUAAAUAARRRRRRRRUUURUUADRDDDAAAUUURDDDAUUL"
)
GOALS = {(10, 1), (12, 1), (10, 6), (12, 6), (10, 11), (12, 11)}
ACTIVE_NAME = {"F": "Fighter", "T": "Thief", "W": "Wizard",
               "P": "Priest", "B": "Bard", "D": "Druid"}


def band(y):
    return "top" if y <= 3 else ("middle" if y <= 8 else "bottom")


def main():
    room = json.loads(subprocess.check_output(
        [sys.executable, "-m", "soko_mcp", "get-room", "--room", "III-21"],
        cwd=str(ROOT), text=True))
    assert len(ROUTE) == 316, len(ROUTE)
    assert ROUTE == room["reference_route"], "route drifted from catalog"
    oracle = PuzzleScriptOracle(3, room["grid"])
    frames = []
    for i, key in enumerate(ROUTE):
        before = oracle.find_active()
        moved, won = oracle.step(key)
        after = oracle.find_active()
        ax, ay, ah = after if after else (None, None, None)
        heroes_on_goals = 0
        for y in range(oracle.h):
            for x in range(oracle.w):
                if oracle.is_hero(oracle.obj[y][x]) and oracle.floor[y][x] == "G":
                    heroes_on_goals += 1
        frames.append({
            "i": i + 1, "key": key,
            "active_before": before[2] if before else None,
            "active": ah, "x": ax, "y": ay,
            "band": band(ay) if ay is not None else None,
            "moved": moved, "won": won,
            "heroes_on_goals": heroes_on_goals,
        })
        if won and i + 1 != len(ROUTE):
            raise SystemExit(f"early win at key {i + 1}")
    assert oracle.check_win(), "route does not win"

    # Segments: maximal runs with the same active hero (after the key).
    segments = []
    for f in frames:
        if not segments or segments[-1]["hero"] != f["active"]:
            segments.append({"hero": f["active"], "start": f["i"], "end": f["i"],
                             "keys": [f["key"]], "bands": {f["band"]}})
        else:
            s = segments[-1]
            s["end"] = f["i"]
            s["keys"].append(f["key"])
            s["bands"].add(f["band"])
    for s in segments:
        s["n"] = s["end"] - s["start"] + 1
        s["moves"] = sum(1 for k in s["keys"] if k in "UDLR")
        s["switches_in"] = sum(1 for k in s["keys"] if k == "A")
        s["bands"] = sorted(s["bands"])

    from collections import Counter
    summary = {
        "room": "III-21",
        "route_len": len(ROUTE),
        "route_sha256": room["baseline"]["response_sha256"],
        "holder": "futarchist",
        "record_id": 159,
        "a_presses": ROUTE.count("A"),
        "move_presses": sum(ROUTE.count(c) for c in "UDLR"),
        "keys_by_hero": dict(Counter(f["active"] for f in frames)),
        "keys_by_band": dict(Counter(f["band"] for f in frames)),
        "segments": len(segments),
        "hero_visits": dict(Counter(s["hero"] for s in segments)),
        "band_transitions": sum(
            1 for a, b in zip(frames, frames[1:]) if a["band"] != b["band"]),
        "first_goal_key": next(f["i"] for f in frames if f["heroes_on_goals"] > 0),
        "all_goals_key": next(f["i"] for f in frames if f["heroes_on_goals"] == 6),
        "segments_detail": segments,
    }
    (HERE / "autopsy.json").write_text(json.dumps(
        {"summary": summary, "frames": frames}, indent=1))
    lines = ["# III-21 316-key route autopsy",
             "",
             f"Route: {len(ROUTE)} keys, holder futarchist (record 159).",
             f"A-presses: {summary['a_presses']} of {len(ROUTE)} keys "
             f"({100 * summary['a_presses'] / len(ROUTE):.1f}% of the route is hero switching).",
             f"Segments (hero visits): {summary['segments']}; "
             f"visits per hero: {summary['hero_visits']}.",
             f"Keys by hero: {summary['keys_by_hero']}.",
             f"Keys by band: {summary['keys_by_band']}; "
             f"band transitions: {summary['band_transitions']}.",
             f"First hero on a goal: key {summary['first_goal_key']}; "
             f"all six on goals: key {summary['all_goals_key']} (win is key 316).",
             "",
             "## Segments",
             "",
             "| # | hero | keys | span | moves | A in seg | bands |",
             "|---|------|-----:|------|------:|--------:|-------|"]
    for j, s in enumerate(segments, 1):
        lines.append(f"| {j} | {ACTIVE_NAME[s['hero']]} | {s['n']} | "
                     f"{s['start']}–{s['end']} | {s['moves']} | {s['switches_in']} | "
                     f"{','.join(s['bands'])} |")
    (HERE / "autopsy.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({k: v for k, v in summary.items()
                      if k != "segments_detail"}, indent=1))


if __name__ == "__main__":
    main()
