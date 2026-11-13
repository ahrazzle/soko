# III-14 15x7: the v14 heuristic (rejected) and an audit of main's floor of 38 or more

Written 2026-11-13. Main at the time of the audit: `9fcb6cfaa27b7e9401fd7a4080131fe62041d083`.

This note has two parts.

1. The "floor 36" claim from the closed PR #41 is unsupported. Its heuristic gives a value that is too high at reachable states.
2. A known-answer audit of main's floor of 38 or more found no fault. Its method, numbers and gaps are below, and the checks that can be rerun are now in `tests/`.

Status labels used here: **VERIFIED** means checked exhaustively or by the committed prover. **TESTED** means checked on a fixed set of states and found clean. **ARGUED** means a reason is given but it is not a proof. **NOT RUN** means nobody ran it.

## 1. Rejected result: the v14 heuristic from PR #41

**Claim.** A certified floor of 36 (no solution of 35 keys or fewer) on the 15x7 catalog board of III-14, from a prover called `prove_iii14_v14.cpp`.

**Status: floor 36 unsupported, not refuted.** No shorter solution was found. The claim is unsupported because the proof it rests on does not hold. Main's floor of 38 or more is not affected. The v14 source is not committed here.

**What was checked.**

- The v14 prover file has sha256 `24c565d8a970b206a3cf0bd17b741b260d426711d63ef14bf21ddeca1badde78`. This matches the hash recorded in PR #41 before it was closed.
- The two states below are reachable. They were confirmed on the original v14 code. In both, v14's heuristic says 3, but two keys win.

| Name | Keys | Then | v14 heuristic | Real distance |
| :--- | :--- | :--- | ---: | ---: |
| CE1 | first 38 keys of the PR #41 witness, then `DRDARURDUUL` | `RR` wins | 3 | 2 |
| CE2 | first 42 keys of the PR #41 witness, then `URURARURR` | `LL` wins | 3 | 2 |

- One key later the v14 value drops from 3 to 1. A consistent heuristic can drop by at most 1 per key, so v14's value at these states cannot be used as a lower bound. A heuristic that is too high at one reachable state can cut off the real shortest solutions.
- **Why the runtime check missed it.** v14 checks `h(s) <= 1 + h(s')` only on edges leaving states it expanded. These two states lie past its cutoff, so they were never checked.
- **The rules differ from main.** v14 does not erase crates or walls on door cells when the doors close. Main does (`experiments/iii14_15x7_verified_floor/iii14_15x7_core.hpp`, lines 154 to 158). So the game v14 searches is not a relaxation of the real game, and a bound from it does not carry over.
- **The cause.** v14's window slicing takes contiguous windows of the sorted x and y lists. This is the hazard recorded as F-12 in `docs/admissible-multipiece-bounds.md`.

**The same two states under main's rules** (test `tests/iii14_floor`, section `v14`). All 49 keys of CE1 and all 51 keys of CE2 are accepted by main's `step_concrete`. The resulting boards are the same as the boards v14 reaches, because no door cell holds a crate or wall at those moments. In both, the exact distance by breadth-first search is 2, and main's `eval_h` is 2. So main's heuristic is exact here, and v14's 3 is the overestimate.

The PR #41 witness is not main's `R48`. Both have 48 keys, but they differ in the harvest order near key 8. The witness wins under main's rules.

## 2. Note on main's floor of 38 or more

The floor is stated in `evidence/2026-11-13-iii14-15x7-floor38-ledger/README.md`. This audit did not rerun the search. It checked whether the heuristic that search depends on is consistent and does not overestimate. The result is **supported, not refuted**.

**What the prover uses.** `eval_h` is the largest of seven table lookups: `rf5(s)`, `ha(s)`, `ha(mirror s)`, `gw(s)`, `r2(s)`, `r2(mirror s)` and `r3(s)`, capped at 250. There are no sums. The mirror is the top-bottom reflection of the board.

**Method.** Each lookup `L` was checked on every edge: `L(s) <= 1 + L(s')`, with `L = 0` at a winning state. The same was done for `eval_h`.

| Check | Status | Result |
| :--- | :--- | :--- |
| Every edge in a depth-19 breadth-first search from the start (25.6M states) | TESTED | 0 violations |
| Every edge of the prover's own stored set (58.8M states) | TESTED | 0 violations |
| 200,000 random and greedy walks | TESTED | 0 violations |
| Invariant fuzz: random states that obey the game's rules but need not be reachable | TESTED | 0 violations |
| `d*(s_t) = 48 - t` along `R48` for `t = 28..48` | TESTED | holds. Breadth-first search agrees for `t >= 34` |
| rf5 row-3 Bard entries are mirror symmetric | VERIFIED (all entries) | 13,936,260 compared, 0 mismatches |
| `step_concrete` commutes with the mirror | TESTED | 20M checks, 0 mismatches |

**Gaps.**

- rf5 and ha are argued and tested. They are not formally proved admissible. **ARGUED.**
- The last layer of the search (`f=37`) was not rerun in this audit because of memory. **NOT RUN.**
- Whether `step_concrete` matches `soko_mcp/oracle.py` on random routes had not been tested. The new test below covers it. **TESTED** (section 3).

**Build note.** The prover needs `#include <cassert>` to build with GCC 16. This was added. Apple clang lacks `bits/stdc++.h`, so on macOS build with Homebrew `g++-16`.

## 3. Tests added with this note

All files are in `tests/`. Run:

```sh
python3 -m unittest tests.test_iii14_floor_regression -v
```

This needs a GCC with `bits/stdc++.h` (`g++-16` on macOS) and skips without one. Measured on a 10-core Mac: about 5 s to compile, 19 s to build the five tables, about 2 s for the checks, about 31 s in total with the oracle test. No environment variable gates anything, because the default run is short.

| Test | What it checks | Run time |
| :--- | :--- | ---: |
| `edges/ball_depth_14` | all 538,133 states within 14 keys of the start, 2,498,674 edges, each of the seven lookups and `eval_h` | 0.3 s |
| `edges/walks_off_R48_prefixes` | 600 seeded walks of up to 60 keys that start from a prefix of `R48`, 160,459 edges | under 0.1 s |
| `edges/invariant_fuzz` | 100,000 seeded states that obey the game's rules, 423,657 edges | 0.2 s |
| `exact/R48_tail_t34_48` | breadth-first `d*(s_t) = 48 - t` for `t = 34..48`, and every lookup on both orientations is at most `d*` | 0.6 s |
| `reflection/step_commutes_with_mirror` | 38,300 seeded states, 191,500 state and key pairs | under 0.1 s |
| `reflection/rf5_row3_bard_symmetric` | 13,936,260 rf5 entries | under 0.1 s |
| `v14/*` | the PR #41 witness and the two counterexamples under main's rules (section 1) | 0.4 s |
| `Iii14OracleParity` | 150 seeded routes, 10,638 keys: `step_concrete` and `soko_mcp/oracle.py` give the same state after every key. 82 keys that `step_concrete` refuses were checked as well: the oracle shows no change or a lost hero | about 10 s |

A planted fault (adding 2 to one lookup at a few cells) makes all three `edges/*` tests fail, so the checks can fail.

`tests/iii14_floor/harness.hpp` repeats the board setup and table builds from the top of the prover's `main`, because `main` is not reusable. The setup tests (`R48` wins, the sticky-door route is rejected at key 30) and `test_r48_matches_prover_and_oracle` catch drift between the two.
