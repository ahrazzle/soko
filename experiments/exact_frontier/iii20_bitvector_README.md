# III-20 bitvector SMT experiment

`iii20_bitvector.py` is an independent constraint-based attempt to shorten the
84-key III-20 route. It does not reuse beam scores, mirrored guides, distance
ranking, or explicit breadth-first window enumeration.

The state consists of eight 135-bit vectors: five separate one-hot hero masks,
goblins, crates, and walls, plus a three-bit active-role index. Each transition
uses shifts and masks; contiguous Fighter pushes and Wizard rays use logarithmic
doubling. Goblin combat and Priest shielding are simultaneous bit operations.
No Bard or doors occur in this room. Druid changes to boundary walls are modeled.
The model rejects unchanged directional keys and Druid destruction of heroes.
These cannot improve a five-hero/five-goal solution: unchanged keys are removable,
and a destroyed hero can never be restored by any available rule.

Controls completed:

- All 85 frames of the known 84-key route match `FlatBitmaskOracle` exactly in
  all eight object masks and active identity.
- 500 seeded one-step branches from that trajectory agree, accounting for 139
  removable no-ops and one irreversible hero-loss state.
- A fully specified 36-key route between baseline states 24 and 60 is SAT.

Search results are local to the supplied window, action-switch template, and
reduced rules model. SAT candidates require replay in the pinned original build.
UNSAT is not a global optimality result, and timeouts establish no impossibility.
Per-run JSON records solver status, scope, timing and statistics. No new accepted
route has been found as of the recorded runs.

Example commands (from repository root; Python requires `z3-solver`):

```sh
/tmp/soko-exact-venv/bin/python experiments/exact_frontier/iii20_bitvector.py --calibrate
/tmp/soko-exact-venv/bin/python experiments/exact_frontier/iii20_bitvector.py --fuzz 500
/tmp/soko-exact-venv/bin/python experiments/exact_frontier/iii20_bitvector.py --start 24 --end 60 --save 0 --fix-baseline
/tmp/soko-exact-venv/bin/python experiments/exact_frontier/iii20_bitvector.py --start 24 --end 60 --fixed-switches --keep-states --timeout-ms 30000
/tmp/soko-exact-venv/bin/python experiments/exact_frontier/iii20_bitvector.py --start 24 --end 84 --fixed-switches --keep-states --timeout-ms 60000
```

Use `--delete-index <absolute-zero-based-index>` to form the preserved switch
template by omitting that baseline key. Direction keys in the resulting template
remain unconstrained. Deleting an `A` changes which hero performs all subsequent
movement, a different strategic neighborhood from direction-only repair.
At the final baseline endpoint 84 the goal permits any hero-to-goal assignment;
intermediate endpoints require exact full-state equality.

`--keep-states` matters: eliminating all per-step state variables before bit
blasting caused expensive expression expansion. Keeping the equalities reached
SAT solving and closed the 35-step fixed-switch window 24→60 in about 21 seconds.
The 59-step suffix 24→84 reached 12,164 conflicts but timed out at 60 seconds.

`--export-smt2 <path>` exports assertions, including stable Boolean aliases
`action_<step>_<U/D/L/R/A>`, for an external bit-blast/CNF/SAT backend. Avoid
eliminating those aliases if the external backend must reconstruct a route.

`--backend cadical195` uses the shared `cnf_search.compile_cnf` converter and
PySAT/CaDiCaL. The converter rejects residual non-propositional theory atoms.
Route decoding uses those Boolean aliases rather than Z3 bitvector variables.
The backend runs in a separate process, so `--timeout-ms` caps CNF compilation
and native SAT solving together; an expired cap reports `unknown/wall_timeout`
and the last completed backend stage. It does not claim UNSAT on timeout.
The specified 36-key positive control passed this backend in 13.26 seconds,
including CNF compilation (142,974 variables, 1,327,052 clauses, zero decisions),
and its reconstructed full route passed local replay.

```sh
/tmp/soko-exact-venv/bin/python experiments/exact_frontier/iii20_bitvector.py --start 24 --end 84 --fixed-switches --backend cadical195 --timeout-ms 120000
/tmp/soko-exact-venv/bin/python experiments/exact_frontier/iii20_bitvector.py --start 40 --end 84 --fixed-switches --delete-index 64 --backend cadical195 --timeout-ms 120000
```
