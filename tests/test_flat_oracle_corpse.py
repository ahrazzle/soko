"""Regression tests for FlatBitmaskOracle corpse semantics (NEON-D3).

All checks use unittest assertions so they execute under `python3 -O`.
"""
import random
import unittest

from soko_mcp.catalog import get_room, load_catalog
from soko_mcp.engine_bridge import verify_route_dual
from soko_mcp.flat_oracle import FlatBitmaskOracle, replay_flat_oracle
from soko_mcp.oracle import PuzzleScriptOracle, replay_oracle


class FlatOracleCorpseTests(unittest.TestCase):
    def test_ii4_rrr_agrees_with_puzzlescript_and_renders_corpse(self) -> None:
        room = get_room("II-4")
        ps = replay_oracle(room["part"], room["grid"], "RRR")
        fb = replay_flat_oracle(room["part"], room["grid"], "RRR")
        self.assertFalse(ps["alive"])
        self.assertFalse(fb["alive"])
        self.assertEqual(ps["steps_executed"], fb["steps_executed"])
        self.assertEqual(ps["final_ascii"], fb["final_ascii"])
        self.assertIn("X", fb["final_ascii"])
        self.assertEqual(ps["traj_fnv64"], fb["traj_fnv64"])

        res = verify_route_dual(room["part"], room["grid"], "RRR")
        self.assertTrue(res["differential_match"])
        self.assertTrue(res["trajectory_digest_match"])
        self.assertFalse(res["alive"])

    def test_dead_hero_does_not_weigh_yellow_switch(self) -> None:
        grid = ["#######", "#F{O.G#", "#[....#", "#######"]
        ps = replay_oracle(2, grid, "R")
        fb = replay_flat_oracle(2, grid, "R")
        self.assertFalse(ps["alive"])
        self.assertFalse(fb["alive"])
        self.assertEqual(ps["final_ascii"], fb["final_ascii"])
        self.assertIn("X", fb["final_ascii"])
        self.assertEqual(fb["final_ascii"].splitlines()[2], "#[....#")

    def test_dead_hero_on_goal_is_not_a_win(self) -> None:
        grid = ["######", "#FGO.#", "######"]
        ps_ret = PuzzleScriptOracle(2, grid).step("R")
        fb_ret = FlatBitmaskOracle(2, grid).step("R")
        self.assertEqual(ps_ret, (False, False))
        self.assertEqual(fb_ret, (False, False))

    def test_dragon_fatal_step_agrees_in_dual_verify(self) -> None:
        grid = ["######", "#R..G#", "#..F.#", "######"]
        ps = replay_oracle(2, grid, "U")
        fb = replay_flat_oracle(2, grid, "U")
        self.assertFalse(ps["alive"])
        self.assertFalse(fb["alive"])
        self.assertIn("X", fb["final_ascii"])
        self.assertEqual(ps["final_ascii"], fb["final_ascii"])
        self.assertEqual(ps["traj_fnv64"], fb["traj_fnv64"])

        res = verify_route_dual(2, grid, "U")
        self.assertTrue(res["differential_match"])
        self.assertTrue(res["trajectory_digest_match"])
        self.assertFalse(res["alive"])

    def test_528_catalog_seeded_routes_and_66_references_agree(self) -> None:
        rng = random.Random(20261114)
        checked = 0
        for room_id, room in load_catalog().items():
            ref = room["reference_route"]
            routes = [ref]
            for case in range(8):
                if case % 2:
                    routes.append("".join(rng.choice("UDLRA") for _ in range(rng.randint(1, 60))))
                else:
                    keys = list(ref[: rng.randint(1, len(ref))])
                    for _ in range(rng.randint(0, 4)):
                        keys.insert(rng.randint(0, len(keys)), rng.choice("UDLRA"))
                    routes.append("".join(keys))
            for route in routes:
                checked += 1
                ps = replay_oracle(room["part"], room["grid"], route)
                fb = replay_flat_oracle(room["part"], room["grid"], route)
                for field in ("alive", "exact_win", "premature_win", "steps_executed", "traj_fnv64", "final_ascii"):
                    self.assertEqual(fb[field], ps[field], f"{room_id} route={route!r} field={field}")
        self.assertEqual(checked, 66 * 9)


if __name__ == "__main__":
    unittest.main()
