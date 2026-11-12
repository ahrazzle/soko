# Global flow-cut implementation and verification

This execution plan follows the team's SOP: document the work, share it in the
GitHub repository, implement it, test it, then share the measured results. The
global architecture is already documented in merged PR #16. This document
specifies the implementation and acceptance checks for its completion.

## Work to implement

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

Relevant Foundation-0 research is being assessed in parallel. Any adopted
technique will be linked to its pinned source and the implementation or test
that exercises it. Insights will not be left as unimplemented recommendations
within this work's declared scope.

Status at publication: implementation pending; this plan is shared before
implementation. The completion section will be updated with code, tests, and
execution evidence in the same PR.
