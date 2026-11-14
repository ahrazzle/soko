"""Two-checker primal-dual min-cut, Farkas LP, & Bellman quotient-PDB certificate verifier."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Dict, Hashable, Iterable, Mapping, Sequence, Set, Tuple, TypeVar

Q = TypeVar("Q", bound=Hashable)


@dataclass(frozen=True)
class MinCutCertificate:
    reported_flow: int
    verified_cut_capacity: int
    source_partition: Tuple[int, ...]
    valid: bool
    reason: str


def verify_mincut_certificate(
    source: int,
    sink: int,
    edges: Sequence[Tuple[int, int, int]],
    source_partition: Iterable[int],
    reported_flow: int,
) -> MinCutCertificate:
    s_set: Set[int] = set(source_partition)
    if source not in s_set:
        return MinCutCertificate(reported_flow, -1, tuple(sorted(s_set)), False, "source_missing_from_S")
    if sink in s_set:
        return MinCutCertificate(reported_flow, -1, tuple(sorted(s_set)), False, "sink_inside_S")
    if any(cap < 0 for _, _, cap in edges):
        return MinCutCertificate(reported_flow, -1, tuple(sorted(s_set)), False, "negative_capacity")
    cut_cap = sum(cap for u, v, cap in edges if u in s_set and v not in s_set)
    ok = cut_cap == reported_flow
    return MinCutCertificate(
        reported_flow=reported_flow,
        verified_cut_capacity=cut_cap,
        source_partition=tuple(sorted(s_set)),
        valid=ok,
        reason="ok" if ok else f"cut_capacity_{cut_cap}_mismatch_{reported_flow}",
    )


@dataclass(frozen=True)
class BellmanHomomorphismAudit:
    states_checked: int
    edges_checked: int
    goal_zero_violations: int
    bellman_step_violations: int
    hash64_collisions_detected: int
    admissible: bool


def verify_quotient_pdb_bellman(
    quotient_dist: Mapping[Q, int],
    goal_quotients: Iterable[Q],
    transitions: Iterable[Tuple[Q, Q, int]],
    hash64_fn: Callable[[Q], int] | None = None,
) -> BellmanHomomorphismAudit:
    goal_violations = sum(1 for g in goal_quotients if quotient_dist.get(g, 10**9) != 0)
    step_violations = 0
    edges_checked = 0
    for u, v, cost in transitions:
        edges_checked += 1
        if quotient_dist.get(u, 10**9) > quotient_dist.get(v, 10**9) + cost:
            step_violations += 1

    collisions = 0
    if hash64_fn is not None:
        seen_hashes: Dict[int, Q] = {}
        for q_state in quotient_dist:
            h64 = hash64_fn(q_state) & ((1 << 64) - 1)
            if h64 in seen_hashes and seen_hashes[h64] != q_state:
                collisions += 1
            else:
                seen_hashes[h64] = q_state

    return BellmanHomomorphismAudit(
        states_checked=len(quotient_dist),
        edges_checked=edges_checked,
        goal_zero_violations=goal_violations,
        bellman_step_violations=step_violations,
        hash64_collisions_detected=collisions,
        admissible=(goal_violations == 0 and step_violations == 0),
    )


def verify_farkas_lp_infeasibility(
    matrix_a: Sequence[Sequence[Fraction]],
    rhs_b: Sequence[Fraction],
    dual_y: Sequence[Fraction],
) -> bool:
    if len(dual_y) != len(matrix_a) or len(matrix_a) != len(rhs_b):
        return False
    if any(yi < 0 for yi in dual_y):
        return False
    num_cols = len(matrix_a[0]) if matrix_a else 0
    for j in range(num_cols):
        if sum(dual_y[i] * matrix_a[i][j] for i in range(len(dual_y))) < 0:
            return False
    return sum(dual_y[i] * rhs_b[i] for i in range(len(dual_y))) < 0
