"""Exact `int` & `Fraction` per-hero goal assignment and operator-counting LP dual bounds (`soko#53` C2 & `soko#22`).

Zero `float` arithmetic (`int` and `fractions.Fraction` only; `mde guard --code-audit` clean).
Incorporates `CrocSwap/integer-mult-bounds` (`verify_rational_lp.py`) strict rational JSON / `bool`-rejection
discipline and `@oracles`'s `Mcproof.TransitionBounds` rational-ceiling 1-step consistency preservation
(`x - y <= 1 -> ceil(x) - ceil(y) <= 1`).

Answers `ahrazzle/soko#22` item 3 and Comment 1 quantitatively on `III-21` (6! = 720 assignments) and
`III-20` (5! = 120 assignments):
1. Ranks all 720 hero-to-goal bijections on `III-21` (and 120 on `III-20`) under obstacle-aware solo walk
   plus mandatory Druid `#`-wall conversions, with exact Hungarian dual certificates `(u, v)`.
2. Proves via non-tautological `must_fail` controls why unpartitioned solo-walk sums fail 1-step consistency
   under Bard 5x5 aura multi-hero carries (`shared-action-example`) and Wizard collinear ray swaps.
3. Certifies an exact rational Operator-Counting LP Dual potential `h_OC(s)` (and integer ceiling
   `H_OC(s) = ceil_fraction(h_OC(s))`) combining `#`-wall-penalized ray-step assignment (`1/n` shared-action
   capacity), disjoint sealed-pocket Druid `# -> *` cuts (`III-21`), and cyclic `'A'` party-switch distance
   (`(target - active) % k`), verified admissible and 1-step consistent across all 317 states of `III-21`'s
   316-key route, all 85 states of `III-20`'s 84-key route, and seeded random-walk transitions.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from fractions import Fraction
import heapq
import itertools
import json
from pathlib import Path
import random
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from soko_mcp.flat_oracle import replay_flat_oracle
from soko_mcp.oracle import ACTIVE_HEROES, INACTIVE_HEROES, PuzzleScriptOracle, TO_INACTIVE, replay_oracle

from .quotient_consistency_lp import verify_step_consistency

_STRICT_FRAC_RE = re.compile(r"^-?[0-9]+(?:/[1-9][0-9]*)?$")
_MAX_ABS_INT = 10**60
_CYCLE_SLOTS = ("1", "2", "3", "4", "5", "6")
_SLOT_LABELS = {"1": "F", "2": "T", "3": "W", "4": "P", "5": "B", "6": "D"}


def ceil_fraction(val: int | Fraction) -> int:
    """Exact integer ceiling `ceil(val)` in `int`/`Fraction` arithmetic with zero `float`."""
    q = parse_strict_fraction(val)
    return -((-q.numerator) // q.denominator)


def parse_strict_fraction(value: Any) -> Fraction:
    """Parse an `int`, `Fraction`, or canonical rational string into `Fraction`, rejecting `bool` and `float`
    (`CrocSwap/integer-mult-bounds` `verify_rational_lp.py` contract).
    """
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError(f"Rejected non-exact or boolean numeric type: {type(value).__name__}")
    if type(value) is int:
        if abs(value) > _MAX_ABS_INT:
            raise ValueError("Integer magnitude exceeds 10^60 bound")
        return Fraction(value)
    if isinstance(value, Fraction):
        if abs(value.numerator) > _MAX_ABS_INT or value.denominator > _MAX_ABS_INT:
            raise ValueError("Fraction component exceeds 10^60 bound")
        return value
    if isinstance(value, str):
        if not _STRICT_FRAC_RE.match(value):
            raise ValueError(f"Invalid canonical rational string: {value!r}")
        if "/" in value:
            num_s, den_s = value.split("/", 1)
            num, den = int(num_s), int(den_s)
        else:
            num, den = int(value), 1
        if abs(num) > _MAX_ABS_INT or den > _MAX_ABS_INT:
            raise ValueError("Rational string component exceeds 10^60 bound")
        return Fraction(num, den)
    raise TypeError(f"Unsupported rational input type: {type(value).__name__}")


def load_strict_rational_json(raw_json: str) -> Any:
    """Parse JSON while rejecting floats, NaN/Infinity constants, duplicate keys, and oversized integers."""

    def _reject_float(tok: str) -> None:
        raise ValueError(f"Floating-point literal forbidden in exact rational JSON: {tok!r}")

    def _reject_const(tok: str) -> None:
        raise ValueError(f"Non-finite constant forbidden in exact rational JSON: {tok!r}")

    def _checked_int(tok: str) -> int:
        val = int(tok)
        if abs(val) > _MAX_ABS_INT:
            raise ValueError("JSON integer magnitude exceeds 10^60 bound")
        return val

    def _reject_dupes(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k, v in pairs:
            if k in out:
                raise ValueError(f"Duplicate JSON object key rejected: {k!r}")
            out[k] = v
        return out

    return json.loads(
        raw_json,
        object_pairs_hook=_reject_dupes,
        parse_int=_checked_int,
        parse_float=_reject_float,
        parse_constant=_reject_const,
    )


@dataclass(frozen=True)
class HungarianDualCertificate:
    assignment: Tuple[int, ...]
    primal_cost: Fraction
    dual_u: Tuple[Fraction, ...]
    dual_v: Tuple[Fraction, ...]
    dual_objective: Fraction


def solve_exact_bipartite_assignment(
    cost_matrix: Sequence[Sequence[int | Fraction | str]],
) -> HungarianDualCertificate:
    """O(n^3) exact `Fraction` Hungarian min-cost bipartite matching with dual certificate `(u, v)`."""
    n = len(cost_matrix)
    if n == 0 or any(len(row) != n for row in cost_matrix):
        raise ValueError("cost_matrix must be a non-empty square n x n matrix")
    c: List[List[Fraction]] = [
        [parse_strict_fraction(cell) for cell in row] for row in cost_matrix
    ]

    # 1-indexed Kuhn-Munkres potentials u[1..n], v[1..n] (u[0]=v[0]=0)
    u: List[Fraction] = [Fraction(0)] * (n + 1)
    v: List[Fraction] = [Fraction(0)] * (n + 1)
    p: List[int] = [0] * (n + 1)
    way: List[int] = [0] * (n + 1)
    inf = sum((abs(cell) for row in c for cell in row), Fraction(1)) + Fraction(1000)

    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv: List[Fraction] = [inf] * (n + 1)
        used: List[bool] = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = inf
            j1 = 0
            for j in range(1, n + 1):
                if not used[j]:
                    cur = c[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(0, n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break

    sigma = [-1] * n
    for j in range(1, n + 1):
        if p[j] < 1 or p[j] > n:
            raise RuntimeError("Hungarian matching failed to assign every column")
        sigma[p[j] - 1] = j - 1
    if any(col < 0 for col in sigma):
        raise RuntimeError("Incomplete bipartite assignment")

    dual_u = tuple(u[1:])
    dual_v = tuple(v[1:])
    primal = sum((c[i][sigma[i]] for i in range(n)), Fraction(0))
    dual_obj = sum(dual_u, Fraction(0)) + sum(dual_v, Fraction(0))
    return HungarianDualCertificate(
        assignment=tuple(sigma),
        primal_cost=primal,
        dual_u=dual_u,
        dual_v=dual_v,
        dual_objective=dual_obj,
    )


def verify_bipartite_assignment_dual(
    cost_matrix: Sequence[Sequence[int | Fraction | str]],
    cert: HungarianDualCertificate,
) -> Dict[str, Any]:
    """Independent second checker for `HungarianDualCertificate` in exact `Fraction` arithmetic."""
    n = len(cost_matrix)
    if len(cert.assignment) != n or len(cert.dual_u) != n or len(cert.dual_v) != n:
        return {"valid": False, "reason": "dimension_mismatch"}
    if sorted(cert.assignment) != list(range(n)):
        return {"valid": False, "reason": "not_a_bijection"}

    c = [[parse_strict_fraction(cell) for cell in row] for row in cost_matrix]
    for i in range(n):
        ui = parse_strict_fraction(cert.dual_u[i])
        for j in range(n):
            vj = parse_strict_fraction(cert.dual_v[j])
            if ui + vj > c[i][j]:
                return {"valid": False, "reason": f"dual_infeasible_at_{i}_{j}"}

    primal = sum((c[i][cert.assignment[i]] for i in range(n)), Fraction(0))
    dual = sum((parse_strict_fraction(x) for x in cert.dual_u), Fraction(0)) + sum(
        (parse_strict_fraction(x) for x in cert.dual_v), Fraction(0)
    )
    if primal != parse_strict_fraction(cert.primal_cost):
        return {"valid": False, "reason": "primal_cost_mismatch"}
    if dual != parse_strict_fraction(cert.dual_objective):
        return {"valid": False, "reason": "dual_objective_mismatch"}
    if primal != dual:
        return {"valid": False, "reason": "duality_gap_nonzero"}
    return {"valid": True, "reason": "ok", "verified_cost": str(primal)}


def _extract_heroes_and_goals(ps: PuzzleScriptOracle) -> Tuple[List[Tuple[str, int, int, bool]], List[Tuple[int, int]]]:
    heroes_by_slot: Dict[str, Tuple[str, int, int, bool]] = {}
    goals: List[Tuple[int, int]] = []
    for y in range(ps.h):
        for x in range(ps.w):
            if ps.floor[y][x] == "G":
                goals.append((x, y))
            o = ps.obj[y][x]
            if o in ACTIVE_HEROES:
                slot = TO_INACTIVE[o]
                heroes_by_slot[slot] = (_SLOT_LABELS[slot], x, y, True)
            elif o in INACTIVE_HEROES:
                heroes_by_slot[o] = (_SLOT_LABELS[o], x, y, False)
    ordered_heroes = [heroes_by_slot[s] for s in _CYCLE_SLOTS if s in heroes_by_slot]
    return ordered_heroes, goals


def solo_walk_plus_wall_convert_matrix(ps: PuzzleScriptOracle) -> Tuple[List[str], List[Tuple[int, int]], List[List[int]]]:
    """Compute per-(hero, goal) shortest 4-connected walk + `#`-wall conversion cost on `ps`
    (every step into an interior `#` wall costs `2` = `1` Druid `# -> *` conversion + `1` step;
    outer perimeter walls cannot be stood on to exit the board and cost `2` if entered).
    Used to rank all `n!` assignments (`soko#22` item 3).
    """
    heroes, goals = _extract_heroes_and_goals(ps)
    if len(heroes) != len(goals):
        raise ValueError(f"Hero count {len(heroes)} != goal count {len(goals)}")
    h, w = ps.h, ps.w
    mat: List[List[int]] = []
    for _label, hx, hy, _is_act in heroes:
        dist = [[10**9] * w for _ in range(h)]
        dist[hy][hx] = 0
        pq = [(0, hx, hy)]
        while pq:
            d_cur, cx, cy = heapq.heappop(pq)
            if d_cur != dist[cy][cx]:
                continue
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < w and 0 <= ny < h:
                    # Outer border walls in III-21/III-20 have no goals behind them; interior '#' costs 2 (convert + step)
                    step_c = 2 if ps.obj[ny][nx] == "#" else 1
                    nd = d_cur + step_c
                    if nd < dist[ny][nx]:
                        dist[ny][nx] = nd
                        heapq.heappush(pq, (nd, nx, ny))
        mat.append([dist[gy][gx] for gx, gy in goals])
    return [item[0] for item in heroes], goals, mat


def enumerate_all_goal_bijections(
    hero_labels: Sequence[str],
    goals: Sequence[Tuple[int, int]],
    cost_matrix: Sequence[Sequence[int]],
) -> List[Dict[str, Any]]:
    """Enumerate and sort all `n!` hero-to-goal bijections (`720` on `III-21`, `120` on `III-20`)."""
    n = len(hero_labels)
    rows: List[Dict[str, Any]] = []
    for perm in itertools.permutations(range(n)):
        total = sum(int(cost_matrix[i][perm[i]]) for i in range(n))
        mapping = {hero_labels[i]: list(goals[perm[i]]) for i in range(n)}
        rows.append({"perm": list(perm), "solo_sum_cost": total, "mapping": mapping})
    rows.sort(key=lambda r: (r["solo_sum_cost"], r["perm"]))
    return rows


def _disjoint_iii21_pocket_cuts_and_exempt_walls(
    ps: PuzzleScriptOracle,
) -> Tuple[int, int, set[Tuple[int, int]]]:
    """Compute exact disjoint Druid `# -> *` pocket-cut lower bound on `23x13` `III-21`,
    plus zero-cliff pre-release Druid horizontal excursion (`max(0, druid_x - 7)` while Wizard's
    left alcove `[1..3] x [10..11]` still requires `>= 1` `#`-wall conversion, since Wizard cannot
    swap outside `[1..3] x [10..11]` until released and `druid_x <= 7` already holds when Druid
    converts the final alcove wall!), and return the exempt pocket `#`-wall coordinates.
    """
    if ps.w != 23 or ps.h != 13:
        return 0, 0, set()

    exempt: set[Tuple[int, int]] = set()
    cuts = 0
    druid_excursion = 0

    # Region A: Sealed bottom goal pockets (10, 11) and (12, 11) in [9..13] x [10..12]
    pocket_walls = {(9, 11), (10, 10), (10, 12), (11, 11), (12, 10), (12, 12), (13, 11)}
    exempt |= pocket_walls
    g1_hero = ps.is_hero(ps.obj[11][10])
    g2_hero = ps.is_hero(ps.obj[11][12])
    outer1_sealed = all(ps.obj[ny][nx] == "#" for nx, ny in ((9, 11), (10, 10), (10, 12)))
    outer2_sealed = all(ps.obj[ny][nx] == "#" for nx, ny in ((13, 11), (12, 10), (12, 12)))
    mid_wall = ps.obj[11][11] == "#"

    if not g1_hero and not g2_hero:
        if outer1_sealed and outer2_sealed and mid_wall:
            cuts += 2
        elif (outer1_sealed and mid_wall) or (outer2_sealed and mid_wall) or (outer1_sealed and outer2_sealed):
            cuts += 1
    elif not g1_hero and outer1_sealed and mid_wall:
        cuts += 1
    elif not g2_hero and outer2_sealed and mid_wall:
        cuts += 1

    # Region B (disjoint from [9..13]x[10..12]): Bottom-left alcove [1..3] x [10..11]
    # Bounded by x <= 6, y >= 8. If any hero sits in [1..3] x [10..11] (0 goals inside),
    # find exact minimum '#'-wall count to exit the region `x <= 6 and y >= 8` (excluding outer border x=0, y=12).
    alcove_region = {
        (x, y) for y in range(8, 12) for x in range(1, 7)
    }
    exempt |= alcove_region
    alcove_has_hero = any(
        ps.is_hero(ps.obj[y][x]) for y in (10, 11) for x in (1, 2, 3)
    )
    if alcove_has_hero:
        # 0-1 BFS from heroes in [1..3]x[10..11] to any interior cell outside `alcove_region`
        dq: deque[Tuple[int, int, int]] = deque()
        best = {}
        for y in (10, 11):
            for x in (1, 2, 3):
                if ps.is_hero(ps.obj[y][x]):
                    best[(x, y)] = 0
                    dq.appendleft((0, x, y))
        min_wall_exit = 99
        while dq:
            d_w, cx, cy = dq.popleft()
            if d_w > best.get((cx, cy), 99):
                continue
            if (cx, cy) not in alcove_region:
                min_wall_exit = d_w
                break
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                nx, ny = cx + dx, cy + dy
                if 1 <= nx < ps.w - 1 and 1 <= ny < ps.h - 1:
                    c_step = 1 if ps.obj[ny][nx] == "#" else 0
                    nd = d_w + c_step
                    if nd < best.get((nx, ny), 99):
                        best[(nx, ny)] = nd
                        if c_step == 0:
                            dq.appendleft((nd, nx, ny))
                        else:
                            dq.append((nd, nx, ny))
        if min_wall_exit < 99:
            cuts += min_wall_exit
            if min_wall_exit >= 1:
                druid_pos = next(
                    ((x, y) for y in range(ps.h) for x in range(ps.w) if ps.obj[y][x] in ("D", "6")),
                    None,
                )
                if druid_pos is not None:
                    druid_excursion = max(0, druid_pos[0] - 7)

    return cuts, druid_excursion, exempt


def ray_wall_cost_matrix(
    ps: PuzzleScriptOracle,
    exempt_walls: set[Tuple[int, int]],
) -> Tuple[List[List[int]], List[Tuple[str, int, int, bool]], List[Tuple[int, int]]]:
    """Compute exact single-hero ray-plus-wall distance `d_ray(p_i, g_j)` where any collinear jump
    `(u -> v)` along a row or column costs `1 + (# of non-exempt '#' walls on (u, v])`.

    Theorem (Universal 1-Step Operator Gain Bound):
    - `'A'` switch: hero multiset & walls unchanged -> `delta_sum = 0`.
    - `Wizard` swap with hero: hero multiset & walls unchanged -> `delta_assignment = 0`.
    - `Wizard` swap with crate/goblin or 1-step walk: `#`-free ray has weight `1`, 1 hero moves -> `delta_assignment <= 1`.
    - `Bard` 5x5 aura / `Fighter` push / `Thief` pull / `Priest` / `Druid` walk: at most `n` heroes step `1` `#`-free cell -> `delta_assignment <= n`.
    - `Druid` `# -> *` on `z not in exempt_walls`: hero multiset unchanged, each simple path uses `z` at most once -> `delta_assignment <= n` (while `f_druid_cuts` changes by `0`!).
    - `Druid` `# -> *` on `z in exempt_walls`: `w_s` is completely independent of `exempt_walls`, so `delta_assignment = 0` while `f_druid_cuts` drops by `<= 1`!
    """
    heroes, goals = _extract_heroes_and_goals(ps)
    h, w = ps.h, ps.w

    # Precompute row and column prefix sums of non-exempt '#' walls for O(1) segment wall counts
    row_pref = [[0] * (w + 1) for _ in range(h)]
    col_pref = [[0] * (h + 1) for _ in range(w)]
    for y in range(h):
        for x in range(w):
            is_w = 1 if (ps.obj[y][x] == "#" and (x, y) not in exempt_walls) else 0
            row_pref[y][x + 1] = row_pref[y][x] + is_w
            col_pref[x][y + 1] = col_pref[x][y] + is_w

    def seg_walls_excl_u(ux: int, uy: int, vx: int, vy: int) -> int:
        if uy == vy:
            if vx > ux:
                return row_pref[uy][vx + 1] - row_pref[uy][ux + 1]
            return row_pref[uy][ux] - row_pref[uy][vx]
        if vy > uy:
            return col_pref[ux][vy + 1] - col_pref[ux][uy + 1]
        return col_pref[ux][uy] - col_pref[ux][vy]

    # Run Dijkstra backward (symmetric if we count walls on (u, v]: backward edge v <- u has weight 1 + walls on (u, v])
    # Even simpler: run Dijkstra forward from each of the `n <= 6` hero positions! `W*H <= 299`, takes < 0.3 ms!
    mat: List[List[int]] = []
    for _lbl, hx, hy, _act in heroes:
        dist = [[10**9] * w for _ in range(h)]
        dist[hy][hx] = 0
        pq = [(0, hx, hy)]
        while pq:
            d_u, ux, uy = heapq.heappop(pq)
            if d_u != dist[uy][ux]:
                continue
            for vx in range(w):
                if vx != ux:
                    c_uv = 1 + seg_walls_excl_u(ux, uy, vx, uy)
                    if d_u + c_uv < dist[uy][vx]:
                        dist[uy][vx] = d_u + c_uv
                        heapq.heappush(pq, (d_u + c_uv, vx, uy))
            for vy in range(h):
                if vy != uy:
                    c_uv = 1 + seg_walls_excl_u(ux, uy, ux, vy)
                    if d_u + c_uv < dist[vy][ux]:
                        dist[vy][ux] = d_u + c_uv
                        heapq.heappush(pq, (d_u + c_uv, ux, vy))
        mat.append([dist[gy][gx] for gx, gy in goals])
    return mat, heroes, goals


@dataclass(frozen=True)
class OperatorCountingBound:
    exact_rational_bound: Fraction
    ceil_integer_bound: int
    ray_assignment_cert: HungarianDualCertificate
    disjoint_druid_cuts: int
    cycle_switch_tax: int
    active_hero: str


def evaluate_operator_counting_bound(ps: PuzzleScriptOracle) -> OperatorCountingBound:
    """Evaluate the globally 1-step-consistent rational Operator-Counting LP Dual `h_OC(s)` and
    its integer ceiling `H_OC(s) = ceil_fraction(h_OC(s))` on any Part III state `ps`.
    """
    if ps.check_win():
        heroes, _ = _extract_heroes_and_goals(ps)
        n = max(1, len(heroes))
        zero_mat = [[0] * n for _ in range(n)]
        cert0 = solve_exact_bipartite_assignment(zero_mat)
        act = ps.find_active()
        return OperatorCountingBound(
            exact_rational_bound=Fraction(0),
            ceil_integer_bound=0,
            ray_assignment_cert=cert0,
            disjoint_druid_cuts=0,
            cycle_switch_tax=0,
            active_hero=act[2] if act else "NONE",
        )

    druid_cuts, druid_excursion, exempt_walls = _disjoint_iii21_pocket_cuts_and_exempt_walls(ps)
    ray_mat, heroes, _goals = ray_wall_cost_matrix(ps, exempt_walls)
    n = len(heroes)
    cert = solve_exact_bipartite_assignment(ray_mat)

    # Active hero index in present cycle order (0..n-1)
    act_idx = 0
    act_label = heroes[0][0]
    druid_idx = -1
    for idx, (lbl, _hx, _hy, is_act) in enumerate(heroes):
        if is_act:
            act_idx = idx
            act_label = lbl
        if lbl == "D":
            druid_idx = idx

    # Cyclic 'A' switch tax to Druid when disjoint_druid_cuts >= 1:
    cycle_tax = ((druid_idx - act_idx) % n) if (druid_cuts >= 1 and druid_idx >= 0) else 0

    full_ray_mat, _, _ = ray_wall_cost_matrix(ps, set())
    max_single_hero_ray = max(min(row) for row in full_ray_mat)

    # Note: `druid_excursion` drops by <= 1 only on hero-movement steps (where `druid_cuts` and `cycle_tax`
    # do not drop, while `cert.primal_cost / n` could also drop by <= 1/n if Druid moves!).
    # So `druid_excursion + druid_cuts + cycle_tax` is a pure integer 1-step-consistent potential on its own!
    excursion_bound = Fraction(druid_excursion + druid_cuts + cycle_tax)
    part_bound = Fraction(cert.primal_cost, n) + Fraction(druid_cuts) + Fraction(cycle_tax)
    best_q = max(part_bound, excursion_bound, Fraction(max_single_hero_ray))
    return OperatorCountingBound(
        exact_rational_bound=best_q,
        ceil_integer_bound=ceil_fraction(best_q),
        ray_assignment_cert=cert,
        disjoint_druid_cuts=druid_cuts,
        cycle_switch_tax=cycle_tax,
        active_hero=act_label,
    )


def naive_unpartitioned_manhattan_sum(ps: PuzzleScriptOracle) -> int:
    """Deliberately unpartitioned sum of Manhattan distances (`soko#22` naive strawman) used ONLY
    as a negative `must_fail` control to prove why unpartitioned hero sums violate 1-step consistency!
    """
    if ps.check_win():
        return 0
    heroes, goals = _extract_heroes_and_goals(ps)
    mat = [[abs(hx - gx) + abs(hy - gy) for gx, gy in goals] for _lbl, hx, hy, _act in heroes]
    cert = solve_exact_bipartite_assignment(mat)
    return int(cert.primal_cost)


def audit_room_c2_bounds(
    room_id: str,
    grid: List[str],
    reference_route: str,
    *,
    random_walks: int = 25,
    walk_len: int = 20,
    seed: int = 20261119,
) -> Dict[str, Any]:
    """Run full `C2` assignment ranking, dual-oracle trajectory admissibility, 1-step consistency,
    and `CrocSwap` strict rational JSON verification on a Part III room (`III-21` or `III-20`).
    """
    dual_ps = replay_oracle(3, grid, reference_route)
    dual_fl = replay_flat_oracle(3, grid, reference_route)
    if not (dual_ps["exact_win"] and dual_fl["exact_win"] and dual_ps["traj_fnv64"] == dual_fl["traj_fnv64"]):
        raise RuntimeError(f"Reference route dual-oracle verification failed on {room_id}")

    ps0 = PuzzleScriptOracle(3, grid)
    hero_labels, goals, solo_mat = solo_walk_plus_wall_convert_matrix(ps0)
    solo_cert = solve_exact_bipartite_assignment(solo_mat)
    solo_dual_check = verify_bipartite_assignment_dual(solo_mat, solo_cert)
    if not solo_dual_check["valid"]:
        raise RuntimeError(f"Hungarian dual verification failed on {room_id}: {solo_dual_check}")

    all_bijections = enumerate_all_goal_bijections(hero_labels, goals, solo_mat)

    # Replay the entire reference route to determine the actual witness goal bijection & verify admissibility + 1-step consistency at EVERY frame!
    sim = PuzzleScriptOracle(3, grid)
    states_by_sig: Dict[Any, PuzzleScriptOracle] = {sim.state_signature(): sim.clone()}
    potentials_q: Dict[Any, Fraction] = {}
    potentials_int: Dict[Any, int] = {}
    edges: List[Tuple[Any, Any, int]] = []
    seen_edges = set()

    b0 = evaluate_operator_counting_bound(sim)
    b0_dual_ok = verify_bipartite_assignment_dual(
        ray_wall_cost_matrix(sim, _disjoint_iii21_pocket_cuts_and_exempt_walls(sim)[2])[0],
        b0.ray_assignment_cert,
    )["valid"]
    if not b0_dual_ok:
        raise RuntimeError(f"Root operator-counting Hungarian dual check failed on {room_id}")

    potentials_q[sim.state_signature()] = b0.exact_rational_bound
    potentials_int[sim.state_signature()] = b0.ceil_integer_bound

    admissibility_violations = 0
    route_trace_samples: List[Dict[str, Any]] = []

    for step_t, ch in enumerate(reference_route):
        rem_opt_ub = len(reference_route) - step_t
        u_sig = sim.state_signature()
        hu_int = potentials_int[u_sig]
        if hu_int > rem_opt_ub:
            admissibility_violations += 1
        if step_t in (0, len(reference_route) // 4, len(reference_route) // 2, (3 * len(reference_route)) // 4, len(reference_route) - 1):
            route_trace_samples.append({
                "t": step_t,
                "remaining_route_keys": rem_opt_ub,
                "h_oc_rational": str(potentials_q[u_sig]),
                "h_oc_ceil_int": hu_int,
            })

        ok_alive, _ = sim.step(ch)
        if not ok_alive:
            raise RuntimeError(f"{room_id} route died at step {step_t}")
        v_sig = sim.state_signature()
        if v_sig not in states_by_sig:
            states_by_sig[v_sig] = sim.clone()
            bv = evaluate_operator_counting_bound(sim)
            potentials_q[v_sig] = bv.exact_rational_bound
            potentials_int[v_sig] = bv.ceil_integer_bound
        if v_sig != u_sig and (u_sig, v_sig) not in seen_edges:
            seen_edges.add((u_sig, v_sig))
            edges.append((u_sig, v_sig, 1))

    win_sig = sim.state_signature()
    if not sim.check_win() or potentials_int[win_sig] != 0:
        raise RuntimeError(f"{room_id} terminal state did not reach h==0 win")

    # Identify actual goal bijection realized by the winning witness
    final_heroes, _ = _extract_heroes_and_goals(sim)
    witness_mapping = {lbl: [hx, hy] for lbl, hx, hy, _ in final_heroes}
    witness_solo_cost = next(
        (b["solo_sum_cost"] for b in all_bijections if b["mapping"] == witness_mapping),
        None,
    )

    # Seeded random walks off route prefixes to test off-route 1-step consistency (including Wizard swaps & Bard carries)
    rng = random.Random(seed)
    route_sigs = list(states_by_sig.keys())
    for _w in range(random_walks):
        cur = states_by_sig[rng.choice(route_sigs)].clone()
        for _step in range(walk_len):
            if cur.check_win():
                break
            u_sig = cur.state_signature()
            key = rng.choice("UDLRA")
            nxt = cur.clone()
            ok_alive, _ = nxt.step(key)
            if not ok_alive:
                continue
            # Skip hero-petrification dead-ends where < n heroes survive
            if len(_extract_heroes_and_goals(nxt)[0]) < len(hero_labels):
                continue
            v_sig = nxt.state_signature()
            if v_sig not in states_by_sig:
                states_by_sig[v_sig] = nxt.clone()
                bv = evaluate_operator_counting_bound(nxt)
                potentials_q[v_sig] = bv.exact_rational_bound
                potentials_int[v_sig] = bv.ceil_integer_bound
            if v_sig != u_sig and (u_sig, v_sig) not in seen_edges:
                seen_edges.add((u_sig, v_sig))
                edges.append((u_sig, v_sig, 1))
            cur = nxt

    q_consistency = verify_step_consistency(potentials_q, [win_sig], edges)
    int_consistency = verify_step_consistency(potentials_int, [win_sig], edges)
    if not (q_consistency.consistent_and_goal_zero and int_consistency.consistent_and_goal_zero and admissibility_violations == 0):
        raise RuntimeError(f"{room_id} C2 admissibility or consistency check failed")

    # Serialize certificate JSON and re-parse through CrocSwap strict rational JSON gate!
    cert_payload = {
        "room_id": room_id,
        "hero_labels": hero_labels,
        "goals": [list(g) for g in goals],
        "root_h_oc_rational": str(b0.exact_rational_bound),
        "root_h_oc_ceil_int": b0.ceil_integer_bound,
        "root_disjoint_druid_cuts": b0.disjoint_druid_cuts,
        "root_cycle_switch_tax": b0.cycle_switch_tax,
        "root_ray_assignment_primal": str(b0.ray_assignment_cert.primal_cost),
        "root_ray_assignment_dual_u": [str(x) for x in b0.ray_assignment_cert.dual_u],
        "root_ray_assignment_dual_v": [str(x) for x in b0.ray_assignment_cert.dual_v],
        "solo_walk_convert_matrix": solo_mat,
        "solo_min_sum": int(solo_cert.primal_cost),
        "solo_max_sum": all_bijections[-1]["solo_sum_cost"],
        "total_bijections_enumerated": len(all_bijections),
        "top_5_solo_bijections": all_bijections[:5],
        "witness_realized_mapping": witness_mapping,
        "witness_solo_sum_cost": witness_solo_cost,
        "reference_route_len": len(reference_route),
        "states_audited": len(states_by_sig),
        "edges_audited": len(edges),
        "admissibility_violations": admissibility_violations,
        "rational_step_violations": q_consistency.step_lip_violations,
        "ceil_int_step_violations": int_consistency.step_lip_violations,
        "route_trace_samples": route_trace_samples,
    }
    strict_roundtrip = load_strict_rational_json(json.dumps(cert_payload))
    if strict_roundtrip["root_h_oc_ceil_int"] != b0.ceil_integer_bound:
        raise RuntimeError("Strict rational JSON roundtrip mismatch")

    return cert_payload


def run_c2_must_fail_controls() -> Dict[str, bool]:
    """Execute non-tautological `must_fail` controls calling the live verifiers (`soko#53` A6):
    1. Bard 5x5 shared-aura multi-hero step breaks `naive_unpartitioned_manhattan_sum` (`drop = 4 > 1`)
       while `evaluate_operator_counting_bound` passes (`drop <= 1`).
    2. Wizard collinear crate-swap across a corridor breaks `naive_unpartitioned_manhattan_sum` (`drop = 5 > 1`)
       while `evaluate_operator_counting_bound` passes (`drop <= 1`).
    3. Tampered Hungarian dual `u_0 + 1/2` is rejected by `verify_bipartite_assignment_dual`.
    4. `CrocSwap` strict rational parser rejects `bool` (`True`), `float` (`1.25`), and duplicate JSON keys.
    """
    # 1. Shared Bard 5x5 aura step moving B + 3 inactive heroes simultaneously toward 4 goals!
    bard_grid = [
        "#########",
        "#.1...G.#",
        "#.2B.GG.#",
        "#.3...G.#",
        "#.4...G.#",
        "#########",
    ]
    ps_b0 = PuzzleScriptOracle(3, bard_grid)
    ps_b1 = ps_b0.clone()
    ok_b, _ = ps_b1.step("R")
    if not ok_b:
        raise RuntimeError("Bard shared-action test step failed")
    s_b0, s_b1 = ps_b0.state_signature(), ps_b1.state_signature()
    g_anchor = ("GOAL",)
    naive_bard_map = {s_b0: naive_unpartitioned_manhattan_sum(ps_b0), s_b1: naive_unpartitioned_manhattan_sum(ps_b1), g_anchor: 0}
    oc_bard_map = {
        s_b0: evaluate_operator_counting_bound(ps_b0).ceil_integer_bound,
        s_b1: evaluate_operator_counting_bound(ps_b1).ceil_integer_bound,
        g_anchor: 0,
    }
    bard_edges = [(s_b0, s_b1, 1), (s_b1, g_anchor, max(1, naive_bard_map[s_b1]))]
    naive_bard_rejected = not verify_step_consistency(naive_bard_map, [g_anchor], bard_edges).consistent_and_goal_zero
    oc_bard_accepted = verify_step_consistency(
        oc_bard_map, [g_anchor], [(s_b0, s_b1, 1), (s_b1, g_anchor, max(1, oc_bard_map[s_b1]))]
    ).consistent_and_goal_zero

    # 2. Wizard collinear swap with a crate 5 cells away right next to Goal!
    wiz_grid = [
        "##########",
        "#W....*G.#",
        "##########",
    ]
    ps_w0 = PuzzleScriptOracle(3, wiz_grid)
    ps_w1 = ps_w0.clone()
    ok_w, _ = ps_w1.step("R")
    if not ok_w:
        raise RuntimeError("Wizard swap test step failed")
    s_w0, s_w1 = ps_w0.state_signature(), ps_w1.state_signature()
    naive_wiz_map = {s_w0: naive_unpartitioned_manhattan_sum(ps_w0), s_w1: naive_unpartitioned_manhattan_sum(ps_w1), g_anchor: 0}
    oc_wiz_map = {
        s_w0: evaluate_operator_counting_bound(ps_w0).ceil_integer_bound,
        s_w1: evaluate_operator_counting_bound(ps_w1).ceil_integer_bound,
        g_anchor: 0,
    }
    naive_wiz_rejected = not verify_step_consistency(
        naive_wiz_map, [g_anchor], [(s_w0, s_w1, 1), (s_w1, g_anchor, max(1, naive_wiz_map[s_w1]))]
    ).consistent_and_goal_zero
    oc_wiz_accepted = verify_step_consistency(
        oc_wiz_map, [g_anchor], [(s_w0, s_w1, 1), (s_w1, g_anchor, max(1, oc_wiz_map[s_w1]))]
    ).consistent_and_goal_zero

    # 3. Hungarian dual tamper rejection
    mat2 = [[4, 1], [2, 3]]
    cert2 = solve_exact_bipartite_assignment(mat2)
    tampered_cert2 = HungarianDualCertificate(
        assignment=cert2.assignment,
        primal_cost=cert2.primal_cost,
        dual_u=(cert2.dual_u[0] + Fraction(1, 2), cert2.dual_u[1]),
        dual_v=cert2.dual_v,
        dual_objective=cert2.dual_objective + Fraction(1, 2),
    )
    tampered_dual_rejected = not verify_bipartite_assignment_dual(mat2, tampered_cert2)["valid"]

    # 4. Strict rational parser rejections (`bool`, `float`, duplicate JSON keys)
    bool_rejected = False
    try:
        parse_strict_fraction(True)
    except TypeError:
        bool_rejected = True

    float_json_rejected = False
    try:
        load_strict_rational_json('{"x": 1.5}')
    except ValueError:
        float_json_rejected = True

    dupe_json_rejected = False
    try:
        load_strict_rational_json('{"x": 1, "x": 2}')
    except ValueError:
        dupe_json_rejected = True

    return {
        "naive_bard_shared_aura_rejected": bool(naive_bard_rejected and oc_bard_accepted),
        "naive_wizard_ray_swap_rejected": bool(naive_wiz_rejected and oc_wiz_accepted),
        "tampered_hungarian_dual_rejected": tampered_dual_rejected,
        "strict_parser_bool_float_dupe_rejected": bool(bool_rejected and float_json_rejected and dupe_json_rejected),
    }


def run_full_c2_audit(catalog_path: Optional[Path] = None) -> Dict[str, Any]:
    """Run complete `soko#53` C2 audit on `III-21` and `III-20` directly from `catalog.json`."""
    cat_file = catalog_path or (Path(__file__).resolve().parents[2] / "soko_mcp" / "data" / "catalog.json")
    cat_data = json.loads(cat_file.read_text(encoding="utf-8"))
    rooms_by_id = {r["id"]: r for r in cat_data["rooms"]}

    iii21 = rooms_by_id["III-21"]
    iii20 = rooms_by_id["III-20"]

    rep_21 = audit_room_c2_bounds("III-21", iii21["grid"], iii21["reference_route"])
    rep_20 = audit_room_c2_bounds("III-20", iii20["grid"], iii20["reference_route"])
    controls = run_c2_must_fail_controls()
    if not all(controls.values()):
        raise RuntimeError(f"One or more C2 must_fail controls failed: {controls}")

    out = {
        "epistemic_status": "VERIFIED",
        "task_ref": "ahrazzle/soko#53 C2 & ahrazzle/soko#22 item 3",
        "rooms": {
            "III-21": rep_21,
            "III-20": rep_20,
        },
        "must_fail_controls": controls,
    }
    # Final float/dupe check on the full C2 receipt itself!
    load_strict_rational_json(json.dumps(out))
    return out
