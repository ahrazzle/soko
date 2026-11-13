"""Regression tests for the 15x7 III-14 floor prover's heuristic and step function.

The C++ side (tests/iii14_floor/iii14_floor_tests.cpp) includes the prover's own headers, builds the five
tables once and prints one PASS or FAIL line per check. This module compiles and runs it, maps each line to
a test, and adds three Python-side checks: the prover's R48 route matches the one in the C++ tests and in
soko_mcp/oracle.py, and step_concrete agrees with soko_mcp/oracle.py on seeded random routes.

A GCC with bits/stdc++.h is required (g++-16 on macOS; Apple clang lacks the header). Without one the tests
skip. Default run: about 5 s to compile and about 20 s to build the tables and run the checks.
"""
import random
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from soko_mcp.oracle import FRONTIER_ROOMS, PuzzleScriptOracle

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tests/iii14_floor/iii14_floor_tests.cpp"
PROVER = ROOT / "experiments/iii14_15x7_verified_floor/prove_iii14_15x7_floor.cpp"
W, H = 15, 7


def find_gcc():
    for name in ("g++-16", "g++-15", "g++-14", "g++-13", "g++"):
        exe = shutil.which(name)
        if not exe:
            continue
        probe = subprocess.run([exe, "-x", "c++", "-std=c++20", "-fsyntax-only", "-"], input="#include <bits/stdc++.h>\n",
                               capture_output=True, text=True)
        if probe.returncode == 0:
            return exe
    return None


GCC = find_gcc()


def r48_from(text):
    return re.search(r'const string R48 = "([UDLRA]+)"', text).group(1)


@unittest.skipUnless(GCC, "needs a GCC with bits/stdc++.h")
class Iii14FloorRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.binary = Path(cls.tmp.name) / "iii14_floor_tests"
        build = subprocess.run([GCC, "-O2", "-std=c++20", "-pthread", str(SRC), "-o", str(cls.binary)], capture_output=True, text=True)
        assert build.returncode == 0, build.stderr[-2000:]
        run = subprocess.run([str(cls.binary), "all"], capture_output=True, text=True, timeout=900)
        cls.output = run.stdout
        cls.verdicts = {}
        for line in run.stdout.splitlines():
            m = re.match(r"\[(PASS|FAIL)\] (\S+): (.*)", line)
            if m:
                cls.verdicts[m.group(2)] = (m.group(1) == "PASS", m.group(3))

    def check(self, name):
        self.assertIn(name, self.verdicts, self.output[-3000:])
        ok, detail = self.verdicts[name]
        self.assertTrue(ok, f"{name}: {detail}\n{self.output[-3000:]}")

    def test_setup_matches_prover(self):
        self.check("setup/R48_replays_to_win_and_h_is_zero_at_win")
        self.check("setup/sticky_door_34_route_rejected_at_step_30")

    def test_edge_consistency_ball_depth_14(self):
        self.check("edges/ball_depth_14")

    def test_edge_consistency_walks_off_r48_prefixes(self):
        self.check("edges/walks_off_R48_prefixes")

    def test_edge_consistency_invariant_fuzz(self):
        self.check("edges/invariant_fuzz")

    def test_r48_tail_exact_and_admissible(self):
        self.check("exact/R48_tail_t34_48")

    def test_step_commutes_with_mirror(self):
        self.check("reflection/step_commutes_with_mirror")

    def test_rf5_row3_bard_entries_symmetric(self):
        self.check("reflection/rf5_row3_bard_symmetric")

    def test_pr41_witness_is_not_r48_and_wins_under_main(self):
        self.assertIn("W41 == R48: no", self.output)
        self.check("v14/witness_replays_to_win_under_main")

    def test_pr41_counterexample_states_are_admissible_under_main(self):
        self.check("v14/CE1")
        self.check("v14/CE2")

    def test_r48_matches_prover_and_oracle(self):
        cpp = r48_from(SRC.read_text())
        self.assertEqual(cpp, r48_from(PROVER.read_text()))
        self.assertEqual(cpp, FRONTIER_ROOMS["III-14-15x7"]["reference_route"])


