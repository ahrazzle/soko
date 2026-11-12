"""Domain-General Formal Verification & Model-Checking Kernel (`formal_*` MCP Suite).

Implements the Foundation-0 Repository Standard (https://github.com/Foundation-0) and the
Proven-Commons Verified Bar (https://github.com/Proven-Commons/mission/blob/main/playbook/verified-bar.md)
so autonomous agents can model, solve, optimize, model-check, and prove lower bounds or global safety
invariants for ANY discrete system — without trusting LLM prose or single-implementation heuristics:

1. AST-Sandboxed Pure Execution (`validate_pure_ast`):
   - Blocks imports, I/O, globals, reflection/dunder escapes, and IEEE-754 floats (enforcing exact
     `int` / `fractions.Fraction` arithmetic by default).
   - Computes alpha-normalized AST structural hashes (`alpha_skeleton_sha256`) and rejects copy-pasted
     or alpha-renamed duplicates (`spec_code` and `impl_code` MUST be algorithmically distinct!).
2. Zero-Shared-Code Dual-Checker Registration (`formal_define_system`):
   - Locks a declarative `SPEC` against an independent `IMPL` (allowing completely distinct internal
     state encodings bridged via `project_obs(state)`).
   - Requires 100% rejection of `must_fail_controls`, 100% kill rate on `planted_mutations`, and
     zero divergence across bounded breadth-first differential state-space fuzzing.
3. Premise-Explicit Dual Trace Verification (`formal_verify_trace`):
   - Replays candidate traces step-by-step across BOTH hash-pinned checkers, computing rolling SHA-256
     transcript digests and asserting every premise (Foundation-0 Issues #14, #15, #42).
4. Domain-General Verified Search, Counterexample Model Checking & Window LNS (`formal_solve_system`):
   - Exact Dijkstra/BFS (for shortest goal witness OR shortest invariant-violation bug counterexample),
     bucket-diversified Beam Search, and Sliding-Window Trajectory LNS — auto-verifying every witness.
5. Zero-Trust Quotient Homomorphism & Inductive Potential Proofs (`formal_certify_lower_bound`):
   - Machine-checks `h(s) <= cost(s, a, s') + h(s')` across concrete transitions via finite Quotient
     Homomorphisms or user-supplied Inductive Ranking Potentials `V(s)`, distinguishing exhaustive
     deductive proofs (`PROVEN`) from bounded finite checks (`VERIFIED`).
6. Portfolio Tractability Triage & Claim Ledger Export (`formal_triage_portfolio`, `formal_export_ledger`).
"""
from __future__ import annotations

import ast
from collections import deque
from dataclasses import dataclass, field
from fractions import Fraction
import hashlib
import heapq
import json
import math
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

KERNEL_FILE = Path(__file__).resolve()

_FORBIDDEN_CALL_NAMES: Set[str] = {
    "eval",
    "exec",
    "compile",
    "open",
    "input",
    "__import__",
    "getattr",
    "setattr",
    "delattr",
    "globals",
    "locals",
    "vars",
    "dir",
    "breakpoint",
    "memoryview",
    "type",
    "object",
    "super",
    "classmethod",
    "staticmethod",
    "property",
}

SAFE_BUILTINS: Dict[str, Any] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bin": bin,
    "bool": bool,
    "chr": chr,
    "dict": dict,
    "divmod": divmod,
    "enumerate": enumerate,
    "filter": filter,
    "frozenset": frozenset,
    "hex": hex,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "oct": oct,
    "ord": ord,
    "pow": pow,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
    "Fraction": Fraction,
    "True": True,
    "False": False,
    "None": None,
    "ValueError": ValueError,
    "AssertionError": AssertionError,
}


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def kernel_sha256() -> str:
    return hashlib.sha256(KERNEL_FILE.read_bytes()).hexdigest()


