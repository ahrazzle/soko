# Nine-workstream implementation and execution evidence

The plan was published first in [PR #21](https://github.com/ahrazzle/soko/pull/21).
Wave one implemented causal encoding, events, bounds and mechanics controls;
wave two integrated exact refinement and three solver backends; wave three
tested and measured them. The measured master bottleneck then prompted a
documented, independently reviewed finite-arithmetic experiment and a measured
default choice. All nine requested areas have executable implementations and
tests; unsuccessful optimization experiments are retained and labeled.

## What improved, and what did not

| Question | Observed result |
|---|---|
| Complete known 48-input projection | Full-material deterministic completion SAT in 0.526 s |
| Complete spurious 47-input projection | Contradiction in 0.293 s; independently rechecked against retained transition and Python oracle |
| General guarded-assumption SMT on those same assignments | Both remained unknown at the 35-second outer limit |
| Positive integrated control | Flow 9, exact SAT, and pinned original-engine replay accepted the 48-input route |
| Negative integrated control | A checked prefix contradiction excludes the spurious projection; restricted master becomes UNSAT |
| Five-input backend control | 18/18 runs SAT with checked models; three repetitions per encoding/backend |
| Pinned 47-input monolithic formulations | All 12 encoding/backend/event configurations reached their 20-second limits |
| H47 master arithmetic probe | Bounds off: SAT in 1.87 s; integer bounds and equivalent widened-bitvector bounds: unknown at 20 s |
| Initial unrestricted integrated query | Integer-bound master reached 120 seconds without a candidate |
| Selected unrestricted query | 151 candidates, 150 independently checked exact cuts in 120 seconds; unknown, no record |

The fixed-route comparison is one repetition per cell. It measures specialized
deterministic completion against general assumption-based SMT, not a universal
encoding speedup. Timed-out workers were terminated as process groups; missing
internal phase timings are explicitly null. The original driver is archived
unchanged as `refinement_comparison_driver.py.txt`, matching its recorded hash.
`compare_refinement.py` changes its checkout location to a portable relative
path for rerunning the comparison.

The five-input median wall times were about 1.12 s / 1.06 s / 1.86 s for compact
Z3 / PySAT / CP-SAT, versus 5.58 s / 4.76 s / 6.33 s for the alternative circuit.
The fastest two configurations were within the allocation policy's 20% margin,
so backend selection remained inconclusive. Some component measurements
overlapped other work on the shared host; they are exploratory observations.
CP-SAT used the same Boolean CNF as SAT, not a separate scheduling formulation.

The widened-bitvector bounds were independently reviewed for signed overflow.
Seven tests cover finite arithmetic, release targeting, preserved predicates,
and padded reference metadata. A supplementary mixed integer/bitvector suffix
miter timed out; that experiment is inconclusive. The written bounded-range
argument, exhaustive component checks and wider-bitvector predicate checks are
the basis for equivalence. No solve-time advantage was demonstrated. Numeric
bounds remain opt-in; the measured default uses compact exact completion and
the faster master, with optional proven AA normalization.

## Reproduce and recheck

Install `experiments/causal_solver/requirements.txt`. Commands for fresh runs
are in the [package README](../../experiments/causal_solver/README.md). Benchmark
JSON files retain workload, pins, budgets, versions, source hashes, phase times
and peak memory. `master_arithmetic_probe.py.txt` is the exact historical probe.
Its source hashes can be reconstructed from commit `cfb9bfc`.

```sh
python evidence/2026-11-12-causal-tractability/recheck.py
python evidence/2026-11-12-causal-tractability/recheck.py --html /path/to/pinned-part3.html --chromium /usr/bin/chromium
```

Compressed search artifacts retain complete assignments, accepted cuts, phase
profiles and source identities. `archives.json` identifies the exact source
commit for each run. Rechecking verifies those source snapshots, hero schedules,
every accepted exact/flow cut, and the reference flow. The optional HTML flag
also repeats original-engine replay. Exact certificates additionally pin and
check their actual current verification dependencies; altered dependencies fail
closed. The script does not rerun optimization or claim a new record.

`mechanics-controls.json` records 150 exhaustive short transitions, ten planted
corruptions detected, extra-material blocker fixtures, the known reference win,
and the spurious route's first abstract hero discrepancy at input 26.
`frontier-observation.json` is the saved live response used to choose H47:
III-14 reported length 48 and a displayed lower bound of 43. The solver does
not assume that external lower bound.

## Regression and proof scope

All 53 final focused tests pass. The broad suite initially ran 256 tests with the same 26 failures, 10 errors and
4 skips as the archived baseline; no new failing identities appeared. Subsequent
finite-arithmetic and default-selection changes have dedicated final focused
checks. Logs and `baseline-comparison.json` retain the exact results.

All record claims require original-engine replay and a fresh Frontier
comparison. Master UNSAT and partial-assumption SMT replay are not standalone
checked CNF proofs. Every timeout remains unknown. No new record, stronger
original-game lower bound, or end-to-end formal equivalence is established by
these experiments.
