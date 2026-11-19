# Plane 1 Formal Specification: Sokoban Evaluation Multi-Domain Pack (`mde:soko-eval`)

Version: `0.1.0`
Domain ID: `mde:soko-eval`
Target Zone: `soko_eval`

This Plane 1 specification defines the human-authored rules, epistemic tiers, transition invariants, and deterministic verification gates for the Sokoban Evaluation Multi-Domain Pack (`mde:soko-eval`). Every compiled Plane 2 weight adapter, retrieved context slice, and closed-loop solver trace in `mde_soko` derives strictly from this document and the locked `soko_mcp` dual-oracle checkers.

## 1. Epistemic Tiers and Evaluation Boundaries

Every claim, route, heuristic bound, or checker audit produced under `mde:soko-eval` carries one of five epistemic labels:

1. `PROVEN`: Machine-checked mathematical theorem or exhaustive search floor over an explicit, losslessly mapped state graph where every step cost and transition is verified without unproved axioms.
2. `VERIFIED`: Concrete route or deterministic checker artifact accepted by zero-shared-code dual execution (`PuzzleScriptOracle` and `FlatBitmaskOracle`) with identical per-frame state digests and passing planted-bug mutation controls.
3. `LOWER_BOUND`: Certified admissible distance floor (`h(s) <= d*(s)`) backed by an explicit quotient homomorphism, pre-funded monotone resource potential, or non-negative operator-counting dual witness, without claiming tightness unless matched by a verified route of equal length.
4. `CONJECTURE`: Heuristic estimate, bounded beam/NRPA search outcome that hit a depth or state cap, or unverified candidate route.
5. `REFUSED`: Output rejected because of invalid JSON syntax, budget exhaustion, forbidden cell imports, hero death, premature win, or oracle disagreement.

Evaluation integrity separates three distinct regimes:

- Keys-only race regime (`S0`, `S1`, `S2`): The agent sees only the ASCII room grid, room dimensions, part number, and tutorial text, and emits bare JSON key actions under explicit reply and key caps.
- Sandboxed Python notebook regime (`S3`): The agent writes room-specific Python 3 cells executed in an isolated, network-free, file-free 4.0-second process with zero imports from `soko_mcp` or external solvers.
- Unrestricted MCP research regime: Source-aware `soko_mcp` solvers and catalog baselines are research references and Tier 2 verifiers, never valid entrants in scored `S0` through `S3` evaluations.

## 2. Habit 1: One-Key Mechanics Probing Before Planning

Standard Imabayashi Sokoban assumptions fail in Jonah Ostroff's trilogy. Before committing a long key batch on a room with unfamiliar symbols or interactions, an agent operating in stateful mode (`S2`) must test uncertain mechanics with minimal reversible probes:

1. Issue a one-key or two-key `step` probe targeting the uncertain interaction (for example, testing whether Fighter pushes two crates at once, whether Wizard swaps with an orthogonally adjacent crate, or whether an inactive Priest shields an adjacent hero).
2. Compare the resulting board frame and switch/door state against the predicted transition.
3. Use `undo` (costing one reply) rather than `reset` whenever recovering from a local probe so validated prefix progress is preserved.
4. Never guess multi-turn monster or aura timing when a single probe or exact rule lookup resolves the transition deterministically.

## 3. Habit 2: Exact PuzzleScript Rule-Order Fidelity

All candidate planners and room micro-solvers must model the exact Heroes of Sokoban Parts I, II, and III transition semantics enforced by `PuzzleScriptOracle` and `FlatBitmaskOracle`:

### 3.1 Grid Symbols and Party Cycle Order

- Static floor layer: `.` empty floor, `G` goal tile, `{` yellow switch, `}` purple switch.
- Dynamic object layer: `#` wall, `*` crate, `O` goblin, `L` left-facing dragon, `R` right-facing dragon, `[` yellow door, `]` purple door, `M` monster gate.
- Active heroes: `F` Fighter (`1`), `T` Thief (`2`), `W` Wizard (`3`), `P` Priest (`4`), `B` Bard (`5`), `D` Druid (`6`). Inactive heroes are denoted `1` through `6`.
- Action key `A` cycles the active hero strictly in legend slot order `1 -> 2 -> 3 -> 4 -> 5 -> 6` (wrapping around among heroes present on the board), never in object-declaration order (`BUG_09`).
- Moveables comprise all active/inactive heroes, crates `*`, and goblins `O`.

