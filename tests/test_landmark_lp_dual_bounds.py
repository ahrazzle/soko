"""Deterministic unit and regression tests for `feat/landmark-lp-dual-bounds` (`soko#38` & `soko#53` E3/C7/C2/C3/C1).

Discipline guarantees (`soko#53` A3, A6, A7):
- Zero wall-clock assertions; all assertions test exact node/edge/state counts, rational identities,
  and deterministic seeds.
- Zero bare `assert` statements; runs identically under `python3 -O -B`.
- Every positive verification is paired with non-tautological `must_fail` corruption controls that
  exercise the live checker/verifier gates.
"""
from __future__ import annotations

from fractions import Fraction
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from experiments.landmark_dual_bounds.hero_assignment_bounds import (
    HungarianDualCertificate,
    ceil_fraction,
    load_strict_rational_json,
    parse_strict_fraction,
    run_c2_must_fail_controls,
    run_full_c2_audit,
    solve_exact_bipartite_assignment,
    verify_bipartite_assignment_dual,
)
from experiments.landmark_dual_bounds.iii14_nrpa_runner import (
    find_cpp20_compiler,
    run_iii14_nrpa_experiment,
)
from experiments.landmark_dual_bounds.iii21_retrograde_tb import run_full_c3_retrograde_audit
from experiments.landmark_dual_bounds.original_border_audit import (
    EXPECTED_BOARD_SHA256_LF,
    audit_original_iii14_border_harvest,
)
from experiments.landmark_dual_bounds.quotient_consistency_lp import (
    project_quotient_1lipschitz_lp,
    run_soko38_repair_audit,
    verify_projected_lp_certificate,
    verify_step_consistency,
)
from experiments.landmark_dual_bounds.replay_all import (
    DEFAULT_EVIDENCE_DIR,
    verify_all_evidence_receipts,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PROVER_CPP = REPO_ROOT / "experiments" / "landmark_dual_bounds" / "prove_iii14_15x7_landmark_floor.cpp"


class TestLandmarkLpDualBounds(unittest.TestCase):
    def test_01_original_iii14_outer_border_harvest_audit(self) -> None:
        # Check whether cached Part III HTML is available; if offline without cache, skip network fetch cleanly
        try:
            res = audit_original_iii14_border_harvest()
        except Exception as exc:
            if "curl" in str(exc) or "Could not resolve" in str(exc):
                self.skipTest(f"Offline environment without cached Part III HTML: {exc}")
            raise
        self.assertEqual(res["epistemic_status"], "VERIFIED")
        self.assertTrue(res["outer_border_harvest_legal_in_original"])
        self.assertTrue(res["outer_border_harvest_strictly_necessary_in_room14"])
        self.assertEqual(res["minimum_border_harvests_required_to_win"], 9)
        self.assertEqual(res["room14_level"]["board_sha256_lf"], EXPECTED_BOARD_SHA256_LF)
        self.assertEqual(len(res["puzzlescript_rule_evidence"]["distinct_border_wall_objects_found"]), 0)
        self.assertEqual(len(res["puzzlescript_rule_evidence"]["druid_wall_to_crate_rule"]), 1)
        self.assertTrue(res["must_fail_control"]["must_fail_triggered"])
        for name in ("R48", "W41"):
            self.assertTrue(res["witness_replays"][name]["dual_oracle_exact_win"])
            self.assertTrue(res["witness_replays"][name]["atom_40_invariant_preserved"])
            self.assertGreaterEqual(res["witness_replays"][name]["distinct_border_walls_harvested"], 9)

    def test_02_soko38_consistency_repair_and_1lipschitz_lp_duality(self) -> None:
        res = run_soko38_repair_audit()
        self.assertEqual(res["epistemic_status"], "VERIFIED")
        self.assertEqual(res["raw_unrepaired"]["h_before"], 12)
        self.assertEqual(res["raw_unrepaired"]["h_after"], 10)
        self.assertEqual(res["raw_unrepaired"]["drop"], 2)
        self.assertGreaterEqual(res["raw_unrepaired"]["violations_in_ball"], 1)

        self.assertEqual(res["prefunded_potential_repair"]["h_before"], 11)
        self.assertEqual(res["prefunded_potential_repair"]["h_after"], 10)
        self.assertEqual(res["prefunded_potential_repair"]["violations"], 0)

        self.assertEqual(res["quotient_1lipschitz_lp_repair"]["h_before"], "11")
        self.assertEqual(res["quotient_1lipschitz_lp_repair"]["h_after"], "10")
        self.assertTrue(res["quotient_1lipschitz_lp_repair"]["strong_duality_exact"])
        self.assertTrue(res["quotient_1lipschitz_lp_repair"]["second_checker_valid"])
        for ctrl_ok in res["must_fail_controls"].values():
            self.assertTrue(ctrl_ok)

        # Fractional edge-weight test on `project_quotient_1lipschitz_lp` (`Fraction` exactness, zero float)
        verts = ["u0", "u1", "g"]
        edges = [("u0", "u1", Fraction(3, 2)), ("u1", "g", Fraction(5, 2))]
        h_raw = {"u0": Fraction(6), "u1": Fraction(3), "g": Fraction(0)}
        lp_q = project_quotient_1lipschitz_lp(verts, ["g"], edges, h_raw)
        self.assertEqual(lp_q.projected_h["u1"], Fraction(5, 2))
        self.assertEqual(lp_q.projected_h["u0"], Fraction(4, 1))
        self.assertTrue(lp_q.strong_duality_exact)
        self.assertTrue(verify_projected_lp_certificate(verts, ["g"], edges, h_raw, lp_q)["valid"])

        # Rational ceiling 1-step consistency preservation (`x - y <= 1 -> ceil(x) - ceil(y) <= 1`)
        for num_x in range(0, 25):
            for num_y in range(0, 25):
                qx = Fraction(num_x, 6)
                qy = Fraction(num_y, 6)
                if qx - qy <= 1:
                    self.assertLessEqual(ceil_fraction(qx) - ceil_fraction(qy), 1)

    def test_03_strict_rational_parser_and_hungarian_duality(self) -> None:
        self.assertEqual(parse_strict_fraction("13/6"), Fraction(13, 6))
        self.assertEqual(ceil_fraction(Fraction(13, 6)), 3)
        with self.assertRaises(TypeError):
            parse_strict_fraction(True)
        with self.assertRaises(TypeError):
            parse_strict_fraction(0.5)
        with self.assertRaises(ValueError):
            load_strict_rational_json('{"bad": 2.5}')
        with self.assertRaises(ValueError):
            load_strict_rational_json('{"dup": 1, "dup": 2}')

        mat = [
            [Fraction(7, 2), Fraction(2), Fraction(5)],
            [Fraction(3), Fraction(9, 2), Fraction(1)],
            [Fraction(4), Fraction(3, 2), Fraction(4)],
        ]
        cert = solve_exact_bipartite_assignment(mat)
        chk = verify_bipartite_assignment_dual(mat, cert)
        self.assertTrue(chk["valid"])
        self.assertEqual(cert.primal_cost, Fraction(6))
        self.assertEqual(cert.dual_objective, Fraction(6))

        # Tampered dual must fail closed
        bad_cert = HungarianDualCertificate(
            assignment=cert.assignment,
            primal_cost=cert.primal_cost,
            dual_u=(cert.dual_u[0] + Fraction(1, 3), cert.dual_u[1], cert.dual_u[2]),
            dual_v=cert.dual_v,
            dual_objective=cert.dual_objective + Fraction(1, 3),
        )
        self.assertFalse(verify_bipartite_assignment_dual(mat, bad_cert)["valid"])

    def test_04_c2_hero_assignment_and_operator_counting_bounds(self) -> None:
        res = run_full_c2_audit(
            REPO_ROOT / "soko_mcp" / "data" / "catalog.json",
        )
        self.assertEqual(res["epistemic_status"], "VERIFIED")
        r21 = res["rooms"]["III-21"]
        r20 = res["rooms"]["III-20"]
        self.assertEqual(r21["total_bijections_enumerated"], 720)
        self.assertEqual(r20["total_bijections_enumerated"], 120)
        self.assertEqual(r21["root_h_oc_ceil_int"], 21)
        self.assertEqual(r21["solo_min_sum"], 60)
        self.assertEqual(r21["witness_solo_sum_cost"], 86)
        self.assertEqual(r21["admissibility_violations"], 0)
        self.assertEqual(r21["rational_step_violations"], 0)
        self.assertEqual(r21["ceil_int_step_violations"], 0)
        self.assertEqual(r20["admissibility_violations"], 0)
        self.assertEqual(r20["rational_step_violations"], 0)
        self.assertEqual(r20["ceil_int_step_violations"], 0)
        controls = run_c2_must_fail_controls()
        for ok in controls.values():
            self.assertTrue(ok)

    def test_05_c3_iii21_retrograde_endgame_tablebase(self) -> None:
        res = run_full_c3_retrograde_audit(REPO_ROOT / "soko_mcp" / "data" / "catalog.json")
        self.assertEqual(res["epistemic_status"], "VERIFIED")
        qa = res["quotient_tablebase_audit"]
        self.assertEqual(qa["total_states"], 259584)
        self.assertEqual(qa["goal_violations"], 0)
        self.assertEqual(qa["step_violations"], 0)

        rv = res["route_316_verification"]
        self.assertEqual(rv["states_checked"], 317)
        self.assertEqual(rv["admissibility_violations"], 0)
        self.assertEqual(rv["step_consistency_violations"], 0)
        self.assertIn(316, rv["exact_tail_steps"])
        self.assertIn(315, rv["exact_tail_steps"])
        self.assertIn(314, rv["exact_tail_steps"])

        bd = res["bidirectional_endgame_search"]
        self.assertEqual(bd["exact_suffix_distance"], 10)
        self.assertLess(bd["tb_guided_astar_expanded_states"], bd["blind_bfs_expanded_states"])
        self.assertGreaterEqual(bd["bidirectional_meet_states_count"], 1)
        self.assertTrue(bd["dual_oracle_verified"])
        for ok in res["must_fail_controls"].values():
            self.assertTrue(ok)

    def test_06_cpp20_iii14_landmark_prover_selftest_and_nrpa_determinism(self) -> None:
        compiler = find_cpp20_compiler()
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            prover_bin = tmp / "prove_iii14_landmark"
            out_json = tmp / "selftest.json"
            build = subprocess.run(
                [compiler, "-O3", "-std=c++20", "-pthread", str(PROVER_CPP), "-o", str(prover_bin)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(build.returncode, 0, build.stderr[:1000])
            run = subprocess.run(
                [
                    str(prover_bin),
                    "--self-test",
                    "--walk-edges",
                    "100000",
                    "--max-states",
                    "512000",
                    "--source-path",
                    str(PROVER_CPP),
                    "--json-out",
                    str(out_json),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run.returncode, 0, run.stderr[:1000] + run.stdout[-1000:])
            st_data = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(st_data["board_sha256_lf"], EXPECTED_BOARD_SHA256_LF)
            self.assertEqual(st_data["exhaustive_quotient_edge_audit"]["total_violations"], 0)
            self.assertGreater(
                st_data["exhaustive_quotient_edge_audit"]["total_forward_quotient_edges_checked"],
                4_600_000_000,
            )
            self.assertEqual(st_data["concrete_random_walk_audit"]["violations"], 0)
            self.assertEqual(st_data["astar_summary"]["bellman_violations"], 0)
            for ok in st_data["must_fail_controls"].values():
                self.assertTrue(ok)

        # Deterministic NRPA seed repeatability check across different thread counts (1 vs 4 threads)
        nrpa_a = run_iii14_nrpa_experiment(
            seed=424242, level=1, iterations=8, restarts_prim=1, restarts_open=2, restarts_47=1, horizon_open=50, threads=1
        )
        nrpa_b = run_iii14_nrpa_experiment(
            seed=424242, level=1, iterations=8, restarts_prim=1, restarts_open=2, restarts_47=1, horizon_open=50, threads=4
        )
        self.assertEqual(nrpa_a["total_rollouts_executed"], nrpa_b["total_rollouts_executed"])
        self.assertEqual(nrpa_a["shortest_nrpa_win_len"], nrpa_b["shortest_nrpa_win_len"])

    def test_07_decoupled_evidence_receipts_replay_all(self) -> None:
        summary = verify_all_evidence_receipts(DEFAULT_EVIDENCE_DIR)
        self.assertTrue(summary["overall_passed"])
        self.assertGreaterEqual(summary["certified_15x7_iii14_floor"], 40)
        self.assertGreaterEqual(summary["concrete_walk_edges_verified"], 50_000_000)
        self.assertEqual(summary["lean_theorems_bound"], 6)
        for ok in summary["must_fail_controls"].values():
            self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
