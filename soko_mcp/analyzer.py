"""Structural symmetry, hero-cycle chirality, and combinatorial bottleneck analyzer for PuzzleScript rooms."""
from __future__ import annotations

from typing import Any, Dict, List
from .oracle import ACTIVE_HEROES, HERO_NAMES, INACTIVE_HEROES, TO_INACTIVE


def _norm_dungeon_char(ch: str, swap_dragons: bool = False) -> str:
    if ch in ACTIVE_HEROES or ch in INACTIVE_HEROES:
        return "."
    if swap_dragons:
        if ch == "L":
            return "R"
        if ch == "R":
            return "L"
    return ch


def inspect_room(part: int, rows: List[str]) -> Dict[str, Any]:
    h = len(rows)
    w = len(rows[0])
    heroes = []
    goals = []
    monsters = {"O": 0, "L": 0, "R": 0}
    switches = {"{": 0, "}": 0}
    doors = {"[": 0, "]": 0, "M": 0}
    crates = 0

    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in ACTIVE_HEROES:
                hid = TO_INACTIVE[ch]
                heroes.append({"slot": hid, "symbol": ch, "active": True, "x": x, "y": y, "role": HERO_NAMES[hid]})
            elif ch in INACTIVE_HEROES:
                heroes.append({"slot": ch, "symbol": ch, "active": False, "x": x, "y": y, "role": HERO_NAMES[ch]})
            elif ch == "G":
                goals.append((x, y))
            elif ch in monsters:
                monsters[ch] += 1
            elif ch in switches:
                switches[ch] += 1
            elif ch in doors:
                doors[ch] += 1
            elif ch == "*":
                crates += 1

    heroes.sort(key=lambda item: item["slot"])

    # Compute dungeon symmetry mismatches (excluding heroes)
    mirror_y_diff = 0
    mirror_x_diff = 0
    rot_180_diff = 0
    hero_mirror_y_asymmetric = False
    hero_mirror_x_asymmetric = False

    for y in range(h):
        for x in range(w):
            c0 = _norm_dungeon_char(rows[y][x], False)
            cy = _norm_dungeon_char(rows[h - 1 - y][x], False)
            cx = _norm_dungeon_char(rows[y][w - 1 - x], True)
            cr = _norm_dungeon_char(rows[h - 1 - y][w - 1 - x], True)
            if c0 != cy:
                mirror_y_diff += 1
            if c0 != cx:
                mirror_x_diff += 1
            if c0 != cr:
                rot_180_diff += 1
            h0 = rows[y][x] if (rows[y][x] in ACTIVE_HEROES or rows[y][x] in INACTIVE_HEROES) else None
            hy = rows[h - 1 - y][x] if (rows[h - 1 - y][x] in ACTIVE_HEROES or rows[h - 1 - y][x] in INACTIVE_HEROES) else None
            hx = rows[y][w - 1 - x] if (rows[y][w - 1 - x] in ACTIVE_HEROES or rows[y][w - 1 - x] in INACTIVE_HEROES) else None
            if (h0 is not None or hy is not None) and h0 != hy:
                hero_mirror_y_asymmetric = True
            if (h0 is not None or hx is not None) and h0 != hx:
                hero_mirror_x_asymmetric = True

    present_slots = [item["slot"] for item in heroes]
    chiral_opportunities: List[str] = []
    if mirror_y_diff == 0 and hero_mirror_y_asymmetric:
        chiral_opportunities.append(
            "Exact vertical dungeon reflection symmetry (y <-> H-1-y) with chirally asymmetric hero placement: "
            "a mirrored trajectory may be a useful soft guide for an experimental search."
        )
    if mirror_x_diff == 0 and hero_mirror_x_asymmetric:
        chiral_opportunities.append(
            "Exact horizontal dungeon reflection symmetry (x <-> W-1-x, swapping L<->R dragons) with chirally "
            "asymmetric hero placement: consider a mirrored trajectory as an experimental guide."
        )
    if rot_180_diff == 0 and len(heroes) > 1:
        chiral_opportunities.append(
            "Exact 180-degree rotational dungeon symmetry: a transformed trajectory may provide a search guide."
        )

    total_switches = switches["{"] + switches["}"]
    has_druid = any(item["slot"] == "6" for item in heroes)
    has_bard = any(item["slot"] == "5" for item in heroes)
    bottlenecks: List[str] = []
    if total_switches > crates and has_druid:
        deficit = total_switches - crates
        bottlenecks.append(
            f"Switch-weighing deficit of {deficit} object(s) relative to initial crates ({crates} crates vs {total_switches} switches): "
            f"Druid must create or petrify at least {max(0, deficit - len(heroes))} extra weighing tile(s) before heroes clear the door."
        )
    if has_bard and (crates + len(heroes) >= 3):
        bottlenecks.append(
            "Bard's prior-turn 5x5 Chebyshev Note aura guides charmed objects in the movement direction. "
            "Blocking and uncharming can change their relative offsets; do not assume a rigid group in a proof."
        )

    return {
        "part": part,
        "dimensions": {"width": w, "height": h, "cells": w * h},
        "heroes": heroes,
        "action_cycle_order": " -> ".join(present_slots + ([present_slots[0]] if present_slots else [])),
        "counts": {
            "goals": len(goals),
            "crates": crates,
            "monsters": monsters,
            "switches": switches,
            "doors": doors,
        },
        "symmetries": {
            "mirror_y_mismatches": mirror_y_diff,
            "mirror_x_mismatches": mirror_x_diff,
            "rot_180_mismatches": rot_180_diff,
            "exact_mirror_y": mirror_y_diff == 0,
            "exact_mirror_x": mirror_x_diff == 0,
            "exact_rot_180": rot_180_diff == 0,
            "hero_mirror_y_chirality": hero_mirror_y_asymmetric,
            "hero_mirror_x_chirality": hero_mirror_x_asymmetric,
        },
        "chiral_opportunities": chiral_opportunities,
        "structural_bottlenecks": bottlenecks,
        "recommended_workflow": [
            "1. Load the canonical room and its dated baseline with soko_get_room; replay original-room candidates with soko_replay_original.",
            "2. State a hypothesis and control before using soko_optimize_route: native bounded exact BFS, or Python window BFS when native search is unavailable.",
            "3. Use soko_solve_room to try from scratch. Report resource cutoffs; local replay and exhaustive local bounds do not establish original-engine optimality.",
        ],
    }
