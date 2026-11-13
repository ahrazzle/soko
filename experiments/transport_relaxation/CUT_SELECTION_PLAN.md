# Residual cut selection: implementation and measurement plan

Shared before implementation, 2026-11-12 America/Chicago. Follow-up to
[issue #22](https://github.com/ahrazzle/soko/issues/22) and mithrax-exo's
[Pareto cut study](../../docs/pareto-universal-cuts.md), merged via PR #31.

The study reports smaller symbolic boundaries from reverse residual traversal.
The current checkout contains the note and aggregate report, but no runnable
`sink_minimal` or `lawler_pareto` implementation or the twelve input assignments.
Those measurements cannot yet be independently reproduced from their artifacts.
This work adapts the inexpensive sink-side idea and measures new retained inputs;
it does not claim to reproduce the report or implement predicate-optimal cuts.

1. Implement source-minimal and sink-minimal residual partitions on the existing
   **complete universal graph**, after the same max-flow computation. Reverse
   reachability into the sink gives the sink side; its complement gives the
   maximal source-side minimum cut. Keep every universal crossing edge,
   including currently disabled edges.
2. Offer explicit selection in both global-flow and causal search. Preserve the
   source-minimal default until measurements justify a change. Record the mode
   in output. Continue independently reconstructing each capacity and boundary
   before adding the cut to the master.
3. Test extremal partitions against exhaustive cuts on small graphs, include
   disabled crossing arcs and reverse residual arcs, reject invalid modes,
   and preserve the concrete winning control. Test search option propagation.
4. Compare predicate counts, flow values and runtime on retained candidate
   assignments, keeping assignments and certificates reproducible. Run a
   bounded end-to-end control for each mode. Narrower clauses alone do not
   establish faster record search; no new record or room bound follows.
5. Publish implementation, tests, measured result and limits back to issue #22.

The new assignment-specific intact-flow boundary is not substituted for this
universal boundary: omitted inactive arcs can become enabled on another hero
schedule. New heuristic formulas and the Lawler shared-predicate proposal are
separate work, pending their own executable implementations and checks.

## Implemented outcome

Both residual extrema are implemented in the universal and causal evaluators
and selectable through both search CLIs. The [retained comparison](../../evidence/2026-11-12-residual-cuts/README.md)
has independently checked certificates for twelve predetermined flow-zero
inputs: sink-side selection reduces structural predicate count by 95.28%.
Both end-to-end controls pass, but sink-side selection needs five cuts against
the source-side control's one. The source default is retained. All 55 focused
tests pass, and the arbitrary-pair gadget's unsupported objective claim has a
small executable counterexample. No record or stronger bound is claimed.
