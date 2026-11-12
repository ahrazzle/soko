# Completed record attempts — 2026-11-12

**No new record and no new original-game lower bound resulted.** All record
workers finished. The final live Frontier observation lists III-14 at 48,
III-20 at 84, and III-21 at 316 inputs. III-20 work stopped during compilation
at the user's direction; it did not reach a SAT query.

## III-14: unrestricted bounded queries

Every query below ended `unknown`, with no candidate and no checked UNSAT
proof. Timeout says nothing about whether a shorter route exists. The 43-input
query is a separate model-bound experiment, not a record comparison.

| Query | Horizon | Solve budget |
| --- | ---: | ---: |
| Original CNF, CaDiCaL 1.9.5 | 47 | 3,600 s |
| Original CNF, CaDiCaL 3.0 | 47 | 1,800 s |
| Strengthened CNF, CaDiCaL 1.9.5 | 47 | 1,800 s |
| Original CNF, soft action phases | 47 | 1,800 s |
| Strengthened CNF, action-priority decision callback | 47 | 900 s |
| Strengthened model-bound query | 43 | 300 s |

Soft phases and the decision callback did not constrain the permitted routes.
The strengthened model adds distinct boundary-wall origin landmarks and hero
reachability cones; see its [arguments](../../experiments/exact_frontier/iii14_strengthening.md).
These encodings have empirical calibration, not a formal equivalence proof to
the original game.

The unrestricted horizon-48 action-priority **positive control** recovered the
known 48-input route. Every CNF clause was checked and original-game replay
accepted it. Its 46.6-second runtime has no matched default-solver comparison;
it establishes neither a speedup nor a record. The control and full replay
report are archived here.

## III-21: restricted scheduling queries

The [portable scheduler and evidence](../../experiments/macro_scheduler/README.md)
retain each hero's FIFO inventory of directional runs while freely interleaving
heroes. Both specified finite families exhausted without a 315-input candidate:

- Fixed directions and at most 74 Action inputs: 270,592 states, 15.4 seconds.
- Full-state no-op omission, at most 315 emitted inputs and 75 Actions:
  1,784,930 states, 208.7 seconds.

The second completion increased only the memory limit after a resource
truncation. The queue heuristic changes ordering, never pruning. Neither result
establishes a global original-game lower bound: the inventory, Action cap, and
independently implemented native model limit the claim.

## Validation and reproducibility

The 22 focused tests and portable macro controls passed. The full branch suite
ran 143 tests with 26 failures, 10 errors, and four skips. Its failing-test
multiset exactly matches clean main `2399514`; the suite does **not** pass.
The branch log and focused results are archived here; the original main
comparison is in the [earlier evidence](../2026-11-12-global-record-system/).

`summary.json` indexes the terminal results and the dated Frontier observation.
The bundle manifests preserve CNF and source hashes, but the large CNFs,
assignments, and solver binaries are not committed. Recompile using the
[global-query entry point](../../experiments/exact_frontier/README.md); formulas
may receive different variable numbering and hashes in a new Z3 context. The
macro package includes its compact inputs and controls. These files document
completed experiments, not a promise of continued background search.
