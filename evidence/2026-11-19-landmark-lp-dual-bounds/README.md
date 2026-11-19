# Frontier Landmark LP Dual Lower Bounds, Consistency Repair, and Search (`2026-11-19`)

This directory records the artifacts, exact rational certificates, and reproducible logs for Track 1 and Track 2 on `III-14`, `III-20`, and `III-21`:

- **Track 1a (Original Part III outer-border harvest audit)**: Confirms in Jonah Ostroff's pinned Part III build (`html_sha256 = 380d343ad35a8f8caf6863341172a7771d0d28ced2824a7a3085990614562105`, `puzzlescript_source_sha256 = f66ceb8f8a2c23a3cb270bad62cdf194e47479772cab94f154ed26f0ff7c20e0`) that `#` maps solely to `Wall` (line 262) and `[> Druid | Wall] -> [Druid | Crate Sfx8]` (line 334) legally harvests outer border walls in Room 14.
- **Track 1b (1-step consistency repair and 1-Lipschitz LP projection)**: Reproduces the `12 -> 10` Druid `(0,3) -> (1,3)` wall-to-crate drop in dual oracles and certifies both repairs (`11 -> 10` pre-funded potential and `11 -> 10` exact rational 1-Lipschitz quotient LP projection with Farkas witness chains, `2119 = 2119`, `0` violations).
- **Track 1c (`15x7` `III-14` Landmark + Quotient Floor Prover)**: Combines `Switch3x3_15PDB` (`3^9 = 19,683` switch states) + `need9` harvest deficit + `OrthoFlow5` + `RingFlow5` + `HarvestAdj`, checks `4,699,457,514` quotient edges and `55,000,021` walk edges (`0` violations), and certifies `>= 40` (`LOWER_BOUND_UNWITNESSED`, `663,700,313` states).
- **Track 2a (`III-21` and `III-20` exact rational assignment and operator-counting bounds)**: Ranks all `720` goal bijections on `III-21` (`solo_min = 60`, witness `= 86`) and `120` on `III-20` (`solo_min = 39`, witness `= 43`), and certifies an exact `Fraction` operator-counting bound (`III-21` root `= 21`, `0` violations across `826` states).
- **Track 2b (`III-21` retrograde endgame tablebase)**: Builds `III21EndgameQuotientTB` (`259,584` states, `14,924,148` quotient edges, `0` violations), checks all `317` route states, and verifies `10`-key bidirectional endgame A* from `t = 306` (`12,343` vs `40,545` expansions, `3.28x` reduction).
- **Track 2c (`15x7` `III-14` controlled 2-arm NRPA experiment)**: Runs `383,328` deterministic-seed Level-3 NRPA rollouts (`seed = 20261119`). Primitive NRPA finds `0/6` wins (`TESTED`), while unseeded Landmark-Macro NRPA finds a `70`-key winning route (`traj_fnv64 = b80a2b184a306a76`, `VERIFIED`) and `0/12` routes `<= 47`.

## 1. Summary Table of Certified Results

| Component | Target Room | Epistemic Tier | Certified Value | Checked Scale | Violations |
| :--- | :--- | :--- | :--- | ---: | ---: |
| Original border-wall audit | `III-14-15x7` | `VERIFIED` | Legal and required (`>= 9` border harvests) | `651` source lines + `2` 48-key witnesses | `0` |
| Pre-funded & 1-Lipschitz LP repair | `III-14-15x7` | `VERIFIED` | `12 -> 10` repaired to `11 -> 10` (`2119 = 2119`) | `164` ball states, `379` edges | `0` |
| Quotient forward-edge proof (`4` PDBs) | `III-14-15x7` | `VERIFIED` | `sw9`, `ha`, `rf5`, `o5` globally 1-Lipschitz | `4,699,457,514` forward quotient edges | `0` |
| Concrete random-walk edge audit | `III-14-15x7` | `VERIFIED` | `eval_h(s) - eval_h(s') <= 1` (`16 -> 16` at counterexample) | `55,000,021` concrete edges | `0` |
| Collision-free 256-shard layered A* | `III-14-15x7` | `LOWER_BOUND_UNWITNESSED` | Certified floor `>= 40` (`f = 39` completed in `20.44s`) | `663,700,313` states, `1,129,623,605` edges | `0` |
| Exact `Fraction` assignment & OC dual | `III-21`, `III-20` | `VERIFIED` | `III-21` root `21` (`720` bijections), `III-20` root `3` (`120`) | `826` states, `911` edges | `0` |
| Retrograde endgame tablebase & A* | `III-21` | `VERIFIED` | `10`-key suffix exact (`12,343` vs `40,545` expansions) | `14,924,148` quotient edges, `317` route states | `0` |
| Controlled 2-arm Level-3 NRPA | `III-14-15x7` | `VERIFIED` | Unseeded `70`-key win found (`0` wins `<= 47`) | `383,328` rollouts across `36` restarts | `0` |

## 2. Completed `15x7` `III-14` Layered A* Ledger (`f = 27..39`)

