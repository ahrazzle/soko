# True `15x7` Room `III-14` Certified Lower Bound (`>= 38`) & Session Computation Ledger

## 1. Executive Summary

This ledger captures all C++20 provers, relaxation audits, and macro-window exact search certificates produced in this verification cycle so zero session compute remains isolated outside the repository:

1. **First Certified Collision-Free Lower Bound on True `15x7` Room `III-14` (`>= 38`, `VERIFIED`)**:
   - Prior repository state (`docs/admissible-multipiece-bounds.md`) established `>= 34` on the cropped `14x7` fixture only and explicitly noted that true `15x7` (`Part III`, SHA-256 `f66ceb8f8a2c23a3cb270bad62cdf194e47479772cab94f154ed26f0ff7c20e0`) was not yet established.
   - `experiments/iii14_15x7_verified_floor/prove_iii14_15x7_floor.cpp` certifies **`proven_floor >= 38` (`VERIFIED`)** on the exact `15x7` grid under full Part III PuzzleScript semantics (`expanded = 47,583,293`, `unique_canon_states = 141,107,637` [representing `~282M` raw `15x7` states under vertical-reflection canonicalization], `edges_verified = 223,916,631`, **`bellman_violations = 0`**, `hash_collisions_prevented = 181,027,454` in `105.36s` on 2 CPU cores).
