"""prove_floor on a checkout with no compiled engine (review 5907250524, finding 2).

The binary is untracked, so a fresh clone has none. The first prove_floor call must
compile it before it requires the binary pin, and must name a missing compiler
instead of reporting the source lock as broken.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from soko_mcp import engine_bridge as eb
from soko_mcp.server import FRONTIER_ROOMS


class FreshCloneProveFloorTests(unittest.TestCase):
    def _empty_build_dir(self) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="fresh-build-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        build = tmp / "build"
        patches = [
            mock.patch.object(eb, "CPP_BIN_DIR", build),
            mock.patch.object(eb, "CPP_BIN", build / eb.CPP_BIN.name),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.assertFalse(eb.CPP_BIN.exists())
        return build

    def test_first_prove_floor_compiles_the_engine(self) -> None:
        if not (shutil.which("g++") or shutil.which("clang++")):
            raise unittest.SkipTest("C++20 compiler unavailable")
        self._empty_build_dir()
        meta = FRONTIER_ROOMS["I-1"]
        out = eb.prove_floor_verified(meta["part"], meta["grid"], max_bound=20, budget_sec=10)
        self.assertEqual(out["epistemic_status"], "VERIFIED")
        self.assertEqual(out["proven_floor"], 9)
        self.assertTrue(eb.CPP_BIN.is_file())

    def test_missing_compiler_is_reported_as_backend_unavailable(self) -> None:
        self._empty_build_dir()
        meta = FRONTIER_ROOMS["I-1"]
        self.assertTrue(eb.verify_tcb_lock()["tcb_locked"])
        with mock.patch.object(eb.shutil, "which", return_value=None):
            out = eb.prove_floor_verified(meta["part"], meta["grid"], max_bound=20, budget_sec=10)
        self.assertEqual(out["epistemic_status"], "BACKEND_UNAVAILABLE")
        self.assertEqual(out["unavailable_reason"], "cpp_compile_unavailable_or_failed")
        self.assertEqual(out["proven_floor"], 0)
        self.assertIsNone(out["guarantee"])
        self.assertFalse(eb.CPP_BIN.exists())


if __name__ == "__main__":
    unittest.main()
