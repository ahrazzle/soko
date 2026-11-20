"""Native-search contracts: useful search and conservative interrupted bounds."""
import json
from pathlib import Path
import subprocess
import time
import unittest

from soko_mcp.engine_bridge import ensure_cpp_engine, verify_route_dual
from soko_mcp.catalog import load_catalog
from soko_mcp.oracle import FRONTIER_ROOMS


class BoundedSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exe = ensure_cpp_engine()
        if cls.exe is None:
            raise unittest.SkipTest("C++20 compiler unavailable")

    def invoke(self, mode, grid=None, part=1, p1=20, p2=1000, budget=2, route="-"):
        grid = grid or FRONTIER_ROOMS["I-1"]["grid"]
        payload = (f"{mode} {part} {len(grid[0])} {len(grid)} {p1} {p2} {budget}\n"
                   + "\n".join(grid) + f"\n{route}\n")
        run = subprocess.run([str(self.exe)], input=payload, text=True,
                             capture_output=True, timeout=10, check=True)
        return json.loads(run.stdout)

    def test_optimizer_shortens_real_verified_detour(self):
        seed = "U" + "R" * 9 + "D"
        meta = FRONTIER_ROOMS["I-1"]
        self.assertTrue(verify_route_dual(1, meta["grid"], seed)["valid_winning_route"])
        result = self.invoke("optimize", p1=1000, p2=14, route=seed)
        self.assertEqual(result["best_route"], "R" * 9)
        self.assertTrue(verify_route_dual(1, meta["grid"], result["best_route"])["valid_winning_route"])
        # The improvement must come from the exact window search, not the heuristic tube beam.
        self.assertTrue(result["stages"][0].startswith("window_bfs:"))

    def test_zero_budget_never_claims_positive_floor(self):
        result = self.invoke("prove_lb", p1=500, budget=0)
        self.assertEqual(result["proven_floor"], 0)
        self.assertEqual(result["completed_depth"], -1)
        self.assertFalse(result["exact_optimum_reached"])
        self.assertTrue(result["timed_out"])
        self.assertEqual(result["nodes_expanded"], 0)

    def test_interrupted_layer_does_not_claim_requested_bound(self):
        # This corridor requires four R moves. A three-state cap interrupts the
        # A* layer f = h(start) = 4 before the goal is generated. Layers below
        # the start heuristic count as complete (conditional on admissibility)
        # once the start node is expanded, so the floor is 4, never the bound.
        result = self.invoke("prove_lb", grid=["F...G"], p1=100, p2=3)
        self.assertEqual(result["completed_depth"], 3)
        self.assertEqual(result["proven_floor"], 4)
        self.assertLessEqual(result["proven_floor"], 4)  # the true optimum
        self.assertEqual(result["termination_reason"], "state_limit")
        self.assertEqual(result["states_seen"], 3)
        self.assertFalse(result["exact_optimum_reached"])
        self.assertEqual(result["winning_witness"], "")

    def test_shortest_witness_has_completed_smaller_depths(self):
        result = self.invoke("prove_lb", p1=20)
        self.assertEqual(result["winning_witness"], "R" * 9)
        self.assertEqual(result["proven_floor"], 9)
        self.assertEqual(result["completed_depth"], 8)
        self.assertTrue(result["exact_optimum_reached"])
        self.assertFalse(result["timed_out"])
        self.assertEqual(result["hash_collisions_prevented"], 0)

    def test_depth_limit_does_not_expand_past_requested_depth(self):
        result = self.invoke("solve", p1=0)
        self.assertFalse(result["solved"])
        self.assertEqual(result["completed_depth"], 0)
        self.assertEqual(result["nodes_expanded"], 0)
        self.assertEqual(result["termination_reason"], "depth_limit")

    def test_complete_unsolved_depth_is_a_lower_bound_without_witness(self):
        result = self.invoke("prove_lb", p1=5)
        self.assertEqual(result["proven_floor"], 6)
        self.assertEqual(result["completed_depth"], 5)
        self.assertEqual(result["epistemic_status"], "EXHAUSTIVE_LOWER_BOUND")
        self.assertFalse(result["exact_optimum_reached"])

    def test_exhausted_reachable_graph_cannot_invent_a_solution(self):
        result = self.invoke("prove_lb", grid=["F#G"], p1=10)
        self.assertEqual(result["termination_reason"], "exhausted")
        self.assertEqual(result["proven_floor"], 11)
        self.assertFalse(result["exact_optimum_reached"])
        self.assertEqual(result["winning_witness"], "")

    def test_solve_and_optimize_honor_zero_budget(self):
        start = time.monotonic()
        solved = self.invoke("solve", p1=500, budget=0)
        optimized = self.invoke("optimize", p1=1000, p2=14, budget=0, route="U" + "R" * 9 + "D")
        self.assertFalse(solved["solved"])
        self.assertEqual(optimized["best_route"], "U" + "R" * 9 + "D")
        self.assertTrue(solved["timed_out"])
        self.assertTrue(optimized["timed_out"])
        self.assertLess(time.monotonic() - start, 5)

    def test_large_board_ida_star_reports_how_it_stopped(self):
        # Boards over 256 cells use the IDA* strategy (review 5907250524, finding 4).
        meta = load_catalog()["III-21"]
        finished = self.invoke("prove_lb", grid=meta["grid"], part=3, p1=5, p2=0, budget=30)
        self.assertEqual(finished["search_strategy"], "exact_state_ida_star")
        self.assertEqual(finished["termination_reason"], "max_bound")
        self.assertFalse(finished["timed_out"])
        self.assertEqual(finished["proven_floor"], 6)
        self.assertEqual(finished["completed_depth"], 5)
        self.assertGreater(finished["states_seen"], 0)
        stopped = self.invoke("prove_lb", grid=meta["grid"], part=3, p1=40, p2=0, budget=0)
        self.assertEqual(stopped["termination_reason"], "time_budget")
        self.assertTrue(stopped["timed_out"])
        self.assertEqual(stopped["proven_floor"], 0)

    def test_bound_zero_is_not_raised_to_one(self):
        result = self.invoke("prove_lb", p1=0)
        self.assertEqual(result["requested_bound"], 0)
        self.assertEqual(result["proven_floor"], 1)
        self.assertEqual(result["termination_reason"], "heuristic_exceeds_bound")


if __name__ == "__main__":
    unittest.main()
