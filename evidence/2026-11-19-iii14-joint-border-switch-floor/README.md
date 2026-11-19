# Evidence Bundle: `15x7` `III-14` Joint Bedrock-Conserved & Column-6 Petrified Floor (`>= 42`)

This directory stores machine-checkable receipts and layer logs for the V2 `15x7` `III-14` lower-bound prover (`prove_iii14_15x7_v2_floor.cpp`) and retrograde vault-endgame tablebase (`iii14_bidirectional_endgame.py`).

## First-Principles Diagnosis of the `[40 .. 48]` Gap

Tracing all `49` states along the `48`-key reference route `R48` (`9b6f169376d12a7a`) against the `>= 40` `Switch3x3 + need9` heuristic revealed three distinct phantom shortcuts:

1. **Backstop spawning on `[4..6] x [2..4]`**: In `Switch3x3_15PDB`, each 1D switch strip independently permitted a backstop obstacle (`blk = 1`) at `(7, y)` or `(x, 1)`/`(x, 5)` even when `m_act <= 9` and all `9` harvested obstacles were already accounted for inside `[4..6] x [2..4]`.
2. **Outer-border bedrock phasing (`y = 0` and `y = 6`)**: Abstract hero positions permitted Bard to walk through unharvested `#` border walls `(7..9, 0)` and `(7..9, 6)` (`rows_out_6 = 2`) to enter the vault from `(9, 2)` without Druid petrifying Column 6 (`(6,2), (6,3), (6,4)`).
3. **Undifferentiated switch columns in flow PDBs**: `OrthoFlow5` and `RingFlow5` merged `*` crates and `#` walls on `[4..6] x [2..4]`, allowing zero Column-6 blow-off (`x0a = 0`) on horizontal `R` steps without charging Druid `c6 -> w6` petrifications or `'A'` mode switches.

## V2 Quotient Constructions and Certified Results

| Component | State Space | Forward Quotient Edges Checked | Violations | Impact on `15x7` `III-14` |
| :--- | ---: | ---: | ---: | :--- |
| `BedrockConservedSwitch3x3_15PDB` | `992,023,200` (`946 MiB`) | `4,125,601,380` | `0` | 0-1 BFS `RIGHT_BORDER_MASK` guard + `ext = inc + blk <= 9 - k_in` conservation + `need9` (`+2..+3` keys on `t = 19..33`) |
| `PetrifiedColFlow15PDB` | `909,397,320` (`867 MiB`) | `22,298,783,175` | `0` | Separates `s4, s5, c6, w6, k1L, k1R, k2V, r2, r3` + `(d, adj)` + pigeonhole Column-6 blow-off (`h(s0): 27 -> 29`) |
| Concrete Walk + `Packed24` Audit | `1,000,000` bijective states | `55,000,021` concrete edges | `0` | Lossless 24-byte base-3 5-cell/byte state packing (`sizeof(Packed24) == 24`) |
| 256-Shard 10-Thread Layered A* | `741,241,265` canonical states | `1,239,248,858` A* edges | `0` | Certified floor **`>= 42`** (`LOWER_BOUND_UNWITNESSED`), shrinking `f = 37` `17.40x` vs `main` (`117.77M -> 6.77M`) |
| `III14VaultEndgameTB` (`t = 36 -> 48`) | `147,852` (`64,296` reachable) | `845,232` | `0` | Exact `12`-key tail certified (`0` sub-48 tails from `t = 36`), **`47.56x`** A* reduction (`2,457` vs `116,848` blind BFS) |

## Layer Progression (`main` vs `V1` vs `V2`)

| Layer `f` | Certified Floor | `main` (`SwitchRow`) States | `V1` (`Switch3x3 + need9`) States | `V2` (`BedrockConserved + PetrifiedColFlow`) States | `V2` Layer Time |
| ---: | ---: | ---: | ---: | ---: | ---: |
| `37` | `>= 38` | `117,766,951` (`82.41s`) | `38,051,059` (`2.36s`) | `6,767,349` | `0.91s` |
| `38` | `>= 39` | cap exceeded | `111,356,411` (`6.68s`) | `21,028,585` | `1.92s` |
| `39` | `>= 40` | cap exceeded | `321,478,457` (`20.44s`) | `66,421,410` | `4.99s` |
| `40` | `>= 41` | cap exceeded | cap exceeded | `200,419,558` | `13.91s` |
| `41` | `>= 42` | cap exceeded | cap exceeded | `612,628,443` | `88.28s` |

## Reproduce Verification

```sh
python3 -m soko_mcp.integrity
python3 -O -B -m experiments.landmark_dual_bounds_v2.replay_v2
python3 -O -B -m unittest tests/test_landmark_dual_bounds_v2.py -v
```

## What Is Not Proved

- `LOWER_BOUND_UNWITNESSED` (`>= 42`) proves no winning route of length `<= 41` exists on canonical `15x7` Room 14 (`board_sha256_lf = 300563ca68370b85e44b73f0361320bc79948849f59897a3dd0b5cc470bf351c`). Closing `f = 42, 43` (`>= 44`) at the observed `3.05x` per-layer branching requires ~`5.6B` states (`~140 GiB` RAM or external-memory bucketed A*) unless `t = 18..25` outer-column (`x = 0..2`) flow is coupled directly with `st9`.
- The `12`-key endgame search from `t = 36` proves no `< 12` completion exists from `R48`'s `t = 36` state (`47.56x` speedup over blind BFS) and discovers an alternate `48`-key route (`48019692d1b5491c`), which does not rule out `< 48` routes diverging before `t = 36`.