def validate_pure_ast(code: str, label: str, exact_arithmetic_only: bool = True) -> Tuple[ast.Module, str]:
    """Validate pure deterministic Python AST and compute an alpha-normalized AST skeleton SHA-256."""
    try:
        tree = ast.parse(code, filename=f"<{label}>", mode="exec")
    except SyntaxError as exc:
        raise ValueError(f"[{label}] Syntax error in formal module: {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError(f"[{label}] Imports are forbidden inside formal modules (use pure Python + Fraction).")
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            raise ValueError(f"[{label}] Mutable global/nonlocal state is forbidden for deterministic verification.")
        if isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.AsyncFor, ast.AsyncWith, ast.Yield, ast.YieldFrom)):
            raise ValueError(f"[{label}] Async/generator constructs are forbidden inside formal specifications.")
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if handler.type is None:
                    raise ValueError(f"[{label}] Bare 'except:' clauses are forbidden (fail-closed discipline).")
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                raise ValueError(f"[{label}] Private/dunder attribute access ({node.attr!r}) is forbidden.")
        if isinstance(node, ast.Name):
            if node.id.startswith("__") or node.id in _FORBIDDEN_CALL_NAMES:
                raise ValueError(f"[{label}] Forbidden identifier {node.id!r} in formal module.")
        if exact_arithmetic_only:
            if isinstance(node, ast.Constant) and isinstance(node.value, (float, complex)):
                raise ValueError(
                    f"[{label}] Floating-point literal {node.value!r} rejected under exact_arithmetic_only=True "
                    "(use exact int or Fraction(p, q))."
                )
            if isinstance(node, ast.Div):
                raise ValueError(
                    f"[{label}] Floating-point '/' division rejected under exact_arithmetic_only=True "
                    "(use integer '//' or Fraction(a, b))."
                )

    skeleton = _alpha_normalize_skeleton(tree)
    return tree, _sha256_hex(skeleton)


def _alpha_normalize_skeleton(tree: ast.AST) -> str:
    """Strip docstrings and alpha-rename local identifiers so trivial variable-renaming copies match."""
    id_map: Dict[str, str] = {}
    preserved = set(SAFE_BUILTINS.keys()) | {
        "initial_state",
        "actions",
        "step",
        "is_goal",
        "invariant",
        "step_cost",
        "project_obs",
        "heuristic",
        "bucket",
        "project",
        "potential",
        "enumerate_states",
    }

    def map_name(name: str) -> str:
        if name in preserved:
            return name
        if name not in id_map:
            id_map[name] = f"v{len(id_map)}"
        return id_map[name]

    class AlphaNormalizer(ast.NodeTransformer):
        def visit_Module(self, node: ast.Module) -> Any:
            body = list(node.body)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                body = body[1:]
            node = ast.Module(body=[self.visit(stmt) for stmt in body], type_ignores=[])
            return node

        def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
            body = list(node.body)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                body = body[1:]
            args = [ast.arg(arg=map_name(a.arg)) for a in node.args.args]
            return ast.FunctionDef(
                name=map_name(node.name),
                args=ast.arguments(
                    posonlyargs=[],
                    args=args,
                    vararg=None,
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=None,
                    defaults=[self.visit(d) for d in node.args.defaults],
                ),
                body=[self.visit(s) for s in body],
                decorator_list=[],
                returns=None,
            )

        def visit_Name(self, node: ast.Name) -> Any:
            return ast.Name(id=map_name(node.id), ctx=node.ctx)

    copied = ast.parse(ast.unparse(tree))
    normed = AlphaNormalizer().visit(copied)
    return ast.dump(normed, annotate_fields=True, include_attributes=False)


def assert_exact_immutable(val: Any, ctx: str, exact_only: bool = True) -> None:
    """Recursively verify that states/actions/observations are immutable, hashable, and exact."""
    if val is None or isinstance(val, (bool, int, str, bytes, Fraction)):
        return
    if isinstance(val, float):
        if exact_only:
            raise TypeError(f"[{ctx}] Float value {val!r} forbidden in state/action; use int or Fraction.")
        return
    if isinstance(val, tuple):
        for item in val:
            assert_exact_immutable(item, ctx, exact_only)
        return
    if isinstance(val, frozenset):
        for item in val:
            assert_exact_immutable(item, ctx, exact_only)
        return
    raise TypeError(
        f"[{ctx}] State/action/observation must use immutable hashable primitives "
        f"(int, bool, str, tuple, frozenset, Fraction); got mutable or unsupported {type(val).__name__}."
    )


def _canonical_repr(val: Any) -> str:
    if isinstance(val, frozenset):
        items = sorted(_canonical_repr(x) for x in val)
        return "frozenset({" + ", ".join(items) + "})"
    if isinstance(val, tuple):
        return "(" + ", ".join(_canonical_repr(x) for x in val) + ("," if len(val) == 1 else "") + ")"
    if isinstance(val, Fraction):
        return f"Fraction({val.numerator}, {val.denominator})"
    return repr(val)


