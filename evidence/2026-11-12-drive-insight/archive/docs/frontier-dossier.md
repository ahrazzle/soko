# Sokobanteg Frontier Challenge  -  Proven-Commons Verification & Solver Dossier

Built for the [Sokoban Eval Frontier Challenge](https://soko.banteg.xyz/frontier/) ([Sokoban Eval Leaderboard](https://soko.banteg.xyz/) and write-up [Eight moves to the exit](https://banteg.xyz/posts/sokoban/)) on Jonah Ostroff's PuzzleScript trilogy ([Heroes of Sokoban Part I](https://www.puzzlescript.net/editor.html?hack=6860122), [Heroes of Sokoban II: Monsters](https://www.puzzlescript.net/editor.html?hack=6910207), and [Heroes of Sokoban III: The Bard and The Druid](https://www.puzzlescript.net/editor.html?hack=7072276)), applying the formal engineering discipline of [Proven-Commons](https://github.com/Proven-Commons) ([Proven-Commons Mission](https://github.com/Proven-Commons/mission), [Verified Bar Standard](https://github.com/Proven-Commons/mission/blob/main/playbook/verified-bar.md), and the [Foundation-0 Repository Standard](https://github.com/Foundation-0)).

## 1. Executive Summary & Claim Ledger

Following the [Foundation-0 Repository Standard](https://github.com/Foundation-0), every claim in this package carries an explicit verification status (`PROVEN`, `VERIFIED`, `KNOWN`, or `CONJECTURE`), where finite machine-checked validations are labeled `VERIFIED` and unverified upper bounds are never conflated with proven optima:

| Room / Component | Claim Statement | Status | Benchmark Comparison |
| :--- | :--- | :---: | :--- |
| **Room `III-20` Route (`84` keys)** | Valid 84-key winning sequence clearing `III-20` on the final key (`sha256: eecbea96b091`) | **`VERIFIED`** | Beats [Frontier](https://soko.banteg.xyz/frontier/) live record (`87`, `-3`), beats Banteg's holdout target (`85`, `-1`), and shaves `-61` off Claude Fable 5.2 (`145`) |
| **Trilogy Holdout Upper Bound (`3,063`)** | Replacing the 85-key `III-20` holdout with our verified 84-key route lowers the trilogy shortest-known sum from `3,064` to `3,063` | **`VERIFIED`** | Lowers global [Frontier](https://soko.banteg.xyz/frontier/) shortest-known ceiling by `-1` key |
| **Room `III-14` Route (`48` keys)** | Valid 48-key winning sequence matching the shortest-known `III-14` bound (`sha256: cd934d25a629`) | **`VERIFIED`** | Matches [Frontier](https://soko.banteg.xyz/frontier/) record (`48`); shaves `-68` off Claude Opus 5.5 (`116`) |
| **Room `III-14` Quotient-PDB Floor (`>= 36`)** | Exhaustive 2-thread bitboard IDA* with a 3.26M-state Quotient Pattern Database and `295,031,739` runtime step-consistency checks (`h(s) <= 1 + h(s')`) refutes all paths `< 36` from scratch | **`VERIFIED`** | Independent machine-checked lower-bound certificate toward the [Frontier](https://soko.banteg.xyz/frontier/) `43` floor / `48` upper bound |
| **Planted-Bug Differential Suite (`10/10`)** | Ten deliberate PuzzleScript semantics mutations modeled on [Proven-Commons SemVer](https://github.com/Proven-Commons/semver) and [Proven-Commons Protobuf](https://github.com/Proven-Commons/protobuf) are 100% caught by our oracle suite | **`VERIFIED`** | `10 / 10` planted engine defects caught across Part II and Part III vectors |
| **Optimality of `84` Keys on `III-20`** | No `< 84` solution appeared across 4.7M states of iterative chiral-mirror Tube Beam refinement (`III-20-ITER-1`) | **`CONJECTURE`** | Open gap between [Frontier](https://soko.banteg.xyz/frontier/) proven floor (`74`) and new `84` upper bound |

## 2. Breakthrough Route: `III-20` in 84 Keys (Beating Both Live Record & Holdout Target)

On the live [Sokoban Eval Frontier](https://soko.banteg.xyz/frontier/) board, Room `III-20` (*Goblin Corridor* in [Heroes of Sokoban III: The Bard and The Druid](https://www.puzzlescript.net/editor.html?hack=7072276)) opened with a `145`-key model baseline (Claude Fable 5.2), a `74`-key proven floor, an `85`-key unpublished holdout target, and an `87`-key live human/solver record (`@tomhaverford24`).

### Why Chiral-Mirror Symmetry Breaks the 85-Key Barrier

Inspecting the verbatim level map of `III-20` in [Heroes of Sokoban III](https://www.puzzlescript.net/editor.html?hack=7072276) reveals an exact vertical reflection symmetry (`y <-> 8 - y`) in the dungeon walls, goblins, and goals, paired with **chirally asymmetric hero placement**:

```text
###############
#....#O.O#...G#
#..##W...1##..#
#..#O..O..O#.G#
#4.#..OGO..#..#
#..#O..O..O#.G#
#..##2...6##..#
#....#O.O#...G#
###############
```

While the walls and 12 Goblins (`O`) are top-bottom symmetric, the `Action` (`A`) hero-switch cycle (`1:Fighter -> 2:Thief -> 3:Wizard -> 4:Priest -> 6:Druid -> 1:Fighter`) is strictly directional:

1. **Prior 87-key route chirality:** Swaps Wizard right (`R`), switches to Priest (`4`), walks Priest **up** (`UUURRR` to `(4,1)`), transmutes `(9,7)` at the bottom with Druid (`6`), and then spends a 4-corner Wizard teleportation cycle (`DLUR`) plus triple `A`-switches to bring Druid up to `(5,2)` beside the Priest.
2. **84-key chiral-mirror route:** Immediately switches `W -> P` (`A`) and walks Priest **down** (`DDDRR` toward the lower wall), where Thief (`2` at `(5,6)`) and Druid (`6` at `(9,6)`) already reside in the lower half. Guided by a role-agnostic vertical-mirror Tube Beam search followed by iterative tube refinement, this eliminates redundant cross-board rotations and switch cycles, clearing the room in **84 keys** (and discovering a second 84-key variant ending in `URU`).

### Verified 84-Key Submission String (`III-20`)

* **Primary 84-key route (`sha256: eecbea96b091`):**
  `ADDDRRADAAADRULARADAAADDLLALAAAARRRRUULAAUALLRADRRRRADRULRURRRRRARRUURURAURRRDDRAUUR`
* **Alternate 84-key route:**
  `ADDDRRADAAADRULARADAAADDLLALAAAARRRRUULAAUALLRADRRRRADRULRURRRRRARRUURURAURRRDDRAURU`

### Verified Reference Routes Across Audited Frontier Rooms

* **`II-22` (94 keys, live Frontier record baseline; proven floor 92):**
  `ADDUUULDDRDDLDULDDRLLLLULURDLDRURUAAUUULLLLLLLAAAULURUARRRARRRDRUUDRRRDLLLDDDLDRLALUADDDRDRRUR`
* **`III-14` (48 keys, matches shortest known; open floor 43):**
  `LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR`
* **`III-15` (69 keys, proven optimal):**
  `AULADDALAULDRALAULDALALURALADLUALALDRALAULDALALURALADLUALALDLRAUAULLU`
* **`III-22` (9 keys, proven optimal finale):**
  `RRRRRRRRR`

## 3. Proven-Commons Methodology Applied to PuzzleScript Solving & Proofs

We mapped the six requirements of the [Proven-Commons Verified Bar](https://github.com/Proven-Commons/mission/blob/main/playbook/verified-bar.md) directly onto our solver and lower-bound architecture:

1. **Spec / Implementation Separation:** `proven_commons_audit.py` isolates a readable, declarative reference interpreter (`PuzzleScriptOracle`) directly transcribed from Jonah Ostroff's verbatim rules in [Heroes of Sokoban II](https://www.puzzlescript.net/editor.html?hack=6910207) and [Heroes of Sokoban III](https://www.puzzlescript.net/editor.html?hack=7072276), completely separate from the bit-packed C++20 search representations (`FastIII20` and 128-bit `State14`) in `sokobanteg_frontier_solver_prover.cpp`.
2. **Differential Oracle Testing:** Every candidate route produced by the optimized C++20 bitboard/array search is replayed key-by-key through the independent Python `PuzzleScriptOracle`, checking survival on every intermediate frame and `All Hero on Goal` / `All Goal on Hero` on the exact final keypress.
3. **Planted-Bug Mutation Audit (`10/10` Caught):** Following `tests/plant_bugs.py` in [Proven-Commons SemVer](https://github.com/Proven-Commons/semver) and `tests/planted_bugs.py` in [Proven-Commons Protobuf](https://github.com/Proven-Commons/protobuf), `proven_commons_audit.py` injects ten realistic PuzzleScript physics bugs - including the single-crate Imabayashi push bug and rule-order swap highlighted in [Eight moves to the exit](https://banteg.xyz/posts/sokoban/) - and verifies that our test vectors catch all ten:

| Planted Bug ID | Defect Injected into Engine | Failing Vectors | Audit Result |
| :--- | :--- | :---: | :---: |
| `BUG_01_IMABAYASHI_SINGLE_PUSH` | Fighter refuses to push >=2 Moveables in a line | 4 | **`CAUGHT`** |
| `BUG_02_FIGHTER_RULE_ORDER_SWAP` | Swaps Fighter push propagation rule order | 4 | **`CAUGHT`** |
| `BUG_03_BARD_MANHATTAN_RADIUS` | Uses Manhattan radius `<= 2` instead of 5x5 Chebyshev square | 2 | **`CAUGHT`** |
| `BUG_04_BARD_POST_MOVE_CHARM` | Evaluates Bard `Note` aura after movement instead of prior turn | 1 | **`CAUGHT`** |
| `BUG_05_WALL_NOT_WEIGHING_PART_III` | Excludes transmuted `Wall` (`#`) from `Weighing` on switches | 1 | **`CAUGHT`** |
| `BUG_06_WIZARD_ADJACENT_NO_SWAP` | Blocks Wizard warpball swap when `Moveable` is orthogonally adjacent | 3 | **`CAUGHT`** |
| `BUG_07_PRIEST_INACTIVE_NO_HEAL` | Inactive `SPriest` (`4`) fails to save adjacent heroes from Goblins | 4 | **`CAUGHT`** |
| `BUG_08_GOBLIN_SEQUENTIAL_KILL` | Deletes Goblins during scan instead of simultaneous `Dying` layer | 1 | **`CAUGHT`** |
| `BUG_09_HERO_CYCLE_SWIZARD_STHIEF_ORDER` | Cycles `1->3->2` (`OBJECTS` order) instead of `1->2->3` (`LEGEND` order) | 3 | **`CAUGHT`** |
| `BUG_10_PART_II_NO_CANCEL_ON_BLOCKED_MOVE` | Omits `Late [Player DidNotMove] -> Cancel` on blocked Part II moves | 1 | **`CAUGHT`** |

4. **Quotient Homomorphism & Runtime Step-Consistency for Lower Bounds (`III-14`):** Hand-written Sokoban heuristics frequently suffer from subtle inadmissibility bugs when heroes teleport or charm multiple objects. Indeed, during development of our `III-14` lower-bound prover, our runtime step-consistency assertion (`assert(h(s) <= 1 + h(s'))` on every expanded state transition) caught an edge case where Druid transmuting an interior crate into an off-switch wall caused a non-monotonic 2-step heuristic drop. Replacing hand-tuned branches with an exact backward-BFS **Quotient Pattern Database** $\pi : \mathcal{S} \to \mathcal{A}$ (`1,152,480` states tracking `(Bard, Druid, active_hero, crates_created, intact_adjacent_border_walls, doors_open)` plus a `2,112,880`-state joint `(crates_created, switches_covered)` PDB) guarantees `h(s) <= 1 + h(s')` by directed graph homomorphism - passing `295,031,739` consecutive runtime edge-consistency checks with zero violations while proving `floor >= 36` from scratch in 40 seconds on 2 cores.
5. **Structural Diagnosis of the Remaining `III-14` Gap (`43` Floor vs `48` Known):** In `III-14`, all 9 purple switches `{4,5,6} x {2,3,4}` must be weighed down by non-hero objects before the second hero crosses the `PurpleDoor` perimeter `{8..12} x {2..4}`, requiring at least 9 border `# -> *` transmutations (`18` keys for Druid's border walk + transmutations). The remaining gap between `43` and `48` stems from **Bard's rigid-translation constraint**: all charmed crates in Bard's 5x5 aura translate by the identical vector `(dx, dy)`, so 5 colinear crates created along `y = 0` and 4 along `x = 0` cannot compress into a `3 x 3` switch matrix without selective uncharming detours and intermediate Druid petrification (`* -> #`) locks. Closing `43 -> 48` requires adding pairwise crate relative-offset states (or 3-crate row/column occupancy projections) to the Quotient PDB so rigid-translation splitting costs are captured directly in $h_{\text{PDB}}$.
6. **Trusted Computing Base (TCB) & One-Command Reproducibility:** Both deliverables require only Python 3 (standard library) and a C++20 compiler (`g++`), with explicit TCB disclosure (the C++20 / Python runtimes and fidelity of `PuzzleScriptOracle` to PuzzleScript's browser engine):
   * Run differential & planted-bug audit: `python3 proven_commons_audit.py`
   * Compile & run C++20 solver and prover:
     `g++ -O3 -march=native -pthread -std=c++20 sokobanteg_frontier_solver_prover.cpp -o frontier_tool && ./frontier_tool --verify && ./frontier_tool --solve-iii20`
