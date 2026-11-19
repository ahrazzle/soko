"""Static AST Soundness & Anti-Tautology Auditor (`formal_audit_checkers` MCP Tool).

Synchronized two-way between `soko-verified-mcp` (v0.4.0) and `Foundation-0/formal-claims-audit` (PR #16).
Detects four empirical verification hazards uncovered during multi-agent formal verification audits:
1. `IDENTICAL_ALPHA_SKELETON`: `spec` and `impl` checkers share the same AST structure up to local variable renaming.
2. `FLOAT_LITERAL_IN_EXACT_CHECKER` / `FLOAT_DIVISION_IN_EXACT_CHECKER`: IEEE-754 float literals or `/` true division
   inside an exact rational/integer certificate checker (instead of `int` / `fractions.Fraction`).
3. `OPTIMISTIC_TRUE_DEFAULT_F01`: Verification boolean flags (`verified`, `valid`, `match`, `differential_match`, `ok`)
   initialized to `True` before conditional guards, enabling silent single-oracle pass-through (`F-01`).
4. `VACUOUS_CONSTANT_TRUE_RETURN` / `BARE_EXCEPT_SWALLOW` / `MUTABLE_GLOBAL_SCOPE`: Trivial stubs or exception-swallowing
   handlers that break replay determinism or fail-closed verification.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

PRESERVED_NAMES: Set[str] = {
    "abs", "all", "any", "bin", "bool", "chr", "dict", "divmod", "enumerate",
    "filter", "frozenset", "hex", "int", "isinstance", "len", "list", "map",
    "max", "min", "oct", "ord", "pow", "range", "repr", "reversed", "set",
    "sorted", "str", "sum", "tuple", "zip", "Fraction", "True", "False", "None",
    "ValueError", "AssertionError",
}

SUSPICIOUS_BOOL_NAMES: Set[str] = {
    "verified", "is_verified", "valid", "is_valid", "ok",
    "match", "differential_match", "dual_checked", "passed",
}


def alpha_skeleton_sha256(source: str, preserved_api: Optional[Set[str]] = None) -> str:
    """Compute SHA-256 of an alpha-normalized AST (ignoring docstrings and local variable renames)."""
    tree = ast.parse(source)
    keep = PRESERVED_NAMES | (preserved_api or set())
    id_map: Dict[str, str] = {}

    def canon(name: str) -> str:
        if name in keep:
            return name
        if name not in id_map:
            id_map[name] = f"v{len(id_map)}"
        return id_map[name]

    class Normalizer(ast.NodeTransformer):
        def visit_Module(self, node: ast.Module) -> Any:
            body = list(node.body)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body = body[1:]
            return ast.Module(body=[self.visit(s) for s in body], type_ignores=[])

        def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
            body = list(node.body)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body = body[1:]
            args = [ast.arg(arg=canon(a.arg)) for a in node.args.args]
            return ast.FunctionDef(
                name=canon(node.name),
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
            return ast.Name(id=canon(node.id), ctx=node.ctx)

    norm_tree = Normalizer().visit(tree)
    return hashlib.sha256(ast.dump(norm_tree, include_attributes=False).encode("utf-8")).hexdigest()


def audit_checker_source(
    source: str,
    label: str = "<checker>",
    strict_exact_math: bool = True,
) -> Dict[str, Any]:
    """Audit a single Python checker source string for F-01, floating-point drift, and vacuous stubs."""
    tree = ast.parse(source, filename=label)
    findings: List[Dict[str, Any]] = []

    for node in ast.walk(tree):
        if strict_exact_math:
            if isinstance(node, ast.Constant) and isinstance(node.value, (float, complex)):
                findings.append({
                    "rule": "FLOAT_LITERAL_IN_EXACT_CHECKER",
                    "line": getattr(node, "lineno", 0),
                    "detail": f"Floating-point literal {node.value!r} risks rounding drift; use int or fractions.Fraction.",
                })
            elif isinstance(node, ast.Div):
                findings.append({
                    "rule": "FLOAT_DIVISION_IN_EXACT_CHECKER",
                    "line": getattr(node, "lineno", 0),
                    "detail": "True division '/' produces IEEE-754 float; use '//' or fractions.Fraction(num, den).",
                })
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            findings.append({
                "rule": "MUTABLE_GLOBAL_SCOPE",
                "line": getattr(node, "lineno", 0),
                "detail": "Mutable global/nonlocal statement inside checker undermines replay determinism.",
            })
        if isinstance(node, ast.Try):
            for h in node.handlers:
                if h.type is None:
                    findings.append({
                        "rule": "BARE_EXCEPT_SWALLOW",
                        "line": getattr(h, "lineno", 0),
                        "detail": "Bare 'except:' clause can silently swallow assertion or solver failures.",
                    })
        if isinstance(node, ast.Assert) and isinstance(node.test, ast.Constant) and node.test.value is True:
            findings.append({
                "rule": "VACUOUS_ASSERT_TRUE",
                "line": getattr(node, "lineno", 0),
                "detail": "Vacuous 'assert True' provides zero verification coverage.",
            })
        if isinstance(node, ast.FunctionDef):
            stmts = node.body
            if (
                stmts
                and isinstance(stmts[0], ast.Expr)
                and isinstance(stmts[0].value, ast.Constant)
                and isinstance(stmts[0].value.value, str)
            ):
                eff_stmts = stmts[1:]
            else:
                eff_stmts = stmts
            if (
                len(eff_stmts) == 1
                and isinstance(eff_stmts[0], ast.Return)
                and isinstance(eff_stmts[0].value, ast.Constant)
                and eff_stmts[0].value.value is True
            ):
                findings.append({
                    "rule": "VACUOUS_CONSTANT_TRUE_RETURN",
                    "line": eff_stmts[0].lineno,
                    "detail": f"Function {node.name}() unconditionally returns True (vacuous stub).",
                })
            for idx, stmt in enumerate(stmts):
                if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Constant) and stmt.value.value is True:
                    for tgt in stmt.targets:
                        if isinstance(tgt, ast.Name) and tgt.id.lower() in SUSPICIOUS_BOOL_NAMES:
                            has_later_if = any(isinstance(later, ast.If) for later in stmts[idx + 1 :])
                            if has_later_if:
                                findings.append({
                                    "rule": "OPTIMISTIC_TRUE_DEFAULT_F01",
                                    "line": stmt.lineno,
                                    "detail": (
                                        f"Verification flag {tgt.id!r} initialized to True in {node.name}() "
                                        "before conditional branch (fail-open F-01 hazard)."
                                    ),
                                })

    code_sha256 = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return {
        "label": label,
        "code_sha256": code_sha256,
        "alpha_skeleton_sha256": alpha_skeleton_sha256(source),
        "clean": len(findings) == 0,
        "findings_count": len(findings),
        "findings": findings,
    }


def audit_dual_checkers(
    spec_source: str,
    impl_source: Optional[str] = None,
    preserved_api: Optional[Set[str]] = None,
    strict_exact_math: bool = True,
) -> Dict[str, Any]:
    """Audit either a single checker or a pair of independent checkers (`SPEC` vs `IMPL`)."""
    s_rep = audit_checker_source(spec_source, label="spec", strict_exact_math=strict_exact_math)
    if impl_source is None or not impl_source.strip():
        verdict = "PASS" if s_rep["clean"] else "FAIL"
        return {
            "epistemic_status": "VERIFIED" if verdict == "PASS" else "REJECTED_CHECKER_HAZARD",
            "mode": "single_checker",
            "verdict": verdict,
            "spec_audit": s_rep,
        }

    i_rep = audit_checker_source(impl_source, label="impl", strict_exact_math=strict_exact_math)
    s_skel = alpha_skeleton_sha256(spec_source, preserved_api=preserved_api)
    i_skel = alpha_skeleton_sha256(impl_source, preserved_api=preserved_api)
    distinct = s_skel != i_skel
    verdict = "PASS" if (distinct and s_rep["clean"] and i_rep["clean"]) else "FAIL"
    return {
        "epistemic_status": "VERIFIED" if verdict == "PASS" else "REJECTED_CHECKER_HAZARD",
        "mode": "dual_checker",
        "verdict": verdict,
        "distinct_alpha_skeleton": distinct,
        "spec_skeleton_sha256": s_skel,
        "impl_skeleton_sha256": i_skel,
        "spec_audit": s_rep,
        "impl_audit": i_rep,
    }


def audit_builtin_soko_oracles() -> Dict[str, Any]:
    """Self-audit `soko_mcp/oracle.py` against `soko_mcp/flat_oracle.py`."""
    pkg_dir = Path(__file__).resolve().parent
    spec_src = (pkg_dir / "oracle.py").read_text(encoding="utf-8")
    impl_src = (pkg_dir / "flat_oracle.py").read_text(encoding="utf-8")
    return audit_dual_checkers(spec_src, impl_src, strict_exact_math=True)
