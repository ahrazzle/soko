"""Pure-Python DIMACS CNF builder, Sinz sequential counter, evaluator, and DPLL solver."""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


class CNFFormula:
    """Zero-dependency DIMACS CNF container, clause auditor, and iterative DPLL solver."""

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
