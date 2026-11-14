"""Fresh-clone gate for review 5907250524 finding 2 on PR #52.

On a checkout with no compiled engine, the first Sokoban command may be
prove-floor. It must compile the engine and search, not report the lock as
unlocked with floor 0. The test copies the manifest-covered sources into a
temporary directory with no cpp/build and runs the CLI there.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HAS_COMPILER = bool(shutil.which("g++") or shutil.which("clang++"))


def _fresh_copy(dest: Path) -> None:
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "build")
    for rel in ("soko_mcp", "cpp", "tracks"):
        shutil.copytree(ROOT / rel, dest / rel, ignore=ignore)
    for rel in ("SHA256SUMS", "pyproject.toml"):
        shutil.copy2(ROOT / rel, dest / rel)


def _prove_floor(cwd: Path, room: str, max_bound: int, budget: int) -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "soko_mcp", "prove-floor", "--room", room,
         "--max-bound", str(max_bound), "--budget-sec", str(budget)],
        cwd=cwd, capture_output=True, text=True, timeout=budget + 150,
    )
    return json.loads(proc.stdout)


class FreshCloneProveFloorTests(unittest.TestCase):
    @unittest.skipUnless(HAS_COMPILER, "needs g++ or clang++")
    def test_first_prove_floor_compiles_and_searches(self) -> None:
        with tempfile.TemporaryDirectory(prefix="soko-fresh-") as tmp:
            dest = Path(tmp)
            _fresh_copy(dest)
            self.assertFalse((dest / "cpp" / "build").exists())
            out = _prove_floor(dest, "fixture:I-1", 12, 10)
            self.assertNotEqual(out["epistemic_status"], "REJECTED_TCB_UNLOCKED")
            self.assertEqual(out["epistemic_status"], "VERIFIED")
            self.assertEqual(out["proven_floor"], 9)
            self.assertTrue((dest / "cpp" / "build" / "soko_engine").is_file())

    def test_missing_compiler_is_named_not_reported_as_unlocked(self) -> None:
        with tempfile.TemporaryDirectory(prefix="soko-nocc-") as tmp:
            dest = Path(tmp)
            _fresh_copy(dest)
            env_path = str(dest / "empty-bin")
            (dest / "empty-bin").mkdir()
            proc = subprocess.run(
                [sys.executable, "-m", "soko_mcp", "prove-floor", "--room", "fixture:I-1",
                 "--max-bound", "12", "--budget-sec", "5"],
                cwd=dest, capture_output=True, text=True, timeout=120,
                env={"PATH": env_path, "PYTHONPATH": str(dest)},
            )
            out = json.loads(proc.stdout)
            self.assertEqual(out["epistemic_status"], "REJECTED_CPP_ENGINE_UNAVAILABLE")
            self.assertEqual(out["proven_floor"], 0)
            self.assertIsNone(out["guarantee"])
            self.assertEqual(out["cpp_unavailable_reason"], "cpp_compile_unavailable_or_failed")


class StrategyBSearchFieldsTests(unittest.TestCase):
    """Review 5907250524 finding 4: boards over 256 cells keep timed_out and states_seen."""

    @unittest.skipUnless(HAS_COMPILER, "needs g++ or clang++")
    def test_iii21_finished_bound_and_timeout_are_distinguished(self) -> None:
        done = _prove_floor(ROOT, "III-21", 5, 3)
        self.assertEqual(done["search_strategy"], "exact_state_ida_star")
        self.assertEqual(done["termination_reason"], "max_bound")
        self.assertIs(done["timed_out"], False)
        self.assertIsInstance(done["states_seen"], int)
        self.assertGreater(done["states_seen"], 0)

        timed = _prove_floor(ROOT, "III-21", 300, 1)
        self.assertEqual(timed["search_strategy"], "exact_state_ida_star")
        self.assertEqual(timed["termination_reason"], "time_budget")
        self.assertIs(timed["timed_out"], True)
        self.assertIsInstance(timed["states_seen"], int)


class ReadmeFloorGateTests(unittest.TestCase):
    """Review 5907250524 finding 1: READMEs state only floors this repo reproduces."""

    def test_no_unreproduced_proven_floor_in_readmes(self) -> None:
        sys.path.insert(0, str(ROOT / "tools"))
        try:
            import check_readme_floors
        finally:
            sys.path.pop(0)
        self.assertEqual(check_readme_floors.static_check(), [])


if __name__ == "__main__":
    unittest.main()
