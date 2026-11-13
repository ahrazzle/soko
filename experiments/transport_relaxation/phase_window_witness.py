"""
Phase-window transport witness (`experiments/transport_relaxation/phase_window_witness.py`)
===============================================================================
Regression witness against a false-feasibility trap in phase-shifted transport
relaxations.

A static union relaxation merges every `(crate, target)` window edge across the
whole phase interval into one network and checks feasibility there. That ignores
phase: each edge is only open while the macro phase `b` sits inside its window
`[lo, hi]`. A deadlock whose crates are mutually phase-incompatible can look
routable to the union relaxation (flow n) while no single phase routes them all
(flow < n at every b).

This module sweeps exact rational 1-D interval knots across the phase interval and
computes max flow per knot with the repo's `CertifiedDinic`. Sweeping only knot
points is exact for the **maximum** over the interval, by monotonicity: between
consecutive knots the active edge set is constant, and on an open segment
`(k_i, k_{i+1})` it equals the intersection of the two endpoint sets (intervals are
closed, so `lo <= k_i` and `hi >= k_{i+1}` there). Max flow is monotone in the
edge set, hence every segment flow is dominated by its endpoint knot flow. No
intermediate tick needs enumeration.

What it is not: a solver for the game, a proof about Sokoban, or a claim about
`experiments/macro_scheduler/`. It is a bounded, exact checker for the static-union
relaxation, with a self-contained certificate whose verifier re-derives everything
from the recorded inputs.

Derived from a peer bundle dropped 2026-11-13 (Gemini task agent, Apache-2.0).
Rewritten to reuse this repository's `CertifiedDinic` and so that the verifier
re-derives the clipping, the knot set, every per-knot flow and the static-union
flow from the recorded window list instead of trusting recorded outputs. See
issue #44 for the verification and for what was not landed.
"""

from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from typing import Any, Dict, List, Sequence, Tuple, Union

from experiments.transport_relaxation.dinic_kernel import CertifiedDinic, verify_9flow_min_cut

RationalLike = Union[int, str, Fraction]


def _to_q(x: RationalLike) -> Fraction:
    return x if isinstance(x, Fraction) else Fraction(x)


def _q_str(x: Fraction) -> str:
    return f"{x.numerator}/{x.denominator}"


def _canon_sha256(payload: Dict[str, Any]) -> str:
    body = {k: v for k, v in payload.items() if k != "certificate_sha256"}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _run_on_edges(
    n_crates: int,
    n_targets: int,
    edges: Sequence[Tuple[int, int]],
) -> Tuple[int, Dict[str, Any], CertifiedDinic, int, int]:
    net = CertifiedDinic()
    src = net.add_node("src")
    for c in range(n_crates):
        net.add_node(f"crate:{c}")
    for t in range(n_targets):
        net.add_node(f"target_in:{t}")
    for t in range(n_targets):
        net.add_node(f"target_out:{t}")
    sink = net.add_node("sink")
    crates = list(range(1, 1 + n_crates))
    tin = list(range(1 + n_crates, 1 + n_crates + n_targets))
    tout = list(range(1 + n_crates + n_targets, 1 + n_crates + 2 * n_targets))
    for c in range(n_crates):
        net.add_edge(src, crates[c], 1)
    for t in range(n_targets):
        net.add_edge(tin[t], tout[t], 1)
        net.add_edge(tout[t], sink, 1)
    for c, t in edges:
        net.add_edge(crates[c], tin[t], 1)
    flow = net.max_flow(src, sink)
    cut = net.min_cut(src)
    return flow, cut, net, src, sink


def _strict_int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _indices_in_range(
    window_edges: Sequence[Tuple[Any, Any, Any, Any]],
    n_crates: int,
    n_targets: int,
) -> bool:
    """True iff every crate index is in 0..n_crates-1 and every target index is
    in 0..n_targets-1. Python list indexing would otherwise alias -1 to the last
    node and raise on n, so the network builder must never see either."""
    for c_idx, t_idx, _, _ in window_edges:
        if not (_strict_int(c_idx) and _strict_int(t_idx)):
            return False
        if not (0 <= c_idx < n_crates and 0 <= t_idx < n_targets):
            return False
    return True


