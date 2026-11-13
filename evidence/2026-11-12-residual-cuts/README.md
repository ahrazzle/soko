# Residual cut selection: implemented and checked

2026-11-12 America/Chicago. Base: main `27406dd`. This follows the
[shared plan](../../experiments/transport_relaxation/CUT_SELECTION_PLAN.md),
the team's [issue #22 discussion](https://github.com/ahrazzle/soko/issues/22), and
mithrax-exo's [Pareto-cut proposal](../../docs/pareto-universal-cuts.md).

Both global-flow and causal search now accept `--cut-selection sink_minimal`.
The source-minimal default is unchanged. Both choices use the same maximum-flow
algorithm and retain all universal crossing arcs, including disabled arcs.
Reverse residual reachability into the sink yields the maximal source-side
minimum cut. It does not optimize predicate count among every minimum cut.

## Measured result and limits

The benchmark selects the first twelve distinct, valid, deficient assignments
in the retained `global47-selected-search.json.gz` archive, before comparing
cut modes. These happen to be its first twelve candidates, all with flow zero.
No candidate was selected according to the new method's benefit.

| Structural count over 12 inputs | Source-minimal | Sink-minimal | Change |
|---|---:|---:|---:|
| Distinct nonconstant predicates | 22,560 | 1,065 | −95.28% |
| All grouped predicates, including constants | 22,560 | 1,065 | −95.28% |
| Universal crossing arcs | 22,560 | 5,249 | −76.73% |

All 24 cut certificates independently check. The predicate grouping matches
`global_master.add_cut`'s `(kind, params)` keys, not simplification of the final
Z3 expression. Both modes preserve the flow-nine reference witness.

The end-to-end reference control reaches the same 48-key route in both modes:
source-minimal uses **one cut / two iterations**; sink-minimal uses **five cuts /
six iterations**. Recorded elapsed times are 2.18s and 3.86s respectively, from
single controls run concurrently with tests; they are not a speed benchmark.
The extra cuts illustrate that smaller expressions do not ensure more useful
cuts. The default remains unchanged for that reason.

These are new, narrow fixed-input measurements. They do not reproduce the
original report's twelve inputs or its 44.06% figure, establish faster record
search, or certify a stronger room bound. The causal solver's default exact-first
order can reject candidates before reaching this flow option. Original-engine
replay was not repeated; the controls check flow witnesses and local replay.

## Validation and artifacts

- `tests.txt`: 55 focused unittest cases pass. Coverage includes exhaustive
  comparison with all cuts on 50 seeded tiny graphs, reverse residual arcs,
  disabled boundary arcs, independent certificates, known-win witnesses,
  invalid inputs, and CLI/worker propagation. Independent code review passed.
- `comparison.json.gz`: full assignments, archive/source hashes, both cut
  certificates per input, capacities, counts and the reference witness. Gzip
  is deterministic. `summary.json` contains the small readable result.
- `source_minimal-control.json.gz` and `sink_minimal-control.json.gz`: complete
  command, checkpoints, assignments, checked cuts, witnesses and logs.
- `predicate-gadget-counterexample.json`: all four auxiliary-node placements
  for the proposed arbitrary-pair gadget. No original pair crosses, yet the
  gadget's minimum cost is 10 rather than zero. This challenges its generic
  exact predicate objective, not independently checked cut validity.
- `SHA256SUMS`: artifact hashes. The existing root integrity manifest also
  passes; the core MCP and original mechanics were not changed.

Reproduce from this checkout (requires the existing Z3 dependency):

```sh
python -m experiments.transport_relaxation.compare_cut_selection --output /tmp/comparison.json.gz
python -m experiments.transport_relaxation.predicate_gadget_counterexample
python -m unittest tests.test_residual_cut_selection tests.test_universal_flow tests.test_global_cut_certificates tests.test_global_master tests.test_global_search tests.test_causal_master tests.test_causal_search tests.test_transport_nonstuttering_9flow -v
python -m experiments.transport_relaxation.global_search control --horizon 48 --timeout-seconds 25 --cut-selection sink_minimal --output /tmp/new-sink-control
```

The benchmark regenerates complete certificates from the pinned input archives.
Source hashes identify this implementation; subsequent code changes will change
those hashes. Use a new output directory for search controls.