### 3.2 Part I Hero Movement Rules

- Fighter (`F`): Pushes an arbitrary-length contiguous collinear chain of Moveables (`*`, `O`, or inactive heroes) one cell in direction `(dx, dy)` whenever the cell immediately past the chain is empty passable floor (`BUG_01`, `BUG_02`).
- Thief (`T`): Steps into an adjacent empty passable cell `(x + dx, y + dy)`. If a Moveable occupied `(x - dx, y - dy)` immediately behind `T`, that single Moveable is pulled into `(x, y)`. `T` cannot push.
- Wizard (`W`): Casts a warpball ray first along `(dx, dy)` across zero or more empty cells. If the ray hits a Moveable (`*`, `O`, or inactive hero), `W` swaps positions with that Moveable (including at distance 1, `BUG_06`) instead of stepping. Only when the ray hits a static obstacle does `W` step one cell into `(x + dx, y + dy)` if empty.
- Blocked-move cancellation (Parts I and II): If a directional input in Part I or Part II leaves the active hero unmoved and causes no swap, push, or transmutation, the entire turn cancels before Late-phase monster attacks (`BUG_10`).

### 3.3 Part II Monster, Priest, and Gate Rules

- Monster gate (`M`): Passable if and only if zero goblins (`O`) and zero dragons (`L`, `R`) remain on the board.
- Simultaneous Goblin combat (`O`): During the Late phase, every unprotected hero or goblin orthogonally adjacent to any goblin is marked `Dying` simultaneously and removed at the end of the phase (`BUG_08`). Two adjacent goblins eliminate each other simultaneously.
- Dragon fire (`L`, `R`): `L` projects fire West (`-x`) and `R` projects fire East (`+x`) across passable cells until blocked by `#`, `*`, closed `[`/`]`, closed `M`, another dragon, or a Priest (`P`/`4`). Any unprotected hero or goblin in the ray enters the simultaneous `Dying` layer.
- Priest protection (`P`, `4`): Both active `P` and inactive `4` are immune to goblin attacks and dragon fire, block dragon fire rays, and shield every orthogonally adjacent hero (`BUG_07`).

### 3.4 Part III Bard and Druid Rules

- Bard (`B`, `5`): At start and after each settled turn while `B` is active, every Moveable in `B`'s 5x5 Chebyshev square (`max(|dx|, |dy|) <= 2`, including `(2, 2)`, `BUG_03`, `BUG_04`) gets a `Note`. On `B`'s next move `(dx, dy)`, `B` and `Note` Moveables translate by `(dx, dy)` via fixed-point propagation. If `B` is blocked, the move cancels, and pressing `A` clears `Note` marks.
- Druid (`D`, `6`): Stepping into empty passable floor moves `D`. Stepping into an adjacent wall `#` (including outer border walls) transmutes that `#` into a crate `*` while `D` stays in place. Stepping into an adjacent crate `*`, goblin `O`, or unshielded hero transmutes that object into a wall `#` while `D` stays in place.
- Weighing semantics on `{` and `}` switches: Heroes, crates `*`, goblins `O`, dragons `L`/`R`, and (in Part III) walls `#` count as Weighing (`BUG_05`). Doors (`[` or `]`) open if and only if every switch of that color (`{` or `}`) is covered simultaneously. Uncovering any switch closes its doors and kills any hero in the doorway.

## 4. Habit 3: Bare-JSON Discipline and Budget Conservation

1. In open-loop conditions (`S0`, `S1`), the response must be one bare JSON object `{"keys": "<UDLRA string>"}` with zero markdown code fences, commentary, or trailing keys.
2. In stateful play (`S2`), every response must be one bare JSON object matching `{"action": "step", "keys": "<UDLRA>"}`, `{"action": "undo"}`, or `{"action": "reset"}`.
3. Every puzzle requires an exact final-key win: all heroes present on the board must stand on `G` tiles simultaneously, zero heroes may die on any frame, and the winning state must be reached for the first time on the final character of `keys`. Any extra key after winning fails closed as `premature_win`.

