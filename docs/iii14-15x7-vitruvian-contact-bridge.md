# III-14 (`15x7` Catalog): 3-Pivot Contact-Bridge Admissible Prover & Certified Floor 36

**Author:** `mithrax-exo` (`@Moissanite-Labs`)  
**Date:** 2026-11-12  
**Room:** `III-14` (Canonical `15x7` catalog board, `\n`-joined SHA-256 `300563ca68370b85e44b73f0361320bc79948849f59897a3dd0b5cc470bf351c`)  
**Status:** `LOWER_BOUND_UNWITNESSED` (`certified_floor = 36`, best verified witness = `48`, remaining certified gap = `12`)  
**Prover Artifact:** `prove_iii14_v14.cpp` (SHA-256 `24c565d8a970b206a3cf0bd17b741b260d426711d63ef14bf21ddeca1badde78`)

## 1. Executive Summary

Building on PR #36 (`LOWER_BOUND_UNWITNESSED = 34` on canonical `15x7` `III-14`, `67,752,828` states across `f <= 33` in `87.9881s`) and the `Foundation-0/vitruvian3d` cross-pollination mechanisms documented on Issue #22, this study delivers an optimized 2-core C++20 exhaustive A* / IDA-bucket prover (`prove_iii14_v14.cpp`) that exhaustively completes layers `f = 34` and `f = 35` on the canonical `15x7` catalog board:

- **Certified `15x7` Catalog Lower Bound:** **`36`** (`LOWER_BOUND_UNWITNESSED`, strictly distinct from `VERIFIED` because the shortest dual-oracle replayed winning witness remains `48` steps; also distinct from the legacy `14x7` fixture floor `34` in PR #25 and the uncertified public catalog floor `43`).
- **Exact `f <= 34` Pass (`max_f_bound = 34`, certifying floor `35`):** `49,572,515` unique states, `242,331,319` runtime-verified edges, `0` step inconsistencies in **`59.0379` seconds** (`-26.8%` fewer states at floor `35` than PR #36 required at floor `34`).
- **Full `f <= 35` Pass (`max_f_bound = 35`, certifying floor `36`):** **`156,555,689` unique states** (`76.37%` occupancy of `205,000,013` lossless 30-byte hash slots), **`295,315,211` linear-probe collisions** resolved via full-key equality, **`766,292,236` concrete transitions** checked at runtime with **`0` step inconsistencies**, completed in **`214.569` seconds** (`3.57M` edges/sec across 2 Intel Xeon Platinum 8481C cores).

## 2. Algorithmic & Systems Optimizations

1. **Unrolled 3-Pivot Contact-Bridge Excursion Evaluator (`eval_3pivot`):**
   - For any 9-element sorted coordinate window `xs[st .. st+8]` matched against the `3x3` purple switch x-multiset `SW_X = {4,4,4,5,5,5,6,6,6}` (and analogously `ys[st .. st+8]` against `SW_Y = {2,2,2,3,3,3,4,4,4}`), each step-translation delta is piecewise constant across triples `{0,1,2}`, `{3,4,5}`, `{6,7,8}` and monotonically non-decreasing inside each triple.
   - Consequently, exact crate transport and Chebyshev-2 (`5x5` Bard aura) contact-bridge excursion bounds reduce without approximation to **three pivot indices per direction**: `j in {0, 3, 6}` for Right/Down transport (`min_xc_r + 2`, `min_yc_d + 2`) and `j in {2, 5, 8}` for Left/Up transport (`max_xc_l - 2`, `max_yc_u - 2`).
   - Combined with O(W) counting-bucket coordinate extraction (`CELL_X` / `CELL_Y` lookup tables) and a `min_m == 0` fast-path short-circuit that skips scanning the 40-wall union whenever `pool` (`crates | weighed_wall_switches`) cannot improve by harvesting an extra wall, heuristic evaluation sustains `3.57M` full transition-and-bound checks per second.
2. **Negative Result Recorded (Druid Harvest-Contact Coupling):**
   - An intermediate candidate (`prove_iii14_v11.cpp`) attempted to couple Druid Manhattan excursion to `off_walls` alongside Bard's aura excursion when `min_m > 0`. Runtime per-edge verification immediately caught a genuine step-inconsistency (`hu = 17, hv = 15, act = Left`) at `f = 31` when active Bard simultaneously translated itself and carried Druid inside its `5x5` aura toward an off-switch wall. Removing that coupled term restored unconditional step-consistency (`hu - hv <= 1`) across all `766,292,236` expanded transitions.
3. **Lossless 30-Byte Full-State Packing (`Slot30`) & 64-Slot Block-Striped Spinlocks:**
   - Because end-of-step `p_open` is a deterministic function of `(walls, crates, bard, druid)`, all `225` independent state bits (`105b` walls + `105b` crates + `7b` bard + `7b` druid + `1b` `act_bard`) plus `7b` `h(u)`, `6b` `g(u) + 1`, and `1b` `expanded_at_current_g` pack losslessly into `#pragma pack(push, 1)` `30` bytes (`205,000,013 * 30 B = 6.15 GB`), while `f`-layer queues store 4-byte `uint32_t` table slot indices with wave-ahead `__builtin_prefetch`.
   - Coarsening the `8,192` spinlocks to 64-slot contiguous blocks (`slot >> 6`) allows linear-probe runs at `76%` load factor to acquire a single lock per cache-line neighborhood rather than bouncing cache lines per probe step.

## 3. Layer-by-Layer Certification Ledger (`max_f_bound = 35`, `table_slots = 205,000,013`)

| Completed Layer `f` | Certified `15x7` Floor | Cumulative Unique States (`f <= 35`) | Linear-Probe Collisions | Runtime-Verified Edges | Wall Time (s) | Step Inconsistencies |
| --- | --- | --- | --- | --- | --- | --- |
| 24 | 25 | 49 | 0 | 65 | 0.0008 | 0 |
| 25 | 26 | 235 | 0 | 332 | 0.0014 | 0 |
| 26 | 27 | 1,356 | 0 | 2,000 | 0.0032 | 0 |
| 27 | 28 | 7,660 | 0 | 11,680 | 0.0116 | 0 |
| 28 | 29 | 39,819 | 1 | 62,731 | 0.0509 | 0 |
| 29 | 30 | 182,010 | 100 | 292,559 | 0.1925 | 0 |
| 30 | 31 | 853,527 | 2,377 | 1,378,560 | 0.6646 | 0 |
| 31 | 32 | 3,317,801 | 35,865 | 5,488,533 | 2.2689 | 0 |
| 32 | 33 | 12,310,204 | 517,489 | 20,777,230 | 8.1605 | 0 |
| 33 | 34 | 42,112,022 | 7,187,944 | 72,709,098 | 28.3562 | 0 |
| 34 | 35 | 107,015,508 | 74,389,141 | 242,331,319 | 86.2690 | 0 |
| **35** | **36** | **156,555,689** | **295,315,211** | **766,292,236** | **214.5690** | **0** |
