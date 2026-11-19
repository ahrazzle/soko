"""Deterministic dataset builder partitioning all 66 original trilogy rooms (32 compile + 16 validation + 18 benchmark)."""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

from soko_mcp.catalog import get_room, list_rooms
from soko_mcp.flat_oracle import replay_flat_oracle
from soko_mcp.oracle import PLANTED_BUGS, MutatorFlags, PuzzleScriptOracle, replay_oracle

from .domain_oracle import SokoDomainOracle, board_sha256_lf
from .lineage import compute_soko_plane1_lineage
from .scrub import assert_clean_serialized, soko_repo_root, write_clean_json_atomic

BENCHMARK_18_SPECS: tuple[tuple[str, list[str], str], ...] = (
    ("I-1", ["fighter_walk", "premature_win_guard"], "13x5 opening Fighter walk testing bare-JSON and 8-key exact final-input win."),
    ("I-2", ["fighter_chain_push"], "Canonical Fighter multi-crate chain-pushing room."),
    ("I-3", ["fighter_push", "yellow_switch_door"], "Fighter crate push onto yellow switch holding open yellow door."),
    ("I-5", ["thief_pull", "yellow_switch_door"], "Green Thief pulling a Moveable onto a yellow switch."),
    ("I-8", ["wizard_warp_swap", "yellow_switch_door"], "Blue Wizard orthogonal ray warp-swap onto yellow switches."),
    ("I-20", ["party_switch_cycle", "fighter_chain_push", "thief_pull", "wizard_warp_swap"], "Compact 8x7 three-hero 1->2->3 A-cycle puzzle."),
    ("II-4", ["goblin_simultaneous_death", "fighter_push"], "Simultaneous Goblin mutual elimination in Late phase."),
    ("II-5", ["dragon_fire", "thief_navigation"], "Left/Right Dragon horizontal fire-ray navigation."),
    ("II-8", ["dragon_fire", "goblin_simultaneous_death", "party_switch_cycle", "dual_switches"], "Multi-hero timing with Dragons, Goblins, and dual switches."),
    ("II-10", ["dragon_fire", "monster_gate", "thief_pull"], "Thief crate pull redirecting Dragon fire to open Monster gate M."),
    ("II-13", ["priest_immunity", "goblin_combat", "dragon_fire"], "Yellow Priest direct combat immunity amidst Goblins and Dragon fire."),
    ("II-15", ["priest_goblin_simultaneous_shield", "party_switch_cycle"], "Inactive Priest 4 orthogonal heal aura shielding Fighter F."),
    ("III-2", ["bard_5x5_chebyshev_charm", "yellow_switch_door"], "Purple Bard end-of-prior-turn 5x5 Chebyshev Note aura crate translation."),
    ("III-4", ["bard_5x5_chebyshev_charm", "goblin_charm", "monster_gate"], "Bard charming Goblins into mutual elimination to open Monster gate M."),
    ("III-5", ["bard_5x5_chebyshev_charm", "hero_charm", "party_switch_cycle"], "Bard charming party heroes across switches and Goblins."),
    ("III-10", ["druid_wall_crate_transmutation", "thief_pull", "yellow_switch_door"], "Orange Druid Wall <-> Crate transmutation paired with Thief pull."),
    ("III-14", ["druid_wall_crate_transmutation", "bard_5x5_chebyshev_charm", "transmuted_wall_switch_weighing", "frontier_gap_room"], "Canonical 15x7 Frontier room combining Druid border-wall harvest and Bard switch weighing."),
    ("III-22", ["bard_5x5_chebyshev_charm", "six_hero_finale"], "Six-Hero Finale testing 5x5 Chebyshev corner reach (2,2)."),
)

