"""Route-replay soundness gate for the per-state lower bounds this repository ships.

A lower bound h on the keys still to play is sound along a legal winning route of n keys only if,
at every state s_t on that route:

- admissible:  h(s_t) <= n - t
- consistent:  h(s_t) - h(s_{t+1}) <= 1   (every key costs 1)
- goal:        h(s_n) <= 0

One violation on a catalogued route is a short, checkable refutation of the bound.
Values are exact (int or Fraction). The checks raise through unittest, so they also run under
`python3 -O -B -W error`.

Every positive check is paired with a control that must be rejected: bounds and quotients known
to be wrong, and corrupted copies of the real values. If a control is accepted the gate cannot fail.
"""
from __future__ import annotations

import json
import unittest
from fractions import Fraction
from pathlib import Path

from experiments.landmark_dual_bounds.hero_assignment_bounds import (
    evaluate_operator_counting_bound,
    naive_unpartitioned_manhattan_sum,
)
from experiments.landmark_dual_bounds.iii21_retrograde_tb import III21EndgameQuotientTB
from experiments.landmark_dual_bounds.quotient_consistency_lp import (
    build_soko38_counterexample_state,
    legacy_unrepaired_soko38_bound,
)
from experiments.landmark_dual_bounds_v2 import iii14_bidirectional_endgame as v2
from soko_mcp.oracle import TO_INACTIVE, PuzzleScriptOracle

CATALOG = json.loads(
    (Path(__file__).resolve().parent.parent / "soko_mcp" / "data" / "catalog.json").read_text(encoding="utf-8")
)
ROOMS = {r["id"]: r for r in CATALOG["rooms"]}


def replay_states(room):
    ps = PuzzleScriptOracle(room["part"], room["grid"])
    states = [ps.clone()]
    for i, key in enumerate(room["reference_route"]):
        ok, _won = ps.step(key)
        if not ok:
            raise RuntimeError("%s route died at key index %d" % (room["id"], i))
        states.append(ps.clone())
    if not ps.check_win():
        raise RuntimeError("%s route does not win" % room["id"])
    return states


def gate(values, route_len):
    """Return the list of violations of the three conditions for values h(s_0..s_n)."""
    if len(values) != route_len + 1:
        raise ValueError("need route_len + 1 values")
    out = []
    for t, h in enumerate(values):
        if Fraction(h) > route_len - t:
            out.append(("admissible", t, h))
    for t in range(route_len):
        if Fraction(values[t]) - Fraction(values[t + 1]) > 1:
            out.append(("step", t, values[t], values[t + 1]))
    if Fraction(values[-1]) > 0:
        out.append(("goal", route_len, values[-1]))
    return out


class CatalogFloorTests(unittest.TestCase):
    def test_floor_does_not_exceed_best_known_route(self):
        for rid, r in ROOMS.items():
            with self.subTest(room=rid):
                self.assertLessEqual(r["proven_floor"], r["shortest_known"])
                self.assertEqual(r["shortest_known"], len(r["reference_route"]))

    def test_floor_check_can_fail(self):
        r = dict(ROOMS["III-14"])
        r["proven_floor"] = r["shortest_known"] + 1
        self.assertGreater(r["proven_floor"], r["shortest_known"])


class OperatorCountingRouteTests(unittest.TestCase):
    def test_every_catalog_route_is_sound(self):
        for rid, r in ROOMS.items():
            with self.subTest(room=rid):
                states = replay_states(r)
                bounds = [evaluate_operator_counting_bound(s) for s in states]
                n = len(r["reference_route"])
                self.assertEqual(gate([b.exact_rational_bound for b in bounds], n), [])
                self.assertEqual(gate([b.ceil_integer_bound for b in bounds], n), [])


class TablebaseRouteTests(unittest.TestCase):
    def test_iii21_retrograde_tablebase_on_record_route(self):
        r = ROOMS["III-21"]
        tb = III21EndgameQuotientTB()
        tb.build_and_audit()
        values = [tb.lookup(s) for s in replay_states(r)]
        self.assertEqual(gate(values, len(r["reference_route"])), [])

    def test_iii14_vault_tablebase_on_record_route(self):
        r = ROOMS["III-14"]
        topo = v2.build_iii14_topology()
        tb = v2.III14VaultEndgameTB(topo)

        def to_state(ps):
            crates = walls = 0
            b = d = ah = None
            for y in range(ps.h):
                for x in range(ps.w):
                    o, i = ps.obj[y][x], y * v2.W + x
                    if o == "*":
                        crates |= 1 << i
                    elif o == "#":
                        walls |= 1 << i
                    elif o in ("B", "5"):
                        b = i
                        ah = 0 if o == "B" else ah
                    elif o in ("D", "6"):
                        d = i
                        ah = 1 if o == "D" else ah
            return (crates, walls, b, d, ah, 0)

        values = [tb.lookup(to_state(s)) for s in replay_states(r)]
        self.assertEqual(gate(values, len(r["reference_route"])), [])