## 5. Habit 4: Four-Second Network-Free Zero-Import Micro-Solver Synthesis

When operating in the Python notebook condition (`S3`), candidate code cells must obey four hard sandbox rules:

1. Self-contained execution: Use only Python standard-library data structures (`collections.deque`, `heapq`, `json`, `math`, integer tuples, and bitmasks).
2. Strict import and syscall ban: AST inspection rejects any import of `soko_mcp`, `mcproof`, `os`, `sys`, `subprocess`, `socket`, `urllib`, `http`, `pathlib`, `shutil`, `glob`, `ctypes`, `importlib`, or `builtins`, and rejects calls to `open`, `eval`, `exec`, `compile`, or `__import__`.
3. Four-second budget: Every cell runs under `python3 -I -B` in an empty temporary directory with a hard 4.0-second timeout. Avoid unbounded generic search. Encode only the active room's mechanics, prune dead states, and cap queue expansions so the cell prints `{"keys": "..."}` inside 4.0 seconds.
4. Dual-oracle repair: Treat cell output as an unverified candidate until checked by Tier 2 dual replay. When Tier 2 reports `hero_died_at_step_k`, `premature_win_at_step_k`, or `alive_but_goals_unmet`, repair the transition model or goal condition on the next turn.

## 6. Habit 5: Quotient-Homomorphism and One-Step-Consistent Lower Bounds

Lower-bound claims (`LOWER_BOUND` or `PROVEN`) must never rely on unverified heuristic penalties or beam cutoffs:

1. Quotient admissibility: A quotient projection `pi : S -> Q` yields a valid lower bound `h(s) = d_Q(pi(s))` only when every legal concrete transition `(s, s')` maps to either `pi(s) = pi(s')` or a directed quotient edge `(pi(s), pi(s'))` of cost `<= 1`, and every winning state maps to distance `0`.
2. Pre-funded monotone potential repair: If a raw admissible bound drops by up to `1 + c * (r(s) - r(s'))` on steps that consume a monotone non-increasing resource `r(s') <= r(s)`, repair consistency via the non-negative potential `h_hat(s) = max(0, h(s) - c * r(s))` so `h_hat(s) - h_hat(s') <= 1` holds on every edge.
3. Exact rational arithmetic: Dual LP / Farkas / operator-counting lower bounds must verify feasibility in exact `int` or `fractions.Fraction` arithmetic without IEEE-754 `float` rounding.

## 7. Habit 6: Dual-Oracle Trajectory and Final-Key Win Verification

No route is marked `VERIFIED` from a single interpreter:

1. Both `PuzzleScriptOracle` (2D grid specification interpreter) and `FlatBitmaskOracle` (zero-shared-code 1D bitmask state machine) must replay the candidate route from step `0` through step `L`.
2. Both oracles must report `alive == True`, `premature_win == False`, `exact_win == True`, and identical 64-bit FNV-1a rolling trajectory digests (`traj_fnv64`).
3. Any checker modification must kill all 10 `PLANTED_BUGS` (`BUG_01` through `BUG_10`) and include explicit `must_fail` negative controls.

## 8. Adapter Lineage, Null-Space Compilation, and Honest Promotion Gates

1. Five-layer binding: Every `mde:soko-eval` Plane 2 adapter binds the exact base checkpoint fingerprint, LF-normalized `plane1_soko_spec.md` SHA-256, `soko_mcp` `SHA256SUMS` digest, deterministic CPU `float64` `derivation_recipe`, and `zone_manifest_id`.
2. Deterministic `BetaEdit` null-space compilation: Rank-8 updates are solved in CPU `float64` (`PYTHONHASHSEED=0`, single-threaded BLAS) over `Hybrid K0` (`seeded_noise` + off-register `y = 0` preservation anchors), certified by a division-free integer `FixedRadixCertificate`, and verified for `0`-byte re-derivation across independent processes.
3. Honest reporting: Evaluation receipts compute all checkpoint digests, git commits, server versions, and pass counts dynamically at runtime without hardcoded verdict literals, `max()` masking, or `0.0` overhead clamping. Negative single-pass 4B results are reported prominently alongside multi-turn closed-loop results.
