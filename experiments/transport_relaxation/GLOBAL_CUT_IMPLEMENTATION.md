# Global flow-cut implementation and verification

This execution plan follows the team's SOP: document the work, share it in the
GitHub repository, implement it, test it, then share the measured results. The
global architecture is already documented in merged PR #16. This document
specifies the implementation and acceptance checks for its completion.

## Implemented scope

1. A bounded master chooses every action, both hero trajectories, active hero,
   and one common material landmark. It fixes no reference route or schedule.
2. A fixed universal time-expanded network retains every potential cell,
   origin release, stay, carry, and switch-exit edge. Capacities are exact
   Boolean predicates of the master assignment, or constant unit capacities.
3. A maximum-flow subproblem either reconstructs nine material histories or
   returns a deficient cut. The master receives the sum of **all** universal
   outgoing capacities for that cut, including currently disabled edges.
4. A separate checker reconstructs cut boundaries and their capacities from
   the instance and master assignment. It rejects missing or changed edges,
   invalid partitions, nonviolated cuts, and altered source/instance artifacts.
5. An executable loop runs until a relaxed witness, a checked encoded-UNSAT
   result, or an explicit resource limit. All limits remain inconclusive.
   Original-game claims require the existing separate original-engine replay.

The first implementation remains a necessary transport relaxation. Feasible
flow is not a concrete winning route. The global loop must not imply that
blocking and freezing rules have been restored merely by adding flow cuts.

## Completeness and certificates

All potential network edges must have stable identities across master
assignments. A fixed cut gives a necessary capacity inequality for every
assignment, not only the failed schedule. The history landmark is selected
once for all nine switch exits. Terminal handling must preserve every concrete
win at or below the horizon; any normalization used for earlier wins requires
a written argument and positive controls.

The source/grid guard, universe topology, capacity predicates, accepted cuts,
runtime versions, and result artifacts must be pinned. A solver UNSAT claim
without independent proof checking remains unverified. A checked CNF proof
still relies on the documented game-to-flow projection and encoding/compilation.

## Required tests and execution

- The known 48-input route must induce a nine-unit universal-network flow and
  survive every learned cut.
- Universal and existing conditional flow networks must agree on matched
  fixed schedules and landmarks.
- A planted missing-disabled-edge bug must fail: another valid assignment
  can enable an edge omitted by the faulty cut.
- Small finite instances must support exhaustive comparison of the cut loop
  with direct feasibility, including infeasible and changing-landmark cases.
- Tampered partitions, edge lists, source identities, and certificates must
  fail closed. Timeout must never be promoted to infeasibility.
- Run a bounded unrestricted III-14 pilot with progress and durable results.
  Report actual outcomes, including no improvement or timeout.

## Completion and measured results

The plan was published in commit `84d3d0e` and PR #17 before implementation.
PR #17 was merged while implementation was underway; the implementation and
results are therefore shared in a follow-up PR. The executable core is commit
`d6fd09d`, with subsequent CLI path/deadline fixes covered by regression tests.

All five scope items above are implemented in `global_master.py`,
`universal_flow.py`, `cut_certificate.py`, and `global_search.py`. The master
searches all permitted hero/action schedules; it pins a reference only in the
explicitly labeled `control` command. The independent checker reconstructs the
complete source-derived graph as well as each cut boundary and capacity.

Acceptance checks now cover:

- Exhaustive full cut-loop/direct-flow agreement on four small finite networks,
  including an infeasible network and a changed landmark after a learned cut.
- Known 48-input and constructed 47-input schedules at six landmarks, with
  universal and conditional flow values agreeing at 0, 7, 8 and 9.
- Missing disabled edges, altered predicates, invented movement, changed
  sources, invalid partitions, duplicate IDs, and corrupted witness paths.
- The reference and its abstract prefix padding, sampled numeric/symbolic
  capacity agreement, iteration/deadline limits, and CLI paths from another cwd.

The real reference control learns one cut and then recovers the 48-input route;
its nine paths pass independent checking, and the route passes the pinned
original PuzzleScript build. A one-input UNSAT control passes DRAT checking.
The unrestricted 47-input pilot accepts eight independently checked cuts in
120 seconds and ends `unknown` during the ninth master query. It establishes
neither a better route nor a stronger lower bound. The global network has
9,921 nodes and 29,413 potential edges at that horizon.

The [portable evidence and replay command](../../evidence/2026-11-12-global-cuts/README.md)
retain every accepted cut, assignment, source pin, reference witness, original
replay and proof-control artifact. Foundation-0 methods and their implemented
test mappings are documented in [FOUNDATION_RESEARCH.md](FOUNDATION_RESEARCH.md).
