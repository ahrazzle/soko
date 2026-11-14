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
                    # After a death the readable oracle renders the corpse frame while
                    # the native engine keeps the last live frame; neither can win.
                    if readable["alive"]:
                        self.assertEqual(native["final_ascii"], readable["final_ascii"])


if __name__ == "__main__":
    unittest.main()