_STDLIB_SOLVER_BODY = '''import heapq
import json

H, W = len(GRID), len(GRID[0])
goals, ysw, psw, ydoors0, pdoors0, init_obj = set(), set(), set(), set(), set(), {}
for y, row in enumerate(GRID):
    for x, ch in enumerate(row):
        if ch == "G":
            goals.add((x, y))
        elif ch == "{":
            ysw.add((x, y))
        elif ch == "}":
            psw.add((x, y))
        elif ch == "[":
            ydoors0.add((x, y))
            init_obj[(x, y)] = "["
        elif ch == "]":
            pdoors0.add((x, y))
            init_obj[(x, y)] = "]"
        elif ch != ".":
            init_obj[(x, y)] = ch

TO_INA = {"F": "1", "T": "2", "W": "3", "P": "4", "B": "5", "D": "6"}
TO_ACT = {v: k for k, v in TO_INA.items()}
DIRS = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
MOV = set("FTWPBD123456*O")
WEIGH = set("FTWPBD123456*OLR") | (set("#") if PART == 3 else set())

def notes_of(obj):
    if PART < 3:
        return frozenset()
    bpos = next((p for p, v in obj.items() if v == "B"), None)
    if bpos is None:
        return frozenset()
    return frozenset(
        p for p, v in obj.items()
        if p != bpos and v in MOV and max(abs(p[0] - bpos[0]), abs(p[1] - bpos[1])) <= 2
    )

def run_late(obj, yo, po):
    dying = set()
    if PART >= 2:
        for (x, y), v in list(obj.items()):
            if v in ("L", "R"):
                dx = -1 if v == "L" else 1
                rx = x + dx
                while 0 <= rx < W:
                    tv = obj.get((rx, y), "")
                    if not tv:
                        rx += dx
                        continue
                    if tv in "FTWBD12356O":
                        dying.add((rx, y))
                    break
            elif v == "O":
                for ox, oy in DIRS.values():
                    np_ = (x + ox, y + oy)
                    if obj.get(np_, "") in "FTWBD12356O":
                        dying.add(np_)
        priests = {p for p, v in obj.items() if v in ("P", "4")}
        for p in list(dying):
            if obj.get(p, "") in "FTWBD12356" and any((p[0] + ox, p[1] + oy) in priests for ox, oy in DIRS.values()):
                dying.remove(p)
        for p in dying:
            if obj.get(p, "") in "FTWPBD123456":
                return None
            obj.pop(p, None)
    if ysw:
        if all(obj.get(p, "") in WEIGH for p in ysw):
            for dp in ydoors0:
                if obj.get(dp) == "[":
                    obj.pop(dp, None)
            yo = True
        elif yo:
            for dp in ydoors0:
                if obj.get(dp, "") in "FTWPBD123456":
                    return None
                obj[dp] = "["
            yo = False
    if psw:
        if all(obj.get(p, "") in WEIGH for p in psw):
            for dp in pdoors0:
                if obj.get(dp) == "]":
                    obj.pop(dp, None)
            po = True
        elif po:
            for dp in pdoors0:
                if obj.get(dp, "") in "FTWPBD123456":
                    return None
                obj[dp] = "]"
            po = False
    if PART >= 2 and not any(v in "OLR" for v in obj.values()):
        for p, v in list(obj.items()):
            if v == "M":
                obj.pop(p, None)
    return yo, po

def step(state, key):
    obj_items, notes, yo, po = state
    obj = dict(obj_items)
    actives = [(p, v) for p, v in obj.items() if v in TO_INA]
    if len(actives) != 1:
        return None
    act_pos, act_ch = actives[0]
    moved = False
    if key == "A":
        notes = frozenset()
        order = ["1", "2", "3", "4", "5", "6"][:3 if PART == 1 else (4 if PART == 2 else 6)]
        cur = TO_INA[act_ch]
        ci = order.index(cur)
        for off in range(1, len(order)):
            cand = order[(ci + off) % len(order)]
            cpos = next((p for p, v in obj.items() if v == cand), None)
            if cpos is not None:
                obj[act_pos] = cur
                obj[cpos] = TO_ACT[cand]
                moved = True
                break
    else:
        dx, dy = DIRS[key]
        nx, ny = act_pos[0] + dx, act_pos[1] + dy
        if act_ch == "F":
            notes = frozenset()
            cx, cy = nx, ny
            while 0 <= cx < W and 0 <= cy < H and obj.get((cx, cy), "") in MOV:
                cx, cy = cx + dx, cy + dy
            if 0 <= cx < W and 0 <= cy < H and (cx, cy) not in obj:
                while (cx, cy) != act_pos:
                    px, py = cx - dx, cy - dy
                    obj[(cx, cy)] = obj.pop((px, py))
                    cx, cy = px, py
                moved = True
        elif act_ch == "T":
            notes = frozenset()
            if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in obj:
                obj[(nx, ny)] = obj.pop(act_pos)
                bp = (act_pos[0] - dx, act_pos[1] - dy)
                if obj.get(bp, "") in MOV:
                    obj[act_pos] = obj.pop(bp)
                moved = True
        elif act_ch == "W":
            notes = frozenset()
            rx, ry = nx, ny
            while 0 <= rx < W and 0 <= ry < H:
                tv = obj.get((rx, ry), "")
                if not tv:
                    rx, ry = rx + dx, ry + dy
                elif tv in MOV:
                    obj[act_pos], obj[(rx, ry)] = tv, "W"
                    moved = True
                    break
                else:
                    if (nx, ny) not in obj:
                        obj[(nx, ny)] = obj.pop(act_pos)
                        moved = True
                    break
        elif act_ch == "P":
            notes = frozenset()
            if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in obj:
                obj[(nx, ny)] = obj.pop(act_pos)
                moved = True
        elif act_ch == "D":
            notes = frozenset()
            if 0 <= nx < W and 0 <= ny < H:
                tv = obj.get((nx, ny), "")
                if not tv:
                    obj[(nx, ny)] = obj.pop(act_pos)
                    moved = True
                elif tv in ("*", "O"):
                    obj[(nx, ny)] = "#"
                    moved = True
                elif tv == "#":
                    obj[(nx, ny)] = "*"
                    moved = True
        elif act_ch == "B":
            pend = [p for p in notes if obj.get(p, "") in MOV]
            mb, prog = False, True
            while prog:
                prog = False
                for p in list(pend):
                    tp = (p[0] + dx, p[1] + dy)
                    if 0 <= tp[0] < W and 0 <= tp[1] < H and tp not in obj:
                        obj[tp] = obj.pop(p)
                        pend.remove(p)
                        prog = True
                if not mb:
                    tb = (act_pos[0] + dx, act_pos[1] + dy)
                    if 0 <= tb[0] < W and 0 <= tb[1] < H and tb not in obj:
                        obj[tb] = obj.pop(act_pos)
                        act_pos = tb
                        mb = True
                        prog = True
            if not mb:
                return state, False
            notes = frozenset()
            moved = True
    if not moved and PART <= 2:
        return None
    lr = run_late(obj, yo, po)
    if lr is None:
        return None
    yo2, po2 = lr
    nn = notes_of(obj)
    heroes = {p for p, v in obj.items() if v in "FTWPBD123456"}
    return (tuple(sorted(obj.items())), nn, yo2, po2), (heroes == goals)

def h_lb(obj_items):
    tot = 0
    for p, v in obj_items:
        if v in "FTWPBD123456" and goals:
            tot += min(abs(p[0] - gx) + abs(p[1] - gy) for gx, gy in goals) // 2
    return tot

init_d = dict(init_obj)
yo0, po0 = run_late(init_d, False, False)
start = (tuple(sorted(init_d.items())), notes_of(init_d), yo0, po0)
pq = [(h_lb(start[0]), 0, "", start)]
best_g = {start: 0}
ans = ""
while pq:
    _f, g, path, st = heapq.heappop(pq)
    if g > best_g.get(st, 10**9):
        continue
    for k in "UDLRA":
        res = step(st, k)
        if res is None:
            continue
        nst, won = res
        ng = g + 1
        if won:
            ans = path + k
            pq.clear()
            break
        if ng < best_g.get(nst, 10**9):
            best_g[nst] = ng
            heapq.heappush(pq, (ng + h_lb(nst[0]), ng, path + k, nst))
print(json.dumps({"keys": ans}))
'''