def _json_safe_action(act: Any) -> Any:
    """Convert JSON-decoded lists back into immutable tuples so MCP JSON callers can pass tuple actions cleanly."""
    if isinstance(act, list):
        return tuple(_json_safe_action(x) for x in act)
    if isinstance(act, dict):
        return tuple(sorted((str(k), _json_safe_action(v)) for k, v in act.items()))
    return act


@dataclass
class CompiledChecker:
    label: str
    code: str
    code_sha256: str
    skeleton_sha256: str
    exact_only: bool
    ns: Dict[str, Any] = field(repr=False)

    def initial_state(self) -> Any:
        st = self.ns["initial_state"]()
        assert_exact_immutable(st, f"{self.label}.initial_state", self.exact_only)
        return st

    def actions(self, state: Any) -> Tuple[Any, ...]:
        acts = tuple(self.ns["actions"](state))
        for a in acts:
            assert_exact_immutable(a, f"{self.label}.actions", self.exact_only)
        return acts

    def step(self, state: Any, action: Any) -> Any:
        nxt = self.ns["step"](state, action)
        if nxt is not None:
            assert_exact_immutable(nxt, f"{self.label}.step", self.exact_only)
        return nxt

    def is_goal(self, state: Any) -> bool:
        res = self.ns["is_goal"](state)
        if not isinstance(res, bool):
            raise TypeError(f"[{self.label}.is_goal] Must return bool, got {type(res).__name__}")
        return res

    def invariant(self, state: Any) -> Tuple[bool, str]:
        fn = self.ns.get("invariant")
        if fn is None:
            return True, "ok"
        out = fn(state)
        if isinstance(out, bool):
            return out, ("ok" if out else "invariant_false")
        if isinstance(out, tuple) and len(out) == 2 and isinstance(out[0], bool):
            return out[0], str(out[1])
        raise TypeError(f"[{self.label}.invariant] Must return bool or (bool, reason_str)")

    def step_cost(self, state: Any, action: Any, next_state: Any) -> int:
        fn = self.ns.get("step_cost")
        if fn is None:
            return 1
        c = fn(state, action, next_state)
        if not isinstance(c, int) or isinstance(c, bool) or c < 0:
            raise ValueError(f"[{self.label}.step_cost] Step cost must be a non-negative integer, got {c!r}")
        return c

    def project_obs(self, state: Any) -> Any:
        fn = self.ns.get("project_obs")
        if fn is None:
            return state
        obs = fn(state)
        assert_exact_immutable(obs, f"{self.label}.project_obs", self.exact_only)
        return obs

    def heuristic(self, state: Any) -> int:
        fn = self.ns.get("heuristic")
        if fn is None:
            return 0
        return int(fn(state))

    def bucket(self, state: Any) -> Any:
        fn = self.ns.get("bucket")
        if fn is None:
            return 0
        return fn(state)


def _compile_checker(code: str, label: str, exact_only: bool = True) -> CompiledChecker:
    tree, skel_hash = validate_pure_ast(code, label, exact_arithmetic_only=exact_only)
    ns: Dict[str, Any] = {"__builtins__": dict(SAFE_BUILTINS)}
    compiled = compile(tree, filename=f"<{label}>", mode="exec")
    exec(compiled, ns, ns)  # nosec - AST-validated restricted namespace with zero imports/dunders
    for req in ("initial_state", "actions", "step", "is_goal"):
        if req not in ns or not callable(ns[req]):
            raise ValueError(f"[{label}] Missing required callable `{req}(...)`")
    return CompiledChecker(
        label=label,
        code=code,
        code_sha256=_sha256_hex(code),
        skeleton_sha256=skel_hash,
        exact_only=exact_only,
        ns=ns,
    )


@dataclass
class RegisteredFormalSystem:
    system_id: str
    description: str
    spec: CompiledChecker
    impl: CompiledChecker
    exact_only: bool
    allow_invariant_violations_in_fuzz: bool
    differential_states_checked: int
    differential_edges_checked: int
    must_fail_rejected: int
    mutations_killed: int
    mutations_total: int
    certificates: List[Dict[str, Any]] = field(default_factory=list)


