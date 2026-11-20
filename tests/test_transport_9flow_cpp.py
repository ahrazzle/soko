"""Portable ISO C++20 compilation and execution tests for transport-relaxation verifiers."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parent.parent
TR_DIR = REPO_ROOT / "experiments" / "transport_relaxation"
AUDIT_CPP = TR_DIR / "transport_relaxation_9flow_audit.cpp"
RUNGS_CPP = TR_DIR / "verify_relaxation_rungs.cpp"


def _find_cxx_compiler() -> str | None:
    return shutil.which("clang++") or shutil.which("g++") or shutil.which("c++")


class Transport9FlowCppTests(unittest.TestCase):
    def test_no_gnu_bits_stdcpp_header_dependency(self) -> None:
        for src in (AUDIT_CPP, RUNGS_CPP):
            text = src.read_text(encoding="utf-8")
            self.assertNotIn("bits/stdc++.h", text, f"{src.name} must use standard ISO C++20 headers")

    def test_transport_9flow_audit_compiles_and_verifies_r30_r33(self) -> None:
        cxx = _find_cxx_compiler()
        if cxx is None:
            self.skipTest("No C++20 compiler available")
        with tempfile.TemporaryDirectory() as td:
            audit_bin = Path(td) / "transport_relaxation_9flow_audit"
            comp = subprocess.run(
                [cxx, "-std=c++20", "-O2", str(AUDIT_CPP), "-o", str(audit_bin)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(comp.returncode, 0, msg=comp.stderr)

            run = subprocess.run(
                [str(audit_bin)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run.returncode, 0, msg=run.stderr)
            self.assertIn(
                "1. R1/R2 Witness r30 (H=30, t_L=29): BipartiteMatching=9/9 | TimeExpanded9Flow=5/9",
                run.stdout,
            )
            self.assertIn(
                "2. R3 Flow Witness r33 (H=33, t_L=32): BipartiteMatching=9/9 | TimeExpanded9Flow=9/9",
                run.stdout,
            )

            rungs_bin = Path(td) / "verify_relaxation_rungs"
            comp_rungs = subprocess.run(
                [cxx, "-std=c++20", "-O2", "-DNDEBUG", str(RUNGS_CPP), "-o", str(rungs_bin)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(comp_rungs.returncode, 0, msg=comp_rungs.stderr)


if __name__ == "__main__":
    unittest.main()
