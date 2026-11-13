# True `15x7` Room `III-14` Certified Lower Bound (`>= 38`) & Session Computation Ledger

## 1. Summary of Verified Results

1. **First Certified Collision-Free Lower Bound on True `15x7` Room `III-14` (`>= 38`, `VERIFIED`)**:
   - Prior repository state (`docs/admissible-multipiece-bounds.md`) established `>= 34` on the cropped `14x7` fixture only and noted that true `15x7` (`Part III`, SHA-256 `f66ceb8f8a2c23a3cb270bad62cdf194e47479772cab94f154ed26f0ff7c20e0`) was not yet established.
   - `experiments/iii14_15x7_verified_floor/prove_iii14_15x7_floor.cpp` certifies **`proven_floor >= 38` (`VERIFIED`)** on the exact `15x7` grid under full Part III PuzzleScript semantics (`expanded = 47,583,293`, `unique_canon_states = 141,107,637` [representing `~282M` raw `15x7` states under vertical-reflection canonicalization], `edges_verified = 223,916,631`, **`bellman_violations = 0`**, `hash_collisions_prevented = 181,027,454` in `105.36s` on 2 CPU cores).
2. **Sticky-Door vs. Crushing-Door Phase Transition (`H* = 34` vs. `H* >= 38`)**:
   - Under a relaxed sticky-door rule (`open_pd &= weighing`, omitting Part III's purple-door slam-shut crush rule), exact collision-free A* reaches a global optimum at **`34` steps** (`LULULUULRURRURURUALDRRUDRRUDDRURRR`), where only `8` border walls are harvested (`7` crates + `2` heroes weigh the `9` switches, and Druid steps onto purple door `(8,3)` before Bard steps off a switch on step `30`).
   - Both independent Part III PuzzleScript reference interpreters (`soko_mcp/oracle.py` and `soko_mcp/flat_oracle.py`) confirm that step `30` of `LULULUULRURRURURUALDRRUDRRUDDRURRR` **crushes Druid on `(8,3)` (`alive = False`, `steps_executed = 30`)** when `< 9` switches remain weighed.
   - Enforcing the exact Part III purple-door slam-shut law (`doors_open == all_sw` at turn-end, crushing any hero and erasing any obstacle on `PDOOR_MASK` when `all_sw` drops to `false`) forces **all `9` switches** to be covered by non-hero obstacles (`k0 == 9, km >= 9`) when the second hero crosses `PDOOR_MASK`, lifting `h(s0)` from `22–24` to **`27`** and certifying **`>= 38`** with `0` Bellman violations.
3. **Transport-Relaxation Rungs & LNS Audit (`experiments/transport_relaxation/verify_relaxation_rungs.cpp`)**:
   - Certifies `0` violations of the Unblocked-Crate Non-Stuttering Theorem across `250,000` concrete `15x7` states (`255,924` stutters checked), separates Hall matching (`r30`: `9/9` Hall, `5/9` intact-border `9`-flow) from intact-border `9`-flow (`r33`: `9/9` intact-border `9`-flow, fails concrete replay via unblocked-crate stuttering), and records `3,536` goal-reaching LNS window perturbations (`w in {5, 6, 7}`, net `-1..-3` keys) around `r48` (`0` `R3` or `R4` shortcuts `< 48`).
4. **Room `II-22` (`94` Live vs. `92` Known) Exact Macro-Window Audit (`experiments/ii22_macro_audit/verify_ii22_windows.cpp`)**:
   - Implements a 48-byte collision-free 91-slot nibble-packed `PackedII22` engine and verifies `0` shortcuts across `15,000,000`-state exact BFS runs on 7 overlapping windows of the `94`-step live record (`[54..94]` exact depth `20`, `[46..94]` `25`, `[34..74]` `36`, `[26..64]` `27`, `[16..54]` `24`, `[0..40]` `36`, `[38..86]` `32`), alongside `24,000,000`-state canonical macro-switch Dial A* runs from `L in {54, 46, 34}`.

## 2. Certified `15x7` `III-14` Progression Log (`2` CPU Cores, `MAX_STATES = 152,000,000`)

| Certified Floor (`15x7`) | Expanded Canon States | Unique Canon States Stored | Concrete `15x7` Edges Audited | Bellman Violations | Hash Probe Collisions Prevented | Wall Time (s) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `>= 28` | `5` | `22` | `25` | `0` | `0` | `0.48` |
| `>= 30` | `1,062` | `3,788` | `5,108` | `0` | `0` | `0.48` |
| `>= 32` | `23,155` | `79,157` | `112,176` | `0` | `31` | `0.55` |
| `>= 34` | `310,830` | `1,014,310` | `1,490,348` | `0` | `5,983` | `1.11` |
| `>= 35` | `1,066,296` | `3,439,387` | `5,080,519` | `0` | `63,745` | `2.51` |
| `>= 36` | `3,646,633` | `11,542,585` | `17,321,940` | `0` | `658,195` | `7.04` |
| `>= 37` | `11,904,056` | `37,076,418` | `56,349,201` | `0` | `7,079,156` | `22.83` |
| **`>= 38` (`VERIFIED`)** | **`38,578,394`** | **`117,766,522`** | **`181,959,400`** | **`0`** | **`105,495,450`** | **`82.41`** |
| *(End of `105.36s` budget in `f=38`)* | `47,583,293` | `141,107,637` | `223,916,631` | `0` | `181,027,454` | `105.36` |

## 3. Reproduction Commands

```bash
# 1. True 15x7 III-14 Exact Lower-Bound Prover (4.0s -> >= 35; 95.0s -> >= 38)
g++ -O3 -march=native -std=c++20 -pthread \
  experiments/iii14_15x7_verified_floor/prove_iii14_15x7_floor.cpp \
  -o prove_iii14_15x7_floor
./prove_iii14_15x7_floor 95.0

# 2. Transport-Relaxation Rungs & Non-Stuttering Theorem Verifier
g++ -O3 -march=native -std=c++20 \
  experiments/transport_relaxation/verify_relaxation_rungs.cpp \
  -o verify_relaxation_rungs
./verify_relaxation_rungs

# 3. Room II-22 91-Slot Nibble-Packed Exact Macro-Window Verifier
g++ -O3 -march=native -std=c++20 \
  experiments/ii22_macro_audit/verify_ii22_windows.cpp \
  -o verify_ii22_windows
./verify_ii22_windows 1500000
```
