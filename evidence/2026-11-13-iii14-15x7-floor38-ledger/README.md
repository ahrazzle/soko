> Ledger text corrected after review 5886834600, starting from Carbon's 11:46 PM CT revision of the ledger Doc. The original bundle copy hashes to `3fd04639746602493b01a5dce35fd977229dcfdcdd7148b988c756915db88af7` and lives at commit `2a34ca9e85c0b4daecc09a18b4aab71463e6f510`.

# True `15x7` Room `III-14` Certified Lower Bound (`>= 38`) & Session Computation Ledger

## 1. Executive Summary

This ledger captures all C++20 provers, relaxation audits, and macro-window exact search certificates produced in this verification cycle so zero session compute remains isolated outside the repository:

1. **First Certified Collision-Free Lower Bound on True `15x7` Room `III-14` (`>= 38`, `VERIFIED`)**:
   - Certifies the first verified collision-free lower bound on true `15x7` Room III-14 ([Sokoban Eval Frontier](https://soko.banteg.xyz/frontier/), [Part III PuzzleScript](https://www.puzzlescript.net/editor.html?hack=7072276), SHA-256 `f66ceb8f8a2c23a3cb270bad62cdf194e47479772cab94f154ed26f0ff7c20e0`), surpassing the prior `14x7`-fixture-only `>= 34` bound on [ahrazzle/soko](https://github.com/ahrazzle/soko). The bound `>= 38` attaches to the finished `f=37` layer: `expanded = 38,578,394`, `unique_canon_states = 117,766,522`, `edges_verified = 181,959,400`, `bellman_violations = 0`, `hash_collisions_prevented = 105,495,450` in `82.41s`. The later recorded point `expanded = 47,583,293`, `unique_canon_states = 141,107,637` (a ceiling of `~282M` raw `15x7` states under vertical-reflection canonicalization, twice the canonical count), `edges_verified = 223,916,631`, `bellman_violations = 0`, `hash_collisions_prevented = 181,027,454` in `105.36s` is a chunk boundary inside `f=38` at `g=22`.
   - `experiments/iii14_15x7_verified_floor/prove_iii14_15x7_floor.cpp` certifies **`proven_floor >= 38` (`VERIFIED`)** on the exact `15x7` grid under full Part III PuzzleScript semantics at that finished `f=37` layer, with the later `f=38` chunk recorded in the table below.
2. **Sticky-Door vs. Crushing-Door Phase Transition (`34` under sticky doors vs. `>= 38`)**:
   - Relaxing Part III's purple-door slam-shut crush rule (`open_pd &= weighing`) yields a `34`-step winning route (`LULULUULRURRURURUALDRRUDRRUDDRURRR`) and therefore an upper bound under that rule: doors first reach the full mask at step `29`, and the heroes finish on the two goals, Bard `(9,3)` and Druid `(11,3)`. Under exact Part III rules, Druid is crushed on purple door `(8,3)` at step `30` under both `soko_mcp/oracle.py` and `soko_mcp/flat_oracle.py`. At step `29` the doors are open, the Druid is at `(7,3)`, the Bard is at `(5,4)`, and every switch is occupied by eight `*` crates plus the Bard. At step `30` the Bard's push puts the inactive Druid on door `(8,3)` and leaves switches `(4,2)`, `(4,3)`, and `(4,4)` empty. Enforcing `doors_open == all_sw` at turn-end forces all `9` switches to hold non-hero obstacles (`k0 == 9, km >= 9`) when the second hero crosses `PDOOR_MASK`, lifting `h(s0)` to `27` and certifying `>= 38`.
3. **Transport-Relaxation Audit**:
   - Certifies `0` violations of the Unblocked-Crate Non-Stuttering Theorem across `250,000` concrete states (`255,924` stutters checked) and records the flow witnesses, including r30 HeroFlow 7/9: `r30` (`H=30`, `t_L=29`) Hall=`9/9` | HeroFlow=`7/9` | IntactFlow=`5/9`; `r33` (`H=33`, `t_L=32`) Hall=`9/9` | HeroFlow=`9/9` | IntactFlow=`9/9`; `r48` (`H=48`, `t_L=47`) IntactFlow=`9/9`.
4. **Room II-22 (`94` Live vs. `92` Known) Exact Window Audit**:
   - 48-byte collision-free 91-slot nibble-packed `PackedII22` engine. An independent rerun in review 5886834600 of `./verify_ii22_windows 15000000` printed `shortcuts_found=0` and exact depths `[0..40]` `35`, `[34..74]` `35`, `[54..94]` `19`, `[46..94]` `24`, `[26..64]` `26`, `[16..54]` `23`, `[38..86]` `31`. The same rerun of `./verify_ii22_windows 1500000` printed `shortcuts_found=0` and exact depths `[0..40]` `29`, `[34..74]` `27`, `[54..94]` `16`, `[46..94]` `19`, `[26..64]` `17`, `[16..54]` `16`, `[38..86]` `24`.
5. **Full Raw Code Bundle**: [2026-11-13_iii14-15x7-floor38-bundle.zip](https://drive.google.com/file/d/1b1z5VHaJFXB4VLzEp8oP41EqNB18xTfx/view?usp=drivesdk) in [soko/gem-nexus](https://drive.google.com/drive/folders/1epn3KIIUwoZy1hpWg-pRbUfTgrd93J74).

## 2. Certified 15x7 III-14 Progression Table

| Certified Floor (15x7) | Expanded Canon States | Unique Canon States | Concrete Edges Audited | Bellman Violations | Collisions Prevented | Wall Time (s) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `>= 28` | `5` | `22` | `25` | `0` | `0` | `0.48` |
| `>= 30` | `1,062` | `3,788` | `5,108` | `0` | `0` | `0.48` |
| `>= 32` | `23,155` | `79,157` | `112,176` | `0` | `31` | `0.55` |
| `>= 34` | `310,830` | `1,014,310` | `1,490,348` | `0` | `5,983` | `1.11` |
| `>= 35` | `1,066,296` | `3,439,387` | `5,080,519` | `0` | `63,745` | `2.51` |
| `>= 36` | `3,646,633` | `11,542,585` | `17,321,940` | `0` | `658,195` | `7.04` |
| `>= 37` | `11,904,056` | `37,076,418` | `56,349,201` | `0` | `7,079,156` | `22.83` |
| **`>= 38` (`VERIFIED`)** | **`38,578,394`** | **`117,766,522`** | **`181,959,400`** | **`0`** | **`105,495,450`** | **`82.41`** |
| End of `105.36s` run (chunk inside `f=38` at `g=22`) | `47,583,293` | `141,107,637` | `223,916,631` | `0` | `181,027,454` | `105.36` |

## 3. Reproduction Commands

```bash
g++ -O3 -std=c++20 -pthread experiments/iii14_15x7_verified_floor/prove_iii14_15x7_floor.cpp -o prove_iii14_15x7_floor
./prove_iii14_15x7_floor 95.0

g++ -O3 -std=c++20 experiments/transport_relaxation/verify_relaxation_rungs.cpp -o verify_relaxation_rungs
./verify_relaxation_rungs

g++ -O3 -std=c++20 experiments/ii22_macro_audit/verify_ii22_windows.cpp -o verify_ii22_windows
./verify_ii22_windows 15000000
./verify_ii22_windows 1500000
```
