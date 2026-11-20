"""Known-answer tests for experiments/route_lineage/lineage.py.

The comparison must say "same plan" for routes known to share a plan and
"different plan" for routes known to differ, and its order score must sit near
one half for unrelated orders.
"""
import json
import random
import unittest
from pathlib import Path

from experiments.route_lineage import lineage
from experiments.route_lineage.lineage import compare, milestones

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "2026-11-20-public-route-lineage"


def route(rid):
    return next(r for r in json.loads((EVIDENCE / "controls.json").read_text()) if r["id"] == rid)


class TestRouteLineage(unittest.TestCase):
    def test_noop_lap_keeps_the_plan(self):
        # With six heroes present, six A presses return control to the same hero.
        a, b = route("III-21:316"), route("III-21:316+lap")
        ma, mb = milestones(a["room"], a["keys"]), milestones(b["room"], b["keys"])
        self.assertTrue(ma["won"] and mb["won"])
        self.assertEqual([e[1] for e in ma["events"]], [e[1] for e in mb["events"]])
        c = compare(ma, mb)
        self.assertEqual(c["events"], 1.0)
        self.assertEqual(c["order"], 1.0)
        self.assertGreater(c["states"], 0.99)

    def test_known_different_plans_score_low(self):
        # III-16: the 77-key optimizer stop and the proven 47-key route use different plans
        # (15 hero segments against 7), see evidence/2026-11-13-seeded-search-stall.
        a, b = route("III-16:cold.best"), route("III-16:ref")
        c = compare(milestones(a["room"], a["keys"]), milestones(b["room"], b["keys"]))
        self.assertLess(c["events"], 0.3)
        self.assertLess(c["states"], 0.05)

    def test_seed_and_polish_score_high(self):
        a, b = route("III-16:cold"), route("III-16:cold.best")
        c = compare(milestones(a["room"], a["keys"]), milestones(b["room"], b["keys"]))
        self.assertGreater(c["events"], 0.9)
        self.assertGreater(c["states"], 0.4)

    def test_order_score_is_one_half_for_unrelated_orders(self):
        rng = random.Random(0)
        labels = [f"open {i},0" for i in range(40)]
        scores = []
        for _ in range(200):
            perm = labels[:]
            rng.shuffle(perm)
            a = {"events": [[i, e] for i, e in enumerate(labels)], "states": {0}}
            b = {"events": [[i, e] for i, e in enumerate(perm)], "states": {0}}
            scores.append(compare(a, b)["order"])
        self.assertAlmostEqual(sum(scores) / len(scores), 0.5, delta=0.02)

    def test_public_iii21_families(self):
        d = json.loads((EVIDENCE / "lineage.json").read_text())
        rs = [r for r in d["routes"] if r["room"] == "III-21"]
        self.assertEqual(len(rs), 30)
        self.assertTrue(all(r["won"] for r in rs))
        self.assertEqual(len({r["handle"] for r in rs}), 7)
        # Every public III-21 route kills the goblins from (11,4) and (13,9) together.
        for r in rs:
            kills = {e[1]: e[0] for e in r["milestones"] if e[1].startswith("kill")}
            self.assertEqual(kills["kill 11,4"], kills["kill 13,9"], r["id"])


class TestGoblinIdentity(unittest.TestCase):
    """A moved goblin is not a dead goblin (cases found by the 2026-11-20 review)."""

    def run_case(self, rows, keys):
        room = f"III-T{len(lineage._GRIDS)}"
        lineage._GRIDS[room] = rows
        return [e[1] for e in milestones(room, keys)["events"]]

    def test_chain_push_kills_nothing(self):
        # Fighter pushes crate, goblin, crate, goblin left; both goblins live.
        self.assertEqual(self.run_case(["#########", "#..O*O*F#", "#G.......", "#########"], "L"), [])

    def test_wizard_swap_kills_nothing(self):
        # The warpball swaps the Wizard with a goblin three cells away.
        self.assertEqual(self.run_case(["#########", "#W..O...#", "#G......#", "#########"], "R"), [])

    def test_petrification_is_one_event(self):
        # The Druid turns the goblin into a wall: one petrify event, no wall or kill event.
        self.assertEqual(self.run_case(["#########", "#.DO....#", "#G4.....#", "#########"], "R"), ["petrify 3,1"])


if __name__ == "__main__":
    unittest.main()