def oracle_state(o):
    """(crates, walls, bard, druid, druid_active, doors_open) as the C++ side prints it, or None if a hero is lost."""
    crates = walls = 0
    heroes = {}
    for y in range(H):
        for x in range(W):
            i = y * W + x
            c = o.obj[y][x]
            if c == "*":
                crates |= 1 << i
            elif c == "#":
                walls |= 1 << i
            elif c in ("B", "5"):
                heroes["B"] = (i, c == "B")
            elif c in ("D", "6"):
                heroes["D"] = (i, c == "D")
    if len(heroes) != 2:
        return None
    opened = any(o.floor[y][x] == "PO" for y in range(H) for x in range(W))
    bi, di = heroes["B"][0], heroes["D"][0]
    return (crates, walls, bi % W, bi // W, di % W, di // W, 1 if heroes["D"][1] else 0, 1 if opened else 0)


@unittest.skipUnless(GCC, "needs a GCC with bits/stdc++.h")
class Iii14OracleParity(unittest.TestCase):
    """step_concrete must give the same state as soko_mcp/oracle.py after every key of seeded random routes."""
    NROUTES, LEN, SEED = 150, 70, 20261113

    def test_seeded_routes_match_oracle(self):
        r48 = FRONTIER_ROOMS["III-14-15x7"]["reference_route"]
        grid = FRONTIER_ROOMS["III-14-15x7"]["grid"]
        rng = random.Random(self.SEED)
        routes, expected = [], []
        for _ in range(self.NROUTES):
            o = PuzzleScriptOracle(3, grid)
            keys, states = "", [oracle_state(o)]
            for k in range(rng.randrange(0, 49)):          # R48 prefix
                alive, _ = o.step(r48[k]); self.assertTrue(alive)
                keys += r48[k]; states.append(oracle_state(o))
            for _ in range(self.LEN):
                order = rng.sample("UDLRA", 5)
                if rng.random() < 0.1:                      # sometimes an arbitrary key, rejected or not
                    order = order[:1]
                chosen = None
                for key in order:
                    c = o.clone(); alive, _ = c.step(key)
                    if len(order) == 1 or (alive and oracle_state(c) not in (None, states[-1])):
                        chosen = key; break
                if chosen is None:
                    break
                alive, _ = o.step(chosen)
                keys += chosen; states.append(oracle_state(o) if alive else None)
                if not alive or states[-1] is None:
                    break
            routes.append(keys); expected.append(states)
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "t"
            build = subprocess.run([GCC, "-O2", "-std=c++20", "-pthread", str(SRC), "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr[-2000:])
            run = subprocess.run([str(binary), "route"], input="\n".join(routes) + "\n", capture_output=True, text=True, timeout=300)
        chunks, cur = [], []
        for line in run.stdout.splitlines():
            if line == "end":
                chunks.append(cur); cur = []
            else:
                cur.append(line)
        self.assertEqual(len(chunks), len(routes))

        def parse(line):
            p = line.split()
            return (int(p[1], 16), int(p[2], 16)) + tuple(int(v) for v in p[3:9])

        compared = rejected = 0
        for r, (route, exp, got) in enumerate(zip(routes, expected, chunks)):
            self.assertEqual(parse(got[0]), exp[0], f"route {r} start state differs")
            for step in range(1, len(got)):
                line = got[step]
                if line == "rej":
                    # step_concrete refuses: the oracle must show a lost hero, a death, or no change.
                    rejected += 1
                    prev, now = exp[step - 1], exp[step] if step < len(exp) else None
                    self.assertTrue(now is None or now == prev, f"route {r} step {step} key {route[step-1]}: step_concrete rejects, oracle moves on\n  oracle {now}\n  before {prev}")
                    break
                compared += 1
                self.assertEqual(parse(line), exp[step], f"route {r} step {step} key {route[step-1]} route {route[:step]}\n  step_concrete {parse(line)}\n  oracle        {exp[step]}")
        self.assertGreater(compared, 3000)
        print(f"oracle parity: {len(routes)} routes, {compared} keys compared, {rejected} rejected keys consistent")


if __name__ == "__main__":
    unittest.main()
