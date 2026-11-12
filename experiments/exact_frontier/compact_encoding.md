# Compact exact encoding

The III-14 global builder now defaults to `iii14_compact.py`. The legacy
transition and builder remain available; call
`build_problem(horizon, encoding='legacy')` to compare them. Both use the same
initial state, hero and action cardinalities, guarded landmarks, absorbing
victory, final objective, and all 105 board cells. No route prefix or schedule
is fixed.

The old builder repeats movement selection, note generation, door updates,
cancellation, and next-state equalities in five action branches. The compact
builder selects direction-dependent intermediate values first and shares the
remaining computation. The four directional fixed-point masks retain the
original jump sequence. This is an algebraic refactor, not a relaxed model or
a restricted search family.

## Equivalence obligation

For each of `U D L R A`, the checker creates an arbitrary symbolic state and
asks whether either legality or any next-state component differs. It assumes
no reachability, occupancy, hero-count, note, or topology invariant. All five
queries are unsatisfiable. Together they cover every exactly-one action
selection. Identical initial and final conditions and the identical absorbing
goal rule then preserve the bounded paths; the landmarks are unchanged.

```sh
python -m experiments.exact_frontier.check_compact_equivalence \
  --output /tmp/iii14-equivalence \
  --proof-checker /tmp/soko-drat-trim/drat-trim
python -m unittest tests.test_compact_encoding \
  experiments.exact_frontier.test_iii14_problem
```

The independent checker verifies the transformed difference CNFs. Z3's
expression construction, simplification and bit-blasting remain trusted. In
this run simplification reduces each difference to false, so each CNF contains
an empty clause and its DRAT check is trivial. The certificates do **not**
independently prove the SMT-to-CNF translation. This establishes the refactor's
equivalence relative to the legacy symbolic model under that trust boundary;
it does not prove either model equivalent to the original PuzzleScript game.

Four planted semantic bugs (legality, active hero, notes, and door state) are
detected by satisfiable difference queries. Separate tests ensure an extra input
after a known victory remains absorbed, and an unchecked proof or timeout
cannot be reported as checked equivalence. The original-game known-route
control remains a separate acceptance check.

## Compilation measurement

Use the same compiler in fresh processes for each encoding:

```sh
python -m experiments.exact_frontier.compare_encodings \
  --output /tmp/iii14-comparison --horizons 47 --keep-cnf
```

The harness records source hashes, dependency versions, output hashes, compile
time, and peak memory. It performs no SAT record search. Output directories
must be empty, and a timeout or error prevents a completed comparison claim.
Short horizons can simplify to false from the existing landmarks; their
variable counts do not measure transition compression.

For the unrestricted 47-input problem, with the same landmarks enabled:

| Metric | Legacy | Compact |
| --- | ---: | ---: |
| Variables | 715,288 | 343,781 |
| Clauses | 5,834,178 | 2,865,101 |
| DIMACS bytes | 190,895,385 | 95,217,606 |
| Peak compilation memory | 3.78 GiB | 1.95 GiB |
| Compilation time, single run | 50.9 s | 32.2 s |

All 235 action aliases survive in both formulas. Clause count falls 50.9%;
memory falls 48.4%. Timings are single measurements on a shared machine with
other validation work running, not a controlled runtime benchmark. No SAT
solving speedup, new record, or new original-game lower bound is established.

The [portable evidence](../../evidence/2026-11-12-compact-system/README.md)
contains the comparison metadata, difference CNFs and proofs, tests, and
known-route replay. The large record-query CNFs are kept outside the repository.
