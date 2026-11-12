"""AST-sandboxed Houdini inductive safety invariant & deadlock-trap synthesizer (`formal_synthesize_invariant`)."""
from __future__ import annotations

from collections import deque
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .formal_kernel import (
    SAFE_BUILTINS,
    _canonical_repr,
    _get_locked_system,
    _sha256_hex,
    assert_exact_immutable,
    kernel_sha256,
    validate_pure_ast,
)


def synthesize_formal_invariant(
    system_id: str,
    candidates_code: str,
    synthesis_mode: str = "houdini_safety",
    universe_code: Optional[str] = None,
    max_concrete_states: int = 100000,
) -> Dict[str, Any]:
    reg = _get_locked_system(system_id)
    spec, impl = reg.spec, reg.impl
    c_tree, cand_skel = validate_pure_ast(candidates_code, f"{system_id}.SYNTH", exact_arithmetic_only=reg.exact_only)
    cand_ns: Dict[str, Any] = {"__builtins__": dict(SAFE_BUILTINS)}
    exec(compile(c_tree, filename=f"<{system_id}.SYNTH>", mode="exec"), cand_ns, cand_ns)
    cand_sha256 = _sha256_hex(candidates_code)
    pred_fn = cand_ns.get("predicates")
    if not callable(pred_fn):
        raise ValueError("candidates_code must define `predicates()`")
    raw_preds = pred_fn()
    pred_items: List[Tuple[str, Callable[[Any], Any]]] = (
        [(str(k), v) for k, v in raw_preds.items()] if isinstance(raw_preds, dict) else [(str(k), v) for k, v in raw_preds]
    )
    explicit_enum = cand_ns.get("enumerate_states")
    universe_sha256: Optional[str] = None
    if universe_code is not None and universe_code.strip():
        u_tree, _ = validate_pure_ast(universe_code, f"{system_id}.UNIVERSE", exact_arithmetic_only=reg.exact_only)
        u_ns: Dict[str, Any] = {"__builtins__": dict(SAFE_BUILTINS)}
        exec(compile(u_tree, filename=f"<{system_id}.UNIVERSE>", mode="exec"), u_ns, u_ns)
        explicit_enum = u_ns["enumerate_states"]
        universe_sha256 = _sha256_hex(universe_code)

    s0, u0 = spec.initial_state(), impl.initial_state()
    concrete_states: List[Any] = []
    concrete_edges: List[Tuple[Any, Any, Any]] = []
    universal_domain = callable(explicit_enum)
    if universal_domain:
        raw_states = list(explicit_enum())
        state_set = set(raw_states)
        if s0 not in state_set:
            return {"epistemic_status": "REJECTED_INITIAL_STATE_NOT_IN_DOMAIN", "system_id": reg.system_id}
        for st in raw_states:
            assert_exact_immutable(st, "enumerate_states", reg.exact_only)
            concrete_states.append(st)
            for act in spec.actions(st):
                ns = spec.step(st, act)
                if ns is None:
                    continue
                if ns not in state_set:
                    return {"epistemic_status": "REJECTED_DOMAIN_NOT_INDUCTIVELY_CLOSED", "system_id": reg.system_id}
                concrete_edges.append((st, act, ns))
        complete_space = True
    else:
        q: deque[Tuple[Any, Any]] = deque([(s0, u0)])
        visited: Set[Any] = {s0}
        truncated = False
        while q:
            sc, uc = q.popleft()
            if spec.project_obs(sc) != impl.project_obs(uc):
                raise RuntimeError("SPEC/IMPL divergence")
            concrete_states.append(sc)
            for act in spec.actions(sc):
                ns, nu = spec.step(sc, act), impl.step(uc, act)
                if (ns is None) != (nu is None):
                    raise RuntimeError("SPEC/IMPL survival divergence")
                if ns is None:
                    continue
                concrete_edges.append((sc, act, ns))
                if ns not in visited:
                    if len(visited) >= max_concrete_states:
                        truncated = True
                        continue
                    visited.add(ns)
                    q.append((ns, nu))
        complete_space = not truncated

    state_idx = {st: i for i, st in enumerate(concrete_states)}
    num_states, num_preds = len(concrete_states), len(pred_items)
    truth = [[bool(pfn(st)) for st in concrete_states] for _, pfn in pred_items]
    idx_edges = [(state_idx[s], act, state_idx[ns]) for s, act, ns in concrete_edges]
    s0_idx = state_idx[s0]

    if synthesis_mode == "houdini_safety":
        active: Set[int] = {p for p in range(num_preds) if truth[p][s0_idx]}
        rounds, changed = 0, True
        while changed and active:
            changed = False
            rounds += 1
            for u_i, _act, v_i in idx_edges:
                if all(truth[p][u_i] for p in active):
                    for p in [p for p in sorted(active) if not truth[p][v_i]]:
                        active.remove(p)
                        changed = True
        active_names = [pred_items[p][0] for p in sorted(active)]
        ind_states = [i for i in range(num_states) if all(truth[p][i] for p in active)]
        implies_target = all(spec.invariant(concrete_states[i])[0] for i in ind_states)
        epistemic = "PROVEN" if (complete_space and implies_target) else (
            "VERIFIED_INDUCTIVE_LEMMA_TOO_WEAK_FOR_TARGET" if complete_space else "VERIFIED_ON_BOUNDED_REACHABLE_SUBGRAPH"
        )
        cert = {
            "epistemic_status": epistemic,
            "certificate_kind": "HOUDINI_INDUCTIVE_SAFETY_INVARIANT",
            "system_id": reg.system_id,
            "synthesis_mode": synthesis_mode,
            "universal_domain_induction": universal_domain,
            "complete_domain_closed": complete_space,
            "implies_target_invariant": implies_target,
            "synthesized_conjuncts": active_names,
            "fixpoint_rounds": rounds,
            "states_checked": num_states,
            "transitions_checked": len(idx_edges),
            "checker_pins": {
                "spec_sha256": spec.code_sha256,
                "impl_sha256": impl.code_sha256,
                "candidates_sha256": cand_sha256,
                "candidates_skeleton_sha256": cand_skel,
                "universe_sha256": universe_sha256,
                "formal_kernel_sha256": kernel_sha256(),
            },
        }
        if epistemic == "PROVEN":
            reg.certificates.append(cert)
        return cert

    if synthesis_mode == "deadlock_trap":
        goal_flags = [spec.is_goal(st) for st in concrete_states]
        active_t: Set[int] = {
            p for p in range(num_preds) if not any(truth[p][i] and goal_flags[i] for i in range(num_states))
        }
        rounds, changed = 0, True
        while changed and active_t:
            changed = False
            rounds += 1
            in_union = [any(truth[q][i] for q in active_t) for i in range(num_states)]
            for u_i, _act, v_i in idx_edges:
                if in_union[u_i] and not in_union[v_i]:
                    for p in [p for p in sorted(active_t) if truth[p][u_i]]:
                        active_t.remove(p)
                        changed = True
                    in_union = [any(truth[q][i] for q in active_t) for i in range(num_states)]
        trap_names = [pred_items[p][0] for p in sorted(active_t)]
        trapped = [i for i in range(num_states) if any(truth[p][i] for p in active_t)]
        epistemic_t = "PROVEN" if (complete_space and trap_names) else (
            "REJECTED_NO_SOUND_TRAP_FOUND" if not trap_names else "VERIFIED_ON_BOUNDED_REACHABLE_SUBGRAPH"
        )
        cert_t = {
            "epistemic_status": epistemic_t,
            "certificate_kind": "IRREVERSIBLE_DEADLOCK_TRAP_CERTIFICATE",
            "system_id": reg.system_id,
            "synthesis_mode": synthesis_mode,
            "universal_domain_induction": universal_domain,
            "complete_domain_closed": complete_space,
            "synthesized_traps": trap_names,
            "fixpoint_rounds": rounds,
            "deadlocked_states_certified": len(trapped),
            "initial_state_trapped": (s0_idx in trapped),
            "states_checked": num_states,
            "transitions_checked": len(idx_edges),
            "checker_pins": {
                "spec_sha256": spec.code_sha256,
                "impl_sha256": impl.code_sha256,
                "candidates_sha256": cand_sha256,
                "formal_kernel_sha256": kernel_sha256(),
            },
        }
        if epistemic_t == "PROVEN":
            reg.certificates.append(cert_t)
        return cert_t

    raise ValueError(f"Unsupported synthesis_mode {synthesis_mode!r}")
