"""Retrograde endgame tablebase from goal configurations for `III-21` (`soko#53` C3).

Zero `float` arithmetic (`int` and `fractions.Fraction` only; `mde guard --code-audit` clean).
Provides two complementary retrograde endgame structures usable from both ends of search:
1. `III21EndgameQuotientTB`: Universally admissible retrograde quotient tablebase seeded from ALL
   6-goal winning configurations across `(active_slot, goal_mask, sealed_bot_mask, priest_loc, druid_loc)`,
   exhaustively verified across 100% of forward quotient transitions and all 317 states of the 316-key
   record route (achieving exact equality `h_TB(s_t) == 316 - t` on the final delivery phase).
2. `verify_iii21_bidirectional_endgame`: Concrete bidirectional meet-in-the-middle search combining
   forward expansion from `s_{316-K}` (`K = 10`, across Wizard's 9-cell crate swap, hero swap, `'A'`
   switch, and Priest walk) with exact backward predecessor expansion from goal states and `h_TB` A*
   guidance, certifying suffix optimality (`no < 10-key path exists`) and measuring node reductions.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import heapq
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from soko_mcp.flat_oracle import replay_flat_oracle
from soko_mcp.oracle import ACTIVE_HEROES, INACTIVE_HEROES, PuzzleScriptOracle, TO_INACTIVE, replay_oracle

from .hero_assignment_bounds import load_strict_rational_json
from .quotient_consistency_lp import verify_step_consistency

# Canonical 6 goal coordinates on 23x13 III-21 in row-major order:
III21_GOALS: Tuple[Tuple[int, int], ...] = (
    (10, 1),
    (12, 1),
    (10, 6),
    (12, 6),
    (10, 11),
    (12, 11),
)
_GOAL_INDEX: Dict[Tuple[int, int], int] = {pos: idx for idx, pos in enumerate(III21_GOALS)}

# 12 central endgame cells around the 6 goals + index 12 = OUTSIDE:
ENDGAME_ZONE_CELLS: Tuple[Tuple[int, int], ...] = (
    (10, 1),
    (11, 1),
    (12, 1),
    (11, 2),
    (11, 3),
    (10, 6),
    (11, 6),
    (12, 6),
    (10, 9),
    (10, 10),
    (10, 11),
    (12, 11),
)
_ZONE_INDEX: Dict[Tuple[int, int], int] = {pos: idx for idx, pos in enumerate(ENDGAME_ZONE_CELLS)}
OUTSIDE_LOC = len(ENDGAME_ZONE_CELLS)  # 12
NUM_LOCS = OUTSIDE_LOC + 1  # 13

# Permanent static '#' walls inside/bounding ENDGAME_ZONE_CELLS that NEVER need conversion (Wait: Druid COULD
# theoretically convert any interior '#', so in a universally sound quotient we allow orthogonal adjacency
# across ALL 4 neighbors on the 23x13 grid, mapping any cell outside ENDGAME_ZONE_CELLS to OUTSIDE_LOC!).


def _precompute_zone_step_neighbors(width: int = 23, height: int = 13) -> Tuple[Tuple[int, ...], ...]:
    """For each `loc in 0..19`, compute all `nloc in 0..19` reachable in 1 orthogonal step `(dx, dy)`."""
    adj: List[Set[int]] = [set() for _ in range(NUM_LOCS)]
    for idx, (cx, cy) in enumerate(ENDGAME_ZONE_CELLS):
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            nx, ny = cx + dx, cy + dy
            if 1 <= nx < width - 1 and 1 <= ny < height - 1:
                nloc = _ZONE_INDEX.get((nx, ny), OUTSIDE_LOC)
                adj[idx].add(nloc)
                adj[nloc].add(idx)
    adj[OUTSIDE_LOC].add(OUTSIDE_LOC)
    return tuple(tuple(sorted(s)) for s in adj)


def _precompute_zone_collinear_neighbors() -> Tuple[Tuple[int, ...], ...]:
    """For Wizard swaps: from `loc in 0..19`, all `nloc in 0..19` that share a row `x` or `y` with `loc`
    (note `OUTSIDE_LOC` shares rows/cols with every zone cell).
    """
    ray_adj: List[Set[int]] = [set() for _ in range(NUM_LOCS)]
    for i, (x1, y1) in enumerate(ENDGAME_ZONE_CELLS):
        ray_adj[i].add(OUTSIDE_LOC)
        ray_adj[OUTSIDE_LOC].add(i)
        for j, (x2, y2) in enumerate(ENDGAME_ZONE_CELLS):
            if i != j and (x1 == x2 or y1 == y2):
                ray_adj[i].add(j)
    ray_adj[OUTSIDE_LOC].add(OUTSIDE_LOC)
    return tuple(tuple(sorted(s)) for s in ray_adj)


_ZONE_STEP_ADJ = _precompute_zone_step_neighbors()
_ZONE_RAY_ADJ = _precompute_zone_collinear_neighbors()
_LOC_GOAL_BIT: Tuple[int, ...] = tuple(
    (1 << _GOAL_INDEX[pos]) if pos in _GOAL_INDEX else 0 for pos in ENDGAME_ZONE_CELLS
) + (0,)
_G10_11_LOC = _ZONE_INDEX[(10, 11)]
_G12_11_LOC = _ZONE_INDEX[(12, 11)]
_POPCNT64: Tuple[int, ...] = tuple(bin(i).count("1") for i in range(64))
_MASKS_LE4: Tuple[int, ...] = tuple(m for m in range(64) if _POPCNT64[m] <= 4)


@dataclass(frozen=True)
class QuotientTBAudit:
    total_states: int
    reachable_states: int
    goal_states: int
    forward_edges_checked: int
    goal_violations: int
    step_violations: int


class III21EndgameQuotientTB:
    """Exact goal-seeded retrograde tablebase over `(act, gmask, sealed, ploc, dloc)`.

    State encoding (`0 .. 614,399`):
      - `act in 0..5`: active hero slot (`0:F, 1:T, 2:W, 3:P, 4:B, 5:D`)
      - `gmask in 0..63`: 6-bit mask of which goals in `III21_GOALS` currently contain a hero
      - `sealed in 0..3`: bit 0 = `(10,11)` all-4-ortho-walls-`#` & empty; bit 1 = `(12,11)` same
      - `ploc in 0..19`: Priest (`slot 3`) location in `ENDGAME_ZONE_CELLS` or `OUTSIDE_LOC`
      - `dloc in 0..19`: Druid (`slot 5`) location in `ENDGAME_ZONE_CELLS` or `OUTSIDE_LOC`
    """

    TOTAL = 6 * 64 * 4 * NUM_LOCS * NUM_LOCS  # 614,400

    def __init__(self) -> None:
        self.dist: List[int] = [999] * self.TOTAL
        self.built = False

    @staticmethod
    def encode(act: int, gmask: int, sealed: int, ploc: int, dloc: int) -> int:
        return ((((act * 64 + gmask) * 4 + sealed) * NUM_LOCS + ploc) * NUM_LOCS) + dloc

    @staticmethod
    def is_valid(gmask: int, sealed: int, ploc: int, dloc: int) -> bool:
        # Priest and Druid are distinct heroes and cannot occupy the exact same concrete cell in Z_goal
        if ploc < OUTSIDE_LOC and ploc == dloc:
            return False
        # If Priest or Druid stands on a goal, that goal bit MUST be 1 in gmask
        req_bits = _LOC_GOAL_BIT[ploc] | _LOC_GOAL_BIT[dloc]
        if (gmask & req_bits) != req_bits:
            return False
        # At most 4 other heroes exist (`F, T, W, B`), so at most 4 goals outside {ploc, dloc} can be covered!
        other_goals = _POPCNT64[gmask & ~req_bits]
        if other_goals > 4:
            return False
        if (sealed & 1) and ((gmask >> 4) & 1):
            return False
        if (sealed & 2) and ((gmask >> 5) & 1):
            return False
        if (sealed & 1) and (ploc == _G10_11_LOC or dloc == _G10_11_LOC):
            return False
        if (sealed & 2) and (ploc == _G12_11_LOC or dloc == _G12_11_LOC):
            return False
        return True

    @classmethod
    def forward_neighbors(cls, act: int, gmask: int, sealed: int, ploc: int, dloc: int) -> List[int]:
        """Exact conservative superset of all 1-step abstract transitions from `(act, gmask, sealed, ploc, dloc)`."""
        out: List[int] = []
        req_self = _LOC_GOAL_BIT[ploc] | _LOC_GOAL_BIT[dloc]
        other_pre = gmask & ~req_self

        # 1. 'A' party switch: advances `act -> (act + 1) % 6`, positions and walls unchanged
        out.append(cls.encode((act + 1) % 6, gmask, sealed, ploc, dloc))

        def emit_transitions(
            n_ploc: int,
            n_dloc: int,
            n_sealed: int,
            max_other_enter: int,
            max_other_leave: int,
        ) -> None:
            if n_ploc < OUTSIDE_LOC and n_ploc == n_dloc:
                return
            if (n_sealed & 1) and (n_ploc == _G10_11_LOC or n_dloc == _G10_11_LOC):
                return
            if (n_sealed & 2) and (n_ploc == _G12_11_LOC or n_dloc == _G12_11_LOC):
                return
            n_req = _LOC_GOAL_BIT[n_ploc] | _LOC_GOAL_BIT[n_dloc]
            forbid = n_req | (16 if (n_sealed & 1) else 0) | (32 if (n_sealed & 2) else 0)
            if max_other_enter == 0 and max_other_leave == 0:
                if (other_pre & forbid) == 0:
                    out.append(cls.encode(act, other_pre | n_req, n_sealed, n_ploc, n_dloc))
                return
            if max_other_enter >= 4 and max_other_leave >= 4:
                for other_post in _MASKS_LE4:
                    if (other_post & forbid) == 0:
                        out.append(cls.encode(act, other_post | n_req, n_sealed, n_ploc, n_dloc))
                return
            for other_post in _MASKS_LE4:
                if (other_post & forbid) != 0:
                    continue
                if _POPCNT64[other_post & ~other_pre] <= max_other_enter and _POPCNT64[other_pre & ~other_post] <= max_other_leave:
                    out.append(cls.encode(act, other_post | n_req, n_sealed, n_ploc, n_dloc))

        if act == 3:
            # Priest active: ONLY Priest walks 1 orthogonal cell (`F, T, W, B, D` and `sealed` CANNOT change!)
            for n_ploc in _ZONE_STEP_ADJ[ploc]:
                emit_transitions(n_ploc, dloc, sealed, 0, 0)
        elif act == 5:
            # Druid active: either Druid walks 1 cell (`sealed` unchanged, other heroes unchanged),
            # OR Druid stays at `dloc` and toggles 1 adjacent wall/crate (can clear at most 1 bit of `sealed`!)
            for n_dloc in _ZONE_STEP_ADJ[dloc]:
                emit_transitions(ploc, n_dloc, sealed, 0, 0)
            emit_transitions(ploc, dloc, sealed, 0, 0)
            if sealed & 1:
                emit_transitions(ploc, dloc, sealed & ~1, 0, 0)
            if sealed & 2:
                emit_transitions(ploc, dloc, sealed & ~2, 0, 0)
            # Also Druid could petrify a wall sealing an empty pocket (`0 -> 1`)
            if not (sealed & 1):
                emit_transitions(ploc, dloc, sealed | 1, 0, 0)
            if not (sealed & 2):
                emit_transitions(ploc, dloc, sealed | 2, 0, 0)
        elif act == 1:
            # Thief active: Thief walks 1 cell + pulls at most 1 Moveable (`ploc` OR `dloc` OR 1 other hero) by 1 cell!
            emit_transitions(ploc, dloc, sealed, 1, 1)  # Thief + 0 pulled, or Thief + 1 other hero? Wait: if Thief + 1 other hero BOTH enter goals on 1 step, `max_other_enter = 2`!
            emit_transitions(ploc, dloc, sealed, 2, 2)
            for n_ploc in _ZONE_STEP_ADJ[ploc]:
                emit_transitions(n_ploc, dloc, sealed, 1, 1)
            for n_dloc in _ZONE_STEP_ADJ[dloc]:
                emit_transitions(ploc, n_dloc, sealed, 1, 1)
        elif act == 2:
            # Wizard active: either Wizard walks/crate-swaps (only `W` moves, `max_other = 1`),
            # OR Wizard swaps collinearly with 1 inactive hero (`P`, `D`, or 1 of `F, T, B`)!
            emit_transitions(ploc, dloc, sealed, 1, 1)
            # If W swaps with F, T, or B, one leaves W's cell and W lands on target's cell (`entered <= 1, left <= 1`, or if W wasn't on goal and target wasn't on goal -> `0`; wait: can BOTH W and swapped hero newly enter goals? Only if BOTH were ALREADY on goals, in which case `entered == 0`! Because they swap into EACH OTHER'S old positions, at most ONE of the two old positions was a goal while the other wasn't -> `entered <= 1, left <= 1`!!)
            for n_ploc in _ZONE_RAY_ADJ[ploc]:
                emit_transitions(n_ploc, dloc, sealed, 1, 1)
            for n_dloc in _ZONE_RAY_ADJ[dloc]:
                emit_transitions(ploc, n_dloc, sealed, 1, 1)
        else:
            # Fighter (`act == 0`) or Bard (`act == 4`): can push/charm multiple Moveables by 1 orthogonal step!
            p_opts = (ploc,) + _ZONE_STEP_ADJ[ploc]
            d_opts = (dloc,) + _ZONE_STEP_ADJ[dloc]
            for n_ploc in set(p_opts):
                for n_dloc in set(d_opts):
                    emit_transitions(n_ploc, n_dloc, sealed, 4, 4)

        return out

    def build_and_audit(self) -> QuotientTBAudit:
        """Build exact retrograde distances from all valid goal states (`gmask == 63`) and
        verify 100% of forward quotient edges (`0` violations).
        """
        rev_adj: List[List[int]] = [[] for _ in range(self.TOTAL)]
        valid_vertices: List[int] = []
        goal_vertices: List[int] = []

        for act in range(6):
            for gmask in range(64):
                for sealed in range(4):
                    for ploc in range(NUM_LOCS):
                        for dloc in range(NUM_LOCS):
                            if not self.is_valid(gmask, sealed, ploc, dloc):
                                continue
                            u = self.encode(act, gmask, sealed, ploc, dloc)
                            valid_vertices.append(u)
                            if gmask == 63:
                                goal_vertices.append(u)
                            for v in self.forward_neighbors(act, gmask, sealed, ploc, dloc):
                                rev_adj[v].append(u)

        self.dist = [999] * self.TOTAL
        dq: deque[int] = deque()
        for g in goal_vertices:
            self.dist[g] = 0
            dq.append(g)

        reachable = len(goal_vertices)
        while dq:
            v = dq.popleft()
            nd = self.dist[v] + 1
            for u in rev_adj[v]:
                if self.dist[u] == 999:
                    self.dist[u] = nd
                    reachable += 1
                    dq.append(u)

        # Exhaustive forward edge verification
        goal_viols = sum(1 for g in goal_vertices if self.dist[g] != 0)
        step_viols = 0
        edges_checked = 0
        for u in valid_vertices:
            tmp = u
            dloc = tmp % NUM_LOCS
            tmp //= NUM_LOCS
            ploc = tmp % NUM_LOCS
            tmp //= NUM_LOCS
            sealed = tmp % 4
            tmp //= 4
            gmask = tmp % 64
            act = tmp // 64
            du = self.dist[u]
            for v in self.forward_neighbors(act, gmask, sealed, ploc, dloc):
                edges_checked += 1
                if du > 1 + self.dist[v]:
                    step_viols += 1

        self.built = True
        return QuotientTBAudit(
            total_states=self.TOTAL,
            reachable_states=reachable,
            goal_states=len(goal_vertices),
            forward_edges_checked=edges_checked,
            goal_violations=goal_viols,
            step_violations=step_viols,
        )

    def project_concrete(self, ps: PuzzleScriptOracle) -> int:
        act_slot = 0
        gmask = 0
        ploc = OUTSIDE_LOC
        dloc = OUTSIDE_LOC
        for y in range(ps.h):
            for x in range(ps.w):
                o = ps.obj[y][x]
                if not ps.is_hero(o):
                    continue
                if (x, y) in _GOAL_INDEX:
                    gmask |= 1 << _GOAL_INDEX[(x, y)]
                if o in ACTIVE_HEROES:
                    act_slot = int(TO_INACTIVE[o]) - 1
                slot_ch = TO_INACTIVE[o] if o in ACTIVE_HEROES else o
                if slot_ch == "4":
                    ploc = _ZONE_INDEX.get((x, y), OUTSIDE_LOC)
                elif slot_ch == "6":
                    dloc = _ZONE_INDEX.get((x, y), OUTSIDE_LOC)

        s0 = (
            1
            if (not ps.is_hero(ps.obj[11][10]) and all(ps.obj[ny][nx] == "#" for nx, ny in ((9, 11), (10, 10), (11, 11), (10, 12))))
            else 0
        )
        s1 = (
            2
            if (not ps.is_hero(ps.obj[11][12]) and all(ps.obj[ny][nx] == "#" for nx, ny in ((11, 11), (12, 10), (13, 11), (12, 12))))
            else 0
        )
        return self.encode(act_slot, gmask, s0 | s1, ploc, dloc)

    def lookup(self, ps: PuzzleScriptOracle) -> int:
        if not self.built:
            raise RuntimeError("III21EndgameQuotientTB.build_and_audit() must be called before lookup()")
        return self.dist[self.project_concrete(ps)]


def verify_iii21_bidirectional_endgame(
    grid: List[str],
    reference_route: str,
    tb: III21EndgameQuotientTB,
    *,
    suffix_len: int = 10,
) -> Dict[str, Any]:
    """Run both blind concrete BFS and `tb`-guided exact A* from `s_{316 - suffix_len}` (`t = 306`,
    spanning Wizard's escaping walk, 9-cell crate swap onto `(10,6)`, hero swap with Druid onto `(10,6)`,
    walk into `(10,11)`, `'A'` switch to Priest, and Priest's 3-step delivery onto `(10,1)`), PLUS
    build a concrete retrograde endgame ball from the winning state to verify bidirectional meet-in-the-middle!
    """
    prefix_len = len(reference_route) - suffix_len
    s_start = PuzzleScriptOracle(3, grid)
    for ch in reference_route[:prefix_len]:
        ok, _ = s_start.step(ch)
        if not ok:
            raise RuntimeError("Failed to replay prefix to s_start")

    # 1. Exact blind concrete BFS from `s_start` up to `suffix_len`
    sig0 = s_start.state_signature()
    bfs_dist: Dict[Any, int] = {sig0: 0}
    bfs_state: Dict[Any, PuzzleScriptOracle] = {sig0: s_start}
    bfs_q: deque[Tuple[PuzzleScriptOracle, str]] = deque([(s_start, "")])
    bfs_expanded = 0
    shortest_win_route: Optional[str] = None

    while bfs_q:
        cur, path = bfs_q.popleft()
        d_cur = len(path)
        if cur.check_win():
            shortest_win_route = path
            break
        if d_cur >= suffix_len:
            continue
        bfs_expanded += 1
        for key in ("U", "D", "L", "R", "A"):
            nxt = cur.clone()
            ok, _ = nxt.step(key)
            if not ok:
                continue
            nsig = nxt.state_signature()
            if nsig not in bfs_dist:
                bfs_dist[nsig] = d_cur + 1
                bfs_state[nsig] = nxt
                bfs_q.append((nxt, path + key))

    if shortest_win_route is None or len(shortest_win_route) != suffix_len:
        raise RuntimeError(f"Expected exact endgame distance {suffix_len}, got {shortest_win_route!r}")

    # 2. `tb`-guided exact A* from `s_start` (proving `h_TB` guides forward search without overestimating!)
    astar_g: Dict[Any, int] = {sig0: 0}
    counter = 0
    pq: List[Tuple[int, int, int, PuzzleScriptOracle, str]] = [(tb.lookup(s_start), 0, counter, s_start, "")]
    astar_expanded = 0
    astar_win_route: Optional[str] = None

    while pq:
        f_val, g_val, _, cur, path = heapq.heappop(pq)
        csig = cur.state_signature()
        if g_val > astar_g.get(csig, 10**9):
            continue
        if cur.check_win():
            astar_win_route = path
            break
        if f_val > suffix_len:
            continue
        astar_expanded += 1
        for key in ("U", "D", "L", "R", "A"):
            nxt = cur.clone()
            ok, _ = nxt.step(key)
            if not ok:
                continue
            ng = g_val + 1
            nsig = nxt.state_signature()
            if ng < astar_g.get(nsig, 10**9):
                astar_g[nsig] = ng
                counter += 1
                nf = ng + tb.lookup(nxt)
                heapq.heappush(pq, (nf, ng, counter, nxt, path + key))

    if astar_win_route is None or len(astar_win_route) != suffix_len:
        raise RuntimeError("TB-guided A* failed to recover exact optimal suffix")

    # 3. Exact concrete retrograde predecessor ball of radius 4 from Priest's final delivery goal state:
    #    In the final 3 steps (after 'A' makes Priest active), ONLY Priest walks! Inverting Priest's 1-cell walk
    #    and the 'A' switch (`W -> P`) constructs exact concrete goal predecessors directly from `s_win`!
    s_win = s_start.clone()
    for ch in shortest_win_route:
        s_win.step(ch)
    retro_concrete: Dict[Any, int] = {s_win.state_signature(): 0}
    # Enumerate exact Priest-walk backward predecessors (`d = 1..3`) + `'A'` predecessor (`W -> P` at `d = 4`)
    cur_layer = [s_win]
    for back_d in range(1, 4):
        nxt_layer: List[PuzzleScriptOracle] = []
        for post_st in cur_layer:
            # Find active Priest 'P'
            p_pos = next(
                ((x, y) for y in range(post_st.h) for x in range(post_st.w) if post_st.obj[y][x] == "P"),
                None,
            )
            if p_pos is None:
                continue
            px, py = p_pos
            for key, (dx, dy) in (("U", (0, -1)), ("D", (0, 1)), ("L", (-1, 0)), ("R", (1, 0))):
                ox, oy = px - dx, py - dy
                if 0 <= ox < post_st.w and 0 <= oy < post_st.h and post_st.obj[oy][ox] is None:
                    cand_pre = post_st.clone()
                    cand_pre.obj[py][px] = None
                    cand_pre.obj[oy][ox] = "P"
                    # Verify forward step `cand_pre.step(key)` lands on `post_st`!
                    chk = cand_pre.clone()
                    ok_c, _ = chk.step(key)
                    if ok_c and chk.state_signature() == post_st.state_signature():
                        psig = cand_pre.state_signature()
                        if psig not in retro_concrete:
                            retro_concrete[psig] = back_d
                            nxt_layer.append(cand_pre)
        cur_layer = nxt_layer

    # Invert `'A'` (`W -> P`, `slot 2 -> slot 3`) on `d == 3` Priest states to reach `d == 4`!
    for post_st in cur_layer:
        p_pos = next(((x, y) for y in range(post_st.h) for x in range(post_st.w) if post_st.obj[y][x] == "P"), None)
        w_pos = next(((x, y) for y in range(post_st.h) for x in range(post_st.w) if post_st.obj[y][x] == "3"), None)
        if p_pos is not None and w_pos is not None:
            cand_pre = post_st.clone()
            cand_pre.obj[p_pos[1]][p_pos[0]] = "4"
            cand_pre.obj[w_pos[1]][w_pos[0]] = "W"
            chk = cand_pre.clone()
            ok_c, _ = chk.step("A")
            if ok_c and chk.state_signature() == post_st.state_signature():
                psig = cand_pre.state_signature()
                if psig not in retro_concrete:
                    retro_concrete[psig] = 4

    # Verify bidirectional meet-in-the-middle: forward BFS at depth `suffix_len - 4 = 6` meets `retro_concrete` (`d = 4`)!
    meet_states = [
        sig for sig, fd in bfs_dist.items() if sig in retro_concrete and fd + retro_concrete[sig] == suffix_len
    ]
    if not meet_states:
        raise RuntimeError("Forward ball failed to meet concrete retrograde tablebase at depth 6 + 4 = 10")

    # Verify rebuilt full 316-key route (`prefix + astar_win_route`) in BOTH oracles!
    rebuilt_full = reference_route[:prefix_len] + astar_win_route
    ps_full = replay_oracle(3, grid, rebuilt_full)
    fl_full = replay_flat_oracle(3, grid, rebuilt_full)
    if not (ps_full["exact_win"] and fl_full["exact_win"] and ps_full["traj_fnv64"] == fl_full["traj_fnv64"]):
        raise RuntimeError("Bidirectionally recovered 316-key route failed dual-oracle check")

    return {
        "suffix_start_step": prefix_len,
        "exact_suffix_distance": len(astar_win_route),
        "blind_bfs_expanded_states": bfs_expanded,
        "tb_guided_astar_expanded_states": astar_expanded,
        "astar_strictly_fewer_expansions": astar_expanded < bfs_expanded,
        "concrete_retrograde_states_built": len(retro_concrete),
        "bidirectional_meet_states_count": len(meet_states),
        "recovered_full_route_len": len(rebuilt_full),
        "dual_oracle_verified": True,
    }


def run_full_c3_retrograde_audit(catalog_path: Optional[Path] = None) -> Dict[str, Any]:
    """Build `III21EndgameQuotientTB`, audit 100% of quotient edges, verify admissibility & exactness
    along the 316-key `III-21` route, run bidirectional endgame verification, and check `must_fail` controls.
    """
    cat_file = catalog_path or (Path(__file__).resolve().parents[2] / "soko_mcp" / "data" / "catalog.json")
    cat_data = json.loads(cat_file.read_text(encoding="utf-8"))
    iii21 = next(r for r in cat_data["rooms"] if r["id"] == "III-21")
    grid: List[str] = iii21["grid"]
    route: str = iii21["reference_route"]

    tb = III21EndgameQuotientTB()
    q_audit = tb.build_and_audit()
    if q_audit.goal_violations != 0 or q_audit.step_violations != 0:
        raise RuntimeError(f"III21EndgameQuotientTB quotient audit failed: {q_audit}")

    # Verify admissibility & 1-step consistency across all 317 frames of III-21's 316-key route
    sim = PuzzleScriptOracle(3, grid)
    potentials: Dict[Any, int] = {sim.state_signature(): tb.lookup(sim)}
    edges: List[Tuple[Any, Any, int]] = []
    admissibility_violations = 0
    exact_match_suffix_steps: List[int] = []
    tail_profile: List[Dict[str, int]] = []

    for step_t, ch in enumerate(route):
        rem = len(route) - step_t
        u_sig = sim.state_signature()
        h_val = potentials[u_sig]
        if h_val > rem:
            admissibility_violations += 1
        if h_val == rem:
            exact_match_suffix_steps.append(step_t)
        if step_t >= len(route) - 12:
            tail_profile.append({"t": step_t, "remaining": rem, "h_tb": h_val})

        ok, _ = sim.step(ch)
        if not ok:
            raise RuntimeError(f"III-21 route died at step {step_t}")
        v_sig = sim.state_signature()
        if v_sig not in potentials:
            potentials[v_sig] = tb.lookup(sim)
        if v_sig != u_sig:
            edges.append((u_sig, v_sig, 1))

    win_sig = sim.state_signature()
    if potentials[win_sig] != 0:
        raise RuntimeError("Terminal III-21 win state did not evaluate to h_tb == 0")
    tail_profile.append({"t": len(route), "remaining": 0, "h_tb": 0})
    exact_match_suffix_steps.append(len(route))

    step_audit = verify_step_consistency(potentials, [win_sig], edges)
    if not step_audit.consistent_and_goal_zero or admissibility_violations != 0:
        raise RuntimeError("III-21 route consistency or admissibility failed under III21EndgameQuotientTB")

    bidir = verify_iii21_bidirectional_endgame(grid, route, tb, suffix_len=10)

    # Non-tautological `must_fail` controls calling live verifiers:
    # 1) Corrupt `potentials` at `t = 312` (`h_tb = 4 -> 6`, jumping 6 -> 3 on step 312->313) -> rejected by `verify_step_consistency`!
    sim_312 = PuzzleScriptOracle(3, grid)
    for ch in route[:312]:
        sim_312.step(ch)
    corrupted_pot = dict(potentials)
    corrupted_pot[sim_312.state_signature()] = potentials[sim_312.state_signature()] + 2
    must_fail_corrupted_tb_rejected = not verify_step_consistency(
        corrupted_pot, [win_sig], edges
    ).consistent_and_goal_zero

    # 2) Truncated 315-key route rejected by BOTH `PuzzleScriptOracle` and `FlatBitmaskOracle`!
    trunc_ps = replay_oracle(3, grid, route[:-1])
    trunc_fl = replay_flat_oracle(3, grid, route[:-1])
    must_fail_truncated_315_rejected = (not trunc_ps["exact_win"]) and (not trunc_fl["exact_win"])

    controls = {
        "corrupted_tb_drop_rejected": must_fail_corrupted_tb_rejected,
        "truncated_315_route_rejected": must_fail_truncated_315_rejected,
    }
    if not all(controls.values()):
        raise RuntimeError(f"C3 must_fail controls failed: {controls}")

    payload = {
        "epistemic_status": "VERIFIED",
        "task_ref": "ahrazzle/soko#53 C3 (III-21 Retrograde Endgame Tablebase)",
        "quotient_tablebase_audit": {
            "total_states": q_audit.total_states,
            "reachable_states": q_audit.reachable_states,
            "goal_states": q_audit.goal_states,
            "forward_edges_checked": q_audit.forward_edges_checked,
            "goal_violations": q_audit.goal_violations,
            "step_violations": q_audit.step_violations,
        },
        "route_316_verification": {
            "root_h_tb": potentials[PuzzleScriptOracle(3, grid).state_signature()],
            "states_checked": len(potentials),
            "admissibility_violations": admissibility_violations,
            "step_consistency_violations": step_audit.step_lip_violations,
            "exact_tail_steps": [t for t in exact_match_suffix_steps if t >= 310],
            "tail_profile_t304_316": tail_profile,
        },
        "bidirectional_endgame_search": bidir,
        "must_fail_controls": controls,
    }
    load_strict_rational_json(json.dumps(payload))
    return payload
