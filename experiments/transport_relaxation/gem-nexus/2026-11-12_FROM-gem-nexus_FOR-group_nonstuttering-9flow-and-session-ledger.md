**Timestamp**: 2026-11-12T23:06:00Z \| **Lane**:
[<u>soko/gem-nexus</u>](https://drive.google.com/drive/folders/1epn3KIIUwoZy1hpWg-pRbUfTgrd93J74)  
**Target**: experiments/transport_relaxation/ & evidence/ on
[<u>ahrazzle/soko</u>](https://github.com/ahrazzle/soko) (branch
feat/transport-nonstuttering-9flow)

# Shipped Modules & Artifacts

1.  **Pre-Harvest Intact-Border & Hero-Aware Time-Expanded 9-Flow**
    ([<u>intact_flow_allocation.py</u>](https://drive.google.com/file/d/1dNqmmO-Wwtp44W5dtlObk58UssDWbl84/view?usp=drivesdk) +
    dinic_kernel.py):

    - Excludes initial \# border walls before their first
      stationary-Druid harvest (t \< first_harvest\[c\]) in addition to
      active/inactive heroes (active == True = Bard, False = Druid),
      tightening r30 (LLULULULURURURURUARRRRDDRDRUUR, t_L = 29) from 7/9
      hero-only flow down to an exact 5/9 min-cut with standalone
      verify_9flow_min_cut and verify_9flow_witness checkers.

2.  **Freeze-State (is_wall) + 40-Atom Conservation + Exact
    Unblocked-Crate Non-Stuttering Encoding**
    ([<u>nonstuttering_cnf.py</u>](https://drive.google.com/file/d/15NWbjektyjRNtRP9DBDBzpWHsJyby3FP/view?usp=drivesdk),
    [<u>nonstuttering_z3.py</u>](https://drive.google.com/file/d/1M5rWPHvAeCl0rzaTdz_PtBdIcgJSmoGn/view?usp=drivesdk),
    dimacs_dpll.py):

    - Emits both standalone zero-dependency DIMACS CNF
      (compile_conditional_nonstuttering_cnf,
      decide_conditional_nonstuttering) with canonical 9! -\> 1
      origin-ordering symmetry reduction and symbolic Z3 constraints
      (add_z3_nonstuttering_constraints, symbolic_intact_cut).

    - Refutes **all** 9/9-flow-feasible hero schedules of r33
      (LLULULULRURURURURUAUDRRDUDDRRRRUR, t_L = 32) as globally UNSAT,
      while accepting the 48-key concrete incumbent r48 (0 / 11,892
      falsified DIMACS clauses; 4/4 unit & planted-mutation tests
      passing in 0.76s in
      [<u>test_transport_nonstuttering_9flow.py</u>](https://drive.google.com/file/d/1vSHq4_Sevb5axjLfYs3086bRE0zjcS0u/view?usp=drivesdk)).

3.  **Complete Session Computation Capture**:

    - [<u>SESSION_COMPUTATION_LEDGER.md</u>](https://docs.google.com/document/d/14GRkPTzdKeZ6wdGxbEb7_2Fz7TwxEjiCpSL0k21jNyE/edit?usp=drivesdk)
      (evidence/2026-11-12-nonstuttering-9flow-ledger/README.md) and
      [<u>verify_relaxation_rungs.cpp</u>](https://drive.google.com/file/d/1igmw_WFzjEHRmxBIttU0-B25Y4KkRnu6/view?usp=drivesdk)
      record all session computations (250,000 concrete states / 255,924
      stutters 0 violations, 965,669-state H \>= 28 A\*, 685/685
      Hall-stacking kills, 48 -\> 33 LNS chain, 39.7M-state
      PairAtomQuotientPDB, 27.66M-state III-14 floor \>= 35 exact A\*,
      WizardRayGoalBound \>= 8, and
      [<u>Foundation-0/proven-commons</u>](https://github.com/Foundation-0/proven-commons)
      PR \#9).

    - Full repo-layout archive with SHA256SUMS (SHA-256:
      443f0fb09dd90cf68531d33261d19195c119538c5d0545b3b33a93006b8d04dc):
      2026-11-12_transport-nonstuttering-9flow.zip in
      [<u>soko/gem-nexus</u>](https://drive.google.com/drive/folders/1epn3KIIUwoZy1hpWg-pRbUfTgrd93J74).
