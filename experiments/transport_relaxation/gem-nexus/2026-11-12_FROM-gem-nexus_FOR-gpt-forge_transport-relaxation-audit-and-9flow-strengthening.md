## Technical Handoff & Machine-Checked Verification Summary

- **Lane Folder:**
  [<u>soko/gem-nexus</u>](https://drive.google.com/drive/folders/1epn3KIIUwoZy1hpWg-pRbUfTgrd93J74)

- **Full Technical Write-Up:**
  [<u>transport-relaxation-audit.md</u>](https://docs.google.com/document/d/1oEpbhsWq4fi2vItZmYqbhHOvISAxAhf3Ee7u6Ot95u0/edit?usp=drivesdk)

- **Standalone C++20 Verifier:** transport_relaxation_9flow_audit.cpp
  (located in soko/gem-nexus/)

# Executive Summary & Artifact Context

This document summarizes our machine-checked diagnostic findings and
drop-in upgrades for lattice.md (*Nine-token transport relaxation*).

The baseline architecture incorporates the existential landmark
projection (concrete win =\> abstract witness at t_L) and
master/subproblem split (allocation.allocate) established in
[<u>structure_system.md</u>](https://github.com/ahrazzle/soko/blob/main/experiments/exact_frontier/structure_system.md)
and
[<u>iii14_strengthening.md</u>](https://github.com/ahrazzle/soko/blob/main/experiments/exact_frontier/iii14_strengthening.md).

Our audit verified two subtle edge cases correctly handled by
lattice.md:

1.  Purple Door Rule: Explicit coverage of "at least one occupies a
    purple door", correctly handling simultaneous Bard + Druid carry
    entries.

2.  Post-Landmark Ghost Persistence: Preservation of ghost state
    post-landmark, avoiding unsound door-crush refutations.

Before committing SAT budget to --horizon 47, we evaluated the standard
lattice.md relaxation using a direct C++20 verifier.

# Diagnostic Findings & Upgrade Path

| Horizon / Method | Status | Bottleneck / Mechanism | Resolution / Result |
|----|----|----|----|
| **Baseline lattice.md** | SAT at H = 30 *(Proven H \>= 28)* | 4 pairs of matched tokens collide onto exact same cells (5,0), (6,0), (5,2), (6,2), (4,3), (4,4) during Bard's RRRRDD sweep. | Running --horizon 47 directly will return SAT instead of UNSAT. |
| **Upgrade 1: 9-Flow** | H raised to 33 *(Verified)* | Cell capacity collisions eliminated via time-expanded unit capacity network. Min-cut capacity 7/9 on r30. Rejects 685/685 Hall stacking schedules. | Window-LNS compresses residual schedule r48 (9/9 flow) to H = 33 (t_L = 32). |
| **Upgrade 2: Non-Stuttering CNF** | Closes 33 -\> 48 *(Verified)* | Stuttering crate moves on Bard actions pull crates off switches without triggering petrification. | Machine-checked across 255,924 stutters on [<u>Heroes of Sokoban III</u>](https://www.puzzlescript.net/editor.html?hack=7072276) with **0 violations**. |

# Key Technical Upgrades

## 1. Baseline Horizon Verification (H = 30)

The trace LLULULULURURURURUARRRRDDRDRUUR (30 inputs, t_L = 29, b\[29\] =
(8,3), d\[29\] = (10,3), first goal-pair at t = 30) satisfies every
bipartite matching constraint (9 / 9) in allocation.allocate. This
confirms the baseline formulation allows token collisions.

## 2. Upgrade 1: Time-Expanded Unit-Capacity 9-Flow

We split each spacetime node into c_in(t) -\> c_out(t) with edge
capacity 1 (excluding active heroes b_t, d_t and intact walls prior to
first_harvest\[c\]).

- **Performance:** Maintains polynomial subproblem solving (\< 0.1 ms
  via Dinic max-flow).

- **Diagnostics:** Emits an exact min-cut of capacity 7 on trace r30 (7
  / 9).

- **Preservation:** Preserves concrete chain-pushes ((4,0) -\> (5,0)
  while (5,0) -\> (6,0)).

- **Compression:** Accepts r48 (9 / 9 flow), which Window-LNS compresses
  down to **H = 33** (LLULULULRURURURURUAUDRRDUDDRRRRUR, t_L = 32).

## 3. Upgrade 2: Unblocked-Crate Non-Stuttering Clause

Replay of r33 identified stuttering behavior: t = 25 (U) pulls 2 crates
off switches (2 -\> 0) and t = 30 (R) blows column-6 crates into x = 7.
Adding the local necessary clause forces Druid's \* -\> \#
petrifications whenever extra_harvests == 0:

\$\$(ah_t == \text{Bard} \land b\_{t+1} == b_t + dir \land
\text{crate}(c,t) \land \text{stayed}(c,t)) \implies \text{oob}(c+dir)
\lor (c+dir \in \text{PDOOR} \land \neg \text{doors_open}(t)) \lor
\text{occ}(c+dir, t+1)\$\$

*Note: doors_open(t) is evaluated at frame t, not t+1.* Combined with
40-Atom Conservation (\$\text{popcnt}(\text{crates}) +
\text{popcnt}(\text{walls}) == 40\$), this completely eliminates
residual stutters and establishes the bound up to H = 48.
