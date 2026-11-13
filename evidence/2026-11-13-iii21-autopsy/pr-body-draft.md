# III-21 route autopsy, live-frontier re-baseline, and a fresh-clone lock defect

Adds a dated evidence bundle for III-21, re-baselines the live Frontier numbers to 2026-11-13, and records a defect in the engine lock that blocks the optimiser on a fresh clone. No new record and no raised floor.

## What this adds

- `evidence/2026-11-13-iii21-autopsy/`: live Frontier snapshot (raw API response, 2026-11-13 08:55 UTC), a key-by-key autopsy of the 316-key III-21 record (`autopsy.py`, `autopsy.json`, `autopsy.md`), a left-right mirror analysis (`mirror.py`, `mirror.json`), a fresh-clone lock defect note, and the window-24 optimiser log.
- `docs/original-eval-and-frontier.md`: the three open floors move to the 2026-11-13 values (44, 75, 269).

## Findings

- Live Frontier, 2026-11-13: only III-14 (44/48), III-20 (75/84) and III-21 (269/316) still have a gap. Banteg accepted proofs raising all three floors overnight. Trilogy sums are now 3,063 known and 3,003 floor.
- The 316-key route uses 75 hero-switch presses out of 316 keys. It visits the six heroes in strict cycle order, 13 passes, with 39 switches that do nothing but pass through a hero to reach the next one. Work is spread across the three board bands with 61 crossings, and the first 286 keys park at most one hero on a goal. The last 30 keys park all six.
- The board is exactly mirror-symmetric left to right on rows 0-6, 8 and 12, and breaks on 16 cells in rows 7, 9, 10 and 11. The mirror permutes the heroes in a way that commutes with the switch cycle but swaps every hero role, so it does not transport routes. It is a geometry-only symmetry.
- Fresh-clone defect: a new checkout can rebuild the pinned engine binary on first use, because the reuse check is based on file times. The rebuilt binary differs from the pinned hash, the lock then fails, and the optimiser refuses to run with an error that blames the route. Restoring the pinned binary clears it. The defect note lists three fix directions for review. None is applied here.
- Optimiser, window 24, beam 40,000, 215 s: 316 stays 316, 0 keys saved. No 24-key window anywhere in the route admits a shorter path between its endpoint states.

## Validation

```sh
python3 -m soko_mcp verify --room III-21 --route <316-key route>
python3 evidence/2026-11-13-iii21-autopsy/autopsy.py
python3 evidence/2026-11-13-iii21-autopsy/mirror.py
python3 -m soko_mcp tcb-lock
```

The verify run used the triple oracle with a differential match. The autopsy and mirror scripts reran clean, and the counts in this body match the JSON outputs. The lock check reads True after restoring the pinned binary.
- Full test suite: 184 tests, 24 failures, 30 errors, 9 skipped. The failure set is identical to pristine main at the same commit, so the failures pre-date this change.
- The branch changes no engine code and no pinned binary.

> Automated posting by agentic team with human oversight.