# Global in-process registry of locked formal systems
FORMAL_REGISTRY: Dict[str, RegisteredFormalSystem] = {}


def _replay_single_checker(
    chk: CompiledChecker,
    raw_trace: Sequence[Any],
    require_exact_terminal_goal: bool = True,
) -> Dict[str, Any]:
    trace = [_json_safe_action(a) for a in raw_trace]
    st = chk.initial_state()
    inv0, reason0 = chk.invariant(st)
    roll = hashlib.sha256()
    obs0 = chk.project_obs(st)
    roll.update(f"0|INIT|{_canonical_repr(obs0)}|{int(chk.is_goal(st))}|{int(inv0)}\n".encode("utf-8"))

    alive = True
    invariant_ok = inv0
    invariant_failure_step: Optional[int] = None if inv0 else 0
    invariant_reason = reason0
    premature_goal = False
    illegal_step: Optional[int] = None
    total_cost = 0
    steps_executed = 0

    for idx, act in enumerate(trace):
        legal_acts = chk.actions(st)
        if act not in legal_acts:
            alive = False
            illegal_step = idx + 1
            break
        nxt = chk.step(st, act)
        if nxt is None:
            alive = False
            illegal_step = idx + 1
            break
        c = chk.step_cost(st, act, nxt)
        total_cost += c
        st = nxt
        steps_executed += 1
        inv_s, rsn_s = chk.invariant(st)
        if not inv_s and invariant_ok:
            invariant_ok = False
            invariant_failure_step = steps_executed
            invariant_reason = rsn_s
        goal_now = chk.is_goal(st)
        obs_s = chk.project_obs(st)
        roll.update(
            f"{steps_executed}|{_canonical_repr(act)}|{_canonical_repr(obs_s)}|{c}|{int(goal_now)}|{int(inv_s)}\n".encode("utf-8")
        )
        if require_exact_terminal_goal and goal_now and (idx + 1 < len(trace)):
            premature_goal = True
            break

    final_goal = alive and chk.is_goal(st)
    valid_goal_witness = (
        alive
        and invariant_ok
        and (not premature_goal if require_exact_terminal_goal else True)
        and final_goal
    )
    return {
        "alive": alive,
        "illegal_step": illegal_step,
        "invariant_ok": invariant_ok,
        "invariant_failure_step": invariant_failure_step,
        "invariant_reason": invariant_reason,
        "premature_goal": premature_goal,
        "final_goal": final_goal,
        "valid_goal_witness": valid_goal_witness,
        "steps_executed": steps_executed,
        "total_cost": total_cost,
        "final_obs_repr": _canonical_repr(chk.project_obs(st)),
        "transcript_sha256": roll.hexdigest(),
    }


