"""Tests for soko_mcp/lean4_auditor.py (a source lint, not a proof check)."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from soko_mcp.lean4_auditor import audit_lean4_source, main, strip_lean_comments_preserve_strings

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "lean4_auditor"


def codes(src: str, strict: bool = True) -> set:
    return {f["code"] for f in audit_lean4_source(src, strict_init_only=strict)["findings"]}


class TestCleanModules(unittest.TestCase):
    def test_stock_init_module_is_clean(self) -> None:
        res = audit_lean4_source((FIXTURES / "clean_pure_init.lean").read_text(encoding="utf-8"))
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["finding_count"], 0)

    def test_core_tactics_are_not_reported(self) -> None:
        src = (
            "theorem t (a b c : Nat) : a + b + c = c + (b + a) := by ac_rfl\n"
            "theorem u (x : Int) (h : 0 < x) : 1 <= x := by omega\n"
            "example : 2 + 2 = 4 := by decide\n"
        )
        self.assertEqual(codes(src), set())


class TestTrustBoundary(unittest.TestCase):
    def test_semicolon_axiom_notation_and_attribute(self) -> None:
        src = (
            "def ok : Int := 1; axiom sneaky : False\n"
            'notation:50 lhs " = " rhs => True\n'
            '@[simp, extern "c"] def f : Nat := 0\n'
        )
        self.assertLessEqual(
            {"EXTRA_AXIOM_DECL", "SYNTAX_OVERRIDE_DECL", "UNSOUND_ATTRIBUTE"}, codes(src)
        )

    def test_each_trust_keyword(self) -> None:
        expected = {
            "theorem a : False := by sorry": "UNPROVED_SORRY",
            "theorem a : False := by admit": "UNPROVED_ADMIT",
            "opaque k : Nat": "OPAQUE_CONST_DECL",
            "example : 10 < 11 := by native_decide": "UNVERIFIED_NATIVE_DECIDE",
            "@[implemented_by g] def h : Nat := 0": "UNSOUND_ATTRIBUTE",
            "@[csimp] theorem e : @f = @g := rfl": "UNSOUND_ATTRIBUTE",
            "macro \"x\" : term => `(0)": "SYNTAX_OVERRIDE_DECL",
        }
        for src, code in expected.items():
            with self.subTest(src=src):
                self.assertIn(code, codes(src))

    def test_keywords_in_comments_and_strings_are_ignored(self) -> None:
        src = (
            "-- sorry axiom native_decide\n"
            "/- nested /- sorry -/ still a comment: axiom -/\n"
            'def s : String := "sorry axiom notation"\n'
        )
        self.assertEqual(codes(src), set())

    def test_code_after_a_block_comment_is_still_read(self) -> None:
        self.assertIn("UNPROVED_SORRY", codes("/- note -/ theorem a : False := by sorry\n"))


class TestInitOnlyChecks(unittest.TestCase):
    def test_mathlib_tactics_and_imports(self) -> None:
        for src, code in (
            ("import Mathlib.Tactic\n", "NON_INIT_IMPORT"),
            ("import Batteries\n", "NON_INIT_IMPORT"),
            ("example (x : Int) : x * 2 = 2 * x := by ring\n", "NON_INIT_TACTIC"),
            ("example (x : Int) (h : 0 < x) : 0 <= x := by linarith\n", "NON_INIT_TACTIC"),
            ("example : (2 : Int) + 2 = 4 := by norm_num\n", "NON_INIT_TACTIC"),
        ):
            with self.subTest(src=src):
                self.assertIn(code, codes(src))

    def test_relaxed_mode_skips_init_checks(self) -> None:
        self.assertEqual(codes("import Mathlib\nexample : 1 = 1 := by norm_num\n", strict=False), set())

    def test_float_spec_carrier(self) -> None:
        src = "structure OrthogonalUpdatePair where\n  normSqParent : Float\n  innerProd    : Float\n"
        res = audit_lean4_source(src)
        self.assertEqual([f["line"] for f in res["findings"]], [2, 3])
        self.assertEqual(codes(src), {"IEEE754_FLOAT_SPEC_CARRIER"})

    def test_nonlinear_product_before_omega(self) -> None:
        src = "  _ = -5 * c * (p * p) + 6 * c * p - c := by omega\n"
        self.assertEqual(codes(src), {"NONLINEAR_PRODUCT_IN_OMEGA"})
        self.assertEqual(codes("  _ = 5 * c + 6 * p := by omega\n"), set())


class TestStripper(unittest.TestCase):
    def test_line_numbers_survive_block_comments(self) -> None:
        src = "/-\nline2\nline3\n-/\ntheorem a : False := by sorry\n"
        self.assertEqual(strip_lean_comments_preserve_strings(src).count("\n"), src.count("\n"))
        self.assertEqual(audit_lean4_source(src)["findings"][0]["line"], 5)


class TestCommandLine(unittest.TestCase):
    def test_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "Bad.lean")
            Path(bad).write_text("theorem a : False := by sorry\n", encoding="utf-8")
            clean = str(FIXTURES / "clean_pure_init.lean")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main([clean]), 0)
                self.assertEqual(main([clean, bad]), 1)
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main([]), 2)

    def test_non_utf8_file_exits_nonzero_with_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "not-utf8.lean")
            Path(path).write_bytes(b"\xff\xfe theorem a : False := by sorry\n")
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = main([path])
            self.assertEqual(code, 1)
            payload = json.loads(buf.getvalue())
            self.assertEqual(len(payload), 1)
            self.assertEqual(payload[0]["label"], path)
            self.assertFalse(payload[0]["ok"])
            self.assertIn("UnicodeDecodeError", payload[0]["error"])


if __name__ == "__main__":
    unittest.main()
