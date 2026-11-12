"""Canonical input boundary and identity for empirical Sokoban evidence."""
from __future__ import annotations

import hashlib
import json


def validate_room(part: int, grid: list[str]) -> None:
    """Reject malformed/vacuous starts before any interpreter or native code runs.

    This flat ASCII format cannot represent a hero initially on a goal. It is
    deliberately a canonical starting-room interface, not a saved-state format.
    """
    if type(part) is not int or part not in (1, 2, 3):
        raise ValueError("part must be an integer in 1, 2, 3")
    if not isinstance(grid, list) or not grid or not all(isinstance(row, str) and row for row in grid):
        raise ValueError("grid must contain nonempty text rows")
    if any(len(row) != len(grid[0]) for row in grid):
        raise ValueError("grid must be rectangular")
    if len(grid) * len(grid[0]) > 512:
        raise ValueError("grid must contain at most 512 cells")
    if any(ch not in ".#*GFTWPBD123456OLRM[]{}" for row in grid for ch in row):
        raise ValueError("grid contains an unsupported symbol")
    active = "FTWPBD"
    identities = {hero: str(i + 1) for i, hero in enumerate(active)}
    heroes = [identities.get(ch, ch) for row in grid for ch in row if ch in active + "123456"]
    if sum(ch in active for row in grid for ch in row) != 1 or len(set(heroes)) != len(heroes):
        raise ValueError("canonical starting rooms require one active hero and distinct hero identities")
    if sum(row.count("G") for row in grid) != len(heroes):
        raise ValueError("canonical starting rooms require one goal per hero")


def normalize_route(route: str) -> str:
    if not isinstance(route, str):
        raise ValueError("route must be text")
    clean = route.strip().upper()
    if any(ch not in "UDLRA" for ch in clean):
        raise ValueError("route must contain only U D L R A")
    return clean


def digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def problem_identity(part: int, grid: list[str]) -> dict:
    problem = {
        "adapter": "heroes-of-sokoban-ascii-v1", "part": part, "grid": grid,
        "goal": "heroes occupy exactly the goal cells",
        "termination": "alive and first win on final key", "cost": "number of UDLRA keys",
    }
    return {"problem": problem, "instance_sha256": digest(problem)}
