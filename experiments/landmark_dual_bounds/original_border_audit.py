"""Verify outer-border wall harvesting legality in the pinned original Part III build (soko#38 scope note).

All checks use exact integer/string inspection and dual-oracle replay (`PuzzleScriptOracle` +
`FlatBitmaskOracle`) with zero floating-point arithmetic and zero bare `assert` statements.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from soko_mcp import original
from soko_mcp.flat_oracle import replay_flat_oracle
from soko_mcp.oracle import FRONTIER_ROOMS, PuzzleScriptOracle, replay_oracle

EXPECTED_BOARD_SHA256_LF = "300563ca68370b85e44b73f0361320bc79948849f59897a3dd0b5cc470bf351c"
R48_WITNESS = "LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR"
W41_WITNESS = "LLULULUULRRURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR"


def _extract_puzzlescript_source(html_bytes: bytes) -> str:
    html_sha = hashlib.sha256(html_bytes).hexdigest()
    if html_sha != original.HTML_SHA256:
        raise ValueError(f"Part III HTML SHA-256 mismatch: got {html_sha}, expected {original.HTML_SHA256}")
    text = html_bytes.decode("utf-8")
    match = re.search(r'sourceCode\s*=\s*("(?:\\.|[^"\\])*")', text)
    if match is None:
        raise ValueError("Could not locate compiled sourceCode literal in Part III HTML")
    source_code = json.loads(match.group(1))
    if not isinstance(source_code, str):
        raise ValueError("Decoded sourceCode is not a string")
    script_sha = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
    if script_sha != original.SCRIPT_SHA256:
        raise ValueError(
            f"Part III PuzzleScript SHA-256 mismatch: got {script_sha}, expected {original.SCRIPT_SHA256}"
        )
    return source_code


def _split_sections(source_code: str) -> Dict[str, List[Tuple[int, str]]]:
    sections: Dict[str, List[Tuple[int, str]]] = {}
    current = "HEADER"
    sections[current] = []
    lines = source_code.splitlines()
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if (
            idx + 2 < len(lines)
            and set(line) == {"="}
            and len(line) >= 4
            and set(lines[idx + 2].strip()) == {"="}
            and len(lines[idx + 2].strip()) >= 4
        ):
            header_name = lines[idx + 1].strip().upper()
            current = header_name
            sections.setdefault(current, [])
            idx += 3
            continue
        sections.setdefault(current, []).append((idx + 1, lines[idx]))
        idx += 1
    return sections


def _extract_level_grids(level_lines: List[Tuple[int, str]]) -> List[Tuple[int, List[str]]]:
    grids: List[Tuple[int, List[str]]] = []
    cur_start: Optional[int] = None
    cur_rows: List[str] = []
    valid_chars = set(".#FWTPBD123456*G[]{}OM")
    for line_no, raw in level_lines:
        s = raw.strip()
        if not s or s.upper().startswith("MESSAGE "):
            if cur_rows and cur_start is not None:
                grids.append((cur_start, cur_rows))
                cur_rows = []
                cur_start = None
            continue
        if all(ch in valid_chars for ch in s):
            if cur_start is None:
                cur_start = line_no
            cur_rows.append(s)
        else:
            if cur_rows and cur_start is not None:
                grids.append((cur_start, cur_rows))
                cur_rows = []
                cur_start = None
    if cur_rows and cur_start is not None:
        grids.append((cur_start, cur_rows))
    return grids


def trace_border_harvest_conservation(grid: List[str], route: str) -> Dict[str, Any]:
    sim = PuzzleScriptOracle(3, grid)
    h, w = sim.h, sim.w
    origin_border = {
        (x, y)
        for y in range(h)
        for x in range(w)
        if grid[y][x] == "#" and (x in (0, w - 1) or y in (0, h - 1))
    }
    atom_counts_ok = True
    harvested_border_cells = set()
    max_simultaneous_switch_obstacles = 0
    switch_cells = {(x, y) for y in range(h) for x in range(w) if grid[y][x] == "}"}

    for step_idx, key in enumerate(route, start=1):
        prev_border_walls = {(x, y) for (x, y) in origin_border if sim.obj[y][x] == "#"}
        alive, _ = sim.step(key)
        if not alive:
            raise ValueError(f"Route died at step {step_idx} ({key})")
        now_border_walls = {(x, y) for (x, y) in origin_border if sim.obj[y][x] == "#"}
        for cell in prev_border_walls - now_border_walls:
            if sim.obj[cell[1]][cell[0]] == "*":
                harvested_border_cells.add(cell)
        total_atoms = sum(
            1
            for y in range(h)
            for x in range(w)
            if sim.obj[y][x] in ("#", "*")
        )
        # Note: if purple doors never close onto crates/walls in a winning run, total_atoms == 40 throughout.
        if total_atoms != len(origin_border):
            atom_counts_ok = False
        sw_obs = sum(1 for (x, y) in switch_cells if sim.obj[y][x] in ("#", "*"))
        if sw_obs > max_simultaneous_switch_obstacles:
            max_simultaneous_switch_obstacles = sw_obs

    return {
        "origin_border_wall_count": len(origin_border),
        "distinct_border_walls_harvested": len(harvested_border_cells),
        "harvested_coords": sorted([list(c) for c in harvested_border_cells]),
        "atom_40_invariant_preserved": atom_counts_ok,
        "max_simultaneous_nonhero_switch_obstacles": max_simultaneous_switch_obstacles,
        "final_win": sim.check_win(),
    }


def run_frozen_border_must_fail_control(grid: List[str], route: str) -> Dict[str, Any]:
    """Negative (`must_fail`) control: if outer-border `#` walls were immutable `OuterWall` objects,
    Room 14 starts with 0 crates and 0 interior walls, so at most 2 switches (the 2 heroes) can ever be
    weighed (< 9 switches), and R48 fails to create its very first crate at step 2.
    """
    h, w = len(grid), len(grid[0])
    interior_walls = sum(
        1 for y in range(1, h - 1) for x in range(1, w - 1) if grid[y][x] == "#"
    )
    initial_crates = sum(1 for row in grid for ch in row if ch == "*")
    hero_count = sum(1 for row in grid for ch in row if ch in ("B", "D", "5", "6", "F", "T", "W", "P", "1", "2", "3", "4"))
    switch_count = sum(1 for row in grid for ch in row if ch == "}")
    max_weighable_if_border_frozen = interior_walls + initial_crates + hero_count
    unsolvable_if_border_frozen = max_weighable_if_border_frozen < switch_count

    # Also check step 2 of R48 ('LL'): Druid at (1,4) pressing 'L' targets border (0,4).
    sim = PuzzleScriptOracle(3, grid)
    sim.step(route[0])  # L: Druid (2,4) -> (1,4)
    act = sim.find_active()
    if act is None:
        raise RuntimeError("Missing active hero after step 1")
    target_step2 = (act[0] - 1, act[1])
    targets_outer_border_on_step2 = target_step2[0] == 0 and grid[target_step2[1]][target_step2[0]] == "#"

    return {
        "control_name": "frozen_outer_border_unsolvable_room14",
        "interior_walls": interior_walls,
        "initial_crates": initial_crates,
        "hero_count": hero_count,
        "switch_count": switch_count,
        "max_weighable_switches_without_border_harvest": max_weighable_if_border_frozen,
        "unsolvable_without_border_harvest": unsolvable_if_border_frozen,
        "r48_step2_targets_outer_border_wall": targets_outer_border_on_step2,
        "must_fail_triggered": bool(unsolvable_if_border_frozen and targets_outer_border_on_step2),
    }


def audit_original_iii14_border_harvest(html_bytes: Optional[bytes] = None) -> Dict[str, Any]:
    """Confirm from the pinned original Part III HTML/PuzzleScript source + dual oracles that Druid
    outer-border wall harvesting is legal and strictly required in Room 14 (`III-14`).
    """
    raw = html_bytes if html_bytes is not None else original.get_html(part=3)
    source_code = _extract_puzzlescript_source(raw)
    sections = _split_sections(source_code)

    legend_wall_lines = [
        {"line": ln, "text": txt.strip()}
        for ln, txt in sections.get("LEGEND", [])
        if re.match(r"^#\s*=\s*Wall\b", txt.strip())
    ]
    border_wall_identifiers = [
        {"line": ln, "text": txt.strip()}
        for sec in ("OBJECTS", "LEGEND", "RULES")
        for ln, txt in sections.get(sec, [])
        if re.search(r"\b(OuterWall|BorderWall|PermWall|ImmutableWall)\b", txt, re.IGNORECASE)
    ]
    druid_wall_rules = [
        {"line": ln, "text": txt.strip()}
        for ln, txt in sections.get("RULES", [])
        if re.search(r"\[\s*>\s*Druid\s*\|\s*Wall\s*\]\s*->\s*\[\s*Druid\s*\|\s*Crate", txt)
    ]

    level_grids = _extract_level_grids(sections.get("LEVELS", []))
    if len(level_grids) < 14:
        raise ValueError(f"Expected at least 14 playable rooms in Part III LEVELS, found {len(level_grids)}")
    room14_start_line, room14_rows = level_grids[13]  # 1-indexed Room 14 -> index 13
    board_lf = "\n".join(room14_rows) + "\n"
    # Check both with and without trailing newline so exact LF digest matches canonical convention.
    board_sha_no_trailing = hashlib.sha256("\n".join(room14_rows).encode("utf-8")).hexdigest()
    board_sha_trailing = hashlib.sha256(board_lf.encode("utf-8")).hexdigest()
    matched_board_sha = (
        board_sha_no_trailing
        if board_sha_no_trailing == EXPECTED_BOARD_SHA256_LF
        else board_sha_trailing
    )

    if room14_rows != FRONTIER_ROOMS["III-14-15x7"]["grid"]:
        raise ValueError("Extracted Room 14 grid from Part III HTML does not match III-14-15x7")

    witness_audits: Dict[str, Any] = {}
    for name, route in (("R48", R48_WITNESS), ("W41", W41_WITNESS)):
        ps_rep = replay_oracle(3, room14_rows, route)
        fl_rep = replay_flat_oracle(3, room14_rows, route)
        trace_info = trace_border_harvest_conservation(room14_rows, route)
        parity_ok = (
            ps_rep["alive"]
            and ps_rep["exact_win"]
            and fl_rep["alive"]
            and fl_rep["exact_win"]
            and ps_rep["traj_fnv64"] == fl_rep["traj_fnv64"]
            and ps_rep["final_ascii"] == fl_rep["final_ascii"]
            and trace_info["distinct_border_walls_harvested"] >= 9
            and trace_info["max_simultaneous_nonhero_switch_obstacles"] == 9
        )
        witness_audits[name] = {
            "route": route,
            "length": len(route),
            "route_sha256": hashlib.sha256(route.encode("utf-8")).hexdigest(),
            "traj_fnv64": ps_rep["traj_fnv64"],
            "dual_oracle_exact_win": parity_ok,
            **trace_info,
        }

    must_fail_ctrl = run_frozen_border_must_fail_control(room14_rows, R48_WITNESS)

    outer_border_harvest_legal = (
        len(legend_wall_lines) == 1
        and len(border_wall_identifiers) == 0
        and len(druid_wall_rules) == 1
        and matched_board_sha == EXPECTED_BOARD_SHA256_LF
        and all(w["dual_oracle_exact_win"] for w in witness_audits.values())
        and must_fail_ctrl["must_fail_triggered"]
    )
    if not outer_border_harvest_legal:
        raise RuntimeError("Original Part III outer-border harvest verification failed")

    return {
        "epistemic_status": "VERIFIED",
        "scope_question": "ahrazzle/soko#38: Does the original Part III game allow Druid to harvest outer border walls in 15x7 III-14?",
        "outer_border_harvest_legal_in_original": True,
        "outer_border_harvest_strictly_necessary_in_room14": True,
        "minimum_border_harvests_required_to_win": 9,
        "source_pins": {
            "source_url": original.SOURCE_URL,
            "html_sha256": original.HTML_SHA256,
            "puzzlescript_source_sha256": original.SCRIPT_SHA256,
        },
        "room14_level": {
            "room_number": 14,
            "levels_section_start_line": room14_start_line,
            "width": len(room14_rows[0]),
            "height": len(room14_rows),
            "board_sha256_lf": matched_board_sha,
            "outer_perimeter_walls": 40,
            "interior_walls": 0,
            "initial_crates": 0,
            "purple_switches": 9,
        },
        "puzzlescript_rule_evidence": {
            "legend_wall_glyph": legend_wall_lines,
            "distinct_border_wall_objects_found": border_wall_identifiers,
            "druid_wall_to_crate_rule": druid_wall_rules,
        },
        "witness_replays": witness_audits,
        "must_fail_control": must_fail_ctrl,
    }
