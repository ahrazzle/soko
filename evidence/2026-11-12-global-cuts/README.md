# Global material-cut implementation: execution evidence

The plan was shared and merged in [PR #17](https://github.com/ahrazzle/soko/pull/17)
before implementation. These results use core commit `d6fd09d`; every bundle
pins the exact Python sources, catalog, graph identity and solver version.
Later driver-only fixes normalize subprocess paths and enforce/report deadline
handling after witness replay. They have dedicated regression tests and do not
change the archived solver, graph or certificate semantics.

| Run | Observed result | Scope |
|---|---|---|
| Known 48-input reference, deliberately impossible initial landmark | One checked cut; second candidate supplies nine independently checked paths; 7.32 s | Positive control with reference actions/heroes pinned; pinned original engine separately accepts the recovered route at input 48 |
| Unrestricted III-14, horizon 47 | Eight checked cuts; ninth master query reaches 120 s; `unknown` | No route, new record, or stronger lower bound established |
| III-14, horizon 1 | UNSAT; proof-producing SAT plus independent DRAT check; 0.54 s | Trivial pipeline control, not a new useful bound |

The 47-frame network has 9,921 nodes and 29,413 potential forward edges. Every
edge remains in the universal domain even when its current capacity is zero.
The pilot's `reason: canceled` is Z3's response to its configured remaining-time
limit, not a user cancellation. All runs explicitly set `record_claim: false`.
Runs overlapped with checks, so these timings are observations rather than a
controlled performance comparison.

## Recheck the portable artifacts

From a clone containing the pinned commit, with Z3 installed:

```sh
python evidence/2026-11-12-global-cuts/recheck.py
python evidence/2026-11-12-global-cuts/recheck.py --proof-checker /path/to/drat-trim
```

The compressed bundles retain original UTF-8 file contents (including every
assignment and accepted cut), not a lossy summary. The rechecker verifies source
hashes against Git, independently rebuilds the graph and all nine persisted
cuts, and checks the reference witness. With the optional checker it also
replays the archived CNF proof; its executable hash must match the recorded
checker. No optimization run is needed. `recheck-result.json` records the
completed replay with proof checking.

Fresh execution uses:

```sh
python -m experiments.transport_relaxation.global_search control --output /tmp/global-control --timeout-seconds 90 --max-iterations 100
python -m experiments.transport_relaxation.global_search run --horizon 47 --output /tmp/global-47 --timeout-seconds 120 --max-iterations 200 --proof-checker /path/to/drat-trim
python -m experiments.transport_relaxation.global_search run --horizon 1 --output /tmp/global-unsat-control --timeout-seconds 30 --max-iterations 20 --proof-checker /path/to/drat-trim
```

The original replay used the reference route in `reference48-result.json`,
the pinned Part III HTML and system Chromium via `experiments.original_engine.check`.
Its complete certificate is `reference48-original.json`.

## Validation and claim boundary

`focused-tests.txt` records the passing new and existing transport tests.
`full-tests.txt` records the broad suite at the initial implementation: 209
tests, with the same 26 failures, 10 errors and 4 skips as the prior 175-test
baseline. No new failing test identities appeared. The three later CLI/deadline
regressions are included in the final focused run. `baseline-comparison.json`
records that comparison. `manifest-check.txt` verifies all existing SHA256SUMS
entries. The separate stricter source-manifest command still rejects existing
extra entries; `strict-integrity.txt` records that pre-existing inconsistency.

The system implements a complete finite cut loop for the stated relaxation,
not the full original game's collision/freezing semantics. A relaxed witness
is not a playable win. A checked CNF proof establishes encoded UNSAT, with the
written game projection and encoding/compilation still in the trusted boundary.
Timeouts establish no infeasibility. No end-to-end formal verification or new
record is claimed.