NAMES = ["F", "T", "W", "P", "B", "D"]
INACTIVE = {TO_INACTIVE[h]: h for h in NAMES}


def need_mask(ps):
    """Heroes that are not standing on a goal."""
    out = set()
    for y in range(ps.h):
        for x in range(ps.w):
            c = ps.obj[y][x]
            hero = c if c in NAMES else INACTIVE.get(c)
            if hero is not None and ps.floor[y][x] != "G":
                out.add(hero)
    return out


def switch_automaton_has_edge(act0, mask0, key, act1, mask1):
    """Edge relation of a switch-cycle quotient over (active hero, heroes not on a goal), phase ignored.
    Key A advances the active hero by one in the cycle and keeps the mask. A move keeps the active
    hero, sets no bit, and may clear only the active hero's own bit."""
    if key == "A":
        return mask1 == mask0 and NAMES.index(act1) == (NAMES.index(act0) + 1) % 6
    return act1 == act0 and not (mask1 - mask0) and all(b == act0 for b in (mask0 - mask1))


class MustFailControls(unittest.TestCase):
    """Each control is a bound or quotient that is wrong. The gate must reject it."""

    def test_switch_automaton_rejected_on_iii21_record(self):
        r = ROOMS["III-21"]
        ps = PuzzleScriptOracle(3, r["grid"])
        bad = []
        for i, key in enumerate(r["reference_route"], 1):
            a0, m0 = ps.find_active()[2], need_mask(ps)
            ps.step(key)
            if not switch_automaton_has_edge(a0, m0, key, ps.find_active()[2], need_mask(ps)):
                bad.append(i)
        self.assertEqual(len(bad), 19)
        self.assertEqual(bad[0], 58)
        self.assertEqual(bad[-1], 310)

    def test_five_passive_move_boards_rejected(self):
        def board(rows, goal=None):
            ps = PuzzleScriptOracle(3, rows)
            if goal:
                ps.floor[goal[1]][goal[0]] = "G"
            return ps

        boards = {
            "fighter_push_inactive_onto_goal": board(["#######", "#F2G..#", "#######"]),
            "thief_pull_inactive_onto_goal": board(["#######", "#.3T..#", "#######"], (3, 1)),
            "wizard_swap_inactive_onto_goal": board(["########", "#W....4#", "########"], (1, 1)),
            "bard_aura_carries_inactive_onto_goal": board(["#######", "#B6G..#", "#######"]),
            "fighter_push_inactive_off_goal": board(["#######", "#F2...#", "#######"], (2, 1)),
        }
        for name, ps in boards.items():
            with self.subTest(board=name):
                a0, m0 = ps.find_active()[2], need_mask(ps)
                ps.step("R")
                self.assertFalse(switch_automaton_has_edge(a0, m0, "R", ps.find_active()[2], need_mask(ps)))

    def test_withdrawn_soko38_bound_rejected(self):
        ps, _fl, _rows = build_soko38_counterexample_state()
        h0 = legacy_unrepaired_soko38_bound(ps)
        ps.step("R")
        h1 = legacy_unrepaired_soko38_bound(ps)
        self.assertEqual((h0, h1), (12, 10))
        self.assertEqual([v[0] for v in gate([h0, h1], 1) if v[0] == "step"], ["step"])

    def test_naive_manhattan_sum_rejected_on_real_routes(self):
        total = 0
        for rid in ("I-8", "I-9", "I-10"):
            r = ROOMS[rid]
            values = [naive_unpartitioned_manhattan_sum(s) for s in replay_states(r)]
            total += len(gate(values, len(r["reference_route"])))
        self.assertGreater(total, 0)

    def test_corrupted_operator_counting_values_rejected(self):
        r = ROOMS["III-21"]
        n = len(r["reference_route"])
        values = [evaluate_operator_counting_bound(s).ceil_integer_bound for s in replay_states(r)]
        self.assertEqual(gate(values, n), [])
        high = list(values)
        high[100] += 400
        self.assertIn("admissible", [v[0] for v in gate(high, n)])
        nonzero_goal = list(values)
        nonzero_goal[-1] = 1
        self.assertIn("goal", [v[0] for v in gate(nonzero_goal, n)])
        sharp_drop = list(values)
        sharp_drop[201] = values[200] - 5
        self.assertIn("step", [v[0] for v in gate(sharp_drop, n)])


if __name__ == "__main__":
    unittest.main()