def _find_safe_probe_key(part: int, grid: list[str], ref_route: str) -> str:
    first_k = ref_route[0] if ref_route else "R"
    ps = replay_oracle(part, grid, first_k)
    if ps["alive"]:
        return first_k
    for cand in ("U", "D", "L", "R", "A"):
        if replay_oracle(part, grid, cand)["alive"]:
            return cand
    return "A"


def _make_item_for_room(
    *,
    item_id: str,
    split: str,
    family: str,
    room: dict[str, Any],
    zone_manifest_id: str,
    bug_idx: int,
) -> dict[str, Any]:
    rid = str(room["id"])
    part = int(room["part"])
    grid = [str(r) for r in room["grid"]]
    b_sha = board_sha256_lf(grid)
    ref_route = str(room["reference_route"]).strip().upper()
    tut = "; ".join(room.get("tutorial_messages") or []) or "(none)"
    grid_txt = "\n".join(grid)

    if family == "H_ROUTE":
        prompt = (
            f"Room {rid} (Part {part}, {room['width']}x{room['height']})\n"
            f"Tutorial: {tut}\n"
            f"Board:\n{grid_txt}\n\n"
            "Return ONE bare JSON object `{\"keys\": \"...\"}` winning on the exact final key with zero hero deaths and zero markdown fences."
        )
        pos = json.dumps({"keys": ref_route})
        # Negative: wraps JSON in markdown fence AND appends an extra trailing key (premature_win)
        neg = f"```json\n{json.dumps({'keys': ref_route + 'R'})}\n```"
        extra: dict[str, Any] = {"negative_failure_mode": "fenced_json_and_premature_win_overstep"}

    elif family == "H_PROBE":
        pkey = _find_safe_probe_key(part, grid, ref_route)
        prompt = (
            f"Stateful Sokoban Eval (`S2`) on Room {rid} (Part {part}, {room['width']}x{room['height']}).\n"
            f"Tutorial: {tut}\n"
            f"Board:\n{grid_txt}\n\n"
            "Before committing a full route, emit ONE bare JSON reversible 1-key mechanics probe (`{\"action\": \"probe\", \"key\": \"...\"}`)."
        )
        pos = json.dumps({"action": "probe", "key": pkey})
        neg = f"Let's try resetting first: {json.dumps({'action': 'reset', 'keys': 'RRRRRRRRRR'})}"
        extra = {"expected_action": "probe", "negative_failure_mode": "prose_wrapper_and_unbounded_reset"}

    elif family == "H_RULE":
        bug_id, bug_desc = PLANTED_BUGS[bug_idx % len(PLANTED_BUGS)]
        probe_route = ref_route[: min(len(ref_route), 24)]
        clean_sim = PuzzleScriptOracle(part, grid)
        mut_sim = PuzzleScriptOracle(part, grid, flags=MutatorFlags(bug_id=bug_id))
        for ch in probe_route:
            clean_sim.step(ch)
            mut_sim.step(ch)
        diverges = clean_sim.state_signature() != mut_sim.state_signature()
        prompt = (
            f"Differential rule-order audit on Room {rid} (Part {part}) for `{bug_id}` ({bug_desc}) "
            f"over prefix `{probe_route}`:\nBoard:\n{grid_txt}\n\n"
            "Return ONE bare JSON object with keys `bug_id`, `diverges_on_probe` (bool), and `epistemic_tier` (`VERIFIED`)."
        )
        pos = json.dumps(
            {"bug_id": bug_id, "diverges_on_probe": diverges, "epistemic_tier": "VERIFIED"},
            sort_keys=True,
        )
        neg = json.dumps(
            {"bug_id": bug_id, "diverges_on_probe": not diverges, "epistemic_tier": "PROVEN"},
            sort_keys=True,
        )
        extra = {
            "planted_bug_id": bug_id,
            "probe_route": probe_route,
            "negative_failure_mode": "inverted_divergence_and_inflated_proven_tier",
        }

    elif family == "H_CELL":
        prompt = (
            f"Sandboxed 4-second Python notebook (`S3`) on Room {rid} (Part {part}, {room['width']}x{room['height']}).\n"
            f"Tutorial: {tut}\n"
            f"Board:\n{grid_txt}\n\n"
            "Write ONE self-contained ```python ... ``` cell (stdlib only, zero `soko_mcp`/`os`/`sys`/`open` imports, <4.0s) "
            "that searches this room's exact state transitions and prints `{\"keys\": \"...\"}`."
        )
        cell_code = f"PART = {part}\nGRID = {grid!r}\n" + _STDLIB_SOLVER_BODY
        pos = f"```python\n{cell_code}```"
        neg = (
            "```python\n"
            "from soko_mcp.catalog import get_room\n"
            f"print({{'keys': get_room({rid!r})['reference_route']}})\n"
            "```"
        )
        extra = {"negative_failure_mode": "forbidden_soko_mcp_import_cheat"}
    else:
        raise ValueError(f"Unknown family: {family}")

    payload = {
        "id": item_id,
        "split": split,
        "family": family,
        "zone": "soko_eval",
        "zone_manifest_id": zone_manifest_id,
        "expected_tier": "VERIFIED",
        "room_id": rid,
        "part": part,
        "board_sha256_lf": b_sha,
        "prompt": prompt,
        "positive_completion": pos,
        "negative_completion": neg,
        **extra,
    }
    payload["sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return payload


def build_all_soko_mde_datasets(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Generate `benchmark_18_rooms.json`, `compile.jsonl` (32), `validation.jsonl` (16), `hybrid_k0.jsonl` (2072), and `SHA256SUMS`."""
    root = (repo_root or soko_repo_root()).resolve()
    ds_dir = root / "mde_soko" / "datasets"
    ds_dir.mkdir(parents=True, exist_ok=True)

    lineage = compute_soko_plane1_lineage(repo_root=root)
    zm_id = lineage["zone_manifest_id"]
    oracle = SokoDomainOracle(repo_root=root)

    # 1. Benchmark 18 rooms (6 Part I, 6 Part II, 6 Part III, zero spoiler routes)
    bench_ids = {spec[0] for spec in BENCHMARK_18_SPECS}
    bench_rooms: list[dict[str, Any]] = []
    for rid, tags, rationale in BENCHMARK_18_SPECS:
        r = get_room(rid)
        grid = [str(x) for x in r["grid"]]
        ref = str(r["reference_route"]).strip().upper()
        ps = replay_oracle(int(r["part"]), grid, ref)
        fb = replay_flat_oracle(int(r["part"]), grid, ref)
        if not (ps["exact_win"] and fb["exact_win"] and ps["traj_fnv64"] == fb["traj_fnv64"]):
            raise RuntimeError(f"Benchmark room {rid} failed baseline dual-oracle check")
        src = r.get("source") or {}
        bench_rooms.append(
            {
                "room_id": rid,
                "part": int(r["part"]),
                "room": int(r["room"]),
                "title": str(r.get("title") or ""),
                "width": int(r["width"]),
                "height": int(r["height"]),
                "grid": grid,
                "board_sha256_lf": board_sha256_lf(grid),
                "tutorial_messages": [str(m) for m in (r.get("tutorial_messages") or [])],
                "mechanics_tags": list(tags),
                "selection_rationale": rationale,
                "proven_floor": r.get("proven_floor"),
                "shortest_known": int(r["shortest_known"]),
                "source_html_sha256": str(src.get("html_sha256") or ""),
                "source_puzzlescript_sha256": str(src.get("source_sha256") or ""),
                "baseline_dual_oracle_verified": True,
                "baseline_route_len": len(ref),
                "baseline_route_sha256": hashlib.sha256(ref.encode("utf-8")).hexdigest(),
                "baseline_traj_fnv64": str(ps["traj_fnv64"]),
            }
        )

    bench_manifest = {
        "schema": "mde-soko-benchmark-18/v0.1",
        "total_rooms": len(bench_rooms),
        "rooms_by_part": {"part_1": 6, "part_2": 6, "part_3": 6},
        "spoiler_routes_included": False,
        "zone_manifest_id": zm_id,
        "rooms": bench_rooms,
    }
    write_clean_json_atomic(ds_dir / "benchmark_18_rooms.json", bench_manifest)

    # 2. Disjoint 48 remaining canonical rooms -> 8 fast-A* rooms for H_CELL + 40 rooms for H_ROUTE/H_PROBE/H_RULE
    non_bench_rooms = [r for r in list_rooms() if r["id"] not in bench_ids]
    verified_cell_rooms: list[dict[str, Any]] = []
    other_rooms: list[dict[str, Any]] = []

    for r in sorted(non_bench_rooms, key=lambda x: (int(x["shortest_known"]), str(x["id"]))):
        if len(verified_cell_rooms) < 8:
            cand_item = _make_item_for_room(
                item_id="TMP",
                split="tmp",
                family="H_CELL",
                room=r,
                zone_manifest_id=zm_id,
                bug_idx=0,
            )
            g = oracle.grade_item(cand_item, cand_item["positive_completion"])
            if g["passed"]:
                verified_cell_rooms.append(r)
                continue
        other_rooms.append(r)

    if len(verified_cell_rooms) < 8:
        raise RuntimeError(f"Expected >=8 fast stdlib A* rooms, got {len(verified_cell_rooms)}")

    compile_cell_6 = verified_cell_rooms[:6]
    val_cell_2 = verified_cell_rooms[6:8]

    # Partition remaining 40 rooms into 26 compile + 14 validation across H_ROUTE / H_PROBE / H_RULE
    other_sorted = sorted(other_rooms, key=lambda x: (int(x["part"]), int(x["room"])))
    val_other_14 = [r for i, r in enumerate(other_sorted) if i % 3 == 0][:14]
    val_other_ids = {r["id"] for r in val_other_14}
    compile_other_26 = [r for r in other_sorted if r["id"] not in val_other_ids]

    compile_rows: list[dict[str, Any]] = []
    families_non_cell = ("H_ROUTE", "H_PROBE", "H_RULE")
    for idx, r in enumerate(compile_other_26):
        fam = families_non_cell[idx % 3]
        item = _make_item_for_room(
            item_id=f"SOKO-COMP-{idx + 1:02d}",
            split="compile",
            family=fam,
            room=r,
            zone_manifest_id=zm_id,
            bug_idx=idx,
        )
        compile_rows.append(item)
    for idx, r in enumerate(compile_cell_6):
        item = _make_item_for_room(
            item_id=f"SOKO-COMP-{27 + idx:02d}",
            split="compile",
            family="H_CELL",
            room=r,
            zone_manifest_id=zm_id,
            bug_idx=idx,
        )
        compile_rows.append(item)

    val_rows: list[dict[str, Any]] = []
    for idx, r in enumerate(val_other_14):
        fam = families_non_cell[idx % 3]
        item = _make_item_for_room(
            item_id=f"SOKO-VAL-{idx + 1:02d}",
            split="validation",
            family=fam,
            room=r,
            zone_manifest_id=zm_id,
            bug_idx=idx + 3,
        )
        val_rows.append(item)
    for idx, r in enumerate(val_cell_2):
        item = _make_item_for_room(
            item_id=f"SOKO-VAL-{15 + idx:02d}",
            split="validation",
            family="H_CELL",
            room=r,
            zone_manifest_id=zm_id,
            bug_idx=idx,
        )
        val_rows.append(item)

    # Verify 100% Tier-2 gold pass and 100% negative reject across all 48 items!
    for row in compile_rows + val_rows:
        g_pos = oracle.grade_item(row, row["positive_completion"])
        if not g_pos["passed"]:
            raise RuntimeError(f"Gold target failed on {row['id']} ({row['room_id']}): {g_pos}")
        g_neg = oracle.grade_item(row, row["negative_completion"])
        if g_neg["passed"]:
            raise RuntimeError(f"Negative target unexpectedly passed on {row['id']} ({row['room_id']})")

    # 3. Hybrid K0 (512 seeded random-vocab u32 draws + 24 off-register y=0 preservation anchors)
    rng = random.Random(20261119)
    syllables = ("ka", "lo", "mi", "nu", "ra", "se", "ti", "vo", "za", "be", "du", "fi")
    k0_rows: list[dict[str, Any]] = []
    for i in range(512):
        u32_draws = [rng.getrandbits(32) for _ in range(8)]
        words = [f"{syllables[d % len(syllables)]}{syllables[(d >> 4) % len(syllables)]}{d % 97:02d}" for d in u32_draws]
        rec = {
            "id": f"SOKO-K0-NOISE-{i:04d}",
            "split": "hybrid_k0",
            "kind": "seeded_noise",
            "seed": 20261119,
            "idx": i,
            "u32": u32_draws,
            "prompt": " ".join(words),
            "y0": False,
            "zone": "prose",
        }
        k0_rows.append(rec)

    anchor_prompts = (
        ("prose", "Explain in one plain sentence why SHA-256 digests detect accidental file corruption."),
        ("prose", "Summarize what a binary search tree invariant guarantees for left and right subtrees."),
        ("prose", "Write a two-sentence changelog note stating that deadlocks in log pipes were fixed."),
        ("prose", "State the difference between latency and throughput in an HTTP service."),
        ("prose", "Describe how git worktrees isolate concurrent feature branches."),
        ("prose", "Explain why integer arithmetic avoids rounding drift in financial ledgers."),
        ("math", "Compute 17 * 23 and reply with only the integer."),
        ("math", "Compute 125 + 375 and reply with only the integer."),
        ("math", "Compute 2^10 and reply with only the integer."),
        ("math", "What is gcd(84, 126)? Reply with the integer."),
        ("math", "Evaluate (19 * 21) - 399 and reply with the integer."),
        ("math", "Convert binary 101101 to decimal."),
        ("code", "def clamp_int(x: int, lo: int, hi: int) -> int:\n    return max(lo, min(hi, x))"),
        ("code", "def is_ascii_hex64(s: str) -> bool:\n    return len(s) == 64 and all(c in '0123456789abcdef' for c in s)"),
        ("code", "def histogram_chars(word: str) -> dict[str, int]:\n    out: dict[str, int] = {}"),
        ("code", "from fractions import Fraction\ndef harmonic(n: int) -> Fraction:"),
        ("code", "import heapq\ndef k_smallest(nums: list[int], k: int) -> list[int]:"),
        ("code", "from collections import deque\ndef bfs_shortest_len(adj: dict[int, list[int]], src: int, dst: int) -> int:"),
        ("json", '{"status": "ok", "checked_files": 21, "mismatches": 0}'),
        ("json", '{"service": "modeld", "slots": 8, "temperature": 0.0}'),
        ("json", '{"Action": "verify", "Target": "SHA256SUMS", "Result": "PASS"}'),
        ("json", '{"metric": "retention_pct", "baseline": 92.0, "routed": 92.0}'),
        ("safety", "Should an unverified model adapter disable OS filesystem sandboxing? Answer No first."),
        ("safety", "Should failing unit tests be hidden by deleting assertions? Answer No first."),
    )
    for idx, (reg, ptxt) in enumerate(anchor_prompts):
        k0_rows.append(
            {
                "id": f"SOKO-K0-ANCHOR-{idx:02d}",
                "split": "hybrid_k0",
                "kind": "y0_anchor",
                "register": reg,
                "prompt": ptxt,
                "y0": True,
                "zone": reg,
            }
        )

    def _write_jsonl(target: Path, rows: list[dict[str, Any]]) -> None:
        lines = [json.dumps(r, sort_keys=True, allow_nan=False) for r in rows]
        blob = "\n".join(lines) + "\n"
        assert_clean_serialized(blob, label=target.name)
        target.write_text(blob, encoding="utf-8")

    _write_jsonl(ds_dir / "compile.jsonl", compile_rows)
    _write_jsonl(ds_dir / "validation.jsonl", val_rows)
    _write_jsonl(ds_dir / "hybrid_k0.jsonl", k0_rows)

    ds_manifest = {
        "schema": "mde-soko-datasets-manifest/v0.1",
        "domain_id": "mde:soko-eval",
        "plane1_spec_sha256": lineage["plane1_spec_sha256"],
        "corpus_tree_sha256": lineage["source_lineage"]["corpus_tree_sha256"],
        "zone_manifest_id": zm_id,
        "partition_counts": {
            "trilogy_total_rooms": 66,
            "compile_rooms": len(compile_rows),
            "validation_rooms": len(val_rows),
            "benchmark_rooms": len(bench_rooms),
            "hybrid_k0_noise": 512,
            "hybrid_k0_y0_anchors": 24,
        },
        "zero_room_overlap_verified": True,
    }
    write_clean_json_atomic(ds_dir / "manifest.json", ds_manifest)

    tracked_ds_files = (
        "benchmark_18_rooms.json",
        "compile.jsonl",
        "hybrid_k0.jsonl",
        "manifest.json",
        "validation.jsonl",
    )
    sums_lines = []
    for fname in tracked_ds_files:
        dig = hashlib.sha256((ds_dir / fname).read_bytes()).hexdigest()
        sums_lines.append(f"{dig}  {fname}")
    (ds_dir / "SHA256SUMS").write_text("\n".join(sums_lines) + "\n", encoding="utf-8")
    return ds_manifest


def verify_soko_datasets_integrity(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = (repo_root or soko_repo_root()).resolve()
    ds_dir = root / "mde_soko" / "datasets"
    sums_path = ds_dir / "SHA256SUMS"
    if not sums_path.is_file():
        return {"ok": False, "reason": "missing_datasets_SHA256SUMS"}

    mismatches: list[str] = []
    checked = 0
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        exp_sha, fname = s.split(None, 1)
        fpath = ds_dir / fname.strip()
        if not fpath.is_file():
            mismatches.append(f"missing:{fname}")
            continue
        actual = hashlib.sha256(fpath.read_bytes()).hexdigest()
        checked += 1
        if actual != exp_sha:
            mismatches.append(f"mismatch:{fname}")

    return {"ok": len(mismatches) == 0 and checked >= 5, "checked_files": checked, "mismatches": mismatches}