def _clip_and_knots(
    window_edges: Sequence[Tuple[int, int, RationalLike, RationalLike]],
    b_min: Fraction,
    b_max: Fraction,
) -> Tuple[List[Tuple[int, int, Fraction, Fraction]], List[Fraction]]:
    clipped: List[Tuple[int, int, Fraction, Fraction]] = []
    knots = {b_min, b_max}
    for c_idx, t_idx, lo_raw, hi_raw in window_edges:
        lo = max(b_min, _to_q(lo_raw))
        hi = min(b_max, _to_q(hi_raw))
        if lo <= hi:
            clipped.append((int(c_idx), int(t_idx), lo, hi))
            knots.add(lo)
            knots.add(hi)
    return clipped, sorted(knots)


def certify_phase_window_transport(
    *,
    n_crates: int,
    n_targets: int,
    window_edges: Sequence[Tuple[int, int, RationalLike, RationalLike]],
    phase_min: RationalLike = Fraction(0, 1),
    phase_max: RationalLike = Fraction(10, 1),
) -> Dict[str, Any]:
    """
    Certifies whether `n_crates` can be routed simultaneously through unit-capacity
    corridor/goal vertices `0..n_targets-1` at SOME common macro phase `b`.

    Each tuple in `window_edges` is `(crate_idx, target_idx, lo_phase, hi_phase)`.

    Returns the static-union verdict (which ignores phase), the exact max over
    phases, and one witness per Helly knot carrying a recomputable s-t cut.
    `verify_phase_window_certificate` re-derives everything from the recorded
    inputs. No intermediate tick is enumerated.
    """
    b_min = _to_q(phase_min)
    b_max = _to_q(phase_max)
    if n_crates <= 0 or n_targets <= 0 or b_min > b_max:
        raise ValueError("Invalid crate/target counts or phase interval")
    if not _indices_in_range(window_edges, n_crates, n_targets):
        raise ValueError("Crate or target index outside 0..n-1")

    clipped, knots = _clip_and_knots(window_edges, b_min, b_max)

    union_edges = sorted({(c, t) for (c, t, _, _) in clipped})
    static_flow, _, _, _, _ = _run_on_edges(n_crates, n_targets, union_edges)

    best_flow = -1
    best_phase = b_min
    knot_witnesses: List[Dict[str, Any]] = []
    for bk in knots:
        active = [(c, t) for (c, t, lo, hi) in clipped if lo <= bk <= hi]
        fl, cut, net, src, sink = _run_on_edges(n_crates, n_targets, active)
        if not verify_9flow_min_cut(net, src, sink, cut):
            raise RuntimeError("internal: min-cut witness failed self-check")
        knot_witnesses.append({
            "phase_q": _q_str(bk),
            "active_edges": [[c, t] for (c, t) in active],
            "max_flow": fl,
            "min_cut_capacity": cut["capacity"],
            "source_side": cut["source_side"],
        })
        if fl > best_flow:
            best_flow = fl
            best_phase = bk

    payload: Dict[str, Any] = {
        "n_crates": int(n_crates),
        "n_targets": int(n_targets),
        "phase_min_q": _q_str(b_min),
        "phase_max_q": _q_str(b_max),
        "window_edges_q": [
            [int(c), int(t), _q_str(_to_q(lo)), _q_str(_to_q(hi))]
            for (c, t, lo, hi) in window_edges
        ],
        "static_union_flow": static_flow,
        "static_union_feasible": bool(static_flow == n_crates),
        "max_phase_flow": best_flow,
        "max_phase_q": _q_str(best_phase),
        "phase_window_feasible": bool(best_flow == n_crates),
        "static_union_false_feasibility_caught": bool(
            static_flow == n_crates and best_flow < n_crates
        ),
        "knot_witnesses": knot_witnesses,
    }
    payload["certificate_sha256"] = _canon_sha256(payload)
    return payload


