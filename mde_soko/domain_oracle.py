"""Self-contained `DomainOracle`, stateful play session, 4s cell sandbox, and `F-01..F-08` auditor for `mde:soko-eval`."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from soko_mcp.catalog import get_room, load_catalog
from soko_mcp.flat_oracle import replay_flat_oracle
from soko_mcp.oracle import MutatorFlags, PuzzleScriptOracle, replay_oracle

from .scrub import sanitize_text, soko_repo_root

MAX_CELL_TIMEOUT_SEC = 4.0
VALID_SOKO_KEYS = frozenset({"U", "D", "L", "R", "A"})
SHA256_64_RE = re.compile(r"^[0-9a-f]{64}$")

# Fail-closed allowlist: a cell may import only these pure-computation stdlib roots.
ALLOWED_CELL_IMPORTS: frozenset[str] = frozenset(
    {
        "__future__",
        "array",
        "bisect",
        "collections",
        "copy",
        "fractions",
        "functools",
        "heapq",
        "itertools",
        "json",
        "math",
        "typing",
    }
)
FORBIDDEN_CELL_CALLS: frozenset[str] = frozenset(
    {
        "open",
        "exec",
        "eval",
        "compile",
        "__import__",
        "input",
        "breakpoint",
        "globals",
        "locals",
        "vars",
        "getattr",
        "setattr",
        "delattr",
    }
)
FORBIDDEN_DUNDER_ATTRS: frozenset[str] = frozenset(
    {
        "__subclasses__",
        "__bases__",
        "__mro__",
        "__globals__",
        "__code__",
        "__builtins__",
        "__loader__",
        "__spec__",
        "__dict__",
    }
)

# Dunder attributes a cell may use; every other `__x__` attribute can reach builtins or globals.
SAFE_CELL_DUNDER_ATTRS: frozenset[str] = frozenset(
    {
        "__init__",
        "__name__",
        "__len__",
        "__iter__",
        "__next__",
        "__eq__",
        "__hash__",
        "__lt__",
        "__repr__",
        "__str__",
        "__contains__",
        "__getitem__",
    }
)
# Attributes that hop from an allowed module to a forbidden one (e.g. `json.codecs.sys`).
FORBIDDEN_MODULE_HOP_ATTRS: frozenset[str] = frozenset(
    {
        "sys",
        "_sys",
        "os",
        "_os",
        "posix",
        "_posixsubprocess",
        "nt",
        "modules",
        "builtins",
        "_builtins",
        "codecs",
        "io",
        "_io",
        "importlib",
        "_imp",
        "_frozen_importlib",
        "inspect",
        "types",
        "subprocess",
        "shutil",
        "pathlib",
        # Frame/generator/coroutine/traceback introspection attributes (bypass dunder checks).
        "gi_frame",
        "gi_code",
        "gi_yieldfrom",
        "cr_frame",
        "cr_code",
        "cr_await",
        "ag_frame",
        "ag_code",
        "tb_frame",
        "tb_next",
        "f_builtins",
        "f_globals",
        "f_locals",
        "f_back",
        "f_code",
        "func_globals",
        "func_code",
        "im_func",
        "im_self",
        "im_class",
        "co_consts",
        "co_names",
        "co_varnames",
        "mro",
    }
)


def _is_dunder(name: str) -> bool:
    return len(name) > 4 and name.startswith("__") and name.endswith("__")


_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
_PYTHON_FENCE_RE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_JSON_OBJ_RE = re.compile(r"\{[^{}]*\}")


@dataclass(frozen=True)
class DomainDiagnostic:
    """Sanitized Tier 2 diagnostic matching `mcproof.domain_protocol.DomainDiagnostic`."""

    rule: str
    message: str
    line: int | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"rule": self.rule, "message": self.message}
        if self.line is not None:
            out["line"] = self.line
        return out


@dataclass(frozen=True)
class DomainGradeResult:
    """Deterministic Tier 2 verdict matching `mcproof.domain_protocol.DomainGradeResult`."""

    passed: bool
    epistemic_status: str
    diagnostics: tuple[DomainDiagnostic, ...]
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "epistemic_status": self.epistemic_status,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "metrics": dict(self.metrics),
        }


def board_sha256_lf(grid: Sequence[str]) -> str:
    norm = "\n".join(str(r) for r in grid)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def load_soko_catalog_enriched() -> dict[str, dict[str, Any]]:
    raw = load_catalog()
    enriched: dict[str, dict[str, Any]] = {}
    for rid, r in raw.items():
        item = dict(r)
        item["room_id"] = rid
        item["board_sha256_lf"] = board_sha256_lf(item["grid"])
        enriched[rid] = item
    return enriched


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(len(text.split()), (len(text.encode("utf-8")) + 2) // 3) + 4


def parse_bare_or_embedded_json(raw_text: str) -> tuple[bool, dict[str, Any] | None]:
    """Return `(is_strict_bare_json, parsed_dict_or_none)`."""
    stripped = raw_text.strip()
    if stripped.startswith("{") and stripped.endswith("}") and "```" not in stripped:
        try:
            obj = json.loads(stripped)
            if isinstance(obj, dict):
                return True, obj
        except ValueError as exc:
            _err = str(exc)

    for match in reversed(_JSON_OBJ_RE.findall(stripped)):
        try:
            obj2 = json.loads(match)
            if isinstance(obj2, dict):
                return False, obj2
        except ValueError as exc:
            _err2 = str(exc)
    return False, None


def extract_python_cell(raw_text: str) -> str | None:
    matches = _PYTHON_FENCE_RE.findall(raw_text)
    if matches:
        return str(matches[-1]).strip()
    return None


def audit_zero_import_cell(code: str) -> list[dict[str, Any]]:
    """Static AST gate: stdlib import allowlist (fail closed), no dunder reflection, no dynamic eval."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [
            {
                "rule": "CELL_SYNTAX_ERROR",
                "line": exc.lineno or 1,
                "message": f"Python SyntaxError: {exc.msg}",
            }
        ]

    findings: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                root_mod = parts[0]
                if (
                    root_mod not in ALLOWED_CELL_IMPORTS
                    or any(p.startswith("_") and p != "__future__" for p in parts)
                    or any(p in FORBIDDEN_MODULE_HOP_ATTRS for p in parts)
                ):
                    findings.append(
                        {
                            "rule": "FORBIDDEN_CELL_IMPORT",
                            "line": getattr(node, "lineno", 1),
                            "message": f"Import `{alias.name}` is not on the 4-second notebook cell allowlist.",
                        }
                    )
        elif isinstance(node, ast.ImportFrom):
            parts = (node.module or "").split(".")
            root_mod = parts[0]
            bad_mod = (
                node.level > 0
                or root_mod not in ALLOWED_CELL_IMPORTS
                or any(p.startswith("_") and p != "__future__" for p in parts)
                or any(p in FORBIDDEN_MODULE_HOP_ATTRS for p in parts)
            )
            if bad_mod:
                findings.append(
                    {
                        "rule": "FORBIDDEN_CELL_IMPORT",
                        "line": getattr(node, "lineno", 1),
                        "message": f"From-import `{node.module or '.'}` is not on the 4-second notebook cell allowlist.",
                    }
                )
            else:
                for alias in node.names:
                    if (
                        alias.name == "*"
                        or alias.name.startswith("_")
                        or alias.name in FORBIDDEN_MODULE_HOP_ATTRS
                    ):
                        findings.append(
                            {
                                "rule": "FORBIDDEN_CELL_IMPORT",
                                "line": getattr(node, "lineno", 1),
                                "message": f"From-import symbol `{node.module}.{alias.name}` is forbidden in 4-second notebook cells.",
                            }
                        )
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr in (
                "system",
                "popen",
                "urlopen",
                "import_module",
                "exec_module",
                "load_module",
            ):
                findings.append(
                    {
                        "rule": "FORBIDDEN_CELL_CALL",
                        "line": getattr(node, "lineno", 1),
                        "message": f"Method call `.{node.func.attr}(...)` is forbidden in sandboxed cells.",
                    }
                )
        elif isinstance(node, ast.Attribute) and (
            node.attr in FORBIDDEN_DUNDER_ATTRS
            or (_is_dunder(node.attr) and node.attr not in SAFE_CELL_DUNDER_ATTRS)
            or node.attr in FORBIDDEN_MODULE_HOP_ATTRS
        ):
            findings.append(
                {
                    "rule": "FORBIDDEN_CELL_DUNDER",
                    "line": getattr(node, "lineno", 1),
                    "message": f"Attribute `.{node.attr}` is forbidden in sandboxed cells.",
                }
            )
        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_CELL_CALLS:
                findings.append(
                    {
                        "rule": "FORBIDDEN_CELL_CALL",
                        "line": getattr(node, "lineno", 1),
                        "message": f"Builtin `{node.id}` is forbidden in sandboxed cells.",
                    }
                )
            elif _is_dunder(node.id) and node.id not in ("__name__", "__future__"):
                findings.append(
                    {
                        "rule": "FORBIDDEN_CELL_DUNDER",
                        "line": getattr(node, "lineno", 1),
                        "message": f"Dunder name `{node.id}` is forbidden in sandboxed cells.",
                    }
                )
    return findings


