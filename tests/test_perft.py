"""Perft: compare the native move generator with the readable oracle, room by room.

For each catalog room and each depth up to DEPTH, both engines report how many
distinct states are first reached at that depth (no-op moves pruned, deaths
dropped) and an order-independent hash of those states. Counts alone are not
enough: before the multi-hero port the native engine reached a different state
on I-22 at depth 1 with the same count, and only the hash showed it.
"""
import unittest

from soko_mcp.catalog import load_catalog
from soko_mcp.oracle import PuzzleScriptOracle

FNV_OFFSET = 14695981039346656037
MASK64 = (1 << 64) - 1


def readable_perft(part, grid, depth):
    start = PuzzleScriptOracle(part, grid)
    seen = {start.state_signature()}
    layer, layers = [start], []
    for _ in range(depth):
        nxt, digest_sum = [], 0
        for state in layer:
            for key in "UDLRA":
                child = state.clone()
                alive, _ = child.step(key)
                if not alive:
                    continue
                sig = child.state_signature()
                if sig in seen:
                    continue
                seen.add(sig)
                nxt.append(child)
                digest_sum = (digest_sum + child.fold_canonical_digest(FNV_OFFSET)) & MASK64
        layers.append([len(nxt), f"{digest_sum:016x}"])
        layer = nxt
    return layers


class PerftTests(unittest.TestCase):
    DEPTH = 4

    @classmethod
    def setUpClass(cls):
        from soko_mcp.engine_bridge import ensure_cpp_engine
        if ensure_cpp_engine() is None:
            raise unittest.SkipTest("C++20 compiler unavailable")

    def test_native_perft_matches_readable_oracle_on_every_room(self):
        from soko_mcp.engine_bridge import _invoke_cpp
        for room_id, room in load_catalog().items():
            with self.subTest(room=room_id):
                native = _invoke_cpp("perft", room["part"], room["grid"], self.DEPTH, 0, 0)
                self.assertIsNotNone(native)
                self.assertEqual(native["layers"], readable_perft(room["part"], room["grid"], self.DEPTH))


if __name__ == "__main__":
    unittest.main()
