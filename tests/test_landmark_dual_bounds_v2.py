"""Deterministic regression and `must_fail` tests for Wave 4 V2 `15x7` `III-14` bounds & endgame search."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from experiments.landmark_dual_bounds_v2.iii14_bidirectional_endgame import (
    run_iii14_bidirectional_endgame_audit,
)
from experiments.landmark_dual_bounds_v2.replay_v2 import (
    DEFAULT_EVIDENCE_DIR,
    REPO_ROOT,
    verify_all_v2_receipts,
    verify_v2_floor_receipt_dict,
)


class TestLandmarkDualBoundsV2(unittest.TestCase):
    def test_01_cpp20_v2_prover_strict_portable_compile(self) -> None:
        compiler = None
        for cand in ("clang++", "g++-16", "g++-15", "g++", "c++"):
            exe = shutil.which(cand)
            if exe is not None:
                compiler = exe
                break
        if compiler is None:
            self.fail("No C++20 compiler found on PATH")
        cpp_src = REPO_ROOT / "experiments" / "landmark_dual_bounds_v2" / "prove_iii14_15x7_v2_floor.cpp"
        with tempfile.TemporaryDirectory() as td:
            out_bin = Path(td) / "prove_v2"
            proc = subprocess.run(
                [compiler, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror", "-pthread", str(cpp_src), "-o", str(out_bin)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertTrue(out_bin.is_file())

    def test_02_iii14_retrograde_vault_endgame_tablebase_and_48x_astar(self) -> None:
        res = run_iii14_bidirectional_endgame_audit()
        self.assertEqual(res["epistemic_status"], "VERIFIED")
        qa = res["quotient_tablebase_audit"]
        self.assertEqual(qa["goal_violations"], 0)
        self.assertEqual(qa["step_violations"], 0)
        self.assertGreater(qa["forward_quotient_edges_checked"], 800_000)

        eg = res["endgame_12key_search"]
        self.assertEqual(eg["remaining_keys_certified_exact"], 12)
        self.assertFalse(eg["sub_48_tail_exists_from_t36"])
        self.assertLess(eg["tb_guided_astar_expanded_states"] * 20, eg["blind_bfs_expanded_states"])
        self.assertTrue(eg["rebuilt_48_route_dual_verified"])
        self.assertTrue(all(res["must_fail_controls"].values()))

    def test_03_decoupled_v2_evidence_receipts_and_must_fail_tamper_rejection(self) -> None:
        summary = verify_all_v2_receipts(DEFAULT_EVIDENCE_DIR)
        self.assertTrue(summary["overall_passed"])
        self.assertGreaterEqual(summary["certified_15x7_iii14_floor"], 41)
        self.assertGreater(summary["quotient_edges_verified"], 20_000_000_000)
        self.assertGreater(summary["concrete_walk_edges_verified"], 50_000_000)
        self.assertTrue(all(summary["must_fail_controls"].values()))

        # Explicit corruptions rejected fail-closed
        raw = json.loads((DEFAULT_EVIDENCE_DIR / "iii14_15x7_v2_floor_receipt.json").read_text(encoding="utf-8"))
        bad_walk = dict(raw, concrete_random_walk_audit={"edges_checked": 60_000_000, "violations": 1})
        self.assertFalse(
            verify_v2_floor_receipt_dict(bad_walk, raw["prover_source_sha256"], raw["board_sha256_lf"])["valid"]
        )


if __name__ == "__main__":
    unittest.main()