def verify_phase_window_certificate(cert: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Clean-room verifier. Re-derives the clipping, the knot list, every per-knot
    max flow, every min-cut (via `verify_9flow_min_cut`), the max over knots and
    the static-union flow from `window_edges_q`. Recorded outputs are compared
    against the re-derived values, never trusted.

    A prover that invents a passing cut capacity fails here. So does one that
    inflates a knot flow, drops a window from the union, records a source side
    other than the recomputed cut, names a `max_phase_q` that is not a knot
    attaining the recomputed maximum, uses a crate or target index outside
    0..n-1, or re-hashes any of those mutated claims. The only way to pass is to
    exhibit real flows and real cuts.
    """
    if _canon_sha256(cert) != cert.get("certificate_sha256"):
        return False, "certificate_sha256_mismatch"
    try:
        n_c = int(cert["n_crates"])
        n_t = int(cert["n_targets"])
        b_min = Fraction(cert["phase_min_q"])
        b_max = Fraction(cert["phase_max_q"])
        windows = [
            (int(c), int(t), Fraction(lo), Fraction(hi))
            for c, t, lo, hi in cert["window_edges_q"]
        ]
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return False, "malformed_certificate"
    if not (_strict_int(cert["n_crates"]) and _strict_int(cert["n_targets"])):
        return False, "malformed_certificate"
    if n_c <= 0 or n_t <= 0 or b_min > b_max:
        return False, "invalid_counts_or_phase_interval"
    raw_windows = cert["window_edges_q"]
    if not all(isinstance(w, list) and len(w) == 4 for w in raw_windows):
        return False, "malformed_certificate"
    if not _indices_in_range(raw_windows, n_c, n_t):
        return False, "window_index_out_of_range"

    clipped, knots = _clip_and_knots(windows, b_min, b_max)

    union_edges = sorted({(c, t) for (c, t, _, _) in clipped})
    static_flow, _, _, _, _ = _run_on_edges(n_c, n_t, union_edges)
    if static_flow != int(cert["static_union_flow"]):
        return False, "static_union_flow_mismatch"
    if bool(static_flow == n_c) != bool(cert["static_union_feasible"]):
        return False, "static_union_flag_mismatch"

    witnesses = cert.get("knot_witnesses", [])
    if len(witnesses) != len(knots):
        return False, "knot_count_mismatch"

    max_flow = -1
    knot_flows: List[Tuple[str, int]] = []
    for bk, kw in zip(knots, witnesses):
        if not isinstance(kw, dict):
            return False, "malformed_certificate"
        if kw.get("phase_q") != _q_str(bk):
            return False, "knot_phase_mismatch"
        active = [(c, t) for (c, t, lo, hi) in clipped if lo <= bk <= hi]
        if [list(e) for e in active] != kw.get("active_edges"):
            return False, "active_edges_mismatch"
        flow, cut, net, src, sink = _run_on_edges(n_c, n_t, active)
        try:
            rec_flow = int(kw["max_flow"])
            rec_cap = int(kw["min_cut_capacity"])
        except (KeyError, TypeError, ValueError):
            return False, "malformed_certificate"
        if flow != rec_flow:
            return False, f"flow_recomputation_mismatch:{flow}!={kw['max_flow']}"
        if cut["capacity"] != rec_cap:
            return False, "cut_capacity_mismatch"
        if not verify_9flow_min_cut(net, src, sink, cut):
            return False, "cut_self_check_failed"
        # The recorded source side is part of the hashed payload, so it is
        # checked too: it must equal the recomputed residual-reachable side, and
        # the cut it defines must pass verify_9flow_min_cut with the recorded
        # capacity, which in turn must equal the recomputed flow.
        rec_side = kw.get("source_side")
        if not isinstance(rec_side, list) or not all(isinstance(x, str) for x in rec_side):
            return False, "malformed_certificate"
        if rec_side != cut["source_side"]:
            return False, "source_side_mismatch"
        recorded_cut = {
            "capacity": rec_cap,
            "source_side": rec_side,
            "crossing_edges": cut["crossing_edges"],
        }
        if not verify_9flow_min_cut(net, src, sink, recorded_cut):
            return False, "recorded_cut_check_failed"
        if rec_cap != flow:
            return False, "recorded_cut_not_tight"
        knot_flows.append((_q_str(bk), flow))
        max_flow = max(max_flow, flow)

    if max_flow != int(cert["max_phase_flow"]):
        return False, "max_phase_flow_mismatch"
    # max_phase_q must name a knot whose recomputed flow attains the maximum.
    argmax_phases = {q for (q, f) in knot_flows if f == max_flow}
    if cert.get("max_phase_q") not in argmax_phases:
        return False, "max_phase_q_mismatch"
    if bool(max_flow == n_c) != bool(cert["phase_window_feasible"]):
        return False, "phase_feasible_flag_mismatch"
    if cert["static_union_false_feasibility_caught"] != bool(
        static_flow == n_c and max_flow < n_c
    ):
        return False, "false_feasibility_flag_mismatch"
    return True, "verified"
