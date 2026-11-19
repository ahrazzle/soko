"""Exact integer & rational (`Fraction`) 1-step consistency repairs and Farkas dual verifiers (`soko#38`).

Implements and verifies both `soko#38` consistency repairs with zero `float` arithmetic:
1. Closed-form Pre-Funded Transmutation Potential (`h_hat(s) = max(0, h_raw(s) - sum_k c_k * r_k(s))`).
2. Pointwise-Maximal Quotient 1-Lipschitz LP Projector (`max sum_u h_tilde(u)` subject to
   `0 <= h_tilde(u) <= h_raw(u)`, `h_tilde(g) = 0`, and `h_tilde(u) - h_tilde(v) <= cost(u, v)`),
   emitting an explicit Farkas dual witness chain for every quotient vertex `u` and verifying strong
   primal-dual equality (`sum_u h_tilde(u) == sum_u dual_chain_cost(u)`) in exact `Fraction` arithmetic.
3. Concrete reproduction of the exact `soko#38` 15x7 `III-14` board state where Druid at `(0, 3)`
   pressing `'R'` transmutes the wall at `(1, 3)` into a crate (`h_raw: 12 -> 10`, drop `2 > 1`),
   confirming the un-repaired potential fails `verify_step_consistency` (`must_fail`) while both
   repaired potentials pass with `0` violations.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import heapq
from typing import Any, Callable, Dict, Hashable, Iterable, List, Mapping, Optional, Sequence, Tuple, TypeVar

from soko_mcp.flat_oracle import FlatBitmaskOracle, replay_flat_oracle
from soko_mcp.oracle import FRONTIER_ROOMS, PuzzleScriptOracle, replay_oracle

V = TypeVar("V", bound=Hashable)

# Verbatim counterexample board state from ahrazzle/soko#38 (before Druid at (0,3) presses 'R'):
# Legend in soko#38: '#' wall, '*' crate, '}' uncovered switch, '$' crate-on-switch, 'B' Bard, 'D' Druid,
# with closed purple doors ']' at PDOOR_MASK and goals 'G' at (9,3), (11,3) on canonical 15x7 III-14.
SOKO38_BEFORE_DYNAMIC_ROWS: Tuple[str, ...] = (
    "#####.#########",
    "#.............#",
    "**#*}}}]]]]]].#",  # adjusted in constructor below from canonical 15x7 floor
)


def build_soko38_counterexample_state() -> Tuple[PuzzleScriptOracle, FlatBitmaskOracle, List[str]]:
    """Construct the exact `soko#38` 15x7 board state in both `PuzzleScriptOracle` and `FlatBitmaskOracle`.

    In `soko#38`:
      row 0: #####.#########
      row 1: #.............#
      row 2: **#*}}}.......#   (plus closed purple doors ]]]]] at x=8..12)
      row 3: D#*B$}}.......#   ($ at (4,3) is crate on switch, ]G.G] at x=8..12, active Druid at (0,3), inactive SBard '5' at (3,3))
      row 4: ...*$}$#......#   ($ at (4,4) and (6,4) are crates on switches, # at (7,4), ]]]]] at x=8..12)
      row 5: ..............#
      row 6: #......########
    Note: Druid is active ('D' at (0,3)), Bard is inactive ('5' at (3,3)).
    """
    base_grid = FRONTIER_ROOMS["III-14-15x7"]["grid"]
    ps = PuzzleScriptOracle(3, base_grid)

    # Clear all dynamic walls/crates/heroes first while preserving static floor ('G', '}')
    for y in range(ps.h):
        for x in range(ps.w):
            ps.obj[y][x] = None
    ps.notes.clear()

    soko38_overlay = [
        "#####.#########",
        "#.............#",
        "**#*}}}.......#",
        "D#*5*}}.......#",
        "...**}*#......#",
        "..............#",
        "#......########",
    ]
    # Restore closed purple doors ']' from base_grid (since only 3 of 9 switches are weighed, doors are closed)
    grid_rows: List[str] = []
    for y in range(7):
        row_chars: List[str] = []
        for x in range(15):
            ch = soko38_overlay[y][x]
            fch = base_grid[y][x]
            if ch in ("#", "*", "D", "5"):
                ps.obj[y][x] = ch
                row_chars.append(ch)
            elif fch == "]":
                ps.obj[y][x] = "]"
                row_chars.append("]")
            elif fch in ("G", "}"):
                row_chars.append(fch)
            else:
                row_chars.append(".")
        grid_rows.append("".join(row_chars))

    # Re-instantiate both independent oracles directly from the reconstructed 15x7 ASCII grid!
    ps_clean = PuzzleScriptOracle(3, grid_rows)
    flat_clean = FlatBitmaskOracle(3, grid_rows)
    return ps_clean, flat_clean, grid_rows


_TX9 = (4, 4, 4, 5, 5, 5, 6, 6, 6)
_TY9 = (2, 2, 2, 3, 3, 3, 4, 4, 4)


def legacy_unrepaired_soko38_bound(ps: PuzzleScriptOracle) -> int:
    """Exact reproduction of the un-repaired `1ce70ca` window/harvest bound (`ahrazzle/soko#38`).

    In the un-repaired formula, `sw_keys = (2 if ah == 5 else 1) if c > 0 else 0` omitted the `'A'`
    switch charge at `c == 0` when `uncov_sw > 0` and Druid is still active (`ah == 6`). Consequently,
    when Druid at `(0, 3)` presses `'R'` to transmute the interior `#` wall at `(1, 3)` into the 9th
    `*` crate (`c: 1 -> 0`), BOTH `c` (`1 -> 0`) and `sw_keys` (`1 -> 0`) drop on the same key,
    lowering `h` from `12` to `10` (`drop = 2 > 1`).
    """
    if ps.check_win():
        return 0
    xs: List[int] = []
    ys: List[int] = []
    bx = by = dx = dy = 0
    ah = 5
    found_b = False
    found_d = False
    for y in range(ps.h):
        for x in range(ps.w):
            o = ps.obj[y][x]
            is_sw = ps.floor[y][x] == "}"
            if o == "*" or (o == "#" and is_sw):
                xs.append(x)
                ys.append(y)
            if o in ("B", "5"):
                bx, by = x, y
                found_b = True
                if o == "B":
                    ah = 5
            elif o in ("D", "6"):
                dx, dy = x, y
                found_d = True
                if o == "D":
                    ah = 6
    if not (found_b and found_d):
        return 999
    if 9 <= bx <= 11 and by == 3 and 9 <= dx <= 11 and dy == 3:
        return 0
    xs.sort()
    ys.sort()
    k = len(xs)
    best_c = 999
    for c in range(max(0, 9 - k), 10):
        use_old = 9 - c
        # Exact un-repaired bug: else-branch is 0 instead of charging 1 when uncov_sw > 0 and ah == 6!
        sw_keys = (2 if ah == 5 else 1) if c > 0 else 0
        req_r = req_l = req_d = req_u = 0
        min_cbx, max_cbx, min_cby, max_cby = 99, -99, 99, -99
        for j in range(use_old):
            rx = _TX9[j] - xs[k - use_old + j]
            if rx > 0:
                req_r = max(req_r, rx)
                min_cbx = min(min_cbx, xs[k - use_old + j] + 2)
            lx = xs[j] - _TX9[9 - use_old + j]
            if lx > 0:
                req_l = max(req_l, lx)
                max_cbx = max(max_cbx, xs[j] - 2)
            dv = _TY9[j] - ys[k - use_old + j]
            if dv > 0:
                req_d = max(req_d, dv)
                min_cby = min(min_cby, ys[k - use_old + j] + 2)
            uv = ys[j] - _TY9[9 - use_old + j]
            if uv > 0:
                req_u = max(req_u, uv)
                max_cby = max(max_cby, ys[j] - 2)
        if min_cbx < 99 and bx > min_cbx:
            req_l = max(req_l, bx - min_cbx)
        if max_cbx > -99 and bx < max_cbx:
            req_r = max(req_r, max_cbx - bx)
        if min_cby < 99 and by > min_cby:
            req_u = max(req_u, by - min_cby)
        if max_cby > -99 and by < max_cby:
            req_d = max(req_d, max_cby - by)
        for sg in range(2):
            gx_b = 9 if sg == 0 else 11
            gx_d = 11 if sg == 0 else 9
            dbx, ddx, dby, ddy = gx_b - bx, gx_d - dx, 3 - by, 3 - dy
            h_mx = (abs(dbx) + abs(ddx) + abs(dbx - ddx)) >> 1
            h_my = (abs(dby) + abs(ddy) + abs(dby - ddy)) >> 1
            b_mx = max(req_r + req_l, 2 * req_l + dbx, 2 * req_r - dbx, h_mx)
            b_my = max(req_d + req_u, 2 * req_u + dby, 2 * req_d - dby, h_my)
            move_sum = b_mx + b_my
            if c > 0:
                opt_lr = max(4 + req_l, 2 * req_l + dbx, 8 - dbx, b_mx) + b_my
                opt_ud1 = b_mx + max(2 + req_u, 2 * req_u + dby, 4 - dby, b_my)
                opt_ud2 = b_mx + max(req_d + 2, 4 + dby, 2 * req_d - dby, b_my)
                move_sum = min(opt_lr, opt_ud1, opt_ud2)
            best_c = min(best_c, c + sw_keys + move_sum)
    return best_c


def prefunded_transmutation_potential(
    h_raw_val: int,
    charges: Sequence[Tuple[int, int]],
) -> int:
    """Closed-form `soko#38` Pre-Funded Transmutation Potential:
    `h_hat(s) = max(0, h_raw(s) - sum_k c_k * r_k(s))` in exact `int` arithmetic.
    """
    deduction = 0
    for coeff_c, rem_r in charges:
        if coeff_c < 0 or rem_r < 0:
            raise ValueError("Pre-funded charge coefficients and counts must be non-negative integers")
        deduction += int(coeff_c) * int(rem_r)
    return max(0, int(h_raw_val) - deduction)


@dataclass(frozen=True)
class StepConsistencyAudit:
    vertices_checked: int
    goals_checked: int
    edges_checked: int
    goal_zero_violations: int
    negative_value_violations: int
    step_lip_violations: int
    max_excess_over_cost: Fraction
    worst_edge: Optional[Tuple[Any, Any, Fraction, Fraction, Fraction]]
    consistent_and_goal_zero: bool


def verify_step_consistency(
    potential: Mapping[V, int | Fraction],
    goals: Iterable[V],
    edges: Iterable[Tuple[V, V, int | Fraction]],
) -> StepConsistencyAudit:
    """Independent O(|V| + |E|) exact rational (`Fraction`) verifier for:
      1) `potential[v] >= 0` for all `v`,
      2) `potential[g] == 0` for all `g in goals`,
      3) `potential[u] - potential[v] <= cost(u, v)` for every directed edge `(u, v, cost)`.
    """
    neg_viols = 0
    for val in potential.values():
        if Fraction(val) < 0:
            neg_viols += 1

    goal_list = list(goals)
    goal_viols = 0
    for g in goal_list:
        if g not in potential or Fraction(potential[g]) != 0:
            goal_viols += 1

    edge_cnt = 0
    lip_viols = 0
    max_excess = Fraction(0)
    worst: Optional[Tuple[Any, Any, Fraction, Fraction, Fraction]] = None
    for u, v, raw_cost in edges:
        edge_cnt += 1
        c = Fraction(raw_cost)
        if c < 0:
            raise ValueError(f"Negative edge cost {c} on ({u!r}, {v!r})")
        hu = Fraction(potential[u])
        hv = Fraction(potential[v])
        excess = (hu - hv) - c
        if excess > max_excess:
            max_excess = excess
        if excess > 0:
            lip_viols += 1
            if worst is None or excess > (worst[2] - worst[3] - worst[4]):
                worst = (u, v, hu, hv, c)

    ok = neg_viols == 0 and goal_viols == 0 and lip_viols == 0
    return StepConsistencyAudit(
        vertices_checked=len(potential),
        goals_checked=len(goal_list),
        edges_checked=edge_cnt,
        goal_zero_violations=goal_viols,
        negative_value_violations=neg_viols,
        step_lip_violations=lip_viols,
        max_excess_over_cost=max_excess,
        worst_edge=worst,
        consistent_and_goal_zero=ok,
    )


@dataclass(frozen=True)
class QuotientLipschitzLPResult:
    projected_h: Dict[Any, Fraction]
    farkas_witness_chains: Dict[Any, Tuple[Tuple[Any, ...], str, Fraction]]
    primal_objective_sum: Fraction
    dual_objective_sum: Fraction
    strong_duality_exact: bool
    consistency_audit: StepConsistencyAudit


def project_quotient_1lipschitz_lp(
    vertices: Sequence[V],
    goals: Iterable[V],
    edges: Sequence[Tuple[V, V, int | Fraction]],
    h_raw: Mapping[V, int | Fraction],
) -> QuotientLipschitzLPResult:
    """Solve the exact difference-constraint LP (`soko#38` comment 1, zero `float`):
        maximize   sum_{u in V_Q} h_tilde(u)
        subject to 0 <= h_tilde(u) <= h_raw(u)           for all u in V_Q,
                   h_tilde(g) = 0                        for all g in G_Q,
                   h_tilde(u) - h_tilde(v) <= cost(u, v) for all (u, v, cost) in E_Q.

    By Bellman's shortest-path duality theorem, the unique componentwise-maximal feasible vector
    `h_tilde*(u)` equals the shortest-path distance from `u` to a super-sink `SINK` along forward edges
    `(u -> v)` of weight `cost(u, v)` and terminal caps `(w -> SINK)` of weight `0` (if `w in G_Q`) or
    `max(0, h_raw(w))` (otherwise). Each shortest path `u = u_0 -> ... -> u_k -> SINK` is an explicit
    Farkas dual certificate proving `h_tilde(u) <= sum_{i=0}^{k-1} cost(u_i, u_{i+1}) + cap(u_k)`!
    """
    goal_set = set(goals)
    v_index: Dict[V, int] = {v: idx for idx, v in enumerate(vertices)}
    rev_adj: Dict[V, List[Tuple[V, Fraction]]] = {v: [] for v in vertices}

    for u, v, raw_c in edges:
        c = Fraction(raw_c)
        if c < 0:
            raise ValueError(f"Edge cost must be >= 0, got {c}")
        if u in rev_adj and v in rev_adj:
            rev_adj[v].append((u, c))

    best: Dict[V, Fraction] = {}
    witness_next: Dict[V, Optional[Tuple[V, Fraction]]] = {}
    anchor_kind: Dict[V, Tuple[str, Fraction]] = {}

    # Deterministic priority queue keyed by (Fraction distance, integer vertex order)
    pq: List[Tuple[Fraction, int, V]] = []
    for idx, v in enumerate(vertices):
        raw_cap = Fraction(0) if v in goal_set else Fraction(h_raw[v])
        if raw_cap < 0:
            raise ValueError(f"h_raw[{v!r}] = {raw_cap} < 0 makes 0 <= h_tilde(u) <= h_raw(u) infeasible")
        best[v] = raw_cap
        witness_next[v] = None
        anchor_kind[v] = ("goal_zero" if v in goal_set else "raw_cap", raw_cap)
        heapq.heappush(pq, (raw_cap, idx, v))

    while pq:
        d_v, _, v = heapq.heappop(pq)
        if d_v != best[v]:
            continue
        for u, c_uv in rev_adj[v]:
            cand = d_v + c_uv
            if cand < best[u]:
                best[u] = cand
                witness_next[u] = (v, c_uv)
                heapq.heappush(pq, (cand, v_index[u], u))

    chains: Dict[Any, Tuple[Tuple[Any, ...], str, Fraction]] = {}
    dual_sum = Fraction(0)
    for v in vertices:
        path = [v]
        edge_cost_sum = Fraction(0)
        cur = v
        steps = 0
        while witness_next[cur] is not None:
            nxt, c_step = witness_next[cur]  # type: ignore[misc]
            edge_cost_sum += c_step
            path.append(nxt)
            cur = nxt
            steps += 1
            if steps > len(vertices):
                raise RuntimeError("Cycle detected in Farkas witness reconstruction")
        kind, terminal_cap = anchor_kind[cur]
        total_bound = edge_cost_sum + terminal_cap
        chains[v] = (tuple(path), kind, total_bound)
        dual_sum += total_bound

    primal_sum = sum((best[v] for v in vertices), Fraction(0))
    audit = verify_step_consistency(best, goal_set, edges)
    return QuotientLipschitzLPResult(
        projected_h=dict(best),
        farkas_witness_chains=chains,
        primal_objective_sum=primal_sum,
        dual_objective_sum=dual_sum,
        strong_duality_exact=(primal_sum == dual_sum and audit.consistent_and_goal_zero),
        consistency_audit=audit,
    )


def verify_projected_lp_certificate(
    vertices: Sequence[V],
    goals: Iterable[V],
    edges: Sequence[Tuple[V, V, int | Fraction]],
    h_raw: Mapping[V, int | Fraction],
    lp_res: QuotientLipschitzLPResult,
) -> Dict[str, Any]:
    """Independent second checker for `QuotientLipschitzLPResult`:
    1) Verifies primal feasibility (`0 <= h_tilde(u) <= h_raw(u)`, `h_tilde(g) == 0`, `h_tilde(u) - h_tilde(v) <= c(u,v)`).
    2) Verifies every Farkas witness chain `u_0 -> ... -> u_k` uses genuine edges in `edges`, terminates at a valid
       `goal_zero` or `raw_cap` bound, and proves `h_tilde(u_0) == sum_i c(u_i, u_{i+1}) + cap(u_k)` (hence NO feasible
       1-Lipschitz potential can exceed `lp_res.projected_h[u_0]` at ANY vertex!).
    """
    goal_set = set(goals)
    min_edge_cost: Dict[Tuple[V, V], Fraction] = {}
    for u, v, raw_c in edges:
        c = Fraction(raw_c)
        key = (u, v)
        if key not in min_edge_cost or c < min_edge_cost[key]:
            min_edge_cost[key] = c

    audit = verify_step_consistency(lp_res.projected_h, goal_set, edges)
    if not audit.consistent_and_goal_zero:
        return {"valid": False, "reason": "primal_step_consistency_or_goal_failed"}

    for v in vertices:
        hv = Fraction(lp_res.projected_h[v])
        if hv > Fraction(h_raw[v]):
            return {"valid": False, "reason": f"exceeds_h_raw_at_{v!r}"}
        if v not in lp_res.farkas_witness_chains:
            return {"valid": False, "reason": f"missing_farkas_chain_at_{v!r}"}
        chain, kind, reported_bound = lp_res.farkas_witness_chains[v]
        if not chain or chain[0] != v:
            return {"valid": False, "reason": f"invalid_chain_start_at_{v!r}"}
        acc = Fraction(0)
        for i in range(len(chain) - 1):
            ek = (chain[i], chain[i + 1])
            if ek not in min_edge_cost:
                return {"valid": False, "reason": f"nonexistent_witness_edge_{ek!r}"}
            acc += min_edge_cost[ek]
        end_v = chain[-1]
        if kind == "goal_zero":
            if end_v not in goal_set:
                return {"valid": False, "reason": f"forged_goal_anchor_{end_v!r}"}
            term = Fraction(0)
        elif kind == "raw_cap":
            term = Fraction(h_raw[end_v])
        else:
            return {"valid": False, "reason": f"unknown_anchor_kind_{kind!r}"}
        verified_bound = acc + term
        if verified_bound != reported_bound or hv != verified_bound:
            return {"valid": False, "reason": f"duality_gap_at_{v!r}_{hv}_vs_{verified_bound}"}

    primal_sum = sum((Fraction(lp_res.projected_h[v]) for v in vertices), Fraction(0))
    if primal_sum != lp_res.primal_objective_sum or primal_sum != lp_res.dual_objective_sum:
        return {"valid": False, "reason": "objective_sum_mismatch"}

    return {
        "valid": True,
        "reason": "ok",
        "vertices_verified": len(vertices),
        "edges_verified": audit.edges_checked,
        "primal_sum": str(primal_sum),
    }


def run_soko38_repair_audit() -> Dict[str, Any]:
    """End-to-end verification of the `ahrazzle/soko#38` counterexample and both repairs,
    including non-tautological `must_fail` controls calling the live verifiers.
    """
    ps_before, flat_before, grid_before = build_soko38_counterexample_state()
    ps_after = ps_before.clone()
    alive_ps, won_ps = ps_after.step("R")
    alive_fl, won_fl = flat_before.step("R")
    if not (alive_ps and alive_fl and not won_ps and not won_fl):
        raise RuntimeError("soko#38 action 'R' failed to execute cleanly in dual oracles")
    if ps_before.obj[3][0] != "D" or ps_before.obj[3][1] != "#":
        raise RuntimeError("soko#38 before-state mismatch at (0,3)/(1,3)")
    if ps_after.obj[3][0] != "D" or ps_after.obj[3][1] != "*":
        raise RuntimeError("soko#38 after-state mismatch: expected (1,3) '#' -> '*'")
    if replay_oracle(3, grid_before, "R")["traj_fnv64"] != replay_flat_oracle(3, grid_before, "R")["traj_fnv64"]:
        raise RuntimeError("Dual-oracle frame digest mismatch on soko#38 transition")

    h_raw_before = legacy_unrepaired_soko38_bound(ps_before)
    h_raw_after = legacy_unrepaired_soko38_bound(ps_after)
    if h_raw_before != 12 or h_raw_after != 10:
        raise RuntimeError(f"Expected soko#38 raw drop 12 -> 10, got {h_raw_before} -> {h_raw_after}")

    # Build local reachable neighborhood from soko#38 before-state (BFS ball of depth 4 = ~200 states) + goal anchor
    state_by_sig: Dict[Any, PuzzleScriptOracle] = {}
    sig_before = ps_before.state_signature()
    sig_after = ps_after.state_signature()
    state_by_sig[sig_before] = ps_before
    frontier = [ps_before]
    edges_raw: List[Tuple[Any, Any, int]] = []
    seen_edges = set()

    for _depth in range(4):
        nxt_frontier: List[PuzzleScriptOracle] = []
        for cur in frontier:
            u_sig = cur.state_signature()
            for key in ("U", "D", "L", "R", "A"):
                cp = cur.clone()
                ok_alive, _ = cp.step(key)
                if not ok_alive:
                    continue
                # Exclude dead-end hero-petrification (< 2 heroes remaining, rejected in step_concrete)
                if sum(1 for row in cp.obj for o in row if o in ("B", "5", "D", "6")) < 2:
                    continue
                v_sig = cp.state_signature()
                if v_sig == u_sig:
                    continue
                if v_sig not in state_by_sig:
                    state_by_sig[v_sig] = cp
                    nxt_frontier.append(cp)
                if (u_sig, v_sig) not in seen_edges:
                    seen_edges.add((u_sig, v_sig))
                    edges_raw.append((u_sig, v_sig, 1))
        frontier = nxt_frontier

    # Add synthetic goal anchor connected from every leaf by exact admissible upper bound so goal=0 is tested
    goal_sig = ("GOAL_ANCHOR",)
    vertices: List[Any] = list(state_by_sig.keys()) + [goal_sig]
    raw_map: Dict[Any, int] = {
        sig: legacy_unrepaired_soko38_bound(st) for sig, st in state_by_sig.items()
    }
    raw_map[goal_sig] = 0
    for sig, st in state_by_sig.items():
        # Connect states with cost = max(1, raw_map[sig]) to goal anchor so raw_map is admissible on this graph
        edges_raw.append((sig, goal_sig, max(1, raw_map[sig])))

    # 1. Non-tautological `must_fail` control 1: un-repaired raw heuristic MUST be rejected by `verify_step_consistency`!
    unrepaired_audit = verify_step_consistency(raw_map, [goal_sig], edges_raw)
    must_fail_unrepaired_caught = (
        not unrepaired_audit.consistent_and_goal_zero
        and unrepaired_audit.step_lip_violations >= 1
        and unrepaired_audit.max_excess_over_cost == Fraction(1)
    )

    # 2. Repair 1: Pre-Funded Transmutation Potential `h_hat(s) = max(0, h_raw(s) - 1 * r_D(s))`
    # Here `r_D(s) = max(0, 9 - k_pool(s))` (monotone transmutation deficit relative to 9 switch objects,
    # plus 1 when Bard is active and `k_pool(s) < 9` so `'A'` switch into Druid does not drop `h_raw` by > 1):
    # wait: check exact pre-funded charge: on `k_pool < 9`, `sw_keys` adds `1` (if Druid active) or `2` (if Bard active)
    # that vanishes abruptly when `k_pool` hits `9`! Pre-funding `r_sw(s) = (2 if ah==5 else 1) if k_pool < 9 else 0`
    # subtracts the unfunded cliff (`r_sw(before) = 1 -> r_sw(after) = 0`), turning `12 -> 10` into `11 -> 10`!
    prefunded_map: Dict[Any, int] = {goal_sig: 0}
    for sig, st in state_by_sig.items():
        k_pool = sum(
            1
            for y in range(st.h)
            for x in range(st.w)
            if st.obj[y][x] == "*" or (st.obj[y][x] == "#" and st.floor[y][x] == "}")
        )
        is_bard_active = any(st.obj[y][x] == "B" for y in range(st.h) for x in range(st.w))
        r_sw = (2 if is_bard_active else 1) if k_pool < 9 else 0
        prefunded_map[sig] = prefunded_transmutation_potential(raw_map[sig], [(1, r_sw)])

    prefunded_audit = verify_step_consistency(prefunded_map, [goal_sig], edges_raw)

    # 3. Repair 2: Pointwise-Maximal Quotient 1-Lipschitz LP Projection + Dual Farkas Chain Verification
    lp_res = project_quotient_1lipschitz_lp(vertices, [goal_sig], edges_raw, raw_map)
    second_check = verify_projected_lp_certificate(vertices, [goal_sig], edges_raw, raw_map, lp_res)

    # 4. Non-tautological `must_fail` controls 2 & 3 on `verify_projected_lp_certificate`:
    #    Control 2: Inflate `projected_h[sig_before]` from `11` back to `12` -> MUST be rejected!
    inflated_h = dict(lp_res.projected_h)
    inflated_h[sig_before] = Fraction(12)
    tampered_lp_inflated = QuotientLipschitzLPResult(
        projected_h=inflated_h,
        farkas_witness_chains=lp_res.farkas_witness_chains,
        primal_objective_sum=lp_res.primal_objective_sum + Fraction(1),
        dual_objective_sum=lp_res.dual_objective_sum,
        strong_duality_exact=True,
        consistency_audit=lp_res.consistency_audit,
    )
    must_fail_inflated_rejected = not verify_projected_lp_certificate(
        vertices, [goal_sig], edges_raw, raw_map, tampered_lp_inflated
    )["valid"]

    #    Control 3: Forge Farkas witness chain on `sig_before` to claim raw_cap without walking edge -> MUST be rejected!
    forged_chains = dict(lp_res.farkas_witness_chains)
    forged_chains[sig_before] = ((sig_before,), "raw_cap", Fraction(11))
    tampered_lp_forged_dual = QuotientLipschitzLPResult(
        projected_h=lp_res.projected_h,
        farkas_witness_chains=forged_chains,
        primal_objective_sum=lp_res.primal_objective_sum,
        dual_objective_sum=lp_res.dual_objective_sum,
        strong_duality_exact=True,
        consistency_audit=lp_res.consistency_audit,
    )
    must_fail_forged_dual_rejected = not verify_projected_lp_certificate(
        vertices, [goal_sig], edges_raw, raw_map, tampered_lp_forged_dual
    )["valid"]

    #    Control 4: Planted non-zero goal `h(goal) = 1` -> MUST be rejected by `verify_step_consistency`!
    nonzero_goal_map = dict(prefunded_map)
    nonzero_goal_map[goal_sig] = 1
    must_fail_nonzero_goal_rejected = not verify_step_consistency(
        nonzero_goal_map, [goal_sig], edges_raw
    ).consistent_and_goal_zero

    all_passed = (
        must_fail_unrepaired_caught
        and prefunded_audit.consistent_and_goal_zero
        and prefunded_map[sig_before] == 11
        and prefunded_map[sig_after] == 10
        and lp_res.strong_duality_exact
        and lp_res.projected_h[sig_before] == Fraction(11)
        and lp_res.projected_h[sig_after] == Fraction(10)
        and second_check["valid"]
        and must_fail_inflated_rejected
        and must_fail_forged_dual_rejected
        and must_fail_nonzero_goal_rejected
    )
    if not all_passed:
        raise RuntimeError("soko#38 consistency repair audit failed one or more verification gates")

    return {
        "epistemic_status": "VERIFIED",
        "issue_ref": "ahrazzle/soko#38",
        "counterexample_board_rows": grid_before,
        "transition_tested": {"active_hero": "D", "from": [0, 3], "action": "R", "transmuted_cell": [1, 3], "change": "# -> *"},
        "raw_unrepaired": {
            "h_before": h_raw_before,
            "h_after": h_raw_after,
            "drop": h_raw_before - h_raw_after,
            "violations_in_ball": unrepaired_audit.step_lip_violations,
        },
        "prefunded_potential_repair": {
            "h_before": prefunded_map[sig_before],
            "h_after": prefunded_map[sig_after],
            "drop": prefunded_map[sig_before] - prefunded_map[sig_after],
            "vertices_checked": prefunded_audit.vertices_checked,
            "edges_checked": prefunded_audit.edges_checked,
            "violations": prefunded_audit.step_lip_violations,
        },
        "quotient_1lipschitz_lp_repair": {
            "h_before": str(lp_res.projected_h[sig_before]),
            "h_after": str(lp_res.projected_h[sig_after]),
            "primal_objective_sum": str(lp_res.primal_objective_sum),
            "dual_objective_sum": str(lp_res.dual_objective_sum),
            "strong_duality_exact": lp_res.strong_duality_exact,
            "second_checker_valid": second_check["valid"],
            "witness_chain_len_at_counterexample": len(lp_res.farkas_witness_chains[sig_before][0]),
        },
        "must_fail_controls": {
            "unrepaired_soko38_drop2_rejected": must_fail_unrepaired_caught,
            "inflated_primal_12_rejected": must_fail_inflated_rejected,
            "forged_farkas_witness_rejected": must_fail_forged_dual_rejected,
            "nonzero_goal_potential_rejected": must_fail_nonzero_goal_rejected,
        },
    }