2. **Sticky-Door vs. Crushing-Door Phase Transition Theorem (`H* = 34` vs. `H* >= 38`)**:
   - Under a relaxed sticky-door rule (`open_pd &= weighing`, omitting Part III's purple-door slam-shut crush rule), exact collision-free A* reaches a global optimum at **`34` steps** (`LULULUULRURRURURUALDRRUDRRUDDRURRR`), where only `8` border walls are harvested (`7` crates + `2` heroes weigh the `9` switches, and Druid steps onto purple door `(8,3)` before Bard steps off a switch on step `30`).
   - Both independent Part III PuzzleScript reference interpreters (`soko_mcp/oracle.py` and `soko_mcp/flat_oracle.py`) confirm that step `30` of `LULULUULRURRURURUALDRRUDRRUDDRURRR` **crushes Druid on `(8,3)` (`alive = False`, `steps_executed = 30`)** when `< 9` switches remain weighed.
   - Enforcing the exact Part III purple-door slam-shut law (`doors_open == all_sw` at the end of every turn, crushing any hero and erasing any obstacle on `PDOOR_MASK` when `all_sw` drops to `false`) forces **all `9` switches** to be covered by non-hero obstacles (`k0 == 9, km >= 9`) when the second hero crosses `PDOOR_MASK`, lifting `h(s0)` from `22–24` to **`27`** and certifying **`>= 38`** with `0` Bellman violations.
3. **Transport-Relaxation Rung & LNS Perturbation Audit (`experiments/transport_relaxation/verify_relaxation_rungs.cpp`)**:
   - Certifies `0` violations of the Unblocked-Crate Non-Stuttering Theorem across `250,000` concrete `15x7` states (`255,924` stutters checked), separates Hall matching (`r30`: `9/9` Hall, `5/9` intact-border `9`-flow) from intact-border `9`-flow (`r33`: `9/9` intact-border `9`-flow, fails concrete replay via unblocked-crate stuttering), and records the `3,536`-trace LNS window perturbation check around `r48` (`w in {5, 6, 7}`, net `-1..-3` keys -> **`0` `R3` or `R4` shortcuts `< 48`**).
4. **Room `II-22` (`94` Live vs. `92` Reported) Exact Collision-Free Window Audit (`experiments/ii22_macro_audit/verify_ii22_windows.cpp`)**:
   - Implements a 48-byte collision-free 91-slot nibble-packed `PackedII22` engine and verifies `0` shortcuts across `15,000,000`-state exact BFS runs on 7 overlapping windows of the `94`-step live record (`[54..94]` exact depth `20`, `[46..94]` `25`, `[34..74]` `36`, `[26..64]` `27`, `[16..54]` `24`, `[0..40]` `36`, `[38..86]` `32` — proving in particular that no `< 36`-step shortcut exists inside `[0..37]` or `[34..71]`), alongside `24,000,000`-state canonical macro-switch (`k_sw in 0..3` `'A'`s + directional move) Dial A* runs from `L in {54, 46, 34}`.

## 2. True `15x7` Room `III-14` Quotient-Homomorphism Architecture

Every heuristic component in `experiments/iii14_15x7_verified_floor/` is a pure graph homomorphism $\pi: G_{\text{concrete}} \to G_{\text{abstract}}$ with zero unproved pruning, audited dynamically on every expanded concrete edge ($h(s) \le 1 + h(s')$):

- **30-Byte Exact Canonical State (`Packed15`)**: Stores full `105`-bit `crates` (`14` bytes), full `105`-bit `walls` (`14` bytes), `(b_pos, doors_open)` (`1` byte), and `(d_pos, active_hero)` (`1` byte), canonicalized under the exact vertical-reflection board automorphism $y \leftrightarrow 6 - y$ (`pack_canon(s) = min(pack_raw(s), pack_raw(mirror_y(s)))`), halving memory and node expansions with zero loss of exactness.
- **`RingFlow5_15PDB` (`53.2 MiB`)**: Tracks `(km, k0, k1, k2, k3)` (`2,102` tuples of active obstacles across concentric Manhattan-distance rings $D \in \{0, 1, 2, 3, \ge 4\}$ around `SWITCH_MASK`), exact $y$-canonical Bard cell (`0..59`), exact Druid cell + adjacent intact border-wall count `(di, adj)` (`221` states), and `ah`, including exact `back_tp_crush1` door-slam obstacle-erasure predecessors on `PDOOR_MASK`.
- **`HarvestAdj15PDB` (`68.2 MiB`, evaluated on both `s` and `mirror_y(s)`)**: Tracks a `9`-bit missing-wall mask on `{(0,2..5), (1..5,6)}` (`14` walls with $y$-mirror), remaining missing-wall count `kr in 0..9`, exact `(di, adj_other)` preventing in-place double-harvesting, Bard column/chamber zone `b_loc` (`18` zones), `ah`, and `doors_open`.
- **`Gateway67_15PDB` (`30.7 MiB`) & `RowStrip15PDB` (`y = 2, 3`, `6.8 MiB`)**: Exact `6`-cell `[6..7] x [2..4]` (`3^6 = 729`) and `4`-cell `[4..7] x {Y0}` (`3^4 = 81`) obstacle-state quotients with exact `(b, d, ah, doors_open)`, capturing Bard `5x5` aura pull-off and purple-door crush hazards at the vault entrance.

## 3. Certified `15x7` `III-14` Progression Log (`2` CPU Cores, `MAX_STATES = 152,000,000`)

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

## 4. Reproduction Commands

```bash
# 1. True 15x7 III-14 Exact Lower-Bound Prover (pass 10.0 for quick >= 36 smoke test, 95.0 for >= 38)
g++ -O3 -march=native -std=c++20 -pthread \
  experiments/iii14_15x7_verified_floor/prove_iii14_15x7_floor.cpp \
  -o prove_iii14_15x7_floor
./prove_iii14_15x7_floor 95.0

# 2. Transport-Relaxation Rungs & Unblocked-Crate Non-Stuttering Theorem Audit
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

## 5. SHA-256 File Manifest

```text
6f0cf9a601c61cb917e82556aa6bd11d4fabdb2758d68c67f0f4bfaeae299018  evidence/2026-11-13-iii14-15x7-floor38-ledger/README.md
6ee370c5d3d97a16d6ee608d5b551c07be597376e903b7d0f8eae3464b0456cc  experiments/ii22_macro_audit/verify_ii22_windows.cpp
0b84ed3a581614da56e1fd0a851324159e3da374e3c122160e5f75961b02150f  experiments/iii14_15x7_verified_floor/iii14_15x7_core.hpp
63ee18de94e8e2069b7331a90b2ea1275bc5d726a0f613bbde78fe9c0f3bcd82  experiments/iii14_15x7_verified_floor/iii14_gateway67_pdb.hpp
12b889536c1e9329592251fa8397b2ffdb8d78efea96b71442520c5cafa71c0c  experiments/iii14_15x7_verified_floor/iii14_harvest_pdb.hpp
a4455ed02bef546e9eb3ee127f60541c95cb0855df4e8a92775f7ead0f326775  experiments/iii14_15x7_verified_floor/iii14_ringflow5_pdb.hpp
7bd9ec258c51a6dd898bd37f1c299d61a8f4774ae1aaebc250f60cd618fec47f  experiments/iii14_15x7_verified_floor/iii14_rowstrip_pdb.hpp
05d3ec402d20e625044959b63001f911c8336791f2f75980b16963ec9c47a245  experiments/iii14_15x7_verified_floor/prove_iii14_15x7_floor.cpp
fc86cd95797635ba871b381744cf1ced8fcd5a070d20b788d9ce7073b10b9434  experiments/transport_relaxation/verify_relaxation_rungs.cpp
```
