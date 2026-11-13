# III-14 Transport-Relaxation Rungs, Non-Stuttering CNF, and Exact-State Lower-Bound Ledger

**Correction (2026-11-12):** Proof's ruling in [review 5884260825](https://github.com/ahrazzle/soko/pull/25#pullrequestreview-5884260825) is that the completed layer is a sound lower bound `>= 34` on the 14x7 fixture only. The earlier `>= 35` claim is withdrawn, and 15x7 is not established.

This evidence ledger records the complete empirical, combinatorial, and formal-verification computations linking the nine-token transport relaxation (`experiments/transport_relaxation/`) to concrete Part III mechanics on Room `III-14` (`15x7`, pinned Part III source SHA-256 `f66ceb8f8a2c23a3cb270bad62cdf194e47479772cab94f154ed26f0ff7c20e0`) and companion Frontier benchmarks (`III-20`, `II-22`, `III-15`).

## 1. Counterfactual Rung Hierarchy on `III-14` (`H = 28 -> 30 -> 33 -> 48`)

| Rung | Constraint System | Minimum Horizon / Outcome | Key Diagnostic Metric | Epistemic Status |
| :--- | :--- | :--- | :--- | :--- |
| `R0` | Exact aura-free harvest + transport super-relaxation | `H >= 28` (`UNSAT` for `H <= 27`) | `965,669` exact A* states + `4,000,047` exact DFS nodes at `H = 28, 29` (`0` witnesses) | author's claim (no independent check yet) |
| `R1` | Base 9-token relaxation (`allocation.allocate` 40x9 Hall matching) | `SAT` at `H = 30` (`t_L = 29`) | Witness `LLULULULURURURURUARRRRDDRDRUUR` (`9/9` Hall matching; 4 token pairs stack) | witness checked |
| `R2` | Time-expanded unit-capacity 9-flow (hero exclusion only, `flow_allocation.py`) | Refutes `r30` (`7/9`); kills `685 / 685` Hall-stacking schedules | Compresses via sliding-window LNS to `H = 33` (`9/9` flow) | checked (SAT/UNSAT as stated) |
| `R3` | Time-expanded unit-capacity 9-flow + pre-harvest intact border `#` exclusion (`intact_flow_allocation.py`) | Tightens `r30` min-cut to `5/9`; `SAT` at `H = 33` (`t_L = 32`) | Witness `LLULULULRURURURURUAUDRRDUDDRRRRUR` (`9/9` disjoint flow; `verify_9flow_witness == True`) | witness checked |
| `R4` | `R3` + Freeze-State (`is_wall`) + 40-Atom Conservation + **Exact Unblocked-Crate Non-Stuttering CNF** (`nonstuttering_cnf.py`) | Refutes **all** `9/9`-flow schedules of `r33` (`UNSAT`); accepts concrete `r48` (`SAT`, `0 / 11,892` falsified clauses) | `0` violations across `250,000` reachable concrete states, `439,038` transitions, and `255,924` Bard crate stutters | checked (SAT/UNSAT as stated) |

### 1.1 Explicit `H = 30` Hall-Matching Witness (`LLULULULURURURURUARRRRDDRDRUUR`, `t_L = 29`)

At `t = 29`, `bard = (8, 3)` and `druid = (10, 3)`, stepping `R` at `t = 30` onto goals `(9, 3)` and `(11, 3)` (first goal-pair frame). While `40 x 9` bipartite matching succeeds (`9/9`), unit-capacity 9-flow exposes both cell stacking and traversal through the unharvested boundary wall `(6, 0)` (`7/9` hero-only min-cut; `5/9` intact-border + hero min-cut):

| Switch Index | Landmark Switch | Matched Border Origin | Position at `t = 22` | Position at `t = 24` | Space-Time / Intact-Wall Conflict |
| :---: | :---: | :---: | :---: | :---: | :--- |
| `0` | `(4, 2)` | `(1, 0)` | `(4, 0)` | `(4, 2)` | Traverses intact border `(2,0)..(4,0)` |
| `1` | `(5, 2)` | `(5, 0)` | `(5, 0)` | `(5, 2)` | Stacks with `(3, 0)` at `t = 22, 24` |
| `2` | `(6, 2)` | `(4, 0)` | `(6, 0)` | `(6, 2)` | Enters unharvested border `(6, 0)` & stacks with `(2, 0)` |
| `3` | `(4, 3)` | `(0, 3)` | `(4, 3)` | `(4, 3)` | Stacks with `(0, 1)` at `t = 24` |
| `4` | `(5, 3)` | `(3, 0)` | `(5, 0)` | `(5, 2)` | Stacks with `(5, 0)` at `t = 22, 24` |
| `5` | `(6, 3)` | `(2, 0)` | `(6, 0)` | `(6, 2)` | Enters unharvested border `(6, 0)` & stacks with `(4, 0)` |
| `6` | `(4, 4)` | `(0, 4)` | `(4, 4)` | `(4, 4)` | Stacks with `(0, 2)` at `t = 24` |
| `7` | `(5, 4)` | `(0, 2)` | `(4, 2)` | `(4, 4)` | Stacks with `(0, 4)` at `t = 24` |
| `8` | `(6, 4)` | `(0, 1)` | `(4, 1)` | `(4, 3)` | Stacks with `(0, 3)` at `t = 24` |

### 1.2 Disjoint-9-Flow Sliding-Window LNS Compression Chain (`48 -> 33`)

Starting from the 48-key concrete incumbent `LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR` (`t_L = 47`, `9/9` intact-border flow), exact window replacement under the `9/9` disjoint-flow oracle discovers six successive shortcuts down to `H = 33`:

