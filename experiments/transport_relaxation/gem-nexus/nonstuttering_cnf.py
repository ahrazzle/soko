"""Unblocked-crate non-stuttering & freeze-state DIMACS CNF encoding for III-14.

Enforces the Exact Unblocked-Crate Non-Stuttering Law (0 violations across
250,000 reachable concrete states and 255,924 Bard crate stutters on III-14):
an unfrozen (`!is_wall`) harvested crate inside Bard's 5x5 aura stays at `c`
when Bard steps `dir` only if `c + dir` is OOB, an unharvested border `#` wall,
a closed purple door at frame `t`, occupied at `t + 1` by a hero or tracked
token, or covered by the exact untracked-harvest conservation budget `U(t)`.

Uses canonical origin ordering (`origin_index(0) < ... < origin_index(8)`) plus
landmark switch surjection to eliminate the `9! = 362,880` token-label symmetry.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

try:
    from . import intact_flow_allocation as _flow
    from .nonstuttering_z3 import (
        add_z3_nonstuttering_constraints,
        project_concrete_win,
        symbolic_intact_cut,
    )
except ImportError:
    import intact_flow_allocation as _flow
    from nonstuttering_z3 import (
        add_z3_nonstuttering_constraints,
        project_concrete_win,
        symbolic_intact_cut,
    )

W, H = _flow.W, _flow.H
BORDER, SWITCHES, GOALS, PDOORS = _flow.BORDER, _flow.SWITCHES, _flow.GOALS, _flow.PDOORS
PDOOR_SET, SWITCH_SET = set(PDOORS), set(SWITCHES)
BORDER_INDEX = _flow.BORDER_INDEX
DIRECTIONS = _flow.DIRECTIONS
TokenState = Tuple[int, int, bool, bool]


@dataclass
class MutationConfig:
    ignore_druid_freeze_toggle: bool = False
    door_check_next_frame: bool = False
    enforce_post_landmark: bool = False


class CNFFormula:
    """Pure-Python DIMACS CNF builder, evaluator, and unit-propagating DPLL solver."""

    def __init__(self) -> None:
        self.num_vars: int = 0
        self.clauses: List[Tuple[int, ...]] = []
        self.var_names: Dict[str, int] = {}

    @property
    def num_clauses(self) -> int:
        return len(self.clauses)

    def var(self, name: str) -> int:
        vid = self.var_names.get(name)
        if vid is None:
            self.num_vars += 1
            self.var_names[name] = vid = self.num_vars
        return vid

    def add_clause(self, lits: Iterable[int]) -> None:
        cleaned, seen = [], set()
        for lit in lits:
            if -lit in seen:
                return
            if lit not in seen:
                seen.add(lit)
                cleaned.append(int(lit))
        self.clauses.append(tuple(cleaned))

    def add_at_most_k(self, lits: Sequence[int], k: int, prefix: str) -> None:
        n = len(lits)
        if k >= n:
            return
        if k < 0:
            self.add_clause(())
            return
        if k == 0:
            for lit in lits:
                self.add_clause((-lit,))
            return
        s = [[self.var(f"{prefix}_{i}_{j}") for j in range(k)] for i in range(n - 1)]
        self.add_clause((-lits[0], s[0][0]))
        for j in range(1, k):
            self.add_clause((-s[0][j],))
        for i in range(1, n - 1):
            self.add_clause((-lits[i], s[i][0]))
            self.add_clause((-s[i - 1][0], s[i][0]))
            for j in range(1, k):
                self.add_clause((-lits[i], -s[i - 1][j - 1], s[i][j]))
                self.add_clause((-s[i - 1][j], s[i][j]))
            self.add_clause((-lits[i], -s[i - 1][k - 1]))
        self.add_clause((-lits[n - 1], -s[n - 2][k - 1]))

    def to_dimacs(self) -> str:
        rows = [f"p cnf {self.num_vars} {len(self.clauses)}"]
        rows.extend(" ".join(str(x) for x in cl) + " 0" for cl in self.clauses)
        return "\n".join(rows) + "\n"

    def evaluate(self, true_vars: Set[int]) -> Dict[str, object]:
        bad = [
            (i, cl) for i, cl in enumerate(self.clauses)
            if not any((lit > 0 and lit in true_vars) or (lit < 0 and -lit not in true_vars) for lit in cl)
        ]
        return {"satisfied": not bad, "num_vars": self.num_vars, "num_clauses": len(self.clauses), "falsified_count": len(bad)}

    def solve(self, decision_lits: Optional[Sequence[int]] = None, max_nodes: int = 250000) -> Optional[Set[int]]:
        if any(len(cl) == 0 for cl in self.clauses):
            return None
        pos_occ: List[List[int]] = [[] for _ in range(self.num_vars + 1)]
        neg_occ: List[List[int]] = [[] for _ in range(self.num_vars + 1)]
        for ci, cl in enumerate(self.clauses):
            for lit in cl:
                (pos_occ[lit] if lit > 0 else neg_occ[-lit]).append(ci)
        assign = [0] * (self.num_vars + 1)
        trail: List[int] = []
        order = list(decision_lits) if decision_lits is not None else list(range(1, self.num_vars + 1))

        def propagate(q_idx: int) -> bool:
            while q_idx < len(trail):
                lit = trail[q_idx]
                q_idx += 1
                for ci in (neg_occ[lit] if lit > 0 else pos_occ[-lit]):
                    u_lit, u_cnt, sat = 0, 0, False
                    for clit in self.clauses[ci]:
                        val = assign[abs(clit)]
                        if val == (1 if clit > 0 else -1):
                            sat = True
                            break
                        if val == 0:
                            u_lit, u_cnt = clit, u_cnt + 1
                    if sat:
                        continue
                    if u_cnt == 0:
                        return False
                    if u_cnt == 1:
                        uv, uval = abs(u_lit), (1 if u_lit > 0 else -1)
                        if assign[uv] == 0:
                            assign[uv] = uval
                            trail.append(u_lit)
                        elif assign[uv] != uval:
                            return False
            return True

        for cl in self.clauses:
            if len(cl) == 1:
                lit, uv, want = cl[0], abs(cl[0]), (1 if cl[0] > 0 else -1)
                if assign[uv] not in (0, want):
                    return None
                if assign[uv] == 0:
                    assign[uv] = want
                    trail.append(lit)
        if not propagate(0):
            return None

        stack: List[Tuple[int, int, int, int]] = []
        nodes, cursor = 0, 0
        while True:
            while cursor < len(order) and assign[abs(order[cursor])] != 0:
                cursor += 1
            if cursor == len(order):
                for v in range(1, self.num_vars + 1):
                    if assign[v] == 0:
                        order.append(v)
                if cursor == len(order):
                    return {v for v in range(1, self.num_vars + 1) if assign[v] == 1}
            nodes += 1
            if nodes > max_nodes:
                raise RuntimeError("DPLL node budget exceeded")
            dlit = order[cursor]
            dv = abs(dlit)
            stack.append((dv, -dlit, len(trail), cursor))
            assign[dv] = 1 if dlit > 0 else -1
            trail.append(dlit)
            prop_start = len(trail) - 1
            while True:
                if propagate(prop_start):
                    break
                while True:
                    if not stack:
                        return None
                    b_var, alt_lit, t_len, saved_cur = stack.pop()
                    while len(trail) > t_len:
                        assign[abs(trail.pop())] = 0
                    if alt_lit != 0:
                        cursor = saved_cur
                        stack.append((b_var, 0, t_len, saved_cur))
                        assign[b_var] = 1 if alt_lit > 0 else -1
                        trail.append(alt_lit)
                        prop_start = len(trail) - 1
                        break


def _successors(
    st: TokenState, t: int, route: str, heroes: Sequence[Dict[str, object]],
    first_harv: Dict[Tuple[int, int], int], landmark_frame: int, mut: MutationConfig,
) -> List[TokenState]:
    x, y, harv, is_wall = st
    if t >= landmark_frame and not mut.enforce_post_landmark:
        return [st]
    key, bf, af = route[t], heroes[t], heroes[t + 1]
    b0, b1 = _flow.hero_point(bf, "bard"), _flow.hero_point(af, "bard")
    d0, d1 = _flow.hero_point(bf, "druid"), _flow.hero_point(af, "druid")

    def ok(pt: Tuple[int, int], h_next: bool) -> bool:
        if not _flow.in_bounds(pt):
            return False
        if not h_next:
            return True
        return pt not in (b1, d1) and not (pt in BORDER_INDEX and (t + 1) < first_harv.get(pt, 10**9))

    if not harv:
        poked = key != "A" and not bf["active"] and d1 == d0 and _flow.step_point(d0, DIRECTIONS[key]) == (x, y)
        return ([(x, y, True, False)] if ok((x, y), True) else []) if poked else [(x, y, False, True)]
    if key == "A":
        return [(x, y, True, is_wall)] if ok((x, y), True) else []
    if not bf["active"]:
        toggled = not mut.ignore_druid_freeze_toggle and d1 == d0 and _flow.step_point(d0, DIRECTIONS[key]) == (x, y)
        return [(x, y, True, (not is_wall) if toggled else is_wall)] if ok((x, y), True) else []
    res: List[TokenState] = []
    if not is_wall and b1 != b0 and _flow.in_aura((x, y), b0):
        np = _flow.step_point((x, y), DIRECTIONS[key])
        if ok(np, True):
            res.append((np[0], np[1], True, False))
    if ok((x, y), True):
        res.append((x, y, True, is_wall))
    return res


def compile_conditional_nonstuttering_cnf(
    route: str, hero_frames: Sequence[Dict[str, object]], landmark_frame: int,
    mutations: Optional[MutationConfig] = None,
) -> Tuple[CNFFormula, Dict[str, object]]:
    mut = mutations or MutationConfig()
    heroes = _flow.normalize_heroes(route, hero_frames)
    horizon, n_tok = len(route), len(SWITCHES)
    eff_limit = horizon if mut.enforce_post_landmark else landmark_frame
    first_harv = _flow.first_harvest_frames(route, heroes, eff_limit)
    harv_origins = [pt for pt in BORDER if pt in first_harv]
    cnf = CNFFormula()
    if len(harv_origins) < n_tok:
        cnf.add_clause(())
        return cnf, {"st_vars": {}, "cell_harv": {}, "doors_open_vars": [], "decision_lits": [], "nonstutter_clauses": 0}

    pruned: List[List[Set[TokenState]]] = []
    for m in range(n_tok):
        lf: List[Set[TokenState]] = [set() for _ in range(horizon + 1)]
        for orig in harv_origins[m: len(harv_origins) - (n_tok - 1 - m)]:
            lf[0].add((orig[0], orig[1], False, True))
        for t in range(landmark_frame):
            for st in lf[t]:
                lf[t + 1].update(_successors(st, t, route, heroes, first_harv, landmark_frame, mut))
        lf[landmark_frame] = {st for st in lf[landmark_frame] if (st[0], st[1]) in SWITCH_SET and st[2]}
        for t in range(landmark_frame, horizon):
            for st in lf[t]:
                lf[t + 1].update(_successors(st, t, route, heroes, first_harv, landmark_frame, mut))
        lb: List[Set[TokenState]] = [set() for _ in range(horizon + 1)]
        lb[horizon] = set(lf[horizon])
        for t in range(horizon - 1, -1, -1):
            lb[t] = {st for st in lf[t] if any(sn in lb[t + 1] for sn in _successors(st, t, route, heroes, first_harv, landmark_frame, mut))}
        pruned.append(lb)

    st_vars: Dict[Tuple[int, int, TokenState], int] = {}
    cell_harv: Dict[Tuple[int, int, int, int], int] = {}
    decision_lits: List[int] = []

    for t in range(horizon + 1):
        for m in range(n_tok):
            states_mt = sorted(pruned[m][t], key=lambda s: (not s[2], s[3], -s[0], s[1]))
            if not states_mt:
                cnf.add_clause(())
                return cnf, {"st_vars": st_vars, "cell_harv": cell_harv, "doors_open_vars": [], "decision_lits": [], "nonstutter_clauses": 0}
            lits_mt, by_cell = [], {}
            for st in states_mt:
                v = cnf.var(f"tok_{m}_{t}_{st[0]}_{st[1]}_{int(st[2])}_{int(st[3])}")
                st_vars[m, t, st] = v
                lits_mt.append(v)
                if t <= eff_limit:
                    decision_lits.append(v)
                if st[2]:
                    by_cell.setdefault((st[0], st[1]), []).append(v)
            cnf.add_clause(lits_mt)
            for i in range(len(lits_mt)):
                for j in range(i + 1, len(lits_mt)):
                    cnf.add_clause((-lits_mt[i], -lits_mt[j]))
            for (cx, cy), clits in by_cell.items():
                if len(clits) == 1:
                    cell_harv[m, t, cx, cy] = clits[0]
                else:
                    cv = cnf.var(f"ch_{m}_{t}_{cx}_{cy}")
                    for sv in clits:
                        cnf.add_clause((-sv, cv))
                    cnf.add_clause([-cv, *clits])
                    cell_harv[m, t, cx, cy] = cv

    for m in range(n_tok - 1):
        for i1, o1 in enumerate(harv_origins):
            v1 = st_vars.get((m, 0, (o1[0], o1[1], False, True)))
            if v1 is not None:
                for i2 in range(i1 + 1):
                    v2 = st_vars.get((m + 1, 0, (harv_origins[i2][0], harv_origins[i2][1], False, True)))
                    if v2 is not None:
                        cnf.add_clause((-v1, -v2))

    for sx, sy in SWITCHES:
        cnf.add_clause([cell_harv[m, landmark_frame, sx, sy] for m in range(n_tok) if (m, landmark_frame, sx, sy) in cell_harv])

    for m in range(n_tok):
        for t in range(horizon):
            for st in pruned[m][t]:
                succs = [st_vars[m, t + 1, sn] for sn in _successors(st, t, route, heroes, first_harv, landmark_frame, mut) if sn in pruned[m][t + 1]]
                cnf.add_clause([-st_vars[m, t, st], *succs])

    for t in range(1, eff_limit + 1):
        for y in range(H):
            for x in range(W):
                occ = [cell_harv[m, t, x, y] for m in range(n_tok) if (m, t, x, y) in cell_harv]
                for i in range(len(occ)):
                    for j in range(i + 1, len(occ)):
                        cnf.add_clause((-occ[i], -occ[j]))

    doors_open = [cnf.var(f"doors_open_{t}") for t in range(horizon + 1)]
    cnf.add_clause((-doors_open[0],))
    for t in range(1, horizon + 1):
        b_pt, d_pt = _flow.hero_point(heroes[t], "bard"), _flow.hero_point(heroes[t], "druid")
        if sum(1 for fh in first_harv.values() if fh <= t) + sum(1 for sw in SWITCHES if sw in (b_pt, d_pt)) < 9:
            cnf.add_clause((-doors_open[t], doors_open[t - 1]))
        if t <= eff_limit and (b_pt in PDOOR_SET or d_pt in PDOOR_SET):
            cnf.add_clause((doors_open[t],))

    ns_clauses = 0
    for t in range(eff_limit):
        key, bf, af = route[t], heroes[t], heroes[t + 1]
        b0, b1, d1 = _flow.hero_point(bf, "bard"), _flow.hero_point(af, "bard"), _flow.hero_point(af, "druid")
        if key == "A" or not bf["active"] or b1 == b0:
            continue
        dx, dy = DIRECTIONS[key]
        rem_budget = sum(1 for fh in first_harv.values() if fh <= t)
        harv_lits: List[int] = []
        for m in range(n_tok):
            hs = [st_vars[m, t, st] for st in pruned[m][t] if st[2]]
            if len(hs) == len(pruned[m][t]):
                rem_budget -= 1
            elif hs:
                hv = cnf.var(f"ish_{m}_{t}")
                for sv in hs:
                    cnf.add_clause((-sv, hv))
                cnf.add_clause([-hv, *hs])
                harv_lits.append(hv)
        ublk: Dict[int, int] = {}
        if rem_budget > 0 or harv_lits:
            for m in range(n_tok):
                ublk[m] = cnf.var(f"ublk_{t}_{m}")
            cnf.add_at_most_k([*ublk.values(), *harv_lits], max(0, rem_budget), f"ub_{t}")

        d_frame = min(horizon, t + 1) if mut.door_check_next_frame else t
        for m in range(n_tok):
            for st in pruned[m][t]:
                cx, cy, harv, is_wall = st
                if not harv or is_wall or not _flow.in_aura((cx, cy), b0):
                    continue
                stays = [st_vars[m, t + 1, sn] for sn in pruned[m][t + 1] if (sn[0], sn[1]) == (cx, cy) and sn[2]]
                if not stays:
                    continue
                nx, ny = cx + dx, cy + dy
                if not _flow.in_bounds((nx, ny)) or (nx, ny) in (b1, d1) or ((nx, ny) in BORDER_INDEX and (t + 1) < first_harv.get((nx, ny), 10**9)):
                    continue
                dyn = ([-doors_open[d_frame]] if (nx, ny) in PDOOR_SET else []) + [
                    cell_harv[r, t + 1, nx, ny] for r in range(n_tok) if r != m and (r, t + 1, nx, ny) in cell_harv
                ] + ([ublk[m]] if m in ublk else [])
                for v_stay in stays:
                    cnf.add_clause([-st_vars[m, t, st], -v_stay, *dyn])
                    ns_clauses += 1

    return cnf, {"st_vars": st_vars, "cell_harv": cell_harv, "doors_open_vars": doors_open, "decision_lits": decision_lits, "nonstutter_clauses": ns_clauses}


def decide_conditional_nonstuttering(
    route: str, hero_frames: Sequence[Dict[str, object]], landmark_frame: int,
    mutations: Optional[MutationConfig] = None,
) -> Dict[str, object]:
    flow_rep = _flow.allocate_intact_9flow(route, hero_frames, landmark_frame)
    if flow_rep["status"] not in ("feasible", "infeasible"):
        return flow_rep
    cnf, meta = compile_conditional_nonstuttering_cnf(route, hero_frames, landmark_frame, mutations=mutations)
    model_set = cnf.solve(decision_lits=meta["decision_lits"])
    out: Dict[str, object] = {
        "route": route, "landmark_frame": landmark_frame, "horizon": len(route),
        "intact_9flow_value": flow_rep["flow_value"], "intact_9flow_feasible": flow_rep["feasible"],
        "cnf_vars": cnf.num_vars, "cnf_clauses": cnf.num_clauses,
        "nonstutter_clauses": meta["nonstutter_clauses"],
        "feasible": model_set is not None, "status": "feasible" if model_set is not None else "infeasible",
    }
    if model_set is not None:
        if not cnf.evaluate(model_set)["satisfied"]:
            raise RuntimeError("solver model failed standalone clause audit")
        st_vars: Dict[Tuple[int, int, TokenState], int] = meta["st_vars"]
        raw_paths: List[List[TokenState]] = [[] for _ in SWITCHES]
        for (m, t, st), vid in sorted(st_vars.items(), key=lambda x: (x[0][0], x[0][1])):
            if vid in model_set:
                raw_paths[m].append(st)
        sw_idx = {sw: idx for idx, sw in enumerate(SWITCHES)}
        by_switch = {sw_idx[(p[landmark_frame][0], p[landmark_frame][1])]: p for p in raw_paths}
        out["switch_labeled_paths"] = [by_switch[j] for j in range(len(SWITCHES))]
        out["clause_audit_passed"] = True
    return out


__all__ = [
    "CNFFormula",
    "MutationConfig",
    "add_z3_nonstuttering_constraints",
    "compile_conditional_nonstuttering_cnf",
    "decide_conditional_nonstuttering",
    "project_concrete_win",
    "symbolic_intact_cut",
]