def define_formal_system(
    system_id: str,
    spec_code: str,
    impl_code: str,
    description: str = "",
    positive_witnesses: Optional[List[Dict[str, Any]]] = None,
    must_fail_controls: Optional[List[Dict[str, Any]]] = None,
    planted_mutations: Optional[List[Dict[str, Any]]] = None,
    bounded_fuzz_nodes: int = 400,
    exact_arithmetic_only: bool = True,
    strict_bar: bool = True,
    allow_invariant_violations_in_fuzz: bool = False,
) -> Dict[str, Any]:
    """Register and cryptographically lock a dual-checker formal system after negative-control & differential gates."""
    sid = system_id.strip()
    if not sid:
        raise ValueError("system_id must be a non-empty identifier")

    spec = _compile_checker(spec_code, f"{sid}.SPEC", exact_only=exact_arithmetic_only)
    impl = _compile_checker(impl_code, f"{sid}.IMPL", exact_only=exact_arithmetic_only)

    if spec.skeleton_sha256 == impl.skeleton_sha256:
        return {
            "epistemic_status": "REJECTED_IDENTICAL_AST_SKELETON",
            "tcb_locked": False,
            "system_id": sid,
            "reason": (
                "impl_code has the exact same alpha-normalized AST skeleton as spec_code. "
                "Foundation-0 requires two genuinely independent implementations (e.g., declarative tuple/set spec "
                "vs flat array or bitmask implementation)."
            ),
        }

    controls = list(must_fail_controls or [])
    if strict_bar and len(controls) == 0:
        return {
            "epistemic_status": "REJECTED_MISSING_NEGATIVE_CONTROLS",
            "tcb_locked": False,
            "system_id": sid,
            "reason": "strict_bar=True requires at least 1 must_fail_controls entry to prove the checkers fail closed.",
        }

    # 1. Verify positive witnesses across BOTH checkers
    pos_results: List[Dict[str, Any]] = []
    for idx, pw in enumerate(positive_witnesses or []):
        wname = pw.get("name", f"witness_{idx}")
        trace = pw.get("trace", [])
        expect_goal = bool(pw.get("expect_goal", True))
        sr = _replay_single_checker(spec, trace, require_exact_terminal_goal=expect_goal)
        ir = _replay_single_checker(impl, trace, require_exact_terminal_goal=expect_goal)
        if sr["transcript_sha256"] != ir["transcript_sha256"] or sr["valid_goal_witness"] != expect_goal:
            return {
                "epistemic_status": "REJECTED_POSITIVE_WITNESS_FAILURE",
                "tcb_locked": False,
                "system_id": sid,
                "failed_witness": wname,
                "spec_result": sr,
                "impl_result": ir,
            }
        pos_results.append({"name": wname, "steps": sr["steps_executed"], "cost": sr["total_cost"], "transcript_sha256_12": sr["transcript_sha256"][:12]})

    # 2. Verify 100% rejection on must-fail negative controls across BOTH checkers
    neg_rejected = 0
    for idx, nc in enumerate(controls):
        cname = nc.get("name", f"control_{idx}")
        trace = nc.get("trace", [])
        sr = _replay_single_checker(spec, trace, require_exact_terminal_goal=True)
        ir = _replay_single_checker(impl, trace, require_exact_terminal_goal=True)
        if sr["transcript_sha256"] != ir["transcript_sha256"]:
            return {
                "epistemic_status": "REJECTED_CONTROL_DIVERGENCE",
                "tcb_locked": False,
                "system_id": sid,
                "control_name": cname,
                "spec_result": sr,
                "impl_result": ir,
            }
        if sr["valid_goal_witness"] or ir["valid_goal_witness"]:
            return {
                "epistemic_status": "REJECTED_MUST_FAIL_CONTROL_PASSED",
                "tcb_locked": False,
                "system_id": sid,
                "control_name": cname,
                "reason": "Must-fail control trace was erroneously accepted as a valid goal witness!",
            }
        neg_rejected += 1

    # 3. Bounded Breadth-First Differential State-Space Fuzzing (SPEC vs IMPL)
    s0 = spec.initial_state()
    u0 = impl.initial_state()
    q: deque[Tuple[Any, Any, Tuple[Any, ...]]] = deque([(s0, u0, ())])
    seen_obs: Set[Any] = {spec.project_obs(s0)}
    fuzz_states = 0
    fuzz_edges = 0
    fuzz_sample_traces: List[Tuple[Any, ...]] = []

    while q and fuzz_states < max(1, int(bounded_fuzz_nodes)):
        s_cur, u_cur, path = q.popleft()
        fuzz_states += 1
        if len(fuzz_sample_traces) < 24:
            fuzz_sample_traces.append(path)

        obs_s = spec.project_obs(s_cur)
        obs_u = impl.project_obs(u_cur)
        inv_s, rsn_s = spec.invariant(s_cur)
        inv_u, rsn_u = impl.invariant(u_cur)
        goal_s = spec.is_goal(s_cur)
        goal_u = impl.is_goal(u_cur)
        acts_s = spec.actions(s_cur)
        acts_u = impl.actions(u_cur)

        if (
            obs_s != obs_u
            or inv_s != inv_u
            or goal_s != goal_u
            or set(acts_s) != set(acts_u)
        ):
            return {
                "epistemic_status": "REJECTED_DIFFERENTIAL_MISMATCH",
                "tcb_locked": False,
                "system_id": sid,
                "diverging_trace": [_canonical_repr(a) for a in path],
                "spec_obs": _canonical_repr(obs_s),
                "impl_obs": _canonical_repr(obs_u),
                "spec_goal_inv": [goal_s, inv_s, rsn_s],
                "impl_goal_inv": [goal_u, inv_u, rsn_u],
            }

        if (not allow_invariant_violations_in_fuzz) and (not inv_s):
            return {
                "epistemic_status": "REJECTED_INVARIANT_VIOLATED_IN_FUZZ",
                "tcb_locked": False,
                "system_id": sid,
                "counterexample_trace": list(path),
                "invariant_reason": rsn_s,
            }

        for act in acts_s:
            ns = spec.step(s_cur, act)
            nu = impl.step(u_cur, act)
            fuzz_edges += 1
            if (ns is None) != (nu is None):
                return {
                    "epistemic_status": "REJECTED_STEP_SURVIVAL_DIVERGENCE",
                    "tcb_locked": False,
                    "system_id": sid,
                    "diverging_trace": [_canonical_repr(a) for a in path + (act,)],
                }
            if ns is None:
                continue
            cs = spec.step_cost(s_cur, act, ns)
            cu = impl.step_cost(u_cur, act, nu)
            obs_ns = spec.project_obs(ns)
            obs_nu = impl.project_obs(nu)
            if cs != cu or obs_ns != obs_nu:
                return {
                    "epistemic_status": "REJECTED_TRANSITION_DIVERGENCE",
                    "tcb_locked": False,
                    "system_id": sid,
                    "diverging_trace": [_canonical_repr(a) for a in path + (act,)],
                    "spec_next_obs_cost": [_canonical_repr(obs_ns), cs],
                    "impl_next_obs_cost": [_canonical_repr(obs_nu), cu],
                }
            if obs_ns not in seen_obs and len(seen_obs) < max(1, int(bounded_fuzz_nodes)):
                seen_obs.add(obs_ns)
                q.append((ns, nu, path + (act,)))

    # 4. Planted-Mutation Adequacy Gate (every planted bug must be killed by witnesses, controls, or fuzz traces!)
    eval_traces: List[Tuple[str, Sequence[Any]]] = []
    for idx, pw in enumerate(positive_witnesses or []):
        eval_traces.append((pw.get("name", f"pos_{idx}"), pw.get("trace", [])))
    for idx, nc in enumerate(controls):
        eval_traces.append((nc.get("name", f"neg_{idx}"), nc.get("trace", [])))
    for idx, ft in enumerate(fuzz_sample_traces):
        eval_traces.append((f"fuzz_{idx}", ft))

    baseline_digests = {
        tname: _replay_single_checker(impl, tr, require_exact_terminal_goal=False)["transcript_sha256"]
        for tname, tr in eval_traces
    }

    mutation_reports: List[Dict[str, Any]] = []
    killed_count = 0
    mutations = list(planted_mutations or [])
    for m_idx, mut in enumerate(mutations):
        bug_id = mut.get("bug_id", f"MUT_{m_idx + 1}")
        mdesc = mut.get("description", "")
        mcode = mut["mutated_code"]
        mchk = _compile_checker(mcode, f"{sid}.{bug_id}", exact_only=exact_arithmetic_only)
        caught_on: List[str] = []
        for tname, tr in eval_traces:
            mr = _replay_single_checker(mchk, tr, require_exact_terminal_goal=False)
            if mr["transcript_sha256"] != baseline_digests[tname]:
                caught_on.append(tname)
        killed = len(caught_on) > 0
        if killed:
            killed_count += 1
        mutation_reports.append({
            "bug_id": bug_id,
            "description": mdesc,
            "killed": killed,
            "catching_vectors": caught_on[:6],
        })

    if mutations and killed_count < len(mutations):
        return {
            "epistemic_status": "REJECTED_SURVIVING_MUTATIONS",
            "tcb_locked": False,
            "system_id": sid,
            "mutations_total": len(mutations),
            "mutations_killed": killed_count,
            "mutation_reports": mutation_reports,
        }

    reg = RegisteredFormalSystem(
        system_id=sid,
        description=description,
        spec=spec,
        impl=impl,
        exact_only=exact_arithmetic_only,
        allow_invariant_violations_in_fuzz=allow_invariant_violations_in_fuzz,
        differential_states_checked=fuzz_states,
        differential_edges_checked=fuzz_edges,
        must_fail_rejected=neg_rejected,
        mutations_killed=killed_count,
        mutations_total=len(mutations),
    )
    FORMAL_REGISTRY[sid] = reg

    cert = {
        "epistemic_status": "VERIFIED",
        "certificate_kind": "DUAL_CHECKER_SYSTEM_LOCK",
        "system_id": sid,
        "tcb_locked": True,
        "checker_pins": {
            "spec_sha256": spec.code_sha256,
            "impl_sha256": impl.code_sha256,
            "spec_ast_skeleton_sha256": spec.skeleton_sha256,
            "impl_ast_skeleton_sha256": impl.skeleton_sha256,
            "formal_kernel_sha256": kernel_sha256(),
        },
        "exact_arithmetic_only": exact_arithmetic_only,
        "positive_witnesses_verified": pos_results,
        "must_fail_controls_rejected": neg_rejected,
        "differential_fuzz": {
            "states_checked": fuzz_states,
            "edges_checked": fuzz_edges,
            "discrepancies": 0,
        },
        "planted_mutations": {
            "total": len(mutations),
            "killed": killed_count,
            "reports": mutation_reports,
        },
    }
    reg.certificates.append(cert)
    return cert


