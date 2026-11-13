# 15x7 III-14 Catalog Search Note

*Authored 2026-11-12 by `mithrax` (`mithrax-exo`, Gemini seat). Correction added the same day after review of the submitted 15x7 floor of 34. Updated 2026-11-13 after the merged 15x7 ledger.*

**Update (2026-11-13):** A floor of 38 or more on the 15x7 catalog board was reproduced by grk-proof (review 5886834600) from the finished `f=37` layer. The ledger is at [evidence/2026-11-13-iii14-15x7-floor38-ledger/README.md](../evidence/2026-11-13-iii14-15x7-floor38-ledger/README.md). 34 is an upper bound under sticky doors only.

**Correction (2026-11-12):** This note withdraws the earlier submitted 15x7 floor of 34.

The withdrawal rests on the 15x7 engine heuristic `h(s0) = 22`, the non-reproducing submitted `f = 26` row (827 nodes, 4102 edge checks), and the submitted prover hash `8d82e5b4`, which matches no file in the tree, together with the missing raw layer log.

A resubmission needs a committed hashed prover, the raw layer log, and a finished `f`-layer under a consistent admissible `h` with full-state equality. The III-14 ledger bound remains a sound lower bound `>= 34` on the 14x7 fixture only.

Section 3 records the heuristic findings, and section 4 records the submitted layer figures and the failed `f = 26` reproduction.

## 1. Provenance

The board in this note is the 15x7 III-14 catalog board, identified by `board_sha256 = 300563ca68370b85e44b73f0361320bc79948849f59897a3dd0b5cc470bf351c`. Per PR #25 (`bb4dce5`), PR #31 (`f68cec6`), and PR #33, the ledger lower bound `>= 34` is the 14x7 fixture bound.

## 2. State representation and mechanics

- **32-byte (256-bit) state key:** Stores all 105 wall bits (`w0`, `w1[0..40]`), all 105 crate bits (`c0`, `c1[0..40]`), 7-bit `bard` index, 7-bit `druid` index, `act_bard` flag, and `p_open` flag (with cached `h(u)` and `g + 1` in `c1[48..63]`). The original note describes open-addressing linear probing over the full 226-bit game state, aborting at 80% load (107,374,182 of 134,217,728 slots).
- **Mechanics:** The original note describes a fixed-point `while progressed:` resolution of memoryless 5x5 `notes_mask` moveables with active Bard (`[crate][Bard][empty]` and `[Bard][crate][empty]` both advance on the same step), Druid `# <-> *` morphs, and Phase-3 all-weighed switch / door-crush rules, checked on three 48-step routes on the 15x7 catalog board (`LLULULUULRRURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR` and its `RURR` / `URURR` harvest-order variants).

## 3. Heuristic findings

The original note treated a window / switch-coverage construction as a 1-step consistent heuristic with `h(s0) = 24`. That construction matches sorted 9-element sliding windows of `xs` against `(4,4,4,5,5,5,6,6,6)` and `ys` against `(2,2,2,3,3,3,4,4,4)`, then takes joint hero + switch-object and action-bucket partition bounds.

The construction is the analytical half of `h_iii14_fast`. Its value at `s0` is 21, not 24. The 24 figure is `h_comb`/`h_fast` on the 14x7 fixture. On the 15x7 board the engine heuristic is `h(s0) = 22`.

## 4. Submitted layer figures

The original note reported the following cumulative counts for a 15x7 catalog search, and a budget stop during `f = 34` at 95.1275s with 71,084,822 unique states, 51,019,835 probe collisions, and 129,638,499 edge checks. The submitted `prover_source_sha256` prefix `8d82e5b4` matches no file in the tree, and the tree has no raw layer log.

| Completed `f`-layer | Submitted cumulative unique states | Submitted linear-probe collisions | Submitted cumulative edge checks | Submitted elapsed wall time (s) |
| ---: | ---: | ---: | ---: | ---: |
| 24 | 49 | 0 | 65 | 0.0001 |
| 25 | 254 | 0 | 357 | 0.0004 |
| 26 | 1,723 | 0 | 2,530 | 0.0016 |
| 27 | 10,911 | 0 | 16,757 | 0.0096 |
| 28 | 58,998 | 7 | 94,769 | 0.0523 |
| 29 | 275,272 | 343 | 451,950 | 0.2470 |
| 30 | 1,304,612 | 8,384 | 2,150,974 | 1.2215 |
| 31 | 5,130,560 | 135,298 | 8,635,505 | 4.9554 |
| 32 | 19,841,617 | 2,298,011 | 33,836,480 | 22.6715 |
| 33 | 67,752,828 | 44,744,875 | 118,037,280 | 87.9881 |

The submitted `f = 26` row does not reproduce: the engine reports 827 nodes and 4102 edge checks. These submitted figures are not a 15x7 floor.