def execute_sandbox_cell(code: str, *, timeout_sec: float = MAX_CELL_TIMEOUT_SEC) -> dict[str, Any]:
    """Run a zero-import Python cell under `python -I -B` in an isolated process group (`<= 4.0s`)."""
    capped = min(max(0.5, float(timeout_sec)), MAX_CELL_TIMEOUT_SEC)
    ast_findings = audit_zero_import_cell(code)
    if ast_findings:
        return {
            "ok": False,
            "timed_out": False,
            "ast_rejected": True,
            "findings": ast_findings,
            "stdout": "",
            "stderr": "; ".join(f["message"] for f in ast_findings),
        }

    with tempfile.TemporaryDirectory(prefix="mde_soko_cell_") as tmp_dir:
        cell_path = Path(tmp_dir) / "cell.py"
        cell_path.write_text(code, encoding="utf-8")
        clean_env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONHASHSEED": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        }
        proc = subprocess.Popen(
            [sys.executable, "-I", "-B", str(cell_path)],
            cwd=tmp_dir,
            env=clean_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            out, err = proc.communicate(timeout=capped)
            ok = proc.returncode == 0
            return {
                "ok": ok,
                "timed_out": False,
                "ast_rejected": False,
                "findings": (
                    []
                    if ok
                    else [
                        {
                            "rule": "CELL_RUNTIME_ERROR",
                            "message": sanitize_text((err or out).strip()[-240:]),
                        }
                    ]
                ),
                "stdout": sanitize_text(out[:8000]),
                "stderr": sanitize_text(err[:2000]),
            }
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError as exc:
                _kill_note = str(exc)
            out, _err = proc.communicate()
            return {
                "ok": False,
                "timed_out": True,
                "ast_rejected": False,
                "findings": [
                    {
                        "rule": "CELL_TIMEOUT_EXCEEDED",
                        "message": f"Python cell exceeded hard {capped:.1f}s timeout.",
                    }
                ],
                "stdout": sanitize_text((out or "")[:4000]),
                "stderr": f"TimeoutExpired: exceeded {capped:.1f}s",
            }


def verify_route_dual_strict(part: int, grid: Sequence[str], route: str) -> dict[str, Any]:
    """Fail-closed dual-Python (`PuzzleScriptOracle` + `FlatBitmaskOracle`) trajectory & final-key win check."""
    rows = [str(r) for r in grid]
    joined = "".join(rows)
    if not any(c in joined for c in "FTWPBD123456") or "G" not in joined:
        return {
            "valid_alphabet": True,
            "alive": False,
            "premature_win": False,
            "exact_win": False,
            "dual_oracle_parity": False,
            "steps_executed": 0,
            "route_len": len(route),
            "clean_route": "",
            "traj_fnv64": "",
            "final_ascii": "\n".join(rows),
            "failure_rule": "VACUOUS_BOARD",
            "failure_message": "Board lacks hero or goal tiles.",
        }

    stripped = "".join(ch for ch in route.upper() if not ch.isspace())
    bad_chars = sorted({ch for ch in stripped if ch not in VALID_SOKO_KEYS})
    if bad_chars:
        return {
            "valid_alphabet": False,
            "alive": False,
            "premature_win": False,
            "exact_win": False,
            "dual_oracle_parity": False,
            "steps_executed": 0,
            "route_len": len(stripped),
            "clean_route": "",
            "traj_fnv64": "",
            "final_ascii": "\n".join(rows),
            "failure_rule": "INVALID_KEY_ALPHABET",
            "failure_message": f"Route contains non-UDLRA characters: {''.join(bad_chars)[:16]}",
        }
    if len(stripped) > 10000:
        return {
            "valid_alphabet": False,
            "alive": False,
            "premature_win": False,
            "exact_win": False,
            "dual_oracle_parity": False,
            "steps_executed": 0,
            "route_len": len(stripped),
            "clean_route": "",
            "traj_fnv64": "",
            "final_ascii": "\n".join(rows),
            "failure_rule": "ROUTE_TOO_LONG",
            "failure_message": "Route exceeds 10,000-key evaluation limit.",
        }

    # F-01 defense: initialize differential_match = False prior to dual-engine comparison
    differential_match = False
    ps = replay_oracle(int(part), rows, stripped)
    fb = replay_flat_oracle(int(part), rows, stripped)
    differential_match = (
        bool(ps["alive"]) == bool(fb["alive"])
        and bool(ps["exact_win"]) == bool(fb["exact_win"])
        and bool(ps["premature_win"]) == bool(fb["premature_win"])
        and str(ps["traj_fnv64"]) == str(fb["traj_fnv64"])
        and str(ps["final_ascii"]) == str(fb["final_ascii"])
        and int(ps["steps_executed"]) == int(fb["steps_executed"])
    )
    if not differential_match:
        return {
            "valid_alphabet": True,
            "alive": False,
            "premature_win": False,
            "exact_win": False,
            "dual_oracle_parity": False,
            "steps_executed": int(ps["steps_executed"]),
            "route_len": len(stripped),
            "clean_route": stripped,
            "traj_fnv64": "",
            "final_ascii": str(ps["final_ascii"]),
            "failure_rule": "DUAL_ORACLE_MISMATCH",
            "failure_message": "PuzzleScriptOracle and FlatBitmaskOracle disagreed on trajectory state.",
        }

    if not ps["alive"]:
        rule = "HERO_DIED"
        msg = f"Hero died at step {ps['steps_executed']} of {len(stripped)}."
    elif ps["premature_win"]:
        rule = "PREMATURE_WIN_EXTRA_KEYS"
        msg = f"Room already won at step {ps['steps_executed']} before trailing keys (len={len(stripped)})."
    elif not ps["exact_win"]:
        rule = "GOALS_NOT_MET"
        msg = f"Route finished alive after {len(stripped)} keys without all heroes on G goals."
    else:
        rule = "EXACT_WIN"
        msg = "Verified exact final-key win across both oracles."

    return {
        "valid_alphabet": True,
        "alive": bool(ps["alive"]),
        "premature_win": bool(ps["premature_win"]),
        "exact_win": bool(ps["exact_win"]),
        "dual_oracle_parity": True,
        "steps_executed": int(ps["steps_executed"]),
        "route_len": len(stripped),
        "clean_route": stripped,
        "traj_fnv64": str(ps["traj_fnv64"]),
        "final_ascii": str(ps["final_ascii"]),
        "failure_rule": rule,
        "failure_message": msg,
    }


@dataclass
class SokoEvalBudget:
    """Explicit reply, key, undo, restart, and Python-cell budget tracker (`banteg.xyz/posts/sokoban/`)."""

    max_replies: int = 1000
    max_keys: int = 10000
    max_cells: int = 4
    replies_used: int = 0
    keys_used: int = 0
    undos_used: int = 0
    restarts_used: int = 0
    cells_used: int = 0
    format_errors: int = 0

    def exhausted(self) -> bool:
        return self.replies_used >= self.max_replies or self.keys_used >= self.max_keys

    def to_dict(self) -> dict[str, int | bool]:
        return {
            "max_replies": self.max_replies,
            "max_keys": self.max_keys,
            "max_cells": self.max_cells,
            "replies_used": self.replies_used,
            "keys_used": self.keys_used,
            "undos_used": self.undos_used,
            "restarts_used": self.restarts_used,
            "cells_used": self.cells_used,
            "format_errors": self.format_errors,
            "budget_exhausted": self.exhausted(),
        }


@dataclass
class SokoPlaySession:
    """Stateful single-room Sokoban Eval session supporting `step`, `probe`, `undo`, `reset`, and `cell`."""

    room_id: str
    budget: SokoEvalBudget = field(
        default_factory=lambda: SokoEvalBudget(max_replies=16, max_keys=300, max_cells=4)
    )
    current_route: str = ""
    cleared: bool = False
    history: list[dict[str, Any]] = field(default_factory=list)

    def _room(self) -> dict[str, Any]:
        return get_room(self.room_id)

    def observe(self) -> dict[str, Any]:
        rm = self._room()
        ver = verify_route_dual_strict(rm["part"], rm["grid"], self.current_route)
        return {
            "room_id": self.room_id,
            "current_route": self.current_route,
            "current_route_len": len(self.current_route),
            "board_ascii": ver["final_ascii"],
            "alive": ver["alive"],
            "exact_win": ver["exact_win"],
            "traj_fnv64": ver["traj_fnv64"],
            "budget": self.budget.to_dict(),
        }

    def apply_reply_json(self, raw_reply: str) -> dict[str, Any]:
        if self.budget.exhausted():
            return {"ok": False, "error": "budget_exhausted", "state": self.observe()}

        self.budget.replies_used += 1
        is_bare, payload = parse_bare_or_embedded_json(raw_reply)
        if not is_bare or payload is None:
            self.budget.format_errors += 1
            rec = {"ok": False, "error": "invalid_bare_json", "budget": self.budget.to_dict()}
            self.history.append(rec)
            return rec

        rm = self._room()
        action = str(payload.get("action") or ("step" if "keys" in payload else "")).strip().lower()

        if action in ("keys", "step"):
            raw_keys = str(payload.get("keys", "")).strip().upper()
            if not raw_keys or any(ch not in VALID_SOKO_KEYS for ch in raw_keys):
                self.budget.format_errors += 1
                rec = {"ok": False, "error": "invalid_or_empty_keys", "budget": self.budget.to_dict()}
                self.history.append(rec)
                return rec
            rem = max(0, self.budget.max_keys - self.budget.keys_used)
            clipped = raw_keys[: min(24, rem)]
            candidate = self.current_route + clipped
            ver = verify_route_dual_strict(rm["part"], rm["grid"], candidate)
            delta_steps = max(0, int(ver["steps_executed"]) - len(self.current_route))
            self.budget.keys_used += max(1, delta_steps) if clipped else 0
            if ver["alive"] and not ver["premature_win"]:
                self.current_route = candidate
                if ver["exact_win"]:
                    self.cleared = True
            rec = {
                "ok": ver["alive"] and not ver["premature_win"],
                "action": "step",
                "keys_submitted": clipped,
                "verification": ver,
                "current_route": self.current_route,
                "cleared": self.cleared,
                "budget": self.budget.to_dict(),
            }
            self.history.append(rec)
            return rec

        if action == "probe":
            key = str(payload.get("key") or payload.get("keys") or "").strip().upper()[:1]
            if len(key) != 1 or key not in VALID_SOKO_KEYS:
                self.budget.format_errors += 1
                return {
                    "ok": False,
                    "error": "probe_requires_single_UDLRA_key",
                    "budget": self.budget.to_dict(),
                }
            before = verify_route_dual_strict(rm["part"], rm["grid"], self.current_route)
            after = verify_route_dual_strict(rm["part"], rm["grid"], self.current_route + key)
            self.budget.keys_used += 1
            if after["exact_win"]:
                self.current_route = self.current_route + key
                self.cleared = True
            else:
                self.budget.undos_used += 1
                self.budget.keys_used += 1
            rec = {
                "ok": True,
                "action": "probe",
                "key": key,
                "probe_alive": after["alive"],
                "probe_won": after["exact_win"],
                "board_changed": before["traj_fnv64"] != after["traj_fnv64"],
                "after_ascii": after["final_ascii"],
                "cleared": self.cleared,
                "budget": self.budget.to_dict(),
            }
            self.history.append(rec)
            return rec

        if action == "undo":
            steps = max(1, int(payload.get("steps", 1)))
            actual = min(steps, len(self.current_route))
            self.current_route = self.current_route[: len(self.current_route) - actual]
            self.budget.undos_used += actual
            self.budget.keys_used += actual
            rec = {"ok": True, "action": "undo", "undone": actual, "state": self.observe()}
            self.history.append(rec)
            return rec

        if action in ("restart", "reset"):
            self.current_route = ""
            self.budget.restarts_used += 1
            self.budget.keys_used += 1
            rec = {"ok": True, "action": "reset", "state": self.observe()}
            self.history.append(rec)
            return rec

        self.budget.format_errors += 1
        return {"ok": False, "error": f"unsupported_action:{action!r}", "budget": self.budget.to_dict()}


CERTIFIED_STATUSES: frozenset[str] = frozenset({"VERIFIED", "PROVEN", "LOWER_BOUND"})
RECOGNIZED_CERT_STATUSES: frozenset[str] = CERTIFIED_STATUSES | frozenset(
    {
        "CONJECTURE",
        "LOWER_BOUND_UNWITNESSED",
        "LINT_PASS",
        "VERIFIED_ON_BOUNDED_REACHABLE_SUBGRAPH",
        "REJECTED",
        "UNVERIFIED_CALLER_BOUNDS",
    }
)


def audit_soko_certificate(cert: Mapping[str, Any]) -> dict[str, Any]:
    """Fail-closed auditor rejecting all 8 historical & live unsound-certificate failure modes (`F-01`..`F-08`)."""
    findings: list[dict[str, str]] = []
    status = str(cert.get("epistemic_status", "")).strip().upper()
    proof_mode = str(cert.get("proof_mode", "")).strip().lower()

    # An omitted or invented status has no checks to fail, so it must not pass.
    if not status:
        findings.append(
            {
                "rule": "F00_STATUS_ABSENT",
                "message": "Certificate omits epistemic_status.",
            }
        )
    elif status not in RECOGNIZED_CERT_STATUSES:
        findings.append(
            {
                "rule": "F00_STATUS_UNKNOWN",
                "message": f"epistemic_status {status!r} is not a recognized certificate status.",
            }
        )

    engines = cert.get("oracles_checked") or cert.get("engines_verified") or []
    if cert.get("differential_match") is True and (not isinstance(engines, list) or len(engines) < 2):
        findings.append(
            {
                "rule": "F01_SINGLE_ENGINE_DIFFERENTIAL_CLAIM",
                "message": "differential_match=True requires >=2 independent replay engines.",
            }
        )

    if cert.get("state_hash_mode") in ("ascii_only", "rendered_board_only") or cert.get("includes_hidden_state") is False:
        findings.append(
            {
                "rule": "F02_PARTIAL_PROJECTION_STATE_HASH",
                "message": "Trajectory digest omits hidden door/Bard-note state bits.",
            }
        )

    pins = cert.get("tcb_pins")
    if status in CERTIFIED_STATUSES:
        if not isinstance(pins, Mapping):
            pins = {}
        if pins.get("tcb_manifest_verified", False) is not True or not SHA256_64_RE.fullmatch(
            str(pins.get("checker_auditor_py_sha256", ""))
        ):
            findings.append(
                {
                    "rule": "F03_TCB_MANIFEST_UNLOCKED",
                    "message": "Certificate TCB pins lack verified SHA256SUMS or 64-hex checker_auditor_py_sha256.",
                }
            )

    if status == "VERIFIED" and "proven_floor" in cert:
        witness = cert.get("witness_route")
        if cert.get("exact_optimum_reached") is False or not isinstance(witness, str) or not witness:
            findings.append(
                {
                    "rule": "F04_UNWITNESSED_VERIFIED_OPTIMUM",
                    "message": "Lower-bound search without matching witness route must be LOWER_BOUND, never VERIFIED.",
                }
            )
        elif len(witness) != int(cert["proven_floor"]):
            findings.append(
                {
                    "rule": "F04_WITNESS_FLOOR_LENGTH_MISMATCH",
                    "message": f"Witness route length {len(witness)} != claimed proven_floor {cert['proven_floor']}.",
                }
            )

    if (
        cert.get("fixture_id")
        and cert.get("canonical_room_id")
        and cert.get("board_sha256_lf") != cert.get("canonical_board_sha256_lf")
    ):
        findings.append(
            {
                "rule": "F05_FIXTURE_CANONICAL_CONFLATION",
                "message": "Fixture lower bound cannot be attributed to canonical room with differing board_sha256_lf.",
            }
        )
    if int(cert.get("step_consistency_violations", 0)) > 0:
        findings.append(
            {
                "rule": "F05_STEP_INCONSISTENCY_DETECTED",
                "message": "Layered A* lower-bound certificate is invalid when step_consistency_violations > 0.",
            }
        )

    if proof_mode == "inductive_potential" or status == "VERIFIED_ON_BOUNDED_REACHABLE_SUBGRAPH":
        if cert.get("complete_space") is not True:
            findings.append(
                {
                    "rule": "F06_TRUNCATED_INDUCTIVE_POTENTIAL",
                    "message": "inductive_potential on an incomplete concrete graph (complete_space != True) is unsound.",
                }
            )

    if status == "PROVEN" and (
        cert.get("impl_invariant_checked") is False or cert.get("obs_projection_injective") is False
    ):
        findings.append(
            {
                "rule": "F07_IMPL_INVARIANT_UNCHECKED_UNDER_COARSE_OBS",
                "message": "PROVEN safety status is unsound when impl.invariant is unchecked or project_obs is non-injective.",
            }
        )

    if status in CERTIFIED_STATUSES:
        w_sha = cert.get("witness_or_proof_sha256")
        if not isinstance(w_sha, str) or not SHA256_64_RE.fullmatch(w_sha):
            findings.append(
                {
                    "rule": "F08_INVALID_WITNESS_SHA256",
                    "message": "witness_or_proof_sha256 must be a lowercase 64-hex SHA-256 digest.",
                }
            )
    if cert.get("source") == "caller_supplied_portfolio_int" and status == "VERIFIED":
        findings.append(
            {
                "rule": "F08_UNVERIFIED_PORTFOLIO_FLOOR_INFLATION",
                "message": "Caller-supplied integer floors without replayed certificate verification cannot be VERIFIED.",
            }
        )

    passed = len(findings) == 0
    # A record that clears every check keeps its own recognized status.
    out_status = status if passed else "REJECTED"
    return {
        "passed": passed,
        "epistemic_status": out_status,
        "finding_count": len(findings),
        "findings": findings,
    }


class SokoDomainOracle:
    """Implements `@oracles`'s `DomainOracle` protocol (`domain_id`, `retrieve_plane1_context`, `grade_candidate`, `format_repair_feedback`)."""

    def __init__(self, *, repo_root: Path | None = None) -> None:
        self._repo_root = (repo_root or soko_repo_root()).resolve()

    @property
    def domain_id(self) -> str:
        return "mde:soko-eval"

    def spec_path(self) -> Path:
        return self._repo_root / "mde_soko" / "spec" / "plane1_soko_spec.md"

    def retrieve_plane1_context(
        self,
        task: Mapping[str, Any],
        prior_diagnostics: Sequence[DomainDiagnostic] = (),
        max_tokens: int = 1100,
    ) -> str:
        res = self.retrieve_plane1(
            task_family=str(task.get("family", "S3")),
            prompt_text=str(task.get("prompt", "")),
            prior_findings=[d.to_dict() for d in prior_diagnostics],
            max_tokens=max_tokens,
        )
        return str(res["excerpt"])

    def retrieve_plane1(
        self,
        *,
        task_family: str,
        prompt_text: str,
        prior_findings: Sequence[Mapping[str, Any]] = (),
        max_tokens: int = 1100,
    ) -> dict[str, Any]:
        raw = self.spec_path().read_text(encoding="utf-8")
        raw_secs = raw.split("\n## ")
        chunks: list[tuple[int, str, str]] = []
        for idx, blk in enumerate(raw_secs[1:], start=1):
            heading = blk.splitlines()[0].strip()
            body = "## " + blk.strip()
            chunks.append((idx, heading, body))

        fam = task_family.upper()
        primary_map: dict[str, tuple[int, ...]] = {
            "H_ROUTE": (4, 3, 7),
            "H_PROBE": (2, 4, 3),
            "H_RULE": (3, 1, 7),
            "H_CELL": (5, 3, 4, 7),
            "S3": (3, 5, 4, 7),
        }
        boosted = {sec: 40 - i * 6 for i, sec in enumerate(primary_map.get(fam, (3, 4, 5, 7)))}
        p_words = {w.lower() for w in _WORD_RE.findall(prompt_text)}
        for f in prior_findings:
            r_up = str(f.get("rule", "")).upper()
            if "CELL" in r_up:
                boosted[5] = boosted.get(5, 0) + 30
            if "BARE_JSON" in r_up or "PREMATURE" in r_up:
                boosted[4] = boosted.get(4, 0) + 30
            if "DIED" in r_up or "GOALS" in r_up:
                boosted[3] = boosted.get(3, 0) + 25

        scored: list[tuple[int, int, str, str]] = []
        for sec_num, heading, body in chunks:
            b_words = {w.lower() for w in _WORD_RE.findall(body)}
            overlap = len(p_words & b_words)
            sc = boosted.get(sec_num, 0) + overlap
            scored.append((sc, sec_num, heading, body))
        scored.sort(key=lambda t: (-t[0], t[1]))

        picked: list[str] = []
        picked_ids: list[str] = []
        used_tokens = 0
        cap = min(max(250, int(max_tokens)), 1500)
        for _sc, sec_num, _hd, body in scored:
            t_est = estimate_tokens(body)
            if used_tokens + t_est > cap:
                continue
            picked.append(body)
            picked_ids.append(f"sec_{sec_num}")
            used_tokens += t_est

        excerpt = "\n\n".join(picked)
        return {
            "domain_id": self.domain_id,
            "excerpt": excerpt,
            "estimated_tokens": estimate_tokens(excerpt),
            "chunk_ids": picked_ids,
        }

    def grade_candidate(self, task: Mapping[str, Any], candidate: str) -> DomainGradeResult:
        """Inference-safe `DomainOracle` hook (zero access to `positive_completion` or answer booleans)."""
        raw = self.grade_inference_only(task, candidate)
        diags = tuple(
            DomainDiagnostic(
                rule=str(f.get("rule", "CHECK_FAILED")),
                message=sanitize_text(str(f.get("message", "")))[:280],
                line=int(f["line"]) if isinstance(f.get("line"), int) else None,
            )
            for f in raw.get("findings", [])
        )
        return DomainGradeResult(
            passed=bool(raw["passed"]),
            epistemic_status=str(raw["epistemic_status"]),
            diagnostics=diags,
            metrics=dict(raw.get("metrics", {})),
        )

    def grade_inference_only(self, item_public_view: Mapping[str, Any], completion_text: str) -> dict[str, Any]:
        """Label-free inference-time Tier 2 check (`#100`: strips ground-truth completions & hidden booleans)."""
        stripped = {
            k: v
            for k, v in item_public_view.items()
            if k not in ("positive_completion", "negative_completion", "expected_tier", "expected_action")
        }
        fam = str(stripped.get("family", "")).strip().upper()
        if fam == "H_RULE":
            is_bare, parsed = parse_bare_or_embedded_json(completion_text)
            if not is_bare or parsed is None:
                return {
                    "passed": False,
                    "epistemic_status": "REFUSED",
                    "findings": [
                        {
                            "rule": "NON_BARE_JSON_AUDIT",
                            "message": "Rule-order audit must be one bare JSON object.",
                        }
                    ],
                }
            findings: list[dict[str, Any]] = []
            bug_id = str(stripped.get("planted_bug_id", ""))
            if parsed.get("bug_id") != bug_id:
                findings.append({"rule": "WRONG_BUG_ID", "message": f"Prompt requested bug_id={bug_id!r}."})
            if not isinstance(parsed.get("diverges_on_probe"), bool):
                findings.append(
                    {"rule": "MISSING_BOOL_DIVERGES", "message": "Field diverges_on_probe must be a boolean."}
                )
            if parsed.get("epistemic_tier") != "VERIFIED":
                findings.append(
                    {
                        "rule": "FINITE_TRACE_TIER_DISCIPLINE",
                        "message": "Bounded trace replay over a single prefix must carry epistemic_tier VERIFIED, not PROVEN.",
                    }
                )
            passed = len(findings) == 0
            return {
                "passed": passed,
                "epistemic_status": "VERIFIED" if passed else "REFUSED",
                "findings": findings,
            }
        return self.grade_item(stripped, completion_text)

    def format_repair_feedback(self, task: Mapping[str, Any], grade: DomainGradeResult) -> str:
        lines = [
            f"Tier 2 `mde:soko-eval` oracle rejected the candidate (status={grade.epistemic_status}):"
        ]
        for idx, d in enumerate(grade.diagnostics[:8], start=1):
            loc = f" (line {d.line})" if d.line is not None else ""
            lines.append(f"{idx}. [{d.rule}]{loc}: {d.message}")
        lines.append("Fix every diagnostic above while respecting the Plane 1 specification.")
        return "\n".join(lines)

    def grade_item(self, item: Mapping[str, Any], completion_text: str) -> dict[str, Any]:
        """Deterministic Tier 2 grader for `mde_soko/datasets/{compile,validation}.jsonl` items."""
        fam = str(item["family"]).strip().upper()
        room = get_room(str(item["room_id"]))
        part = int(room["part"])
        grid = [str(r) for r in room["grid"]]
        findings: list[dict[str, Any]] = []

        if fam == "H_ROUTE":
            is_bare, parsed = parse_bare_or_embedded_json(completion_text)
            if not is_bare or parsed is None or "keys" not in parsed:
                findings.append(
                    {
                        "rule": "NON_BARE_JSON_OR_MISSING_KEYS",
                        "message": 'Expected one bare JSON object {"keys": "..."} with zero fences or prose.',
                    }
                )
                return {"passed": False, "epistemic_status": "REFUSED", "findings": findings}
            ver = verify_route_dual_strict(part, grid, str(parsed["keys"]))
            if not ver["exact_win"]:
                findings.append({"rule": ver["failure_rule"], "message": ver["failure_message"]})
                return {"passed": False, "epistemic_status": "REFUSED", "findings": findings}
            return {
                "passed": True,
                "epistemic_status": "VERIFIED",
                "findings": [],
                "metrics": {"route_len": ver["route_len"], "traj_fnv64": ver["traj_fnv64"]},
            }

        if fam == "H_PROBE":
            is_bare, parsed = parse_bare_or_embedded_json(completion_text)
            if not is_bare or parsed is None:
                findings.append(
                    {
                        "rule": "NON_BARE_JSON_PROBE",
                        "message": "Stateful probe reply must be one bare JSON object.",
                    }
                )
                return {"passed": False, "epistemic_status": "REFUSED", "findings": findings}
            action = str(parsed.get("action", "")).strip()
            expected_action = str(item.get("expected_action", "probe"))
            if action != expected_action:
                findings.append(
                    {
                        "rule": "WRONG_STATEFUL_ACTION",
                        "message": f"Expected stateful action {expected_action!r}, got {action!r}.",
                    }
                )
            if action in ("probe", "step"):
                keys = str(parsed.get("key") or parsed.get("keys") or "")
                if not (1 <= len(keys) <= 2) or any(ch not in VALID_SOKO_KEYS for ch in keys):
                    findings.append(
                        {
                            "rule": "NON_MINIMAL_PROBE_BATCH",
                            "message": "Mechanics probe must supply 1 to 2 valid U/D/L/R/A keys.",
                        }
                    )
                else:
                    ver = verify_route_dual_strict(part, grid, keys)
                    if not ver["alive"]:
                        findings.append(
                            {
                                "rule": "FATAL_PROBE_STEP",
                                "message": "Probe key killed an active or inactive hero.",
                            }
                        )
            passed = len(findings) == 0
            return {
                "passed": passed,
                "epistemic_status": "VERIFIED" if passed else "REFUSED",
                "findings": findings,
            }

        if fam == "H_RULE":
            is_bare, parsed = parse_bare_or_embedded_json(completion_text)
            if not is_bare or parsed is None:
                findings.append(
                    {
                        "rule": "NON_BARE_JSON_AUDIT",
                        "message": "Rule-order audit must be one bare JSON object.",
                    }
                )
                return {"passed": False, "epistemic_status": "REFUSED", "findings": findings}
            bug_id = str(item["planted_bug_id"])
            probe_route = str(item["probe_route"])
            clean_sim = PuzzleScriptOracle(part, grid)
            mut_sim = PuzzleScriptOracle(part, grid, flags=MutatorFlags(bug_id=bug_id))
            for ch in probe_route:
                clean_sim.step(ch)
                mut_sim.step(ch)
            diverges = clean_sim.state_signature() != mut_sim.state_signature()
            if parsed.get("bug_id") != bug_id:
                findings.append({"rule": "WRONG_BUG_ID", "message": f"Expected bug_id={bug_id!r}."})
            if parsed.get("diverges_on_probe") is not diverges:
                findings.append(
                    {"rule": "WRONG_DIVERGENCE_VERDICT", "message": "Divergence boolean disagrees with oracle."}
                )
            if parsed.get("epistemic_tier") != "VERIFIED":
                findings.append(
                    {"rule": "EXPECTED_TIER_MISMATCH", "message": "Differential bug check must report tier VERIFIED."}
                )
            passed = len(findings) == 0
            return {
                "passed": passed,
                "epistemic_status": "VERIFIED" if passed else "REFUSED",
                "findings": findings,
            }

        if fam == "H_CELL":
            code = extract_python_cell(completion_text)
            if code is None:
                return {
                    "passed": False,
                    "epistemic_status": "REFUSED",
                    "findings": [
                        {
                            "rule": "MISSING_PYTHON_CELL",
                            "message": "Expected a fenced ```python ... ``` micro-solver cell.",
                        }
                    ],
                }
            sb = execute_sandbox_cell(code, timeout_sec=MAX_CELL_TIMEOUT_SEC)
            if not sb["ok"]:
                return {
                    "passed": False,
                    "epistemic_status": "REFUSED",
                    "findings": list(sb["findings"]),
                }
            is_bare_out, parsed_out = parse_bare_or_embedded_json(sb["stdout"])
            if not is_bare_out or parsed_out is None or "keys" not in parsed_out:
                return {
                    "passed": False,
                    "epistemic_status": "REFUSED",
                    "findings": [
                        {
                            "rule": "CELL_MISSING_JSON_KEYS",
                            "message": 'Cell stdout must print a bare JSON object {"keys": "..."}.',
                        }
                    ],
                }
            ver = verify_route_dual_strict(part, grid, str(parsed_out["keys"]))
            if not ver["exact_win"]:
                return {
                    "passed": False,
                    "epistemic_status": "REFUSED",
                    "findings": [{"rule": ver["failure_rule"], "message": ver["failure_message"]}],
                }
            return {
                "passed": True,
                "epistemic_status": "VERIFIED",
                "findings": [],
                "metrics": {"route_len": ver["route_len"], "traj_fnv64": ver["traj_fnv64"]},
            }

        return {
            "passed": False,
            "epistemic_status": "REFUSED",
            "findings": [{"rule": "UNKNOWN_FAMILY", "message": f"Unsupported family {fam!r}"}],
        }
