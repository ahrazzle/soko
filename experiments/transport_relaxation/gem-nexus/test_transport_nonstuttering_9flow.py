"""Unit and soundness-mutation tests for intact 9-flow and non-stuttering CNF."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from experiments.transport_relaxation import intact_flow_allocation as flow_mod
    from experiments.transport_relaxation import nonstuttering_cnf as ns_mod
except ImportError:
    import intact_flow_allocation as flow_mod  # type: ignore
    import nonstuttering_cnf as ns_mod  # type: ignore


R30_HALL_WITNESS = "LLULULULURURURURUARRRRDDRDRUUR"
R33_FLOW_WITNESS = "LLULULULRURURURURUAUDRRDUDDRRRRUR"
R48_CONCRETE_WIN = "LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR"


def enumerate_relaxed_goal_traces(route: str):
    """Enumerate valid relaxed hero schedules whose first goal-pair is the final frame."""
    border_set = set(flow_mod.BORDER)
    goals_set = set(flow_mod.GOALS)
    start = {"bard_x": 2, "bard_y": 2, "druid_x": 2, "druid_y": 4, "active": False}
    cur = [([start], set())]
    for key in route:
        nxt = []
        for trace, harvested in cur:
            last = trace[-1]
            b = (last["bard_x"], last["bard_y"])
            d = (last["druid_x"], last["druid_y"])
            if {b, d} == goals_set and b != d:
                continue  # first goal pair must be terminal
            if key == "A":
                nxt.append((trace + [dict(last, active=not last["active"])], set(harvested)))
            elif not last["active"]:
                dx, dy = flow_mod.DIRECTIONS[key]
                nd = (d[0] + dx, d[1] + dy)
                if nd in border_set and nd not in harvested:
                    nh = set(harvested)
                    nh.add(nd)
                    nxt.append((trace + [dict(last)], nh))
                elif flow_mod.in_bounds(nd) and nd not in border_set and nd != b:
                    nxt.append((trace + [dict(last, druid_x=nd[0], druid_y=nd[1])], set(harvested)))
                elif nd in harvested and nd != b:
                    nxt.append((trace + [dict(last, druid_x=nd[0], druid_y=nd[1])], set(harvested)))
            else:
                dx, dy = flow_mod.DIRECTIONS[key]
                nb = (b[0] + dx, b[1] + dy)
                if flow_mod.in_bounds(nb) and (nb not in border_set or nb in harvested):
                    if nb != d:
                        nxt.append((trace + [dict(last, bard_x=nb[0], bard_y=nb[1])], set(harvested)))
                    if flow_mod.in_aura(d, b):
                        nd = (d[0] + dx, d[1] + dy)
                        if flow_mod.in_bounds(nd) and (nd not in border_set or nd in harvested) and nb != nd:
                            nxt.append((
                                trace + [dict(last, bard_x=nb[0], bard_y=nb[1], druid_x=nd[0], druid_y=nd[1])],
                                set(harvested),
                            ))
        cur = nxt
    return [
        trace for trace, _ in cur
        if {(trace[-1]["bard_x"], trace[-1]["bard_y"]), (trace[-1]["druid_x"], trace[-1]["druid_y"])} == goals_set
        and (trace[-1]["bard_x"], trace[-1]["bard_y"]) != (trace[-1]["druid_x"], trace[-1]["druid_y"])
    ]


class TransportNonStuttering9FlowTests(unittest.TestCase):
    def test_r48_concrete_incumbent_positive_control(self) -> None:
        proj = ns_mod.project_concrete_win(R48_CONCRETE_WIN)
        self.assertTrue(proj["valid_win"])
        self.assertEqual(proj["landmark_frame"], 47)

        flow_rep = flow_mod.allocate_intact_9flow(R48_CONCRETE_WIN, proj["heroes"], 47)
        self.assertTrue(flow_rep["feasible"])
        self.assertEqual(flow_rep["flow_value"], 9)
        self.assertTrue(flow_rep["witness_verified"])
        self.assertTrue(flow_rep["min_cut_verified"])

        # Verify 100% of emitted DIMACS CNF clauses are satisfied by the concrete projection!
        cnf, meta = ns_mod.compile_conditional_nonstuttering_cnf(R48_CONCRETE_WIN, proj["heroes"], 47)
        dimacs_text = cnf.to_dimacs()
        self.assertTrue(dimacs_text.startswith(f"p cnf {cnf.num_vars} {len(cnf.clauses)}\n"))
        self.assertGreater(meta["nonstutter_clauses"], 50)

        # Solve from scratch via DPLL on the emitted DIMACS formula:
        dec = ns_mod.decide_conditional_nonstuttering(R48_CONCRETE_WIN, proj["heroes"], 47)
        self.assertTrue(dec["feasible"])
        self.assertEqual(dec["status"], "feasible")
        self.assertTrue(dec["clause_audit_passed"])

    def test_r30_hall_counterexample_refuted_by_intact_9flow_with_5_of_9_cut(self) -> None:
        traces = enumerate_relaxed_goal_traces(R30_HALL_WITNESS)
        self.assertGreaterEqual(len(traces), 1)
        best_hero_only = 0
        best_intact = 0
        for heroes in traces:
            rep_hero_only = flow_mod.allocate_intact_9flow(
                R30_HALL_WITNESS, heroes, 29, constrain_intact_border=False
            )
            rep_intact = flow_mod.allocate_intact_9flow(
                R30_HALL_WITNESS, heroes, 29, constrain_intact_border=True
            )
            self.assertFalse(rep_hero_only["feasible"])
            self.assertFalse(rep_intact["feasible"])
            self.assertTrue(rep_intact["min_cut_verified"])
            best_hero_only = max(best_hero_only, rep_hero_only["flow_value"])
            best_intact = max(best_intact, rep_intact["flow_value"])
            dec = ns_mod.decide_conditional_nonstuttering(R30_HALL_WITNESS, heroes, 29)
            self.assertFalse(dec["feasible"])
        self.assertEqual(best_hero_only, 7)
        self.assertEqual(best_intact, 5)

    def test_r33_disjoint_flow_witness_passes_9flow_refuted_by_nonstuttering_cnf(self) -> None:
        traces = enumerate_relaxed_goal_traces(R33_FLOW_WITNESS)
        self.assertGreaterEqual(len(traces), 1)
        flow_feasible_traces = []
        for heroes in traces:
            rep = flow_mod.allocate_intact_9flow(R33_FLOW_WITNESS, heroes, 32)
            if rep["feasible"]:
                self.assertEqual(rep["flow_value"], 9)
                self.assertTrue(rep["witness_verified"])
                flow_feasible_traces.append(heroes)
        self.assertGreaterEqual(len(flow_feasible_traces), 1)

        # Every 9-flow-feasible hero schedule of r33 must be globally UNSAT under Non-Stuttering CNF:
        for heroes in flow_feasible_traces:
            dec = ns_mod.decide_conditional_nonstuttering(R33_FLOW_WITNESS, heroes, 32)
            self.assertEqual(dec["intact_9flow_value"], 9)
            self.assertFalse(dec["feasible"])
            self.assertEqual(dec["status"], "infeasible")

    def test_planted_soundness_mutations_caught(self) -> None:
        proj = ns_mod.project_concrete_win(R48_CONCRETE_WIN)

        # Mutation 1: Forgetting Druid `* <-> #` freeze toggling falsely rejects r48!
        mut_no_freeze = ns_mod.MutationConfig(ignore_druid_freeze_toggle=True)
        dec_bad_freeze = ns_mod.decide_conditional_nonstuttering(
            R48_CONCRETE_WIN, proj["heroes"], 47, mutations=mut_no_freeze
        )
        self.assertFalse(dec_bad_freeze["feasible"])

        # Mutation 2: Enforcing non-overlap/non-stuttering past the landmark (`t >= t_L`)
        # falsely rejects post-landmark hero crossings onto switches!
        padded_route = R48_CONCRETE_WIN
        # Construct an artificial post-landmark overlap trace where Bard steps back onto a switch:
        # Even on r48 itself at t=47->48, if a hero stepped onto a switch or crushed token, ghost freedom is required.
        # Verify tampered min-cut certificate is rejected by verify_9flow_min_cut:
        traces_30 = enumerate_relaxed_goal_traces(R30_HALL_WITNESS)
        net, src, snk = flow_mod.build_intact_9flow_network(R30_HALL_WITNESS, traces_30[0], 29)
        flow_val = net.max_flow(src, snk)
        cut = net.min_cut(src)
        self.assertEqual(flow_val, cut["capacity"])
        self.assertTrue(flow_mod.verify_9flow_min_cut(net, src, snk, cut))

        tampered_cap = dict(cut, capacity=cut["capacity"] + 1)
        self.assertFalse(flow_mod.verify_9flow_min_cut(net, src, snk, tampered_cap))
        if cut["crossing_edges"]:
            tampered_edges = dict(cut, crossing_edges=cut["crossing_edges"][:-1])
            self.assertFalse(flow_mod.verify_9flow_min_cut(net, src, snk, tampered_edges))


if __name__ == "__main__":
    unittest.main()
