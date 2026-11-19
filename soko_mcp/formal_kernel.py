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

# Builtins that can return floats from exact inputs (pow(2, -1) == 0.5).
_FLOAT_PRODUCING_NAMES: Set[str] = {"pow", "float", "complex"}

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
        if isinstance(node, ast.ClassDef):
            raise ValueError(f"[{label}] Class definitions are forbidden inside formal modules.")
        if isinstance(node, ast.FunctionDef) and node.name.startswith("__"):
            raise ValueError(f"[{label}] Dunder function name {node.name!r} is forbidden inside formal modules.")
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
            if isinstance(node, (ast.BinOp, ast.AugAssign)) and isinstance(node.op, ast.Pow):
                exponent = node.right if isinstance(node, ast.BinOp) else node.value
                if not (
                    isinstance(exponent, ast.Constant)
                    and isinstance(exponent.value, int)
                    and not isinstance(exponent.value, bool)
                    and exponent.value >= 0
                ):
                    raise ValueError(
                        f"[{label}] '**' with a negative or non-literal exponent rejected under "
                        "exact_arithmetic_only=True (int ** -k and Fraction ** non-integer produce floats)."
                    )
            if isinstance(node, ast.Name) and node.id in _FLOAT_PRODUCING_NAMES:
                raise ValueError(
                    f"[{label}] Float-producing builtin {node.id!r} rejected under exact_arithmetic_only=True."
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
        "predicates",
        "projections",
        "features",
        "goal_rhs",
        "dual_y",
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


def _require_exact_number(val: Any, ctx: str, exact_only: bool = True) -> Any:
    """Fail closed unless `val` is an exact int or Fraction (finite float only when not exact_only)."""
    if type(val) is int or type(val) is Fraction:
        return val
    if type(val) is float:
        if exact_only:
            raise TypeError(f"[{ctx}] Float potential {val!r} forbidden under exact_arithmetic_only=True.")
        if not math.isfinite(val):
            raise TypeError(f"[{ctx}] Non-finite potential {val!r} rejected (NaN/inf comparisons are unsound).")
        return val
    raise TypeError(f"[{ctx}] Potential must be exact int or Fraction, got {type(val).__name__}.")


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
        if type(c) is not int or c < 0:
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
        pos_results.append({
            "name": wname,
            "steps": sr["steps_executed"],
            "cost": sr["total_cost"],
            "transcript_sha256": sr["transcript_sha256"],
            "transcript_sha256_12": sr["transcript_sha256"][:12],
        })

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
    seen_pairs: Set[Tuple[Any, Any]] = {(s0, u0)}
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
            goal_ns = spec.is_goal(ns)
            goal_nu = impl.is_goal(nu)
            if goal_ns != goal_nu:
                return {
                    "epistemic_status": "REJECTED_DIFFERENTIAL_MISMATCH",
                    "tcb_locked": False,
                    "system_id": sid,
                    "diverging_trace": [_canonical_repr(a) for a in path + (act,)],
                    "spec_goal": goal_ns,
                    "impl_goal": goal_nu,
                    "reason": "successor goal predicate mismatch (not masked by duplicate project_obs)",
                }
            inv_ns, rsn_ns = spec.invariant(ns)
            inv_nu, rsn_nu = impl.invariant(nu)
            acts_ns = spec.actions(ns)
            acts_nu = impl.actions(nu)
            if inv_ns != inv_nu or set(acts_ns) != set(acts_nu):
                return {
                    "epistemic_status": "REJECTED_DIFFERENTIAL_MISMATCH",
                    "tcb_locked": False,
                    "system_id": sid,
                    "diverging_trace": [_canonical_repr(a) for a in path + (act,)],
                    "spec_inv_actions": [inv_ns, rsn_ns, sorted(_canonical_repr(a) for a in acts_ns)],
                    "impl_inv_actions": [inv_nu, rsn_nu, sorted(_canonical_repr(a) for a in acts_nu)],
                    "reason": "successor invariant or action-set mismatch (checked on every edge, not masked by project_obs)",
                }
            pair_next = (ns, nu)
            if pair_next not in seen_pairs and len(seen_pairs) < max(1, int(bounded_fuzz_nodes)):
                seen_pairs.add(pair_next)
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


def _is_sha256_hex(val: Any) -> bool:
    if not isinstance(val, str) or len(val) != 64:
        return False
    return all(ch in "0123456789abcdef" for ch in val.lower())


def _check_dual_state_parity(
    system_id: str,
    spec: Any,
    impl: Any,
    sc: Any,
    uc: Any,
    path: Sequence[Any],
) -> Optional[Dict[str, Any]]:
    """Verify full SPEC/IMPL state agreement (observation, invariant, goal, legal action set)."""
    obs_s = spec.project_obs(sc)
    obs_u = impl.project_obs(uc)
    inv_s, rsn_s = spec.invariant(sc)
    inv_u, rsn_u = impl.invariant(uc)
    goal_s = spec.is_goal(sc)
    goal_u = impl.is_goal(uc)
    acts_s = spec.actions(sc)
    acts_u = impl.actions(uc)
    if (
        obs_s != obs_u
        or inv_s != inv_u
        or goal_s != goal_u
        or set(acts_s) != set(acts_u)
    ):
        return {
            "epistemic_status": "REJECTED_DIFFERENTIAL_MISMATCH",
            "system_id": system_id,
            "diverging_trace": [_canonical_repr(a) for a in path],
            "spec_obs": _canonical_repr(obs_s),
            "impl_obs": _canonical_repr(obs_u),
            "spec_goal_inv": [goal_s, inv_s, rsn_s],
            "impl_goal_inv": [goal_u, inv_u, rsn_u],
        }
    return None


def _verify_reachable_dual_parity(
    system_id: str,
    spec: Any,
    impl: Any,
    check_step_cost: bool = True,
    max_pairs: int = 100000,
) -> Optional[Dict[str, Any]]:
    """Verify SPEC/IMPL parity across the reachable state space from (s0, u0)."""
    s0 = spec.initial_state()
    u0 = impl.initial_state()
    q: deque[Tuple[Any, Any, Tuple[Any, ...]]] = deque([(s0, u0, ())])
    visited_pairs: Set[Tuple[Any, Any]] = {(s0, u0)}
    while q:
        sc, uc, path = q.popleft()
        mismatch = _check_dual_state_parity(system_id, spec, impl, sc, uc, path)
        if mismatch is not None:
            return mismatch
        for act in spec.actions(sc):
            ns = spec.step(sc, act)
            nu = impl.step(uc, act)
            npath = path + (act,)
            if (ns is None) != (nu is None):
                return {
                    "epistemic_status": "REJECTED_STEP_SURVIVAL_DIVERGENCE",
                    "system_id": system_id,
                    "diverging_trace": [_canonical_repr(a) for a in npath],
                }
            if ns is None:
                continue
            if check_step_cost:
                cs = spec.step_cost(sc, act, ns)
                cu = impl.step_cost(uc, act, nu)
                if cs != cu:
                    return {
                        "epistemic_status": "REJECTED_TRANSITION_DIVERGENCE",
                        "system_id": system_id,
                        "diverging_trace": [_canonical_repr(a) for a in npath],
                        "spec_step_cost": cs,
                        "impl_step_cost": cu,
                    }
            next_mismatch = _check_dual_state_parity(system_id, spec, impl, ns, nu, npath)
            if next_mismatch is not None:
                return next_mismatch
            pair = (ns, nu)
            if pair not in visited_pairs:
                if len(visited_pairs) >= max_pairs:
                    return {
                        "epistemic_status": "REJECTED_INCOMPLETE_DUAL_PARITY_CHECK",
                        "system_id": system_id,
                        "pairs_checked": len(visited_pairs),
                        "reason": f"Reachable dual-checker state pairs exceeded cap={max_pairs}.",
                    }
                visited_pairs.add(pair)
                q.append((ns, nu, npath))
    return None


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


def _window_lns_shortcut_formal(
    chk: CompiledChecker,
    seed_trace: List[Any],
    window_len: int = 8,
    max_window_states: int = 12000,
) -> List[Any]:
    """Domain-general exact sliding-window Dijkstra trajectory optimizer."""
    best = [_json_safe_action(a) for a in seed_trace]
    improved = True
    while improved:
        improved = False
        traj_states = [chk.initial_state()]
        traj_costs = [0]
        for act in best:
            ns = chk.step(traj_states[-1], act)
            if ns is None:
                return best
            c = chk.step_cost(traj_states[-1], act, ns)
            traj_states.append(ns)
            traj_costs.append(traj_costs[-1] + c)

        n = len(best)
        total_cost = traj_costs[-1]
        stride = max(1, window_len // 2)
        for left in range(0, n, stride):
            if improved:
                break
            right = min(n, left + window_len)
            if right - left < 2:
                continue
            targets: Dict[Any, int] = {}
            for k in range(left + 1, right + 1):
                targets[traj_states[k]] = k

            start_s = traj_states[left]
            max_sub_cost = (traj_costs[right] - traj_costs[left]) - 1
            if max_sub_cost < 0:
                continue

            pq_counter = 0
            pq: List[Tuple[int, int, Any, Tuple[Any, ...]]] = [(0, 0, start_s, ())]
            best_g: Dict[Any, int] = {start_s: 0}

            while pq and len(best_g) < max_window_states:
                g, _, cur_s, sub_path = heapq.heappop(pq)
                if g > best_g.get(cur_s, g):
                    continue
                for act in chk.actions(cur_s):
                    ns = chk.step(cur_s, act)
                    if ns is None:
                        continue
                    ok_inv, _ = chk.invariant(ns)
                    if not ok_inv:
                        continue
                    ng = g + chk.step_cost(cur_s, act, ns)
                    npath = sub_path + (act,)
                    if chk.is_goal(ns) and (traj_costs[left] + ng < total_cost):
                        best = best[:left] + list(npath)
                        improved = True
                        break
                    if ns in targets:
                        tk = targets[ns]
                        orig_seg_cost = traj_costs[tk] - traj_costs[left]
                        if ng < orig_seg_cost and not chk.is_goal(ns):
                            best = best[:left] + list(npath) + best[tk:]
                            improved = True
                            break
                    if ng <= max_sub_cost and (ns not in best_g or ng < best_g[ns]) and not chk.is_goal(ns):
                        best_g[ns] = ng
                        pq_counter += 1
                        heapq.heappush(pq, (ng, pq_counter, ns, npath))
                if improved:
                    break
    return best


def solve_formal_system(
    system_id: str,
    mode: str = "reach_goal",
    strategy: str = "exact_dijkstra",
    max_states: int = 50000,
    max_cost: int = 1000,
    beam_width: int = 2000,
    bucket_cap: int = 50,
    seed_trace: Optional[Sequence[Any]] = None,
    window_len: int = 8,
) -> Dict[str, Any]:
    """Solve, model-check, or trajectory-optimize any locked formal system with mandatory dual-checker verification."""
    reg = _get_locked_system(system_id)
    spec = reg.spec
    impl = reg.impl

    if mode == "optimize_trace":
        if not seed_trace:
            raise ValueError("seed_trace is required when mode='optimize_trace'")
        base_ver = verify_formal_trace(system_id, seed_trace, verification_goal="goal_witness")
        if not base_ver["verified"]:
            raise ValueError("seed_trace failed dual-checker goal verification before optimization")
        shortened = _window_lns_shortcut_formal(spec, list(seed_trace), window_len=window_len)
        opt_ver = verify_formal_trace(system_id, shortened, verification_goal="goal_witness")
        if not opt_ver["verified"]:
            raise RuntimeError("Window LNS candidate failed dual-checker verification (fail-closed)!")
        return {
            "epistemic_status": "VERIFIED",
            "system_id": reg.system_id,
            "mode": mode,
            "initial_steps": base_ver["steps_executed"],
            "initial_cost": base_ver["total_cost"],
            "best_steps": opt_ver["steps_executed"],
            "best_cost": opt_ver["total_cost"],
            "cost_saved": base_ver["total_cost"] - opt_ver["total_cost"],
            "improved": opt_ver["total_cost"] < base_ver["total_cost"] or opt_ver["steps_executed"] < base_ver["steps_executed"],
            "trace": shortened,
            "verification": opt_ver,
        }

    if mode not in ("reach_goal", "find_invariant_violation"):
        raise ValueError(f"Unsupported mode {mode!r}; expected 'reach_goal', 'find_invariant_violation', or 'optimize_trace'")

    if strategy == "exact_dijkstra":
        s0 = spec.initial_state()
        u0 = impl.initial_state()
        counter = 0
        pq: List[Tuple[int, int, Any, Any, Tuple[Any, ...]]] = [(0, 0, s0, u0, ())]
        best_g: Dict[Tuple[Any, Any], int] = {(s0, u0): 0}
        seen_spec_states: Set[Any] = {s0}
        truncated_by_budget = False
        # Smallest cost-to-reach among successors dropped by the max_states budget. A goal popped
        # at cost g is optimal only if g <= this value (pruning by max_cost drops only paths with
        # cost > max_cost >= g, so it cannot hide a cheaper goal).
        min_state_pruned_g: Optional[int] = None
        edges_checked = 0

        while pq:
            g, _, s_cur, u_cur, path = heapq.heappop(pq)
            pair_cur = (s_cur, u_cur)
            if g > best_g.get(pair_cur, g):
                continue

            mismatch = _check_dual_state_parity(reg.system_id, spec, impl, s_cur, u_cur, path)
            if mismatch is not None:
                return mismatch

            inv_ok, inv_reason = spec.invariant(s_cur)
            if mode == "find_invariant_violation" and not inv_ok:
                ver = verify_formal_trace(system_id, path, verification_goal="invariant_counterexample", require_exact_terminal_goal=False)
                return {
                    "epistemic_status": ver["epistemic_status"],
                    "system_id": reg.system_id,
                    "mode": mode,
                    "counterexample_found": True,
                    "invariant_reason": inv_reason,
                    "steps": len(path),
                    "total_cost": g,
                    "states_explored": len(seen_spec_states),
                    "trace": list(path),
                    "verification": ver,
                }

            if mode == "reach_goal" and inv_ok and spec.is_goal(s_cur):
                ver = verify_formal_trace(system_id, path, verification_goal="goal_witness", require_exact_terminal_goal=True)
                if min_state_pruned_g is not None and min_state_pruned_g < g:
                    # A state dropped by the max_states budget could lead to a cheaper goal.
                    return {
                        "epistemic_status": "VERIFIED_FEASIBLE_NOT_PROVEN_OPTIMAL" if ver["verified"] else "REJECTED",
                        "certificate_kind": None,
                        "system_id": reg.system_id,
                        "mode": mode,
                        "solved": ver["verified"],
                        "optimal_cost": None,
                        "best_found_cost": g,
                        "unexplored_lower_bound": min_state_pruned_g,
                        "truncated_by_budget": True,
                        "steps": len(path),
                        "states_explored": len(seen_spec_states),
                        "edges_checked": edges_checked,
                        "trace": list(path),
                        "verification": ver,
                    }
                # Since Dijkstra expands states in non-decreasing exact integer step_cost >= 0,
                # the first valid goal popped is guaranteed minimum-cost!
                cert_out = {
                    "epistemic_status": "PROVEN" if ver["verified"] else "REJECTED",
                    "certificate_kind": "EXACT_DIJKSTRA_OPTIMUM",
                    "system_id": reg.system_id,
                    "mode": mode,
                    "solved": ver["verified"],
                    "optimal_cost": g,
                    "steps": len(path),
                    "states_explored": len(seen_spec_states),
                    "edges_checked": edges_checked,
                    "trace": list(path),
                    "verification": ver,
                }
                if ver["verified"]:
                    reg.certificates.append(cert_out)
                return cert_out

            if mode == "reach_goal" and not inv_ok:
                continue

            for act in spec.actions(s_cur):
                ns = spec.step(s_cur, act)
                nu = impl.step(u_cur, act)
                npath = path + (act,)
                edges_checked += 1
                if (ns is None) != (nu is None):
                    return {
                        "epistemic_status": "REJECTED_STEP_SURVIVAL_DIVERGENCE",
                        "system_id": reg.system_id,
                        "diverging_trace": [_canonical_repr(a) for a in npath],
                    }
                if ns is None:
                    continue
                step_c = spec.step_cost(s_cur, act, ns)
                impl_c = impl.step_cost(u_cur, act, nu)
                if step_c != impl_c:
                    return {
                        "epistemic_status": "REJECTED_TRANSITION_DIVERGENCE",
                        "system_id": reg.system_id,
                        "diverging_trace": [_canonical_repr(a) for a in npath],
                        "spec_step_cost": step_c,
                        "impl_step_cost": impl_c,
                    }
                next_mismatch = _check_dual_state_parity(reg.system_id, spec, impl, ns, nu, npath)
                if next_mismatch is not None:
                    return next_mismatch
                ng = g + step_c
                if ng > max_cost:
                    truncated_by_budget = True
                    continue
                pair_next = (ns, nu)
                if pair_next not in best_g or ng < best_g[pair_next]:
                    if pair_next not in best_g and len(best_g) >= max_states:
                        truncated_by_budget = True
                        if min_state_pruned_g is None or ng < min_state_pruned_g:
                            min_state_pruned_g = ng
                        continue
                    best_g[pair_next] = ng
                    seen_spec_states.add(ns)
                    counter += 1
                    heapq.heappush(pq, (ng, counter, ns, nu, npath))

        if not truncated_by_budget:
            # Complete reachable state space exhausted across BOTH SPEC and IMPL!
            cert_unreach = {
                "epistemic_status": "PROVEN",
                "certificate_kind": (
                    "EXHAUSTIVE_GLOBAL_SAFETY_PROOF"
                    if mode == "find_invariant_violation"
                    else "EXHAUSTIVE_GOAL_UNREACHABILITY_PROOF"
                ),
                "system_id": reg.system_id,
                "mode": mode,
                "solved": False,
                "counterexample_found": False,
                "complete_state_space_exhausted": True,
                "reachable_states_verified": len(seen_spec_states),
                "transitions_verified": edges_checked,
                "checker_pins": {
                    "spec_sha256": spec.code_sha256,
                    "impl_sha256": impl.code_sha256,
                    "formal_kernel_sha256": kernel_sha256(),
                },
            }
            reg.certificates.append(cert_unreach)
            return cert_unreach

        return {
            "epistemic_status": "UNSOLVED_WITHIN_BUDGET",
            "system_id": reg.system_id,
            "mode": mode,
            "solved": False,
            "counterexample_found": False,
            "complete_state_space_exhausted": False,
            "states_explored": len(seen_spec_states),
            "edges_checked": edges_checked,
        }

    if strategy == "diversified_beam":
        s0 = spec.initial_state()
        frontier: List[Tuple[int, Any, Tuple[Any, ...]]] = [(0, s0, ())]
        seen: Set[Any] = {s0}
        for _depth in range(1, max_cost + 1):
            candidates: List[Tuple[int, int, Any, Any, Tuple[Any, ...]]] = []
            c_idx = 0
            for g, s_cur, path in frontier:
                for act in spec.actions(s_cur):
                    ns = spec.step(s_cur, act)
                    if ns is None:
                        continue
                    inv_ok, inv_reason = spec.invariant(ns)
                    ng = g + spec.step_cost(s_cur, act, ns)
                    npath = path + (act,)
                    if mode == "find_invariant_violation" and not inv_ok:
                        ver = verify_formal_trace(system_id, npath, verification_goal="invariant_counterexample", require_exact_terminal_goal=False)
                        return {
                            "epistemic_status": ver["epistemic_status"],
                            "system_id": reg.system_id,
                            "mode": mode,
                            "counterexample_found": True,
                            "invariant_reason": inv_reason,
                            "steps": len(npath),
                            "total_cost": ng,
                            "trace": list(npath),
                            "verification": ver,
                        }
                    if not inv_ok:
                        continue
                    if mode == "reach_goal" and spec.is_goal(ns):
                        polished = _window_lns_shortcut_formal(spec, list(npath), window_len=window_len)
                        ver = verify_formal_trace(system_id, polished, verification_goal="goal_witness", require_exact_terminal_goal=True)
                        return {
                            "epistemic_status": ver["epistemic_status"],
                            "system_id": reg.system_id,
                            "mode": mode,
                            "solved": ver["verified"],
                            "total_cost": ver["total_cost"],
                            "steps": ver["steps_executed"],
                            "states_explored": len(seen),
                            "trace": polished,
                            "verification": ver,
                        }
                    if ns in seen or len(seen) >= max_states:
                        continue
                    seen.add(ns)
                    score = ng + spec.heuristic(ns)
                    c_idx += 1
                    candidates.append((score, c_idx, spec.bucket(ns), ns, npath, ng))  # type: ignore[arg-type]

            if not candidates:
                break
            candidates.sort(key=lambda item: (item[0], item[1]))
            b_counts: Dict[Any, int] = {}
            nxt_frontier: List[Tuple[int, Any, Tuple[Any, ...]]] = []
            used_flags = [False] * len(candidates)
            for idx_c, item in enumerate(candidates):
                if len(nxt_frontier) >= beam_width:
                    break
                bkt = item[2]
                b_counts[bkt] = b_counts.get(bkt, 0) + 1
                if b_counts[bkt] <= bucket_cap:
                    used_flags[idx_c] = True
                    nxt_frontier.append((item[5], item[3], item[4]))  # type: ignore[index]
            for idx_c, item in enumerate(candidates):
                if len(nxt_frontier) >= beam_width:
                    break
                if not used_flags[idx_c]:
                    nxt_frontier.append((item[5], item[3], item[4]))  # type: ignore[index]
            frontier = nxt_frontier

        return {
            "epistemic_status": "UNSOLVED_WITHIN_BUDGET",
            "system_id": reg.system_id,
            "mode": mode,
            "solved": False,
            "states_explored": len(seen),
        }

    raise ValueError(f"Unsupported strategy {strategy!r}; use 'exact_dijkstra' or 'diversified_beam'")


def certify_formal_lower_bound(
    system_id: str,
    proof_mode: str,
    certificate_code: str,
    claimed_lower_bound: int,
    max_concrete_states: int = 100000,
    universe_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Machine-check a lower bound (`OPT >= B`) via Quotient Homomorphism or Inductive Potential Certificate."""
    if type(claimed_lower_bound) is not int:
        raise TypeError(f"claimed_lower_bound must be an exact int, got {type(claimed_lower_bound).__name__}")
    reg = _get_locked_system(system_id)
    spec = reg.spec
    impl = reg.impl

    tree, cert_skel = validate_pure_ast(certificate_code, f"{system_id}.CERT", exact_arithmetic_only=reg.exact_only)
    cert_ns: Dict[str, Any] = {"__builtins__": dict(SAFE_BUILTINS)}
    exec(compile(tree, filename=f"<{system_id}.CERT>", mode="exec"), cert_ns, cert_ns)  # nosec
    cert_sha256 = _sha256_hex(certificate_code)

    # Enumerate concrete transitions: either via explicit `enumerate_states()` in certificate_code,
    # or via exhaustive concrete reachability from `initial_state()` across BOTH SPEC and IMPL!
    s0 = spec.initial_state()
    u0 = impl.initial_state()
    explicit_enum = cert_ns.get("enumerate_states")
    if universe_code is not None and universe_code.strip():
        u_tree, _ = validate_pure_ast(universe_code, f"{system_id}.UNIVERSE", exact_arithmetic_only=reg.exact_only)
        u_ns: Dict[str, Any] = {"__builtins__": dict(SAFE_BUILTINS)}
        exec(compile(u_tree, filename=f"<{system_id}.UNIVERSE>", mode="exec"), u_ns, u_ns)  # nosec
        if not callable(u_ns.get("enumerate_states")):
            raise ValueError("universe_code must define callable `enumerate_states()`")
        explicit_enum = u_ns["enumerate_states"]

    concrete_states: List[Any] = []
    concrete_edges: List[Tuple[Any, Any, Any, int]] = []
    complete_space = False

    if callable(explicit_enum):
        raw_states = list(explicit_enum())
        state_set = set(raw_states)
        if s0 not in state_set:
            return {
                "epistemic_status": "REJECTED_INITIAL_STATE_NOT_IN_DOMAIN",
                "system_id": reg.system_id,
                "reason": "enumerate_states() failed to contain initial_state().",
            }
        closed_ok = True
        escape_witness: Optional[Tuple[Any, Any, Any]] = None
        for st in raw_states:
            assert_exact_immutable(st, "enumerate_states", reg.exact_only)
            inv_ok, _ = spec.invariant(st)
            if not inv_ok:
                continue
            concrete_states.append(st)
            for act in spec.actions(st):
                ns = spec.step(st, act)
                if ns is None:
                    continue
                inv_n, _ = spec.invariant(ns)
                if not inv_n:
                    continue
                if ns not in state_set:
                    closed_ok = False
                    escape_witness = (st, act, ns)
                    break
                concrete_edges.append((st, act, ns, spec.step_cost(st, act, ns)))
            if not closed_ok:
                break
        if not closed_ok and escape_witness is not None:
            return {
                "epistemic_status": "REJECTED_DOMAIN_NOT_INDUCTIVELY_CLOSED",
                "system_id": reg.system_id,
                "escaping_transition": [_canonical_repr(x) for x in escape_witness],
            }
        reach_mismatch = _verify_reachable_dual_parity(
            reg.system_id,
            spec,
            impl,
            check_step_cost=True,
            max_pairs=max(max_concrete_states, len(state_set) * 2),
        )
        if reach_mismatch is not None:
            return reach_mismatch
        complete_space = True
    else:
        q: deque[Tuple[Any, Any, Tuple[Any, ...]]] = deque([(s0, u0, ())])
        visited_pairs: Set[Tuple[Any, Any]] = {(s0, u0)}
        seen_concrete: Set[Any] = {s0}
        seen_edges: Set[Tuple[Any, Any, Any, int]] = set()
        truncated = False
        while q:
            sc, uc, path = q.popleft()
            mismatch = _check_dual_state_parity(reg.system_id, spec, impl, sc, uc, path)
            if mismatch is not None:
                return mismatch
            inv_ok, _ = spec.invariant(sc)
            if not inv_ok:
                continue
            if sc not in seen_concrete or len(concrete_states) == 0 or sc not in concrete_states:
                if sc not in concrete_states:
                    concrete_states.append(sc)
            for act in spec.actions(sc):
                ns = spec.step(sc, act)
                nu = impl.step(uc, act)
                npath = path + (act,)
                if (ns is None) != (nu is None):
                    return {
                        "epistemic_status": "REJECTED_STEP_SURVIVAL_DIVERGENCE",
                        "system_id": reg.system_id,
                        "diverging_trace": [_canonical_repr(a) for a in npath],
                    }
                if ns is None:
                    continue
                next_mismatch = _check_dual_state_parity(reg.system_id, spec, impl, ns, nu, npath)
                if next_mismatch is not None:
                    return next_mismatch
                inv_n, _ = spec.invariant(ns)
                if not inv_n:
                    continue
                c = spec.step_cost(sc, act, ns)
                cu = impl.step_cost(uc, act, nu)
                if c != cu:
                    return {
                        "epistemic_status": "REJECTED_TRANSITION_DIVERGENCE",
                        "system_id": reg.system_id,
                        "diverging_trace": [_canonical_repr(a) for a in npath],
                        "spec_step_cost": c,
                        "impl_step_cost": cu,
                    }
                edge_tup = (sc, act, ns, c)
                if edge_tup not in seen_edges:
                    seen_edges.add(edge_tup)
                    concrete_edges.append(edge_tup)
                pair = (ns, nu)
                if pair not in visited_pairs:
                    if ns not in seen_concrete and len(seen_concrete) >= max_concrete_states:
                        truncated = True
                        continue
                    visited_pairs.add(pair)
                    seen_concrete.add(ns)
                    q.append((ns, nu, npath))
        complete_space = not truncated

    if proof_mode == "inductive_potential":
        raw_pot_fn = cert_ns.get("potential")
        if not callable(raw_pot_fn):
            raise ValueError("certificate_code must define `potential(state) -> int | Fraction` for proof_mode='inductive_potential'")
        pot_cache: Dict[Any, Any] = {}

        def pot_fn(state: Any) -> Any:
            if state not in pot_cache:
                pot_cache[state] = _require_exact_number(raw_pot_fn(state), "potential(state)", reg.exact_only)
            return pot_cache[state]

        if not complete_space:
            return {
                "epistemic_status": "REJECTED_INCOMPLETE_CONCRETE_GRAPH_FOR_POTENTIAL",
                "system_id": reg.system_id,
                "certified_lower_bound": None,
                "complete_domain_closed": False,
                "states_checked": len(concrete_states),
                "reason": (
                    f"Concrete reachable state space exceeded max_concrete_states={max_concrete_states}; "
                    "an inductive lower-bound potential cannot certify optimal goal cost on a truncated "
                    "subgraph because unreached transitions or goal states may violate step-consistency "
                    "or goal non-positivity. Increase max_concrete_states or supply an inductively closed "
                    "`enumerate_states()` universe."
                ),
            }

        # Check 1: Goal non-positivity: is_goal(s) => V(s) <= 0
        for st in concrete_states:
            if spec.is_goal(st):
                vs = pot_fn(st)
                if vs > 0:
                    return {
                        "epistemic_status": "REJECTED_GOAL_POTENTIAL_POSITIVE",
                        "system_id": reg.system_id,
                        "violating_goal_state": _canonical_repr(st),
                        "potential_value": str(vs),
                    }

        # Check 2: Inductive step-consistency: V(s) <= cost(s, a, s') + V(s') on EVERY transition!
        for st, act, ns, cost in concrete_edges:
            vs = pot_fn(st)
            vns = pot_fn(ns)
            rhs = cost + vns
            if type(rhs) is float and not math.isfinite(rhs):
                raise TypeError(f"[potential(state)] Non-finite edge sum {rhs!r} rejected.")
            if vs > rhs:
                return {
                    "epistemic_status": "REJECTED_STEP_CONSISTENCY_VIOLATION",
                    "system_id": reg.system_id,
                    "violating_transition": {
                        "state": _canonical_repr(st),
                        "action": _canonical_repr(act),
                        "next_state": _canonical_repr(ns),
                        "step_cost": cost,
                        "V_s": str(vs),
                        "V_next": str(vns),
                    },
                }

        v0 = pot_fn(s0)
        holds = v0 >= claimed_lower_bound
        if not holds:
            return {
                "epistemic_status": "REJECTED_INSUFFICIENT_INITIAL_POTENTIAL",
                "system_id": reg.system_id,
                "V_initial": str(v0),
                "claimed_lower_bound": claimed_lower_bound,
            }

        status = "PROVEN" if complete_space else "VERIFIED_ON_BOUNDED_REACHABLE_SUBGRAPH"
        cert_res = {
            "epistemic_status": status,
            "certificate_kind": "INDUCTIVE_POTENTIAL_LOWER_BOUND",
            "system_id": reg.system_id,
            "certified_lower_bound": claimed_lower_bound,
            "initial_potential": str(v0),
            "complete_domain_closed": complete_space,
            "states_checked": len(concrete_states),
            "edge_inequalities_checked": len(concrete_edges),
            "checker_pins": {
                "spec_sha256": spec.code_sha256,
                "impl_sha256": impl.code_sha256,
                "certificate_sha256": cert_sha256,
                "certificate_skeleton_sha256": cert_skel,
                "formal_kernel_sha256": kernel_sha256(),
            },
        }
        if complete_space:
            reg.certificates.append(cert_res)
        return cert_res

    if proof_mode == "quotient_homomorphism":
        proj_fn = cert_ns.get("project")
        if not callable(proj_fn):
            raise ValueError("certificate_code must define `project(state) -> HashableAbstractState` for proof_mode='quotient_homomorphism'")
        if not complete_space:
            return {
                "epistemic_status": "REJECTED_INCOMPLETE_CONCRETE_GRAPH_FOR_QUOTIENT",
                "system_id": reg.system_id,
                "reason": (
                    f"Concrete reachable state space exceeded max_concrete_states={max_concrete_states}; "
                    "either increase max_concrete_states or supply an inductively closed `enumerate_states()` / `inductive_potential`."
                ),
            }

        abs_rev_adj: Dict[Any, List[Tuple[Any, int]]] = {}
        abs_goals: Set[Any] = set()
        abs_nodes: Set[Any] = set()

        for st in concrete_states:
            ast_node = proj_fn(st)
            assert_exact_immutable(ast_node, "project(state)", reg.exact_only)
            abs_nodes.add(ast_node)
            if spec.is_goal(st):
                abs_goals.add(ast_node)

        for st, _act, ns, cost in concrete_edges:
            u_abs = proj_fn(st)
            v_abs = proj_fn(ns)
            abs_rev_adj.setdefault(v_abs, []).append((u_abs, cost))

        # Exact backward Dijkstra from abstract goals in Quotient Graph
        # Unreachable abstract states are simply absent from h_abs (no finite sentinel).
        h_abs: Dict[Any, int] = {g: 0 for g in abs_goals}
        pq_abs: List[Tuple[int, int, Any]] = []
        ctr = 0
        for g in abs_goals:
            ctr += 1
            heapq.heappush(pq_abs, (0, ctr, g))

        while pq_abs:
            d, _, v_abs = heapq.heappop(pq_abs)
            if d > h_abs[v_abs]:
                continue
            for u_abs, w_cost in abs_rev_adj.get(v_abs, ()):
                nd = d + w_cost
                if u_abs not in h_abs or nd < h_abs[u_abs]:
                    h_abs[u_abs] = nd
                    ctr += 1
                    heapq.heappush(pq_abs, (nd, ctr, u_abs))

        # Exhaustively machine-check concrete homomorphism step-consistency: h(pi(s)) <= cost(s,a,s') + h(pi(s'))
        for st, act, ns, cost in concrete_edges:
            hs = h_abs.get(proj_fn(st))
            hns = h_abs.get(proj_fn(ns))
            # h(pi(s)) <= cost + h(pi(s')); an unreachable successor makes the right side infinite.
            if hns is not None and (hs is None or hs > cost + hns):
                return {
                    "epistemic_status": "REJECTED_HOMOMORPHISM_INCONSISTENT",
                    "system_id": reg.system_id,
                    "violating_transition": [_canonical_repr(st), _canonical_repr(act), _canonical_repr(ns)],
                }

        h0 = h_abs.get(proj_fn(s0))
        if h0 is not None and h0 < claimed_lower_bound:
            return {
                "epistemic_status": "REJECTED_QUOTIENT_BOUND_TOO_WEAK",
                "system_id": reg.system_id,
                "quotient_initial_bound": h0,
                "claimed_lower_bound": claimed_lower_bound,
            }

        cert_q = {
            "epistemic_status": "PROVEN",
            "certificate_kind": "QUOTIENT_HOMOMORPHISM_LOWER_BOUND",
            "system_id": reg.system_id,
            "certified_lower_bound": claimed_lower_bound,
            "quotient_exact_bound": "UNREACHABLE_INF" if h0 is None else h0,
            "concrete_states_verified": len(concrete_states),
            "quotient_states": len(abs_nodes),
            "compression_ratio": round(len(concrete_states) / max(1, len(abs_nodes)), 3),
            "homomorphism_edges_verified": len(concrete_edges),
            "checker_pins": {
                "spec_sha256": spec.code_sha256,
                "impl_sha256": impl.code_sha256,
                "certificate_sha256": cert_sha256,
                "formal_kernel_sha256": kernel_sha256(),
            },
        }
        reg.certificates.append(cert_q)
        return cert_q

    if proof_mode == "cost_partitioned_quotients":
        # Inbound from Foundation-0/gfq-codes + finite-state-proofs:
        # Additive Rational Action-Cost Partitioning across M >= 2 Quotient Graph Homomorphisms
        # in exact `fractions.Fraction` arithmetic (zero floating-point LP solver in TCB!).
        proj_list_fn = cert_ns.get("projections")
        if not callable(proj_list_fn):
            raise ValueError(
                "certificate_code must define `projections() -> sequence of (name, project_fn, weight_fn)` "
                "for proof_mode='cost_partitioned_quotients'"
            )
        if not complete_space:
            return {
                "epistemic_status": "REJECTED_INCOMPLETE_CONCRETE_GRAPH_FOR_QUOTIENT",
                "system_id": reg.system_id,
                "reason": (
                    f"Concrete reachable state space exceeded max_concrete_states={max_concrete_states}; "
                    "increase max_concrete_states or supply an inductively closed `enumerate_states()`."
                ),
            }

        raw_projs = list(proj_list_fn())
        if len(raw_projs) < 2:
            raise ValueError("projections() must return at least 2 (name, project_fn, weight_fn) entries")

        parsed_projs: List[Tuple[str, Callable[[Any], Any], Callable[[Any, Any, Any], Any]]] = []
        for entry in raw_projs:
            if not isinstance(entry, (tuple, list)) or len(entry) != 3:
                raise ValueError("Each entry in projections() must be (name, project_fn, weight_fn)")
            pname, pfn, wfn = str(entry[0]), entry[1], entry[2]
            if not callable(pfn) or not callable(wfn):
                raise ValueError(f"Projection {pname!r} must supply callable project_fn(s) and weight_fn(s, a, ns)")
            parsed_projs.append((pname, pfn, wfn))

        # Step 1: Verify exact rational non-negativity and cost-partitioning sum_m w_m(s, a, s') <= cost(s, a, s')
        edge_weights_per_m: List[List[Fraction]] = [[] for _ in parsed_projs]
        for st, act, ns, cost in concrete_edges:
            w_sum = Fraction(0, 1)
            for m_idx, (pname, _pfn, wfn) in enumerate(parsed_projs):
                raw_w = wfn(st, act, ns)
                if type(raw_w) is not int and type(raw_w) is not Fraction:
                    raise TypeError(f"Weight function {pname!r} must return exact int or Fraction, got {type(raw_w).__name__}")
                wf = Fraction(raw_w)
                if wf < 0:
                    return {
                        "epistemic_status": "REJECTED_NEGATIVE_PARTITION_WEIGHT",
                        "system_id": reg.system_id,
                        "projection": pname,
                        "violating_transition": [_canonical_repr(st), _canonical_repr(act), _canonical_repr(ns)],
                        "weight": str(wf),
                    }
                edge_weights_per_m[m_idx].append(wf)
                w_sum += wf
            if w_sum > Fraction(cost, 1):
                return {
                    "epistemic_status": "REJECTED_COST_PARTITION_OVERFLOW",
                    "system_id": reg.system_id,
                    "violating_transition": [_canonical_repr(st), _canonical_repr(act), _canonical_repr(ns)],
                    "partition_weight_sum": str(w_sum),
                    "concrete_step_cost": cost,
                }

        # Step 2: Solve exact Fraction backward Dijkstra on each Quotient Graph Q_m and machine-check step consistency!
        total_exact_bound = Fraction(0, 1)
        component_reports: List[Dict[str, Any]] = []
        unreachable_any = False

        for m_idx, (pname, pfn, _wfn) in enumerate(parsed_projs):
            abs_rev: Dict[Any, List[Tuple[Any, Fraction]]] = {}
            abs_goals: Set[Any] = set()
            abs_nodes: Set[Any] = set()
            for st in concrete_states:
                an = pfn(st)
                assert_exact_immutable(an, f"{pname}.project", reg.exact_only)
                abs_nodes.add(an)
                if spec.is_goal(st):
                    abs_goals.add(an)
            for e_idx, (st, _act, ns, _cost) in enumerate(concrete_edges):
                u_a = pfn(st)
                v_a = pfn(ns)
                abs_rev.setdefault(v_a, []).append((u_a, edge_weights_per_m[m_idx][e_idx]))

            h_abs_f: Dict[Any, Fraction] = {g: Fraction(0, 1) for g in abs_goals}
            pq_f: List[Tuple[Fraction, int, Any]] = []
            ctr = 0
            for g in abs_goals:
                ctr += 1
                heapq.heappush(pq_f, (Fraction(0, 1), ctr, g))
            while pq_f:
                d_f, _, v_a = heapq.heappop(pq_f)
                if d_f > h_abs_f[v_a]:
                    continue
                for u_a, w_f in abs_rev.get(v_a, ()):
                    nd_f = d_f + w_f
                    if u_a not in h_abs_f or nd_f < h_abs_f[u_a]:
                        h_abs_f[u_a] = nd_f
                        ctr += 1
                        heapq.heappush(pq_f, (nd_f, ctr, u_a))

            for e_idx, (st, act, ns, _cost) in enumerate(concrete_edges):
                hs_f = h_abs_f.get(pfn(st))
                hns_f = h_abs_f.get(pfn(ns))
                wf = edge_weights_per_m[m_idx][e_idx]
                if hns_f is not None and (hs_f is None or hs_f > wf + hns_f):
                    return {
                        "epistemic_status": "REJECTED_HOMOMORPHISM_INCONSISTENT",
                        "system_id": reg.system_id,
                        "projection": pname,
                        "violating_transition": [_canonical_repr(st), _canonical_repr(act), _canonical_repr(ns)],
                    }

            h0_f = h_abs_f.get(pfn(s0))
            if h0_f is None:
                unreachable_any = True
            else:
                total_exact_bound += h0_f
            component_reports.append({
                "name": pname,
                "quotient_states": len(abs_nodes),
                "exact_initial_bound": "UNREACHABLE_INF" if h0_f is None else str(h0_f),
            })

        # Since all concrete step costs are integers, ceil(total_exact_bound) is a valid integer lower bound!
        if unreachable_any:
            # Some quotient cannot reach its abstract goals from pi(s0), so no concrete plan exists
            # and every finite claimed bound holds. No finite sentinel stands in for infinity.
            certified_int_bound = None
        else:
            num, den = total_exact_bound.numerator, total_exact_bound.denominator
            certified_int_bound = -(-num // den)

        if certified_int_bound is not None and certified_int_bound < claimed_lower_bound:
            return {
                "epistemic_status": "REJECTED_PARTITIONED_BOUND_TOO_WEAK",
                "system_id": reg.system_id,
                "exact_rational_sum": "UNREACHABLE_INF" if unreachable_any else str(total_exact_bound),
                "ceil_integer_bound": None if unreachable_any else certified_int_bound,
                "claimed_lower_bound": claimed_lower_bound,
                "components": component_reports,
            }

        cert_cp = {
            "epistemic_status": "PROVEN",
            "certificate_kind": "COST_PARTITIONED_QUOTIENT_LOWER_BOUND",
            "system_id": reg.system_id,
            "certified_lower_bound": claimed_lower_bound,
            "exact_rational_sum": "UNREACHABLE_INF" if unreachable_any else str(total_exact_bound),
            "ceil_integer_bound": "UNREACHABLE_INF" if unreachable_any else certified_int_bound,
            "concrete_states_verified": len(concrete_states),
            "partition_inequalities_verified": len(concrete_edges),
            "components": component_reports,
            "checker_pins": {
                "spec_sha256": spec.code_sha256,
                "impl_sha256": impl.code_sha256,
                "certificate_sha256": cert_sha256,
                "formal_kernel_sha256": kernel_sha256(),
            },
        }
        reg.certificates.append(cert_cp)
        return cert_cp

    if proof_mode == "rational_lp_dual":
        # Inbound from Foundation-0/gfq-codes (`check_bound.py` / `check_bound_independent.py`):
        # Verifies an exact `fractions.Fraction` operator-counting / state-equation Farkas dual certificate
        # (`y >= 0`, `y^T (b - F(goal)) <= 0`, `y^T (F(s') - F(s)) <= cost(s, a, s')`) with ZERO float LP solver in TCB!
        feat_fn = cert_ns.get("features")
        rhs_fn = cert_ns.get("goal_rhs")
        dual_fn = cert_ns.get("dual_y")
        if not (callable(feat_fn) and callable(rhs_fn) and callable(dual_fn)):
            raise ValueError(
                "certificate_code must define `features(state)`, `goal_rhs()`, and `dual_y()` "
                "for proof_mode='rational_lp_dual'"
            )
        if not complete_space:
            # A truncated graph has successors that were never indexed in `concrete_states`,
            # so their features cannot be checked. Reject instead of raising KeyError.
            return {
                "epistemic_status": "REJECTED_INCOMPLETE_CONCRETE_GRAPH_FOR_QUOTIENT",
                "system_id": reg.system_id,
                "reason": (
                    f"Concrete reachable state space exceeded max_concrete_states={max_concrete_states}; "
                    "increase max_concrete_states or supply an inductively closed `enumerate_states()`."
                ),
            }

        def _to_frac_vec(seq: Any, ctx_label: str) -> Tuple[Fraction, ...]:
            tup = tuple(seq)
            out_v: List[Fraction] = []
            for item in tup:
                if type(item) is not int and type(item) is not Fraction:
                    raise TypeError(f"[{ctx_label}] Expected exact int or Fraction, got {type(item).__name__}")
                out_v.append(Fraction(item))
            return tuple(out_v)

        b_vec = _to_frac_vec(rhs_fn(), "goal_rhs")
        y_vec = _to_frac_vec(dual_fn(), "dual_y")
        dim = len(y_vec)
        if dim == 0 or len(b_vec) != dim:
            raise ValueError(f"Dimension mismatch: len(dual_y)={dim} vs len(goal_rhs)={len(b_vec)}")

        for idx_y, y_i in enumerate(y_vec):
            if y_i < 0:
                return {
                    "epistemic_status": "REJECTED_NEGATIVE_DUAL_MULTIPLIER",
                    "system_id": reg.system_id,
                    "index": idx_y,
                    "dual_multiplier": str(y_i),
                }

        feat_cache: Dict[Any, Tuple[Fraction, ...]] = {}
        for st in concrete_states:
            fv = _to_frac_vec(feat_fn(st), "features")
            if len(fv) != dim:
                raise ValueError(f"features(state) length {len(fv)} != dual dimension {dim}")
            feat_cache[st] = fv
            if spec.is_goal(st):
                # Goal condition: y^T (b - F(g)) <= 0 so V(g) = y^T (b - F(g)) <= 0!
                v_goal = sum((y_vec[i] * (b_vec[i] - fv[i]) for i in range(dim)), Fraction(0, 1))
                if v_goal > 0:
                    return {
                        "epistemic_status": "REJECTED_DUAL_GOAL_VIOLATION",
                        "system_id": reg.system_id,
                        "violating_goal_state": _canonical_repr(st),
                        "dual_goal_value": str(v_goal),
                    }

        # Dual feasibility on every concrete operator transition: y^T (F(s') - F(s)) <= cost(s, a, s')
        # (equivalently V(s) - V(s') <= cost(s, a, s') where V(s) = y^T (b - F(s)))!
        for st, act, ns, cost in concrete_edges:
            fs = feat_cache[st]
            fns = feat_cache[ns]
            lhs = sum((y_vec[i] * (fns[i] - fs[i]) for i in range(dim)), Fraction(0, 1))
            if lhs > Fraction(cost, 1):
                return {
                    "epistemic_status": "REJECTED_DUAL_OPERATOR_INFEASIBLE",
                    "system_id": reg.system_id,
                    "violating_transition": [_canonical_repr(st), _canonical_repr(act), _canonical_repr(ns)],
                    "dual_gain": str(lhs),
                    "step_cost": cost,
                }

        f0 = feat_cache[s0]
        v0_exact = sum((y_vec[i] * (b_vec[i] - f0[i]) for i in range(dim)), Fraction(0, 1))
        ceil_v0 = -(-v0_exact.numerator // v0_exact.denominator)
        if ceil_v0 < claimed_lower_bound:
            return {
                "epistemic_status": "REJECTED_DUAL_OBJECTIVE_TOO_WEAK",
                "system_id": reg.system_id,
                "exact_dual_objective": str(v0_exact),
                "ceil_integer_bound": ceil_v0,
                "claimed_lower_bound": claimed_lower_bound,
            }

        status_lp = "PROVEN" if complete_space else "VERIFIED_ON_BOUNDED_REACHABLE_SUBGRAPH"
        cert_lp = {
            "epistemic_status": status_lp,
            "certificate_kind": "RATIONAL_LP_DUAL_FARKAS_LOWER_BOUND",
            "system_id": reg.system_id,
            "certified_lower_bound": claimed_lower_bound,
            "exact_dual_objective": str(v0_exact),
            "ceil_integer_bound": ceil_v0,
            "dual_dimension": dim,
            "dual_multipliers": [str(y) for y in y_vec],
            "complete_domain_closed": complete_space,
            "states_checked": len(concrete_states),
            "operator_inequalities_checked": len(concrete_edges),
            "checker_pins": {
                "spec_sha256": spec.code_sha256,
                "impl_sha256": impl.code_sha256,
                "certificate_sha256": cert_sha256,
                "certificate_skeleton_sha256": cert_skel,
                "formal_kernel_sha256": kernel_sha256(),
            },
        }
        if complete_space:
            reg.certificates.append(cert_lp)
        return cert_lp

    raise ValueError(
        f"Unsupported proof_mode {proof_mode!r}; use 'quotient_homomorphism', 'inductive_potential', "
        "'cost_partitioned_quotients', or 'rational_lp_dual'"
    )


def synthesize_formal_invariant(
    system_id: str,
    candidates_code: str,
    synthesis_mode: str = "houdini_safety",
    universe_code: Optional[str] = None,
    max_concrete_states: int = 100000,
) -> Dict[str, Any]:
    """Synthesize and machine-check maximal inductive invariants (`houdini_safety`) or deadlock traps (`deadlock_trap`)."""
    reg = _get_locked_system(system_id)
    spec = reg.spec
    impl = reg.impl

    c_tree, cand_skel = validate_pure_ast(candidates_code, f"{system_id}.SYNTH", exact_arithmetic_only=reg.exact_only)
    cand_ns: Dict[str, Any] = {"__builtins__": dict(SAFE_BUILTINS)}
    exec(compile(c_tree, filename=f"<{system_id}.SYNTH>", mode="exec"), cand_ns, cand_ns)  # nosec
    cand_sha256 = _sha256_hex(candidates_code)

    pred_fn = cand_ns.get("predicates")
    if not callable(pred_fn):
        raise ValueError("candidates_code must define `predicates() -> dict[str, Callable[[state], bool]]`")
    raw_preds = pred_fn()
    if isinstance(raw_preds, dict):
        pred_items: List[Tuple[str, Callable[[Any], Any]]] = [(str(k), v) for k, v in raw_preds.items()]
    elif isinstance(raw_preds, (tuple, list)):
        pred_items = [(str(k), v) for k, v in raw_preds]
    else:
        raise ValueError("predicates() must return a dict or sequence of (name, callable) pairs")
    if not pred_items or not all(callable(fn) for _, fn in pred_items):
        raise ValueError("predicates() must contain at least one callable predicate")

    explicit_enum = cand_ns.get("enumerate_states")
    universe_sha256: Optional[str] = None
    if universe_code is not None and universe_code.strip():
        u_tree, _ = validate_pure_ast(universe_code, f"{system_id}.UNIVERSE", exact_arithmetic_only=reg.exact_only)
        u_ns: Dict[str, Any] = {"__builtins__": dict(SAFE_BUILTINS)}
        exec(compile(u_tree, filename=f"<{system_id}.UNIVERSE>", mode="exec"), u_ns, u_ns)  # nosec
        if not callable(u_ns.get("enumerate_states")):
            raise ValueError("universe_code must define callable `enumerate_states()`")
        explicit_enum = u_ns["enumerate_states"]
        universe_sha256 = _sha256_hex(universe_code)

    s0 = spec.initial_state()
    u0 = impl.initial_state()
    concrete_states: List[Any] = []
    concrete_edges: List[Tuple[Any, Any, Any]] = []
    complete_space = False
    universal_domain = False

    if callable(explicit_enum):
        universal_domain = True
        raw_states = list(explicit_enum())
        state_set = set(raw_states)
        if s0 not in state_set:
            return {
                "epistemic_status": "REJECTED_INITIAL_STATE_NOT_IN_DOMAIN",
                "system_id": reg.system_id,
                "reason": "enumerate_states() failed to contain initial_state().",
            }
        for st in raw_states:
            assert_exact_immutable(st, "enumerate_states", reg.exact_only)
            concrete_states.append(st)
            for act in spec.actions(st):
                ns = spec.step(st, act)
                if ns is None:
                    continue
                if ns not in state_set:
                    return {
                        "epistemic_status": "REJECTED_DOMAIN_NOT_INDUCTIVELY_CLOSED",
                        "system_id": reg.system_id,
                        "escaping_transition": [_canonical_repr(st), _canonical_repr(act), _canonical_repr(ns)],
                    }
                concrete_edges.append((st, act, ns))
        reach_mismatch = _verify_reachable_dual_parity(
            reg.system_id,
            spec,
            impl,
            check_step_cost=False,
            max_pairs=max(max_concrete_states, len(state_set) * 2),
        )
        if reach_mismatch is not None:
            return reach_mismatch
        complete_space = True
    else:
        q: deque[Tuple[Any, Any, Tuple[Any, ...]]] = deque([(s0, u0, ())])
        visited_pairs: Set[Tuple[Any, Any]] = {(s0, u0)}
        seen_concrete: Set[Any] = {s0}
        seen_edges: Set[Tuple[Any, Any, Any]] = set()
        truncated = False
        while q:
            sc, uc, path = q.popleft()
            mismatch = _check_dual_state_parity(reg.system_id, spec, impl, sc, uc, path)
            if mismatch is not None:
                return mismatch
            if sc not in concrete_states:
                concrete_states.append(sc)
            for act in spec.actions(sc):
                ns = spec.step(sc, act)
                nu = impl.step(uc, act)
                npath = path + (act,)
                if (ns is None) != (nu is None):
                    return {
                        "epistemic_status": "REJECTED_STEP_SURVIVAL_DIVERGENCE",
                        "system_id": reg.system_id,
                        "diverging_trace": [_canonical_repr(a) for a in npath],
                    }
                if ns is None:
                    continue
                next_mismatch = _check_dual_state_parity(reg.system_id, spec, impl, ns, nu, npath)
                if next_mismatch is not None:
                    return next_mismatch
                edge_tup = (sc, act, ns)
                if edge_tup not in seen_edges:
                    seen_edges.add(edge_tup)
                    concrete_edges.append(edge_tup)
                pair = (ns, nu)
                if pair not in visited_pairs:
                    if ns not in seen_concrete and len(seen_concrete) >= max_concrete_states:
                        truncated = True
                        continue
                    visited_pairs.add(pair)
                    seen_concrete.add(ns)
                    q.append((ns, nu, npath))
        complete_space = not truncated

    state_idx = {st: i for i, st in enumerate(concrete_states)}
    num_states = len(concrete_states)
    num_preds = len(pred_items)

    # Pre-evaluate boolean truth table [pred_i][state_j] deterministically
    truth: List[List[bool]] = []
    for pname, pfn in pred_items:
        row: List[bool] = []
        for st in concrete_states:
            val = pfn(st)
            if not isinstance(val, bool):
                raise TypeError(f"Predicate {pname!r} must return bool, got {type(val).__name__}")
            row.append(val)
        truth.append(row)

    # A capped traversal can contain edges to successors that were not admitted.
    # Those edges do not belong to the explored subgraph and must not be
    # mistaken for checked induction obligations.
    open_edges = sum(ns not in state_idx for _, _, ns in concrete_edges)
    idx_edges = [(state_idx[s], act, state_idx[ns]) for s, act, ns in concrete_edges if ns in state_idx]
    proof_scope = ("enumerated_closed_domain" if universal_domain else
                   "complete_reachable_states" if complete_space else "explored_reachable_subgraph")
    s0_idx = state_idx[s0]

    if synthesis_mode == "houdini_safety":
        active: Set[int] = set(range(num_preds))
        refuted: List[Dict[str, Any]] = []
        for pid in sorted(list(active)):
            if not truth[pid][s0_idx]:
                active.remove(pid)
                refuted.append({
                    "predicate": pred_items[pid][0],
                    "reason": "falsified_at_initial_state",
                    "round": 0,
                })

        rounds = 0
        changed = True
        while changed and active:
            changed = False
            rounds += 1
            for u_i, act, v_i in idx_edges:
                if all(truth[p][u_i] for p in active):
                    drop_now = [p for p in sorted(active) if not truth[p][v_i]]
                    for p in drop_now:
                        active.remove(p)
                        changed = True
                        refuted.append({
                            "predicate": pred_items[p][0],
                            "reason": "inductive_step_violation",
                            "round": rounds,
                            "transition": [
                                _canonical_repr(concrete_states[u_i]),
                                _canonical_repr(act),
                                _canonical_repr(concrete_states[v_i]),
                            ],
                        })

        active_names = [pred_items[p][0] for p in sorted(active)]
        inductive_states = [i for i in range(num_states) if all(truth[p][i] for p in active)]
        implies_target = True
        violating_witness: Optional[str] = None
        for i in inductive_states:
            inv_ok, _ = spec.invariant(concrete_states[i])
            if not inv_ok:
                implies_target = False
                if violating_witness is None:
                    violating_witness = _canonical_repr(concrete_states[i])

        if complete_space and implies_target:
            epistemic = "PROVEN"
        elif complete_space:
            epistemic = "VERIFIED_INDUCTIVE_LEMMA_TOO_WEAK_FOR_TARGET"
        else:
            epistemic = "VERIFIED_ON_BOUNDED_REACHABLE_SUBGRAPH"

        cert_h = {
            "epistemic_status": epistemic,
            "certificate_kind": "HOUDINI_INDUCTIVE_SAFETY_INVARIANT",
            "system_id": reg.system_id,
            "synthesis_mode": synthesis_mode,
            "universal_domain_induction": universal_domain,
            "complete_domain_closed": complete_space,
            "proof_scope": proof_scope,
            "open_transitions": open_edges,
            "implies_target_invariant": implies_target,
            "unexcluded_bad_state_sample": violating_witness,
            "synthesized_conjuncts": active_names,
            "conjuncts_retained": len(active_names),
            "conjuncts_refuted": len(refuted),
            "refuted_details": refuted[:16],
            "fixpoint_rounds": rounds,
            "states_checked": num_states,
            "transitions_checked": len(idx_edges),
            "inductive_subspace_size": len(inductive_states),
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
            reg.certificates.append(cert_h)
        return cert_h

    if synthesis_mode == "deadlock_trap":
        goal_flags = [spec.is_goal(st) for st in concrete_states]
        active_t: Set[int] = set(range(num_preds))
        refuted_t: List[Dict[str, Any]] = []

        # Step 1: No trap predicate may hold on any goal state
        for pid in sorted(list(active_t)):
            bad_goal = next((i for i in range(num_states) if truth[pid][i] and goal_flags[i]), None)
            if bad_goal is not None:
                active_t.remove(pid)
                refuted_t.append({
                    "predicate": pred_items[pid][0],
                    "reason": "holds_on_goal_state",
                    "goal_state": _canonical_repr(concrete_states[bad_goal]),
                    "round": 0,
                })

        # Step 2: Greatest fixed point of forward trap-union closure: T_p(s) => OR_{q in active_t} T_q(ns)
        rounds = 0
        changed = True
        while changed and active_t:
            changed = False
            rounds += 1
            in_union = [any(truth[q][i] for q in active_t) for i in range(num_states)]
            for u_i, act, v_i in idx_edges:
                if in_union[u_i] and not in_union[v_i]:
                    drop_now = [p for p in sorted(active_t) if truth[p][u_i]]
                    for p in drop_now:
                        active_t.remove(p)
                        changed = True
                        refuted_t.append({
                            "predicate": pred_items[p][0],
                            "reason": "trap_escaped_on_transition",
                            "round": rounds,
                            "escaping_transition": [
                                _canonical_repr(concrete_states[u_i]),
                                _canonical_repr(act),
                                _canonical_repr(concrete_states[v_i]),
                            ],
                        })
                    in_union = [any(truth[q][i] for q in active_t) for i in range(num_states)]

        active_trap_names = [pred_items[p][0] for p in sorted(active_t)]
        trapped_indices = [i for i in range(num_states) if any(truth[p][i] for p in active_t)]
        epistemic_t = (
            "PROVEN"
            if (complete_space and len(active_trap_names) > 0)
            else ("REJECTED_NO_SOUND_TRAP_FOUND" if len(active_trap_names) == 0 else "VERIFIED_ON_BOUNDED_REACHABLE_SUBGRAPH")
        )
        cert_t = {
            "epistemic_status": epistemic_t,
            "certificate_kind": "IRREVERSIBLE_DEADLOCK_TRAP_CERTIFICATE",
            "system_id": reg.system_id,
            "synthesis_mode": synthesis_mode,
            "universal_domain_induction": universal_domain,
            "complete_domain_closed": complete_space,
            "proof_scope": proof_scope,
            "open_transitions": open_edges,
            "synthesized_traps": active_trap_names,
            "traps_retained": len(active_trap_names),
            "traps_refuted": len(refuted_t),
            "refuted_details": refuted_t[:16],
            "fixpoint_rounds": rounds,
            "deadlocked_states_certified": len(trapped_indices),
            "initial_state_trapped": (s0_idx in trapped_indices),
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
        if epistemic_t == "PROVEN":
            reg.certificates.append(cert_t)
        return cert_t

    raise ValueError(f"Unsupported synthesis_mode {synthesis_mode!r}; use 'houdini_safety' or 'deadlock_trap'")


def _portfolio_item_verified_in_registry(system_id: str, floor_v: int, known_v: int) -> bool:
    reg = FORMAL_REGISTRY.get(system_id)
    if reg is None:
        return False
    floor_ok = floor_v == 0
    witness_ok = False
    for cert in reg.certificates:
        st = cert.get("epistemic_status")
        if st == "PROVEN":
            lb = cert.get("certified_lower_bound")
            if isinstance(lb, int) and lb >= floor_v:
                floor_ok = True
            opt = cert.get("optimal_cost")
            if isinstance(opt, int):
                if opt >= floor_v:
                    floor_ok = True
                if opt <= known_v and cert.get("solved") is True:
                    witness_ok = True
        if st == "VERIFIED":
            if cert.get("certificate_kind") == "TRACE_GOAL_WITNESS" and cert.get("verified") is True:
                tc = cert.get("total_cost")
                if isinstance(tc, int) and tc <= known_v:
                    witness_ok = True
            if cert.get("certificate_kind") == "DUAL_CHECKER_SYSTEM_LOCK":
                for pw in cert.get("positive_witnesses_verified") or []:
                    pw_c = pw.get("cost")
                    if isinstance(pw_c, int) and pw_c <= known_v:
                        witness_ok = True
    return floor_ok and witness_ok


def triage_formal_portfolio(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Rank open problem instances by Proven-Commons expected verified gain per CPU-second."""
    ranked: List[Dict[str, Any]] = []
    closed_count = 0
    all_registry_verified = len(items) > 0

    for item in items:
        iid = str(item["id"])
        floor_v = int(item["proven_floor"])
        known_v = int(item.get("shortest_known", item["live_record"]))
        live_v = int(item["live_record"])
        if floor_v < 0 or known_v < 0 or live_v < 0 or floor_v > known_v or known_v > live_v:
            return {
                "epistemic_status": "REJECTED_INCONSISTENT_PORTFOLIO_BOUNDS",
                "invalid_item_id": iid,
                "proven_floor": floor_v,
                "shortest_known": known_v,
                "live_record": live_v,
                "reason": (
                    f"Item {iid!r} violates 0 <= proven_floor <= shortest_known <= live_record "
                    f"({floor_v}, {known_v}, {live_v})."
                ),
            }
        item_verified = _portfolio_item_verified_in_registry(iid, floor_v, known_v)
        if not item_verified:
            all_registry_verified = False

        active_cells = max(2, int(item.get("active_cells", 64)))
        eff_branching = max(1.5, float(item.get("eff_branching", 4.0)))
        chiral_bonus = 0.75 if bool(item.get("has_chiral_symmetry", False)) else 0.0

        live_slack = live_v - known_v
        holdout_gap = known_v - floor_v

        if live_slack == 0 and holdout_gap == 0:
            closed_count += 1
            priority = 0.0
            status = "CLOSED_OPTIMAL"
        else:
            denom = max(1.0, math.log2(active_cells * eff_branching))
            open_bonus = 3.0 if holdout_gap > 0 else 0.0
            priority = round(open_bonus + (live_slack + 2.0 * holdout_gap) / denom + chiral_bonus, 4)
            status = "OPEN_HOLDOUT_AND_SLACK" if (live_slack > 0 and holdout_gap > 0) else (
                "OPEN_LIVE_SLACK" if live_slack > 0 else "OPEN_FLOOR_OR_HOLDOUT_GAP"
            )

        ranked.append({
            "id": iid,
            "status": status,
            "bounds_verified_in_registry": item_verified,
            "priority_score": priority,
            "proven_floor": floor_v,
            "shortest_known": known_v,
            "live_record": live_v,
            "live_slack": live_slack,
            "open_floor_gap": holdout_gap,
            "has_chiral_symmetry": bool(item.get("has_chiral_symmetry", False)),
        })

    ranked.sort(key=lambda r: (-r["priority_score"], -r["live_slack"], r["id"]))
    return {
        "epistemic_status": "VERIFIED" if all_registry_verified else "UNVERIFIED_CALLER_BOUNDS",
        "caller_bounds_verified": all_registry_verified,
        "total_items": len(items),
        "closed_optimal_count": closed_count,
        "open_items_count": len(items) - closed_count,
        "ranked_portfolio": ranked,
    }


def _collect_registry_artifact_digests() -> Tuple[Set[str], Set[str]]:
    proven_digests: Set[str] = set()
    verified_digests: Set[str] = set()
    for reg in FORMAL_REGISTRY.values():
        verified_digests.add(reg.spec.code_sha256.lower())
        verified_digests.add(reg.impl.code_sha256.lower())
        for cert in reg.certificates:
            cst = cert.get("epistemic_status")
            pins = cert.get("checker_pins") or {}
            cand_hashes: List[str] = []
            for key in ("certificate_sha256", "candidates_sha256", "spec_sha256", "impl_sha256"):
                val = pins.get(key)
                if _is_sha256_hex(val):
                    cand_hashes.append(val.lower())
            tr_sha = cert.get("transcript_sha256")
            if _is_sha256_hex(tr_sha):
                cand_hashes.append(tr_sha.lower())
            ver_sub = cert.get("verification")
            if isinstance(ver_sub, dict):
                v_tr = ver_sub.get("transcript_sha256")
                if _is_sha256_hex(v_tr):
                    cand_hashes.append(v_tr.lower())
            for pw in cert.get("positive_witnesses_verified") or []:
                pw_tr = pw.get("transcript_sha256")
                if _is_sha256_hex(pw_tr):
                    cand_hashes.append(pw_tr.lower())
            if cst == "PROVEN":
                for h in cand_hashes:
                    proven_digests.add(h)
                    verified_digests.add(h)
            elif cst == "VERIFIED":
                for h in cand_hashes:
                    verified_digests.add(h)
    return proven_digests, verified_digests


def export_formal_ledger(extra_claims: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Export Foundation-0 / Proven-Commons epistemic ledger with fail-closed status enforcement."""
    allowed = {"PROVEN", "VERIFIED", "KNOWN", "CONJECTURE"}
    systems_out: Dict[str, Any] = {}
    for sid, reg in sorted(FORMAL_REGISTRY.items()):
        systems_out[sid] = {
            "description": reg.description,
            "spec_sha256": reg.spec.code_sha256,
            "impl_sha256": reg.impl.code_sha256,
            "differential_states_checked": reg.differential_states_checked,
            "must_fail_rejected": reg.must_fail_rejected,
            "mutations_killed": f"{reg.mutations_killed}/{reg.mutations_total}",
            "certificates": reg.certificates,
        }

    proven_digests, verified_digests = _collect_registry_artifact_digests()
    validated_extra: List[Dict[str, Any]] = []
    for cl in extra_claims or []:
        cid = cl.get("claim_id", "<unnamed>")
        st = str(cl.get("epistemic_status", "CONJECTURE")).upper()
        if st not in allowed:
            raise ValueError(f"Invalid epistemic_status {st!r}; must be one of {sorted(allowed)}")
        raw_digest = cl.get("witness_or_proof_sha256")
        if raw_digest is not None and not _is_sha256_hex(raw_digest):
            raise ValueError(
                f"Claim {cid!r} supplies invalid `witness_or_proof_sha256` {raw_digest!r}; "
                "expected a 64-character lowercase hex SHA-256 digest."
            )
        if st in ("PROVEN", "VERIFIED"):
            if not _is_sha256_hex(raw_digest):
                raise ValueError(
                    f"Claim {cid!r} cannot be tagged {st} without a valid 64-hex `witness_or_proof_sha256`!"
                )
            norm_digest = str(raw_digest).lower()
            if st == "PROVEN" and norm_digest not in proven_digests:
                raise ValueError(
                    f"Claim {cid!r} cannot be tagged PROVEN: digest {norm_digest[:12]}... is not bound to any "
                    "PROVEN certificate in FORMAL_REGISTRY."
                )
            if st == "VERIFIED" and norm_digest not in verified_digests:
                raise ValueError(
                    f"Claim {cid!r} cannot be tagged VERIFIED: digest {norm_digest[:12]}... is not bound to any "
                    "machine-checked artifact in FORMAL_REGISTRY (use KNOWN or CONJECTURE for external claims)."
                )
            validated_extra.append({**cl, "epistemic_status": st, "witness_or_proof_sha256": norm_digest})
        else:
            norm_cl = dict(cl)
            norm_cl["epistemic_status"] = st
            if isinstance(raw_digest, str):
                norm_cl["witness_or_proof_sha256"] = raw_digest.lower()
            validated_extra.append(norm_cl)

    return {
        "ledger_standard": "Foundation-0 + Proven-Commons Verified Bar v2",
        "formal_kernel_sha256": kernel_sha256(),
        "registered_systems_count": len(systems_out),
        "systems": systems_out,
        "external_claims": validated_extra,
    }


# ==================== BUILT-IN REFERENCE EXAMPLE: TEAM LEASE-PROTOCOL §5 FENCING ====================
LEASE_EXAMPLE_MD = """# Formalizing `LEASE-PROTOCOL.txt` §5 (Advisory vs. Epoch-Fenced Leases)

Using `formal_define_system` + `formal_solve_system` + `formal_certify_lower_bound`, any agent can model
multi-seat collaboration protocols before deploying them:

1. **Unfenced Advisory Lease (`lease_unfenced_v1`):**
   - Two seats (`S1`, `S2`) contend for a shared resource with lease expiry/re-acquisition.
   - If `S1` reads under epoch 1, stalls across a lease timeout while `S2` acquires epoch 2 and commits,
     and `S1` then issues a late write without fencing-token validation, `S2`'s committed work is silently
     clobbered (`lost_committed_update == True`).
   - `formal_solve_system(mode="find_invariant_violation")` discovers the minimal 5-step split-brain bug trace
     and dual-verifies it (`VERIFIED` counterexample).
2. **Monotonic Epoch-Fenced Lease (`lease_epoch_fenced_v2`):**
   - Storage checks `writer_epoch == store_epoch` atomically upon commit.
   - `formal_solve_system(mode="find_invariant_violation", strategy="exact_dijkstra")` exhausts 100% of
     reachable states across both `SPEC` (tuple records) and `IMPL` (bit-packed integers) with `0` violations,
     emitting `"epistemic_status": "PROVEN"` (`EXHAUSTIVE_GLOBAL_SAFETY_PROOF`).
"""
