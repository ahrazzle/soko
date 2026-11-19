"""Seeded differential replay: native engine vs the readable original-rule oracle.

The fixed regressions in test_trilogy_mechanics pin known divergences. This
test samples routes on every catalog room (random walks and perturbed
reference prefixes) so a native mechanics change that only shows up in some
room or rule interaction is caught. Before the multi-active-hero port the
native engine diverged on I-22 and II-12 under this sampler.
"""
import random
import unittest

from soko_mcp.catalog import load_catalog
from soko_mcp.oracle import replay_oracle


class NativeDifferentialTests(unittest.TestCase):
    CASES_PER_ROOM = 8
    SEED = 20261114

    @classmethod
    def setUpClass(cls):
        from soko_mcp.engine_bridge import ensure_cpp_engine
        if ensure_cpp_engine() is None:
            raise unittest.SkipTest("C++20 compiler unavailable")

    def routes(self, rng, reference):
        for case in range(self.CASES_PER_ROOM):
            if case % 2:
                yield "".join(rng.choice("UDLRA") for _ in range(rng.randint(1, 60)))
            else:
                keys = list(reference[: rng.randint(1, len(reference))])
                for _ in range(rng.randint(0, 4)):
                    keys.insert(rng.randint(0, len(keys)), rng.choice("UDLRA"))
                yield "".join(keys)

    def test_native_trajectory_matches_readable_oracle_on_catalog(self):
        from soko_mcp.engine_bridge import _invoke_cpp
        rng = random.Random(self.SEED)
        for room_id, room in load_catalog().items():
            for route in self.routes(rng, room["reference_route"]):
                with self.subTest(room=room_id, route=route):
                    readable = replay_oracle(room["part"], room["grid"], route)
                    native = _invoke_cpp("verify", room["part"], room["grid"], 0, 0, 0, route)
                    self.assertIsNotNone(native)
                    self.assertEqual(native["traj_fnv64"], readable["traj_fnv64"])
                    for key in ("alive", "exact_win", "premature_win", "steps_executed"):
                        self.assertEqual(native[key], readable[key], key)
                    self.assertEqual(native["final_ascii"], readable["final_ascii"])

    def test_post_death_late_phase_finishes_kills_doors_and_monster_gate(self):
        from soko_mcp.engine_bridge import _invoke_cpp

        # 1. Hero killed by one goblin while adjacent to a second goblin: remaining
        #    goblin-goblin mutual kills and monster-gate opening must still complete.
        board_simul_gate = [
            "#########",
            "#F.O.OGM#",
            "#..O.2..#",
            "#########",
        ]
        for route in ("R", "RR"):
            readable = replay_oracle(2, board_simul_gate, route)
            native = _invoke_cpp("verify", 2, board_simul_gate, 0, 0, 0, route)
            self.assertIsNotNone(native)
            self.assertFalse(readable["alive"])
            self.assertEqual(native["alive"], readable["alive"])
            self.assertEqual(native["final_ascii"], readable["final_ascii"])
            self.assertEqual(
                native["final_ascii"].replace("X", "."),
                readable["final_ascii"].replace("X", "."),
            )

        # 2. Hero steps onto a switch next to a goblin while another hero previously
        #    opened the yellow door: dying hero turns into a corpse (not weighing),
        #    so the yellow door closes on the same late phase.
        board_switch_death = [
            "##########",
            "#*{.[..GG#",
            "#.F.O..2.#",
            "##########",
        ]
        # Step 1 ('U' blocked or 'R' next to O): test hero killed on switch `{`
        board_hero_on_sw = [
            "##########",
            "#..[...GG#",
            "#.F{.O.2.#",
            "##########",
        ]
        for route in ("R", "RR"):
            readable = replay_oracle(2, board_hero_on_sw, route)
            native = _invoke_cpp("verify", 2, board_hero_on_sw, 0, 0, 0, route)
            self.assertIsNotNone(native)
            self.assertEqual(native["alive"], readable["alive"])
            self.assertEqual(native["final_ascii"], readable["final_ascii"])

        # 3. Closing yellow door crushes inactive hero in doorway AND crushes last monster
        #    in second doorway, opening the monster gate 'M' in the same late phase.
        board_door_crush = [
            "###########",
            "#F*..[.[MG#",
            "#..{...O2G#",
            "###########",
        ]
        # Push crate onto '{' to open both '[' doors, move '2' and 'O' or test direct crush:
        board_door_crush2 = [
            "###########",
            "#F{..[.[MG#",
            "#....2..OG#",
            "###########",
        ]
        for route in ("R", "RAUU", "RAAUL"):
            readable = replay_oracle(2, board_door_crush2, route)
            native = _invoke_cpp("verify", 2, board_door_crush2, 0, 0, 0, route)
            self.assertIsNotNone(native)
            self.assertEqual(native["alive"], readable["alive"])
            self.assertEqual(native["final_ascii"], readable["final_ascii"])


if __name__ == "__main__":
    unittest.main()
