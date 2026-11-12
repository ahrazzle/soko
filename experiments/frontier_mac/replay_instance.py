"""Bind differential replay evidence to a specific puzzle and route.

This is an empirical certificate, not a formal proof or a Verified Bar pass.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from soko_mcp.engine_bridge import verify_route_dual


def digest(value: object) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def replay(instance: dict) -> dict:
    part, grid, route = instance.get("part"), instance.get("grid"), instance.get("route")
    if type(part) is not int or part not in (1, 2, 3):
        raise ValueError("part must be 1, 2 or 3")
    if not isinstance(grid, list) or not grid or not all(isinstance(row, str) and row for row in grid):
        raise ValueError("grid must contain nonempty text rows")
    if any(len(row) != len(grid[0]) for row in grid):
        raise ValueError("grid must be rectangular")
    if len(grid) * len(grid[0]) > 512 or any(ch not in ".#*GFTWPBD123456OLRM[]{}" for row in grid for ch in row):
        raise ValueError("grid exceeds the adapter limits or contains an unsupported symbol")
    if not isinstance(route, str) or any(key not in "UDLRA" for key in route):
        raise ValueError("route must contain only uppercase U D L R A")
    # Canonical starting rooms only: flat cells cannot encode a hero on a goal.
    active = "FTWPBD"
    identities = {hero: str(index + 1) for index, hero in enumerate(active)}
    heroes = [identities.get(ch, ch) for row in grid for ch in row if ch in active + "123456"]
    active_count = sum(ch in active for row in grid for ch in row)
    goal_count = sum(row.count("G") for row in grid)
    if active_count != 1 or len(set(heroes)) != len(heroes):
        raise ValueError("canonical starting rooms require one active hero and distinct hero identities")
    if goal_count == 0 or goal_count != len(heroes):
        raise ValueError("canonical starting rooms require one goal per hero and at least one goal")
    # This adapter's semantics are restricted to the interpreter's accepted grid.
    # Source URLs and dates are attribution, not a pinned external ruleset.
    problem = {"adapter": "heroes-of-sokoban-ascii-v1", "part": part, "grid": grid, "goal": "heroes occupy exactly the goal cells", "termination": "alive and first win on final key"}
    result = verify_route_dual(part, grid, route)
    evidence = {
        "schema_version": 1,
        "evidence_level": "differential_replay",
        "formal_proof_checked": False,
        "external_spec_pinned": False,
        "acceptance_checker_pins": {
            "replay_adapter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "engine_bridge_sha256": hashlib.sha256((ROOT / "soko_mcp/engine_bridge.py").read_bytes()).hexdigest(),
        },
        "instance_sha256": digest(problem),
        "route_sha256": hashlib.sha256(route.encode("ascii")).hexdigest(),
        "problem": problem,
        "source": {k: instance[k] for k in ("room_id", "source_url", "record_url", "capture_date", "source_author", "record_holder") if k in instance},
        "observed_record_keys": instance.get("record_keys"),
        "valid_winning_route": result["valid_winning_route"],
        "beats_observed_record": bool(result["valid_winning_route"] and type(instance.get("record_keys")) is int and len(route) < instance["record_keys"]),
        "replay": result,
        "limits": [
            "Two implementations can share a mistaken interpretation of the rules.",
            "Route validity does not establish minimality.",
            "The captured live record may change after capture.",
            "The source URL does not pin the external engine or establish its license.",
        ],
    }
    evidence["certificate_sha256"] = digest(evidence)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cert = replay(json.loads(args.instance.read_text()))
    text = json.dumps(cert, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return 0 if cert["valid_winning_route"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
