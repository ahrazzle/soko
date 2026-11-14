"""Bench signature: a fixed set of native searches whose node counts must not drift.

Stockfish records the node count of a fixed search in every commit, so any change
in search behaviour is visible. These searches all run to completion (solved or
exhausted within the bound), which makes their counts deterministic regardless
of thread count or machine speed. The deep perft hashes cover the move generator
past the depth the oracle comparison in test_perft.py can afford.

The bench detects change, not correctness. If a change is intended, regenerate
with `python3 tests/test_bench.py --write` and say why in the same commit.
"""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from soko_mcp.catalog import get_room  # noqa: E402

BENCH_PATH = Path(__file__).with_name("bench.json")
PROVE_CASES = (("I-22", 20), ("II-12", 30), ("II-22", 30), ("III-15", 30), ("III-20", 30), ("III-22", 12))
PERFT_CASES = (("I-22", 10), ("II-12", 8), ("III-14", 7), ("III-21", 7))
PROVE_KEYS = ("proven_floor", "termination_reason", "nodes_expanded", "edge_consistency_checks", "states_seen", "winning_witness")


def measure():
    from soko_mcp.engine_bridge import _invoke_cpp
    bench = {"prove_lb": {}, "perft": {}}
    for room_id, bound in PROVE_CASES:
        room = get_room(room_id)
        out = _invoke_cpp("prove_lb", room["part"], room["grid"], bound, 0, 300)
        bench["prove_lb"][f"{room_id}@{bound}"] = {key: out.get(key) for key in PROVE_KEYS}
    for room_id, depth in PERFT_CASES:
        room = get_room(room_id)
        layers = _invoke_cpp("perft", room["part"], room["grid"], depth, 0, 0)["layers"]
        bench["perft"][f"{room_id}@{depth}"] = [f"{count}:{digest}" for count, digest in layers]
    return bench


class BenchSignatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from soko_mcp.engine_bridge import ensure_cpp_engine
        if ensure_cpp_engine() is None:
            raise unittest.SkipTest("C++20 compiler unavailable")

    def test_bench_signature_unchanged(self):
        expected = json.loads(BENCH_PATH.read_text())
        actual = measure()
        for section in ("prove_lb", "perft"):
            for case, value in expected[section].items():
                with self.subTest(section=section, case=case):
                    self.assertEqual(actual[section][case], value,
                                     "Search behaviour changed. If intended, run "
                                     "`python3 tests/test_bench.py --write` and explain it in the commit.")
        for out in actual["prove_lb"].values():
            self.assertIn(out["termination_reason"], ("solved", "exhausted"))


    def test_counts_do_not_depend_on_thread_count(self):
        # The A* expands each f-layer in parallel batches. A solving batch used to stop
        # counting edges at the thread that held the win, so II-12@30 reported 1,252,678
        # edge checks on 4 threads and 1,246,415 on 8 (seen on an 8-core machine, #56).
        import os
        from unittest import mock
        from soko_mcp.engine_bridge import _invoke_cpp
        room = get_room("II-12")
        runs = []
        for threads in ("1", "8"):
            with mock.patch.dict(os.environ, {"SOKO_ENGINE_THREADS": threads}):
                out = _invoke_cpp("prove_lb", room["part"], room["grid"], 30, 0, 300)
            runs.append({key: out.get(key) for key in PROVE_KEYS})
        self.assertEqual(runs[0], runs[1])


if __name__ == "__main__":
    if "--write" in sys.argv:
        BENCH_PATH.write_text(json.dumps(measure(), indent=1, sort_keys=True) + "\n")
        print(f"wrote {BENCH_PATH}")
    else:
        unittest.main()