| Completed `f` | Certified Floor | Cumulative Expanded | Cumulative Unique Canonical States | Cumulative Concrete Edges Checked | Hash Collisions Prevented | Elapsed A* Time (`s`) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `27` | `28` | `5` | `22` | `25` | `0` | `0.000` |
| `28` | `29` | `78` | `283` | `386` | `0` | `0.005` |
| `29` | `30` | `570` | `2,020` | `2,761` | `0` | `0.009` |
| `30` | `31` | `2,607` | `8,944` | `12,615` | `0` | `0.015` |
| `31` | `32` | `11,513` | `38,611` | `55,687` | `0` | `0.025` |
| `32` | `33` | `38,723` | `125,447` | `186,539` | `44` | `0.041` |
| `33` | `34` | `136,961` | `428,987` | `655,927` | `435` | `0.072` |
| `34` | `35` | `433,143` | `1,335,999` | `2,063,870` | `4,383` | `0.141` |
| `35` | `36` | `1,380,190` | `4,178,236` | `6,544,241` | `25,088` | `0.336` |
| `36` | `37` | `4,226,498` | `12,643,235` | `19,959,902` | `136,468` | `0.861` |
| `37` | `38` | `12,897,385` | `38,051,059` | `60,768,444` | `767,208` | `2.362` |
| `38` | `39` | `38,294,993` | `111,356,411` | `179,795,871` | `5,122,173` | `6.682` |
| `39` | `40` | `112,337,002` | `321,478,457` | `525,838,149` | `40,466,546` | `20.436` |

Inside `f = 40`, the run reached `242,199,597` expanded states and `663,700,313` unique canonical 30-byte states (`1,129,623,605` runtime-checked concrete edges, `0` Bellman violations) before hitting the per-shard capacity cap (`stop_reason = state_cap_during_layer_40`).

Relative to the prior `f = 37` (`>= 38`) baseline (`117,766,951` states in `82.41s`), `Switch3x3_15PDB + need9 + OrthoFlow5_15PDB` shrinks `f = 37` by `3.10x` to `38,051,059` states (`2.36s`) and upgrades `HarvestAdj15PDB` and `RingFlow5_15PDB` from `ARGUED` to `VERIFIED` via exhaustive forward quotient-edge checks.

## 3. Machine-Checked Lean 4.35.0 Theorem Bindings and Collaborator Transfers

Every mathematical reduction in `experiments/landmark_dual_bounds/` binds to a machine-checked domain-general theorem in `Proven-Commons/mcproof` (`Mcproof.TransitionBounds` / `Mcproof.Spec`, verified across `6/6` Lean kernels with zero axioms beyond `propext`, `Classical.choice`, `Quot.sound`):

- `Switch3x3_15PDB`, `HarvestAdj15PDB`, `RingFlow5_15PDB`, `OrthoFlow5_15PDB`, `III21EndgameQuotientTB` -> `Mcproof.Spec.quotientHeuristic_step_consistent` and `Mcproof.Spec.quotientHeuristic_admissible`.
- `lookup_plus_harvest` (`sw9 + max(0, 9 - m_act)`) -> `Mcproof.Spec.zeroSelfLoop_deficit_composition` and `Mcproof.Spec.conservation_harvest_potential_repair` (matching the zero cross-block leakage criterion from `rohanarun/yang-mills-mass-gap-auto-research` `T03-auxiliary-resolvent-gap`).
- `prefunded_transmutation_potential` -> `Mcproof.Spec.prefundedHeuristic_step_consistent` and `Mcproof.Spec.prefundedVal_bounded_drop_witness`.
- `evaluate_operator_counting_bound` and `ceil_fraction` -> `Mcproof.Spec.operatorCounting_dual_div_admissible` and `Mcproof.Spec.ceilDiv_step_consistent_and_admissible`.
- `cycle_switch_tax` (`(target + k - active) % k`) -> `Mcproof.Spec.cyclicSwitchTax_triangle` and `Mcproof.Spec.cyclicSwitchDist_metric_and_witness`.
- `load_strict_rational_json` and `parse_strict_fraction` -> incorporates `CrocSwap/integer-mult-bounds` (`verify_rational_lp.py`) parse-time `float`, `bool`, and duplicate-key rejection.
- `quotient_macro_code` in `iii14_nrpa_search.cpp` -> incorporates `eumemic/exoplanets` sparse quotient-baseline keying to prevent alias self-suppression across commuting border harvests.

## 4. Reproduction Commands

```sh
# 1. Decoupled verification of all committed receipts and must_fail controls:
python3 -O -B -m experiments.landmark_dual_bounds.replay_all

# 2. Deterministic unit and regression suite (zero wall-clock assertions):
python3 -O -B -m unittest tests/test_landmark_lp_dual_bounds.py -v

# 3. Full 665.6M-state C++20 15x7 III-14 landmark prover run (~76s on 10-core 64 GiB arm64):
clang++ -O3 -std=c++20 -pthread experiments/landmark_dual_bounds/prove_iii14_15x7_landmark_floor.cpp -o prove_iii14_landmark
./prove_iii14_landmark --walk-edges 55000000 --max-states 665600000 --time-limit 180 \
  --source-path experiments/landmark_dual_bounds/prove_iii14_15x7_landmark_floor.cpp \
  --json-out evidence/2026-11-19-landmark-lp-dual-bounds/iii14_15x7_landmark_floor_receipt.json
```

## 5. What Is Not Proved

- **`LOWER_BOUND_UNWITNESSED` (`>= 40` on `15x7` `III-14`)**: Proves no winning route of length `<= 39` exists under exact Part III PuzzleScript crush semantics on the canonical `15x7` Room 14 grid. It does not close the remaining gap between `40` and `48` (`SJanuskas` record) or supersede the external Frontier page's reported floor (`44`).
- **Unseeded NRPA (`C1`)**: Landmark-Macro NRPA discovers a verified `70`-key winning route from scratch without seed routes, whereas `0` routes of length `<= 48` or `<= 47` were found within `383,328` rollouts. Absence of a `<= 47` rollout in NRPA is an empirical search result (`TESTED`), not an impossibility proof.
- **`III-21` Operator-Counting Root Bound (`21`)**: Proves a globally 1-step-consistent exact rational lower bound across all `6` Part III hero mechanics (including Bard `5x5` carries and Wizard collinear swaps) and quantifies why individual hero walk sums (`60..86`) are far below `316`, leaving multi-phase goblin-shield and crate-staging coupling between `21` and `316` open for phase-level synthesis.
