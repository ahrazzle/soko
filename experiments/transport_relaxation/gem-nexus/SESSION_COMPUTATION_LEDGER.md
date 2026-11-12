# III-14 Transport-Relaxation Rungs, Non-Stuttering CNF, and Exact-State Lower-Bound Ledger

This ledger captures the complete empirical, combinatorial, and
formal-verification computations linking the nine-token transport
relaxation (experiments/transport_relaxation/) to concrete Part III
mechanics on [<u>Sokoban Eval
Frontier</u>](https://soko.banteg.xyz/frontier/) Room III-14 (15x7,
pinned [<u>Heroes of Sokoban Part
III</u>](https://www.puzzlescript.net/editor.html?hack=7072276) source
SHA-256
f66ceb8f8a2c23a3cb270bad62cdf194e47479772cab94f154ed26f0ff7c20e0) and
companion Frontier benchmarks (III-20, II-22, III-15), aligned with the
[<u>Proven-Commons Verified
Bar</u>](https://github.com/Proven-Commons/mission/blob/main/playbook/verified-bar.md)
and [<u>ahrazzle/soko</u>](https://github.com/ahrazzle/soko).

## 1. Counterfactual Rung Hierarchy on III-14 (H = 28 -\> 30 -\> 33 -\> 48)

| **Rung** | **Constraint System** | **Minimum Horizon / Outcome** | **Key Diagnostic Metric** | **Epistemic Status** |
|----|----|----|----|----|
| R0 | Exact aura-free harvest + transport super-relaxation | H \>= 28 (UNSAT for H \<= 27) | 965,669 exact A\* states + 4,000,047 exact DFS nodes at H = 28, 29 (0 witnesses) | **PROVEN** |
| R1 | Base 9-token relaxation (allocation.allocate 40x9 Hall matching) | SAT at H = 30 (t_L = 29) | Witness LLULULULURURURURUARRRRDDRDRUUR (9/9 Hall matching; 4 token pairs stack) | **VERIFIED** |
| R2 | Time-expanded unit-capacity 9-flow (hero exclusion only, flow_allocation.py) | Refutes r30 (7/9); kills 685 / 685 Hall-stacking schedules | Compresses via sliding-window LNS to H = 33 (9/9 flow) | **VERIFIED** |
| R3 | Time-expanded unit-capacity 9-flow + pre-harvest intact border \# exclusion ([<u>intact_flow_allocation.py</u>](https://drive.google.com/file/d/1dNqmmO-Wwtp44W5dtlObk58UssDWbl84/view?usp=drivesdk)) | Tightens r30 min-cut to 5/9; SAT at H = 33 (t_L = 32) | Witness LLULULULRURURURURUAUDRRDUDDRRRRUR (9/9 disjoint flow; verify_9flow_witness == True) | **VERIFIED** |
| R4 | R3 + Freeze-State (is_wall) + 40-Atom Conservation + **Exact Unblocked-Crate Non-Stuttering CNF** ([<u>nonstuttering_cnf.py</u>](https://drive.google.com/file/d/15NWbjektyjRNtRP9DBDBzpWHsJyby3FP/view?usp=drivesdk), [<u>nonstuttering_z3.py</u>](https://drive.google.com/file/d/1M5rWPHvAeCl0rzaTdz_PtBdIcgJSmoGn/view?usp=drivesdk)) | Refutes **all** 9/9-flow schedules of r33 (UNSAT); accepts concrete r48 (SAT, 0 / 11,892 falsified clauses) | 0 violations across 250,000 reachable concrete states, 439,038 transitions, and 255,924 Bard crate stutters ([<u>verify_relaxation_rungs.cpp</u>](https://drive.google.com/file/d/1igmw_WFzjEHRmxBIttU0-B25Y4KkRnu6/view?usp=drivesdk)) | **VERIFIED** |

### 1.1 Explicit H = 30 Hall-Matching Witness (LLULULULURURURURUARRRRDDRDRUUR, t_L = 29)

At t = 29, bard = (8, 3) and druid = (10, 3), stepping R at t = 30 onto
goals (9, 3) and (11, 3) (first goal-pair frame). While 40 x 9 bipartite
matching succeeds (9/9), unit-capacity 9-flow exposes both cell stacking
and traversal through the unharvested boundary wall (6, 0) (7/9
hero-only min-cut; 5/9 intact-border + hero min-cut):

| **Switch Index** | **Landmark Switch** | **Matched Border Origin** | **Position at t = 22** | **Position at t = 24** | **Space-Time / Intact-Wall Conflict** |
|----|----|----|----|----|----|
| 0 | (4, 2) | (1, 0) | (4, 0) | (4, 2) | Traverses intact border (2,0)..(4,0) |
| 1 | (5, 2) | (5, 0) | (5, 0) | (5, 2) | Stacks with (3, 0) at t = 22, 24 |
| 2 | (6, 2) | (4, 0) | (6, 0) | (6, 2) | Enters unharvested border (6, 0) and stacks with (2, 0) |
| 3 | (4, 3) | (0, 3) | (4, 3) | (4, 3) | Stacks with (0, 1) at t = 24 |
| 4 | (5, 3) | (3, 0) | (5, 0) | (5, 2) | Stacks with (5, 0) at t = 22, 24 |
| 5 | (6, 3) | (2, 0) | (6, 0) | (6, 2) | Enters unharvested border (6, 0) and stacks with (4, 0) |
| 6 | (4, 4) | (0, 4) | (4, 4) | (4, 4) | Stacks with (0, 2) at t = 24 |
| 7 | (5, 4) | (0, 2) | (4, 2) | (4, 4) | Stacks with (0, 4) at t = 24 |
| 8 | (6, 4) | (0, 1) | (4, 1) | (4, 3) | Stacks with (0, 3) at t = 24 |

### 1.2 Disjoint-9-Flow Sliding-Window LNS Compression Chain (48 -\> 33)

Starting from the 48-key concrete incumbent
LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR (t_L = 47, 9/9
intact-border flow), exact window replacement under the 9/9
disjoint-flow oracle discovers six successive shortcuts down to H = 33:

1.  48 -\> 45 (window \[20, 28\], t_L = 44):
    LLULULULRURURURURUAUDRRDDRRDLRAULDLDRARURDUUR

2.  45 -\> 42 (window \[27, 35\], t_L = 41):
    LLULULULRURURURURUAUDRRDDRRUDDAUDRARURDUUR

3.  42 -\> 39 (window \[27, 35\], t_L = 38):
    LLULULULRURURURURUAUDRRDDRRUDDLRRURDUUR

4.  39 -\> 37 (window \[24, 32\], t_L = 36):
    LLULULULRURURURURUAUDRRDUDDRRDRURDUUR

5.  37 -\> 35 (window \[26, 34\], t_L = 34):
    LLULULULRURURURURUAUDRRDUDDRRRRDUUR

6.  35 -\> 33 (window \[25, 33\], t_L = 32):
    LLULULULRURURURURUAUDRRDUDDRRRRUR

Concrete Part III replay of r33 exposes the two omitted physical laws
closed by
[<u>nonstuttering_cnf.py</u>](https://drive.google.com/file/d/15NWbjektyjRNtRP9DBDBzpWHsJyby3FP/view?usp=drivesdk):

- At t = 24 -\> 25 (U), Bard steps (4, 3) -\> (4, 2) and pulls unfrozen
  switch crates off {4, 5} x {2} into open floor {4, 5} x {1}.

- At t = 29 -\> 30 ('R'), Bard steps (6, 4) -\> (7, 4) and carries
  unpetrified column-6 crates off {6} x {2, 3, 4} into open floor column
  x = 7.

### 1.3 Canonical 9! -\> 1 Origin-Symmetry Reduction and DIMACS CNF Metrics

Sorting the 9 tracked tokens by BORDER_INDEX(origin_0) \< ... \<
BORDER_INDEX(origin_8) and enforcing switch-set surjection at
landmark_frame eliminates all 9! = 362,880 label permutations without
loss of generality
([<u>test_transport_nonstuttering_9flow.py</u>](https://drive.google.com/file/d/1vSHq4_Sevb5axjLfYs3086bRE0zjcS0u/view?usp=drivesdk)):

- On r48 (H = 48, t_L = 47), compile_conditional_nonstuttering_cnf emits
  1,921 variables and 11,892 DIMACS clauses (437 unblocked
  non-stuttering clauses), solved to SAT with 0 falsified clauses on
  both the projected concrete execution and standalone DPLL search.

- On r33 (H = 33, t_L = 32), every 9/9-flow-feasible hero schedule is
  proven UNSAT in \< 0.2s.

## 2. Exact-State Quotient-Homomorphism & Multi-Room Prover Ledger

<table>
<colgroup>
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
</colgroup>
<thead>
<tr>
<th style="text-align: left;"><strong>Computation / Prover
Kernel</strong></th>
<th style="text-align: left;"><strong>Target Room(s)</strong></th>
<th style="text-align: left;"><strong>Exact Verified
Metrics</strong></th>
<th style="text-align: left;"><strong>Source / Artifact</strong></th>
</tr>
<tr>
<th style="text-align: left;">PairAtomQuotientPDB (2-atom unordered
quotient homomorphism)</th>
<th style="text-align: left;">III-14</th>
<th style="text-align: left;">39,719,680 quotient states; 0
step-inconsistencies (h(s) - h(s') &lt;= 1) across all 48 transitions of
r48 (including mixed-block step 25)</th>
<th><a
href="https://drive.google.com/file/d/1gbW96ISqyXpB1mB3FOZEuSut77MWLZyH/view?usp=drivesdk"><u>2026-11-12_soko-verified-mcp-v0.3.0.zip</u></a>,
cpp/soko_engine.cpp</th>
</tr>
<tr>
<th style="text-align: left;">Multi-Core Exact-State Bucketed A*
(CompactNode / Packed14, zero lossy TT pruning)</th>
<th style="text-align: left;">III-14</th>
<th style="text-align: left;">Generic 10s budget: floor &gt;= 32 (1,014
live 64-bit hash collisions caught); 35s prover run: floor &gt;= 35
across 27,656,589 exact states, 110,803,961 transitions, 22,658 hash
collisions prevented</th>
<th style="text-align: left;">cpp/soko_engine.cpp,
cpp/frontier_iii14_iii20_prover.cpp</th>
</tr>
<tr>
<th style="text-align: left;">Matter Conservation &amp; Column-6
Blow-Off Law</th>
<th style="text-align: left;">III-14</th>
<th>popcnt(crates) + popcnt(walls) invariant (40 on 15x7, 38 on 14x7);
open floor at x = 7, y = 1..5 requires Druid * -&gt; # petrification of
(6,2), (6,3), (6,4)</th>
<th><a
href="https://drive.google.com/file/d/15NWbjektyjRNtRP9DBDBzpWHsJyby3FP/view?usp=drivesdk"><u>nonstuttering_cnf.py</u></a></th>
</tr>
<tr>
<th style="text-align: left;">WizardRayGoalBound (warpball ray + step
BFS admissible floor)</th>
<th style="text-align: left;">III-20, III-15, II-22</th>
<th style="text-align: left;">Raises non-pushing Wizard-room floors from
1 to &gt;= 8 immediately</th>
<th style="text-align: left;">cpp/soko_engine.cpp</th>
</tr>
<tr>
<th style="text-align: left;">Dual-Oracle Holdout-Breaking Receipt &amp;
10/10 Mutation Gate</th>
<th style="text-align: left;">III-20</th>
<th>84-key primary (eecbea96b091) and alternate (4edff1ad8c90) routes
verified across Python and C++20 oracles</th>
<th><a
href="https://drive.google.com/file/d/15fgBpkqK-v7XaohjhUrgAPvWYLqzFfVL/view?usp=drivesdk"><u>proven_commons_audit.py</u></a></th>
</tr>
<tr>
<th style="text-align: left;">II-22 Window-16 Exact BFS + Chiral x
&lt;-&gt; 12-x Tube-Beam Audit</th>
<th style="text-align: left;">II-22</th>
<th style="text-align: left;">Replayed 94-key trajectory cleanly;
verified zero &lt;= 16-step local window shortcuts along the 94-key
corridor</th>
<th><a
href="https://drive.google.com/file/d/1_97Ys-vH2Y0NWzNT7ClyTr0im24NyVlE/view?usp=drivesdk"><u>sokobanteg_10core_solver.cpp</u></a></th>
</tr>
<tr>
<th style="text-align: left;">formal_synthesize_invariant
(houdini_safety &amp; deadlock_trap)</th>
<th style="text-align: left;">Domain-general
(lease_epoch_fenced_v2)</th>
<th style="text-align: left;">Universal inductive safety invariant
synthesized and verified (PROVEN) across all 486 syntactic states</th>
<th style="text-align: left;"><p>soko_mcp/formal_kernel.py</p>
<table>
<colgroup>
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
</colgroup>
<thead>
<tr>
<th>Proven-Commons Lean 4 Token Scanner and RFC 9112 HTTP/1.1 Slice</th>
<th>Foundation-0/proven-commons</th>
<th>12/12 forbidden Lean syntax vectors caught; 12/12 RFC 9112 smuggling
bugs + 3/3 Node v18.20.4 CVE vectors caught</th>
<th><a
href="https://github.com/Foundation-0/proven-commons"><u>Foundation-0/proven-commons</u></a>
PR #9</th>
</tr>
</thead>
<tbody>
</tbody>
</table></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

## 3. Reproducing All Verification Checks
