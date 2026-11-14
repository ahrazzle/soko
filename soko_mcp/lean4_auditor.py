"""Static source lint for Lean 4 modules that claim stock-`Init` proofs.

This is a text scan, not a proof check. It reads a Lean 4 source file with
comments removed and string contents blanked, and reports:

- trust-boundary keywords: `sorry`, `admit`, `axiom`, `opaque`, `native_decide`;
- syntax overrides: `notation`, `infix`, `infixl`, `infixr`, `prefix`,
  `postfix`, `macro`, `elab`;
- attributes `extern`, `implemented_by`, `csimp`;
- with ``strict_init_only``: Mathlib-only tactics (`ring`, `ring_nf`,
  `linarith`, `nlinarith`, `polyrith`, `norm_num`) and `import Mathlib`,
  `import Batteries` or `import Std`;
- a `Float`-typed field or binder (`: Float`), since toy `Int`/`Nat` theorems
  say nothing about IEEE-754 values carried beside them;
- a line ending in `:= by omega` whose left side has a left-associated
  constant-times-variable product applied to a parenthesised term, a common
  sign of a nonlinear goal handed to `omega`.

A clean result means none of these patterns appear. It does not mean the
module compiles or that its theorems state what a paper claims; compile it and
run `#print axioms` for that. Known limits: identifiers named like a keyword
(for example a variable `prefix`) are reported; a `"` inside a character
literal confuses the string scanner; declarations split across lines are read
line by line.

Origin: the gem-nexus vault drop of 2026-11-13 (Drive
1EE8vh4oIbAlymoMsdNWlHqp5uIImX_Ni). Changed on the way in: `ac_rfl` is no
longer reported (it is a core Lean 4 tactic and compiles without Mathlib),
`import Batteries` is added, and the self-test that read files from the
author's machine is replaced by tests in tests/test_lean4_auditor.py and a
command line.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Dict, List, Sequence


FORBIDDEN_TRUST_KEYWORDS = {
    "sorry": "UNPROVED_SORRY",
    "admit": "UNPROVED_ADMIT",
    "axiom": "EXTRA_AXIOM_DECL",
    "opaque": "OPAQUE_CONST_DECL",
    "native_decide": "UNVERIFIED_NATIVE_DECIDE",
}

FORBIDDEN_SYNTAX_OVERRIDES = {"notation", "infix", "infixl", "infixr", "prefix", "postfix", "macro", "elab"}
FORBIDDEN_ATTRS = {"extern", "implemented_by", "csimp"}
NON_INIT_TACTICS = {"ring", "ring_nf", "linarith", "nlinarith", "polyrith", "norm_num"}


def strip_lean_comments_preserve_strings(src: str) -> str:
    """Strip `--` line comments and nested `/- ... -/` block comments while replacing
    string literal contents with `"S"` (non-empty placeholder preserving string presence!).
    """
    out: List[str] = []
    i, n = 0, len(src)
    depth = 0
    while i < n:
        if depth > 0:
            if src[i:i+2] == "/-":
                depth += 1
                i += 2
            elif src[i:i+2] == "-/":
                depth -= 1
                i += 2
            else:
                if src[i] == "\n":
                    out.append("\n")
                i += 1
        else:
            if src[i:i+2] == "/-":
                depth = 1
                i += 2
            elif src[i:i+2] == "--":
                while i < n and src[i] != "\n":
                    i += 1
            elif src[i] == '"':
                out.append('"S"')
                i += 1
                while i < n and src[i] != '"':
                    if src[i] == "\\" and i + 1 < n:
                        i += 2
                    else:
                        if src[i] == "\n":
                            out.append("\n")
                        i += 1
                if i < n:
                    i += 1
            else:
                out.append(src[i])
                i += 1
    return "".join(out)


def audit_lean4_source(source: str, label: str = "<lean>", strict_init_only: bool = True) -> Dict[str, object]:
    cleaned = strip_lean_comments_preserve_strings(source)
    findings: List[Dict[str, object]] = []

    for lineno, line in enumerate(cleaned.splitlines(), 1):
        tokens = re.findall(r"@\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_']*|\S", line)
        # 1. Trust-boundary keywords & attributes
        for tok in tokens:
            if tok in FORBIDDEN_TRUST_KEYWORDS:
                findings.append({"line": lineno, "code": FORBIDDEN_TRUST_KEYWORDS[tok], "detail": tok})
            elif tok in FORBIDDEN_SYNTAX_OVERRIDES:
                findings.append({"line": lineno, "code": "SYNTAX_OVERRIDE_DECL", "detail": tok})
            elif tok.startswith("@["):
                inner = tok[2:-1]
                for attr in FORBIDDEN_ATTRS:
                    if re.search(rf"\b{attr}\b", inner):
                        findings.append({"line": lineno, "code": "UNSOUND_ATTRIBUTE", "detail": tok})
            elif strict_init_only and tok in NON_INIT_TACTICS:
                findings.append({"line": lineno, "code": "NON_INIT_TACTIC", "detail": tok})

        if strict_init_only and re.match(r"^\s*import\s+(Mathlib|Batteries|Std)\b", line):
            findings.append({"line": lineno, "code": "NON_INIT_IMPORT", "detail": line.strip()})

        # 2. Unused / unverified Float spec carrier warning
        if re.search(r":\s*Float\b", line):
            findings.append({"line": lineno, "code": "IEEE754_FLOAT_SPEC_CARRIER", "detail": line.strip()})

        # 3. Left-associated nonlinear variable product directly on an `:= by omega` step:
        # e.g. `-5 * c * (p * p) + 6 * c * p - c := by omega`
        if re.search(r":=\s*by\s+omega\b", line):
            lhs = line.split(":=")[0]
            if re.search(r"\b\d+\s*\*\s*[A-Za-z_]\w*\s*\*\s*\(", lhs):
                findings.append({
                    "line": lineno,
                    "code": "NONLINEAR_PRODUCT_IN_OMEGA",
                    "detail": lhs.strip(),
                })

    return {
        "label": label,
        "ok": len(findings) == 0,
        "finding_count": len(findings),
        "findings": findings,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Lint each Lean file given on the command line; print JSON; exit 1 on any finding."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: python3 -m soko_mcp.lean4_auditor FILE.lean [FILE.lean ...]", file=sys.stderr)
        return 2
    results = []
    for path in args:
        with open(path, encoding="utf-8") as fh:
            results.append(audit_lean4_source(fh.read(), label=path))
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