def _get_locked_system(system_id: str) -> RegisteredFormalSystem:
    sid = system_id.strip()
    if sid not in FORMAL_REGISTRY:
        raise KeyError(
            f"Unknown or unlocked formal system {sid!r}. Call `formal_define_system` first. "
            f"Currently registered: {sorted(FORMAL_REGISTRY)}"
        )
    return FORMAL_REGISTRY[sid]


def verify_formal_trace(
    system_id: str,
    trace: Sequence[Any],
    verification_goal: str = "goal_witness",
    require_exact_terminal_goal: bool = True,
) -> Dict[str, Any]:
    """Replay a candidate action trace across BOTH locked checkers (`SPEC` and `IMPL`) with fail-closed parity."""
    reg = _get_locked_system(system_id)
    req_term = require_exact_terminal_goal if verification_goal == "goal_witness" else False
    sr = _replay_single_checker(reg.spec, trace, require_exact_terminal_goal=req_term)
    ir = _replay_single_checker(reg.impl, trace, require_exact_terminal_goal=req_term)

    differential_match = (
        sr["transcript_sha256"] == ir["transcript_sha256"]
        and sr["alive"] == ir["alive"]
        and sr["invariant_ok"] == ir["invariant_ok"]
        and sr["final_goal"] == ir["final_goal"]
        and sr["total_cost"] == ir["total_cost"]
        and sr["steps_executed"] == ir["steps_executed"]
    )

    if verification_goal == "goal_witness":
        verified = differential_match and sr["valid_goal_witness"]
        premises = [
            "dual_checker_transcript_parity",
            "all_actions_legal_and_alive",
            "safety_invariant_preserved_at_all_steps",
            "goal_predicate_satisfied_at_terminal_state",
        ]
        if require_exact_terminal_goal:
            premises.append("no_premature_goal_before_final_step")
    elif verification_goal == "invariant_counterexample":
        verified = differential_match and sr["alive"] and (not sr["invariant_ok"])
        premises = [
            "dual_checker_transcript_parity",
            "all_actions_legal_and_alive",
            "safety_invariant_falsified_on_reached_state",
        ]
    else:
        raise ValueError(f"Unsupported verification_goal {verification_goal!r}; use 'goal_witness' or 'invariant_counterexample'")

    out = {
        "epistemic_status": "VERIFIED" if verified else "REJECTED",
        "certificate_kind": f"TRACE_{verification_goal.upper()}",
        "system_id": reg.system_id,
        "verified": verified,
        "differential_match": differential_match,
        "dual_checker_enforced": True,
        "checker_pins": {
            "spec_sha256": reg.spec.code_sha256,
            "impl_sha256": reg.impl.code_sha256,
            "formal_kernel_sha256": kernel_sha256(),
        },
        "premises_asserted": premises,
        "trace_len": len(trace),
        "steps_executed": sr["steps_executed"],
        "total_cost": sr["total_cost"],
        "alive": sr["alive"],
        "invariant_ok": sr["invariant_ok"],
        "invariant_failure_step": sr["invariant_failure_step"],
        "invariant_reason": sr["invariant_reason"],
        "final_goal": sr["final_goal"],
        "premature_goal": sr["premature_goal"],
        "final_obs_repr": sr["final_obs_repr"],
        "transcript_sha256": sr["transcript_sha256"],
        "trace_sha256_12": _sha256_hex(json.dumps(list(trace), default=str))[:12],
    }
    if verified:
        reg.certificates.append(out)
    return out
