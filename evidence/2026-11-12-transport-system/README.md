# Transport decomposition pilot

**No new record or original-game lower bound resulted.** This round tests a
different optimization representation, motivated by the necessary-constraint
and exact-certificate method in Foundation-0/incentre-lattices. The source is
pinned and attributed in the [design and proofs](../../experiments/transport_relaxation/README.md).

The complete 47-input transport relaxation compiled to 58,452 variables and
412,763 clauses in about 3.5 seconds. Its unrestricted SAT query timed out after
60 seconds. That run produced neither a candidate nor a checked UNSAT proof.

The conditional algorithms then supply a 47-input **abstract witness**:
40 independent token reachability calculations plus matching, or a stronger
time-expanded capacity-flow network. These solve material allocation for fixed
actions, fixed hero positions, and a specified common landmark. They do not
optimize the heroes' actions globally. A failure excludes only those fixed
choices, not all routes of the same length.

For the known 48-input route with all heroes and landmark frame 43 fixed, the
matching algorithm takes about 0.01 seconds versus roughly one second for Z3
solving the same conditional question (construction measured separately).
This is one matched control, not a general speedup claim. Capacity flow also
accepts the reference and the constructed 47-input example in under 0.1 seconds
each. Its reconstructed witnesses pass separate occupancy checks and the base
symbolic model with every frame pinned. Infeasible conditional examples have
Hall or minimum-cut certificates; tests independently check their deficiencies.

The 47-input route fails to win in the pinned original PuzzleScript build.
Local replay first disagrees with the fixed abstract hero trace at input 26:
the abstract Druid stays at `(6,3)` while the actual Druid moves to `(6,2)`.
Even the capacity refinement admits a different material arrangement along
that fixed hero trace. Missing blocking/freezing causes therefore still matter.
Additional unselected material cannot be assumed absent when refining stops.

`allocation-diagnostic.json.gz` and `flow-diagnostic.json.gz` retain the full abstract
witnesses and timings. `original-47-replay.json` is the separate browser replay;
the diagnostics' `original_replay` fields refer to the local Python interpreter.
The two larger reports use standard gzip compression; decompress them with
`gzip -dc FILE.json.gz` to inspect the complete JSON.
`reference48-*` records the original-game positive control and material-identity
projection. The flow report pins its implementation sources.

`global47-*` records the unrestricted timeout. Its model and compiler are
unchanged, but the driver subsequently gained a restricted-control certificate
guard and avoided redundant control reconstruction. The historical driver text
is retained as data in `driver-at-global-query.py.txt`; its hash matches the
query bundle. Reprepare a fresh bundle before solving with changed sources.
Large generated CNFs and assignment files remain outside the repository.

All 54 focused tests pass. The full suite runs 175 tests with 26 failures,
10 errors, and four skips—the same failing-test multiset as the previous
151-test run. Existing failures remain unresolved; the checksum manifest passes.

The proposed global master/cut loop is **not implemented**. A valid future cut
must sum symbolic capacities across a fixed cut of a universal network,
including edges currently disabled by the chosen trajectory. Reusing a local
Hall obstruction directly as a global exclusion is not justified.

`summary.json` indexes outcomes and scopes. `manifest.json` hashes every other
file in this directory. Reproduce the conditional experiments with:

```sh
python -m experiments.transport_relaxation.diagnostic
python -m experiments.transport_relaxation.flow_diagnostic
python -m unittest tests.test_transport_relaxation tests.test_transport_allocation \
  tests.test_transport_flow tests.test_transport_certificates
```
