# Compact exact model and bounded invariant repair

This round improved the system and ran validation controls. **No record search,
record improvement, or new original-game lower bound is claimed.**

The full III-14 47-input formula shrank from 5,834,178 to 2,865,101 clauses
(50.9%), and peak compilation memory from 3.78 to 1.95 GiB (48.4%). Both
formulas retain all 235 action aliases and the same constraints. The comparison
uses fresh sequential worker processes; other validation processes ran on the
same host, so the recorded timings are not a controlled speed benchmark.
The eight-input smoke comparison simplifies to false under the existing
landmarks and is not evidence of transition compression.

`equivalence/` contains five arbitrary-state difference CNFs and independently
checked DRAT results, one per action. Z3 simplification reduces each difference
to false. Z3's symbolic transformations remain trusted; the DRAT checks only
verify the resulting CNFs. This checks the refactor against the old symbolic
model, not either model against the original game. See the
[design and trust boundary](../../experiments/exact_frontier/compact_encoding.md).
The report pins both models, compilation/checking helpers, and checker binary.

`reference-control/` contains the successful known 48-input control and fresh
original PuzzleScript replay. The candidate assignment passed every CNF
clause. The reference actions and oracle frames were pinned, so this is an
acceptance control, not a solving-speed benchmark. The full 500 initial and
100 baseline-prefix random calibration samples also passed under the existing
loss-pruning policy. Large control/query CNFs and assignments are not bundled.

The invariant synthesis repair applies to both the live MCP implementation and
the standalone copy. A state cap now leaves explicit open transitions and a
bounded-subgraph scope instead of raising an indexing error. A complete
reachable-state trap is explicitly distinguished from induction on a supplied
closed universe. Regression tests include an unreachable state where the same
candidate predicate escapes, preventing a globally scoped interpretation of
the reachable-state result.

All 30 focused tests passed. The full suite ran 151 tests with 26 failures,
10 errors, and four skips: the failing-test multiset is identical to the
[previous 143-test run](../2026-11-12-record-execution/branch-tests.txt).
The suite remains failing. An initial run rebuilt the native executable and
added seven checksum-related failures; the comparison run restores the
committed executable and its timestamp. Both logs are retained. No native
engine changes are included. The checksum manifest passes.

`summary.json` records the outcomes. `manifest.json` hashes every other file in
this evidence directory. Absolute paths in raw reports identify the execution
workspace; the copied CNFs and proofs are under the corresponding action
directories here. Reproduction commands are in the linked design document.
