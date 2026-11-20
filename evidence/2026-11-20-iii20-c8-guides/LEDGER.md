# C8 negative-so-far ledger — III-20 structural guide variants (soko-mozi-01-c1)

Slice stopped at the G1 positive-control gate per locked spec section 8
(G1 failure = STOP, do not proceed). No transform completed; nothing below
was redesigned or retuned. Budgets below are the locked D5 values, identical
for every entry: beam_width=120000, window_len=16, max_states_per_stage=6000000,
budget_sec=0.

## G1 positive control (RAN — FAILED, the stop condition)

Verbatim driver output (`python3 evidence/2026-11-20-iii20-c8-guides/run_c8.py G1`,
exit code 3):

```
S84 sha256=eecbea96b09117b108c35cacaa5c3dd39530343d50d7a8b0e48c35ac87a1bca6
S87 sha256=536fabbaba35e466d91cfad83013783bcc1fe33610cedb34c699bb7963f93bf0
engine=/Users/kethuda/.hermes/profiles/proteus/cache/delegation/mcproof-20261119/soko-mozi-01-clone/cpp/build/soko_engine
[G1] seed_desc=S87 prior record (positive control) seed_len=87 seed_sha256=536fabbaba35e466d91cfad83013783bcc1fe33610cedb34c699bb7963f93bf0
[G1] best_len=87 improved=False states_seen=12434306 stages=[] wall=24.1s path=optimize_route_verified
[G1] gate: match=True win=True prem=False len=87 valid_sub84=False
G1 FAILED: 87-seed did not rediscover <=84. STOP per locked section 8.
```

Per-run record: `run_G1.json` (same directory). Triple-oracle gate on the
returned 87-route: spec + flat + cpp20 all agree (differential_match=true,
traj_fnv64=106d14c485ba2096 on all three, exact_win, 87 steps) — no oracle
drift. Engine binary is source-stamped (sha256 stamp matches
cpp/soko_engine.cpp), so no staleness. Diagnosis: the pipeline ran correctly
(12,434,306 states, 24.1 s) but no stage improved — `stages=[]`, i.e. neither
window BFS, the chiral-mirror tube, nor iterative refinement shortened the
87-seed. Leading hypothesis, no action taken: the shipped 87→84 used beam width
200,000 while the locked budget caps at the tool maximum 120,000; widening is
forbidden by the locked spec (sections 7–8), so this stands as the stop.

## Transform rows (§4 field set; unrun stages are N/A, not zero)

| transform_id | seed_route_sha256 | seed_len | beam_width | window_len | max_states_per_stage | budget_sec | nodes_expanded_window | nodes_expanded_tube | nodes_expanded_refine | nodes_expanded_total | states_seen | edge_consistency_checks | best_len_found | gain_vs_84 | oracle_pair | agreement | outcome | source_sha | run_date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 rot90-guide | eecbea96b09117b108c35cacaa5c3dd39530343d50d7a8b0e48c35ac87a1bca6 | 84 | 120000 | 16 | 6000000 | 0 | N/A (not run) | N/A (not run) | N/A (not run) | N/A (not run) | N/A (not run) | N/A (not run) | N/A (not run) | N/A (not run) | spec+flat | N/A | NOTRUN — G1 positive control failed (87-seed held at 87, exit 3); locked §8 stop condition forbids proceeding to transforms | 41b6f9ca54cc24954adcd3e88149c2371a4478e6 | 2026-11-20 |
| T2 role-aware X-mirror guide | eecbea96b09117b108c35cacaa5c3dd39530343d50d7a8b0e48c35ac87a1bca6 | 84 | 120000 | 16 | 6000000 | 0 | N/A (not run) | N/A (not run) | N/A (not run) | N/A (not run) | N/A (not run) | N/A (not run) | N/A (not run) | N/A (not run) | spec+flat | N/A | NOTRUN — interface: locked D4 consumer `optimize_route_verified` (engine_bridge.py:469) takes only a seed, no guide/role knob; C++ `optimize` stdin protocol has no role flag and both `tube_beam_refine` call sites hardcode `role_agnostic=true` (soko_engine.cpp); exposing it needs search-code changes, forbidden by D4 | 41b6f9ca54cc24954adcd3e88149c2371a4478e6 | 2026-11-20 |
| T3 start-offset (k=8) X-mirror guide | eecbea96b09117b108c35cacaa5c3dd39530343d50d7a8b0e48c35ac87a1bca6 | 84 | 120000 | 16 | 6000000 | 0 | N/A (not run) | N/A (not run) | N/A (not run) | N/A (not run) | N/A (not run) | N/A (not run) | N/A (not run) | N/A (not run) | spec+flat | N/A | NOTRUN — interface: consumer derives its guide internally from the full seed and rejects non-winning seeds (ValueError, engine_bridge.py:477-485), so a truncated k=8 remainder cannot be passed as guide/seed without redesign, forbidden by D4 | 41b6f9ca54cc24954adcd3e88149c2371a4478e6 | 2026-11-20 |
| T4 fixed-point refinement (84-seed) | eecbea96b09117b108c35cacaa5c3dd39530343d50d7a8b0e48c35ac87a1bca6 | 84 | 120000 | 16 | 6000000 | 0 | N/A (not run) | N/A (not run) | N/A (not run) | N/A (not run) | N/A (not run) | N/A (not run) | N/A (not run) | N/A (not run) | spec+flat | N/A | NOTRUN — G1 positive control failed (87-seed held at 87, exit 3); locked §8 stop condition forbids proceeding to transforms | 41b6f9ca54cc24954adcd3e88149c2371a4478e6 | 2026-11-20 |

## G1 control row (same field set, for the record that ran)

| transform_id | seed_route_sha256 | seed_len | beam_width | window_len | max_states_per_stage | budget_sec | nodes_expanded_window | nodes_expanded_tube | nodes_expanded_refine | nodes_expanded_total | states_seen | edge_consistency_checks | best_len_found | gain_vs_84 | oracle_pair | agreement | outcome | source_sha | run_date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| G1 positive control (87-seed) | 536fabbaba35e466d91cfad83013783bcc1fe33610cedb34c699bb7963f93bf0 | 87 | 120000 | 16 | 6000000 | 0 | N/A (engine reports aggregate only) | N/A (engine reports aggregate only) | N/A (engine reports aggregate only) | 12434306 | 12434306 | N/A (not instrumented at this interface) | 87 | N/A (control target was ≤84 rediscovery; held at 87) | spec+flat (+cpp20 third check, agreeing) | true | NO_GAIN — CONTROL FAILED, slice stopped per §8 | 41b6f9ca54cc24954adcd3e88149c2371a4478e6 | 2026-11-20 |