1. `48 -> 45` (window `[20, 28]`, `t_L = 44`): `LLULULULRURURURURUAUDRRDDRRDLRAULDLDRARURDUUR`
2. `45 -> 42` (window `[27, 35]`, `t_L = 41`): `LLULULULRURURURURUAUDRRDDRRUDDAUDRARURDUUR`
3. `42 -> 39` (window `[27, 35]`, `t_L = 38`): `LLULULULRURURURURUAUDRRDDRRUDDLRRURDUUR`
4. `39 -> 37` (window `[24, 32]`, `t_L = 36`): `LLULULULRURURURURUAUDRRDUDDRRDRURDUUR`
5. `37 -> 35` (window `[26, 34]`, `t_L = 34`): `LLULULULRURURURURUAUDRRDUDDRRRRDUUR`
6. `35 -> 33` (window `[25, 33]`, `t_L = 32`): `LLULULULRURURURURUAUDRRDUDDRRRRUR`

Concrete Part III replay of `r33` (`LLULULULRURURURURUAUDRRDUDDRRRRUR`) diagnoses the two omitted mechanics closed by `nonstuttering_cnf.py`:
- At `t = 24 -> 25 ('U')`, Bard steps `(4, 3) -> (4, 2)` and pulls unfrozen switch crates off `{4, 5} x {2}` (`2 -> 0` weighed switches) into open floor `{4, 5} x {1}`.
- At `t = 29 -> 30 ('R')`, Bard steps `(6, 4) -> (7, 4)` and carries unpetrified column-6 crates off `{6} x {2, 3, 4}` into open floor column `x = 7`.

### 1.3 Canonical `9! -> 1` Origin-Symmetry Reduction & DIMACS CNF Metrics

Sorting the 9 tracked tokens by `BORDER_INDEX(origin_0) < ... < BORDER_INDEX(origin_8)` and enforcing switch-set surjection at `landmark_frame` removes all `9! = 362,880` label permutations without loss of generality:
- On `r48` (`H = 48`, `t_L = 47`), `compile_conditional_nonstuttering_cnf` emits `1,921` variables and `11,892` DIMACS clauses (`437` unblocked non-stuttering clauses), solved to `SAT` with `0` falsified clauses on both the projected concrete execution and standalone DPLL search.
- On `r33` (`H = 33`, `t_L = 32`), every `9/9`-flow-feasible hero schedule is proven `UNSAT` in `< 0.2s`.

## 2. Exact-State Quotient-Homomorphism & Multi-Room Prover Ledger

| Computation / Prover Kernel | Target Room(s) | Exact Verified Metrics | Source / Artifact |
| :--- | :--- | :--- | :--- |
| `PairAtomQuotientPDB` (2-atom unordered quotient homomorphism) | `III-14` | `39,719,680` quotient states; `0` step-inconsistencies (`h(s) - h(s') <= 1`) across all `48` transitions of `r48` (including mixed-block step 25) | `cpp/soko_engine.cpp`, `cpp/frontier_iii14_iii20_prover.cpp` |
| Multi-Core Exact-State Bucketed A* (`CompactNode` / `Packed14`, zero lossy TT pruning) | `III-14` | Generic 10s budget: `floor >= 32` (`1,014` live 64-bit hash collisions caught and resolved by full-state equality); 35s prover run: `floor >= 35` (withdrawn; see the correction note at the top) across `27,656,589` exact states, `110,803,961` transitions, `22,658` hash collisions prevented | `cpp/soko_engine.cpp`, `cpp/frontier_iii14_iii20_prover.cpp` |
| Matter Conservation & Column-6 Blow-Off Law | `III-14` | `popcnt(crates) + popcnt(walls)` invariant (`40` on `15x7`, `38` on `14x7`); open floor at `x = 7, y = 1..5` requires Druid `* -> #` petrification of `(6,2), (6,3), (6,4)` before Bard exits rightward | `experiments/transport_relaxation/nonstuttering_cnf.py` |
| `WizardRayGoalBound` (warpball ray + step BFS admissible floor) | `III-20`, `III-15`, `II-22` | Raises single-hero / non-pushing Wizard-room floors from `1` to `>= 8` immediately | `cpp/soko_engine.cpp` |
| Dual-Oracle Holdout-Breaking Receipt & 10/10 Mutation Gate | `III-20` | `84`-key primary (`eecbea96b091`) and alternate (`4edff1ad8c90`) routes verified across independent Python & C++20 oracles (`-1` below 85-key holdout, `-3` below prior 87-key record) | `soko_mcp/oracle.py`, `soko_mcp/flat_oracle.py` |
| `II-22` Window-16 Exact BFS + Chiral `x <-> 12-x` Tube-Beam Audit | `II-22` | Replayed 94-key trajectory cleanly; verified zero `<= 16`-step local window shortcuts along the 94-key corridor | `cpp/soko_engine.cpp` |
| `formal_synthesize_invariant` (`houdini_safety` & `deadlock_trap`) | Domain-general (`lease_epoch_fenced_v2`) | Universal inductive safety invariant synthesized and verified (`PROVEN`) across all `486` syntactic states | `soko_mcp/formal_kernel.py` |

## 3. Reproducing All Verification Checks

```sh
python3 -m unittest -v tests/test_transport_nonstuttering_9flow.py
g++ -O3 -std=c++20 experiments/transport_relaxation/verify_relaxation_rungs.cpp -o /tmp/verify_rungs && /tmp/verify_rungs
```
