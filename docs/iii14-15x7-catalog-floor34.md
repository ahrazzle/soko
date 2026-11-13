# Exact Full-State Lower Bound (`LOWER_BOUND_UNWITNESSED = 34`) on Catalog `15x7` `III-14`
*Authored 2026-11-12 by `mithrax` (`mithrax-exo`, Gemini seat) — establishing a collision-free full-state lower bound on the canonical `15x7` `III-14` catalog board (`board_sha256 = 300563ca68370b85e44b73f0361320bc79948849f59897a3dd0b5cc470bf351c`), strictly under `v0.4.0` `LOWER_BOUND_UNWITNESSED` semantics (not `VERIFIED`, as the shortest known witness remains length `48`).*

## 1. Context & Provenance Distinction

## 3. Algebraically Proven & Runtime-Checked 1-Step Consistent Heuristic (`h(s_0) = 24`)

Whenever at least one hero lies outside the closed-door inner region `[8..12] x [2..4]` (`INNER_MASK`), any valid trajectory must pass through a frame where both heroes lie in `INNER_MASK` and `p_open == 1` (requiring all 9 switches `[4..6] x [2..4]` to be occupied simultaneously by 9 distinct elements of `all40 = crates | walls`). By 1D Hardy-Littlewood-Polya uncrossing, matching sorted 9-element sliding windows of `xs` against `(4,4,4,5,5,5,6,6,6)` and `ys` against `(2,2,2,3,3,3,4,4,4)` minimizes directional switch-coverage deficits over all `9!` permutations:

1. **Joint Hero + Switch-Object Bound (`bound1`):** Takes the minimum of (a) `m >= max(1, 9 - |pool|)` off-switch harvests plus `'A'` parity (`+2` if `act_bard`, `+1` if `!act_bard`) plus joint `(Bard, Druid, all40)` cardinal directional maxima, and (b) when `|pool| >= 9` (`pool = crates | (walls & PSW)`), `0` harvests plus `1` `'A'` (if `!act_bard` and `unweighed_sw > 0`) plus joint `(Bard, Druid, pool)` cardinal maxima.
2. **Action-Bucket Partition Bound (`bound2`):** Since only active-Bard directional steps ever move `bard` or `crates`, `bard + switch-object` directional deficits (`bard_moves_pool` / `bard_moves_all40`, guarded by `min(bard_moves_pool, 3 + bard_moves_all40)` when `act_bard && min_m == 0`) are time-disjoint from non-Bard steps (`'A'` switches, `k` harvests, and `ceil(max(0, k - a_cur) / max_deg)` Druid solo walks where `max_deg = max_v |NEIGH4[v] & off_walls|`).
3. **Unconditional Per-Edge Consistency Monitor:** Every expanded legal transition checks `h(u) - h(v) <= 1` at runtime (`exit 2` on any violation). Across **`129,638,499` expanded edges**, **zero** step inconsistencies occurred.

## 4. Layer-by-Layer Execution Ledger (`15x7` Catalog `III-14`)

| Completed `f`-Layer | Certified `15x7` Floor (`LOWER_BOUND_UNWITNESSED`) | Cumulative Unique 256-Bit States | Linear-Probe Collisions | Cumulative Edge Checks | Elapsed Wall Time (s) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| `24` | `25` | `49` | `0` | `65` | `0.0001` |
| `25` | `26` | `254` | `0` | `357` | `0.0004` |
| `26` | `27` | `1,723` | `0` | `2,530` | `0.0016` |
| `27` | `28` | `10,911` | `0` | `16,757` | `0.0096` |
| `28` | `29` | `58,998` | `7` | `94,769` | `0.0523` |
| `29` | `30` | `275,272` | `343` | `451,950` | `0.2470` |
| `30` | `31` | `1,304,612` | `8,384` | `2,150,974` | `1.2215` |
| `31` | `32` | `5,130,560` | `135,298` | `8,635,505` | `4.9554` |
| `32` | `33` | `19,841,617` | `2,298,011` | `33,836,480` | `22.6715` |
| **`33`** | **`34`** | **`67,752,828`** | **`44,744,875`** | **`118,037,280`** | **`87.9881`** |

*(Stopped cleanly on budget during `f = 34` at `95.1275s` with `71,084,822` unique states, `51,019,835` probe collisions, `129,638,499` edge checks, and `0` step inconsistencies.)*

## 2. Lossless 256-Bit State Representation & Bit-Exact Mechanics

- **Exact 32-Byte (`256-bit`) State Key:** Stores all `105` wall bits (`w0`, `w1[0..40]`), all `105` crate bits (`c0`, `c1[0..40]`), `7`-bit `bard` index, `7`-bit `druid` index, `act_bard` flag, and `p_open` flag (with cached `h(u)` and `g + 1` in `c1[48..63]`). Open-addressing linear probing compares full `226`-bit game states—zero lossy hash truncation—and aborts hard at `80%` load (`107,374,182` of `134,217,728` slots).
- **Mechanics Calibration (`soko_mcp/flat_oracle.py`):** Implements the exact fixed-point `while progressed:` resolution of memoryless $5\times 5$ `notes_mask` moveables with active Bard (`[crate][Bard][empty]` and `[Bard][crate][empty]` both advance on the same step), Druid `# <-> *` morphs, and Phase-3 all-weighed switch / door-crush rules. Verified bit-for-bit against three 48-step winning routes on the `15x7` catalog board (`LLULULUULRRURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR` and its `RURR` / `URURR` harvest-order variants) with `h(s_48) = 0` and `h(s_t) <= 48 - t` at every frame.
- 

Per PR #25 (`bb4dce5`), PR #31 (`c050834`), and PR #33, the existing `>= 34` prover bound applied strictly to the legacy **`14x7` fixture**, while an exact full-state search bound on the **`15x7` catalog board** (`###############` / `#.5.}}}.]]]]].#` / `#...}}}.]G.G].#` / `#.D.}}}.]]]]].#`) remained unestablished beyond the `R0` aura-free relaxation (`>= 28`).
