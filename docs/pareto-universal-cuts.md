# Certified Pareto-Minimal Universal Cut Selection (`III-14`)

*Authored 2026-11-12 by `mithrax` (`mithrax-exo`, Gemini seat) — Workstream A follow-up to PRs #16, #19, #21, and #24.*

**Correction (2026-11-12):** The `H=47` figure in this note is `report.json`'s `universe_horizon` on `target_room` "III-14": the construction horizon of the 9,921-node, 29,413-arc universal network used to measure cut predicate counts on 12 deficient traces (`flow` 0 through 6, `all_cuts_capacity_verified` true). The III-14 ledger bound remains a sound lower bound `>= 34` on the 14x7 fixture only.

## 1. Motivation: Master Clause Width in Unrestricted `universe_horizon` 47 Search

**Implementation and objective follow-up (2026-11-12):** The original note and
report preserve reported measurements; they do not include the twelve input
assignments or runnable selection code. A reproducible implementation of the
two residual extrema is now available through `--cut-selection` in the global
and causal search drivers; see the [new comparison](../evidence/2026-11-12-residual-cuts/README.md).
It uses different, retained inputs and does not reproduce the original figures.

The shared-predicate gadget in section 2 is **not an exact objective encoding
for arbitrary directed pairs**. With pairs `u1 -> v1`, `u2 -> v2` and source side
`{s, u1, v1}`, neither pair crosses, but the gadget charges for the cross-pair
path `u1 -> pred_in -> pred_out -> v2`. Its minimum cost is `P` rather than zero;
the [executable counterexample](../experiments/transport_relaxation/predicate_gadget_counterexample.py)
enumerates all four auxiliary placements. Additional structural restrictions
would need to be established for each contracted group. Checking the original
cut's capacity can still establish a valid inequality; it does not establish
minimum predicate count. The generic exact-optimality interpretation of the
proposal and its finite checks should therefore not be used for integration.

In PR #21 (`b760a1c`), unrestricted global search at `universe_horizon` 47 on `III-14` (`9,921` universal nodes, `29,413` universal arcs) accepted 150 checked cuts in 120s yet ended `unknown`. Because `cut_certificate.py` evaluates universal boundary arcs across **all** candidate edges—including arcs with `capacity == 0` under the current hero trace—standard forward residual reachability from `source` (`source_minimal`) ignores disabled arcs and slices across an average of **1,895.50 distinct symbolic predicates** per cut, generating wide `z3.PbGe(..., 9)` constraints.

## 2. Two-Stage Picard-Queyranne + Lawler Predicate-Hyperedge Construction

By complementary slackness (Picard & Queyranne, 1980), after a single Stage-1 active-network max-flow solve (`flow < 9` via `dinic_kernel.CertifiedDinic`), a partition `(S, V \ S)` is a minimum-capacity active cut **if and only if** `S` contains `s_reach` (forward residual closure from `source`), excludes `t_reach` (backward residual closure into `sink`), and cuts zero positive-residual arcs on the contracted core `V \ (s_reach U t_reach)`.

To minimize the exact number of distinct symbolic predicates `len(grouped)` entering `global_master.add_cut`:

1. **Residual Contraction:** Contract `s_reach` into `super_source` and `t_reach` into `super_sink`, keeping only core vertices `V \ (s_reach U t_reach)`. Assign infinite capacity `B = (|E| + 1) * (|E| + 3) + 1` to every positive-residual Stage-1 arc so no non-minimum active cut can ever be chosen.
2. **Lawler Shared-Predicate Hyperedges (1973):** Group all non-constant universal arcs (`kind != 'one'`) crossing core nodes by `(edge.kind, tuple(edge.params))` (for example, all 9 switch-entry arcs at frame `t` share `('landmark', (t,))`). For any predicate key with multiple core node pairs `(u_i, v_i)` (and not already forced across `super_source -> super_sink`), insert a 2-node gadget `pred_in -> pred_out` of capacity `P = |E| + 1` with `u_i -> pred_in` and `pred_out -> v_i` of capacity `B`, plus unit tie-break weight `1` per individual arc.
3. **Independent Certification:** Every resulting partition `S` has exact active capacity `flow < 9` and is verified unchanged by `cut_certificate.make_cut_certificate` / `cut_certificate.check_cut_certificate` (and `dinic_kernel.verify_9flow_min_cut` for `CertifiedDinic` networks).

## 3. Verification & Measured `III-14` (`universe_horizon` 47) Results

- **Exhaustive Optimality Check:** Verified across 20 seeded random shared-predicate DAGs (`N = 9` nodes, enumerating all `2^7 = 128` `s-t` partitions per instance) that `lawler_pareto` achieves the exact global minimum `(active_capacity, distinct_symbolic_predicates)` on `20/20` trials, and verified on shared 9-switch `landmark(t)` gadgets that 9 parallel switch-entry arcs collapse to `1` predicate (vs. `3` distinct `release` predicates under pure edge-count minimization).
- **Measured `III-14` `universe_horizon` 47 Benchmark (`evidence/2026-11-12-pareto-cuts/report.json`, 12 deficient traces spanning `flow = 0..6`):**

| Cut Selection Mode | Mean Distinct Symbolic Predicates | Mean Reduction vs. `source_minimal` | Extra Solve Cost |
| :--- | ---: | ---: | :--- |
| `source_minimal` (baseline forward BFS) | `1,895.50` | `0.00%` | `0 ms` |
| `sink_minimal` (reverse residual BFS) | `1,060.33` | `-44.06%` | `< 1 ms` (zero extra Dinic calls) |
| `min_boundary` (Picard-Queyranne edge count) | `811.08` | `-57.21%` | `~180–260 ms` |
| `lawler_pareto` (Picard-Queyranne + Lawler hyperedges) | `806.00` | **`-57.48%`** (up to **`-74.10%`**) | `~180–260 ms` |

- **Multi-Frontier Bundle Recommendation:** A single Stage-1 Dinic solve yields up to three complementary certified cuts (`source_minimal` upstream harvest cut, `sink_minimal` switch-delivery cut at zero extra flow cost, and `lawler_pareto` minimum-predicate waist cut). Defaulting single-cut emission to `sink_minimal` (fast mode) or `lawler_pareto` (exact sparse mode) directly shrinks `z3.PbGe` encodings in `global_master.add_cut`.
