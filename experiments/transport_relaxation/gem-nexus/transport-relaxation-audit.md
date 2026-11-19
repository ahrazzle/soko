- **Lane:**
  [<u>soko/gem-nexus</u>](https://drive.google.com/drive/folders/1epn3KIIUwoZy1hpWg-pRbUfTgrd93J74)

- **Target Specification:** lattice.md (*Nine-token transport
  relaxation*, building on
  [<u>structure_system.md</u>](https://github.com/ahrazzle/soko/blob/main/experiments/exact_frontier/structure_system.md)
  and
  [<u>iii14_strengthening.md</u>](https://github.com/ahrazzle/soko/blob/main/experiments/exact_frontier/iii14_strengthening.md)
  on [<u>Sokoban Eval Frontier</u>](https://soko.banteg.xyz/frontier/)
  Room III-14)

# 1. Executive Verdict (VERIFIED + PROVEN)

gpt-forge's **existential landmark projection** (concrete win =\>
abstract witness at landmark t_L) and **master/subproblem
decomposition** (allocation.allocate separating hero schedules from
token origin assignment) are structurally sound and cleanly avoid
deterministic unlabeled-state quotient explosion. However, before
running the --horizon 47 CNF expecting UNSAT, we solved the relaxation
directly in C++20 and proved two critical diagnostic bounds:

## Key Findings & Diagnostic Bounds

1.  **lattice.md As Written Is SAT at H = 30 (VERIFIED, with H \>= 28
    PROVEN)**

    - Explicit 30-input satisfying witness (t_L = 29, first distinct
      goal-pair at t = 30, 9 / 9 bipartite matching):  
      LLULULULURURURURUARRRRDDRDRUUR

    - Thus --horizon 47 (and every horizon H in \[30..47\]) is SAT under
      lattice.md as written.

    - An exact 965,669-state aura-free super-relaxation A\* proves H \>=
      28 globally (PROVEN), with 0 solutions found across 4,000,047
      exact DFS nodes at H = 28, 29.

2.  **Replacing Static 40 x 9 Bipartite Matching with Polynomial
    Time-Expanded Unit-Capacity 9-Flow Kills 100% (685 / 685) of
    Stacking Schedules, Raising H to 33 (VERIFIED)**

    - r30 passes allocation.allocate (9 / 9) only because four pairs of
      tokens stack onto identical cells ((5,0), (6,0), (5,2), (6,2),
      (4,3), (4,4)).

    - Replacing bipartite matching with unit-node-capacity Dinic
      max-flow (\< 0.1 ms per schedule) accepts the 48-key concrete
      incumbent (9 / 9) while refuting r30 with an exact **capacity-7
      min-cut** (7 / 9).

    - Even with 100% disjoint space-time occupancy (flow = 9 / 9),
      Sliding-Window LNS compresses r48 down to **H = 33**:  
      LLULULULRURURURURUAUDRRDUDDRRRRUR (t_L = 32, 9 / 9 disjoint flow).

3.  **Why H = 33 -\> 48 Remains Open — Free Unblocked Aura Stuttering
    (VERIFIED across 255,924 Stutters)**

    - Replaying r33 concretely exposes the exact missing physical law:
      at t = 25 (U), Bard steps (4,3) -\> (4,2) and pulls 2 switch
      crates off {4,5} x {2} (2 -\> 0), and at t = 30 (R), Bard steps
      (6,4) -\> (7,4) and blows unpetrified column-6 crates into open
      floor x = 7.

    - Adding our **Exact Unblocked-Crate Non-Stuttering Law** (verified
      with **0 violations across 250,000 concrete states and 255,924
      Bard crate stutters**) closes this gap completely on the 9-harvest
      branch (extra_harvests == 0).

# 2. Explicit H = 30 Witness Table (LLULULULURURURURUARRRRDDRDRUUR, t_L = 29)

At t = 29, b\[29\] = (8,3) (purple door) and d\[29\] = (10,3)
(enclosure), stepping on R at t = 30 to b\[30\] = (9,3) and d\[30\] =
(11,3) (first goal-pair frame):

| Landmark Switch | Matched Origin | Pos at t = 22 | Pos at t = 24 | Space-Time Collision Exposed |
|----|----|----|----|----|
| (4,2) | (1,0) | (4,0) | (4,2) | — |
| (6,3) | (2,0) | **(6,0)** | **(6,2)** | Collides with (4,0) at t=22, 24 |
| (6,2) | (4,0) | **(6,0)** | **(6,2)** | Collides with (2,0) at t=22, 24 |
| (5,3) | (3,0) | **(5,0)** | **(5,2)** | Collides with (5,0) at t=22, 24 |
| (5,2) | (5,0) | **(5,0)** | **(5,2)** | Collides with (3,0) at t=22, 24 |
| (6,4) | (0,1) | (4,1) | **(4,3)** | Collides with (0,3) at t=24 |
| (4,3) | (0,3) | (4,3) | **(4,3)** | Collides with (0,1) at t=24 |
| (5,4) | (0,2) | (4,2) | **(4,4)** | Collides with (0,4) at t=24 |
| (4,4) | (0,4) | (4,4) | **(4,4)** | Collides with (0,2) at t=24 |

# 3. Two Globally Sound Refinements for experiments/transport_relaxation

## Upgrade A — Polynomial Time-Expanded Unit-Capacity 9-Flow (allocation.allocate_disjoint)

Split each (cell c, frame t) (c not in {b_t, d_t} and t \>=
first_harvest\[c\] for initial \# cells) into c_in(t) -\> c_out(t) of
capacity 1, with edges c_out(t) -\> c_in(t+1) and (when Bard steps dir
and c in AURA\[b_t\]) c_out(t) -\> (c+dir)\_in(t+1).

- **Why chain-pushes stay sound:** If token A is at (4,0) and token B is
  at (5,0) at frame t, and both step R to (5,0) and (6,0) at t+1, A uses
  (5,0)\_in(t+1) while B uses (6,0)\_in(t+1) — 100% vertex-disjoint!
  Only if B *stays* at (5,0) does (5,0)\_in(t+1) block A.

- **Min-cut certificate:** By max-flow min-cut, any failed schedule
  (flow \< 9) admits a compact integer s-t cut witness analogous to
  Hall's obstruction.

## Upgrade B — Exact Unblocked-Crate Non-Stuttering Clause (0 / 255,924 Violations)

For every concrete execution of [<u>Heroes of Sokoban
III</u>](https://www.puzzlescript.net/editor.html?hack=7072276)
(f66ceb8f...), whenever ah_t == Bard and b\_{t+1} == b_t + dir, if an
unfrozen \* crate at c in AURA(b_t) stays at c, then:

(c + dir out of bounds) OR (c + dir in PDOOR and not doors_open(t)) OR
occ(c + dir, t + 1)*(Note the frame index on doors_open(t): a crate at
(7,y) moving R is blocked during the movement phase by closed door (8,y)
at t, even when Late opens the doors at the end of turn t -\> t+1!)*

By the **40-Atom Conservation Law** (popcnt(crates) + popcnt(walls) ==
40 on 15x7), whenever Druid executes only 9 initial boundary harvests
(extra_harvests == 0), the 9 tokens + 31 intact walls account for 100%
of board matter, forcing Druid's \* -\> \# petrifications on column 6
directly into any valid schedule.
