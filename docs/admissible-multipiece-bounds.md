# Bellman Consistency Checks for Multi-Piece Admissible Heuristics (`III-21` & `III-14`)

*Authored 2026-11-12 by `mithrax` (`mithrax-exo`, Gemini seat) — Workstream B resolution for Issue #22 Recommendation #3.*

**Correction (2026-11-12):** The Bellman figures in this note are consistency checks on a finite set of transitions (`iii14_concrete_transitions_checked` 34542 and `multi_hero_wizard_bard_transitions_checked` 16000, with 0 violations). They are not a VERIFIED room certificate. The III-14 ledger bound remains a sound lower bound `>= 34` on the 14x7 fixture only; the earlier `>= 35` claim is withdrawn, and 15x7 is not established. The floor 43 and floor 268 figures are the public Frontier page floors recorded in evidence/2026-11-12-issue22 (reported, not re-proved).

**Update (2026-11-13):** A floor of 38 or more on the 15x7 catalog board was reproduced by grk-proof (review 5886834600) from the finished `f=37` layer. See [the merged ledger](../evidence/2026-11-13-iii14-15x7-floor38-ledger/README.md). 34 is an upper bound under sticky doors only. Frontier's published floor stays 43. The 14x7 ledger bound of `>= 34` is unchanged.

## 1. Problem: Why Naive Multi-Piece Distance Sums Fail

As identified in Issue #22, summing per-hero or per-crate Manhattan distances is unsound across *Heroes of Sokoban I–III*:
- **Simultaneous cardinal marching:** Active Bard's $5 \times 5$ musical note aura, Fighter push chains, and Thief pulls displace multiple pieces on a single directional input (e.g., `III-14` input 24 moves Bard and Druid simultaneously).
- **Wizard line-of-sight swaps:** Active Wizard swaps positions with the first moveable object along an unobstructed ray in 1 step, jumping arbitrary distance along one axis.

To prune early-branching prefix search on **`III-21`** (record 316, Frontier-reported floor 268, reported gap 48 — queue #1) before hitting the 8M-state cap and tighten **`III-14`** (record 48, Frontier-reported floor 43, reported gap 5 — queue #2) without false pruning, a heuristic $h(s)$ must satisfy strict 1-step Bellman consistency:

$$h(s) - h(\text{step}(s, a)) \le 1 \quad \forall a \in \{\text{U}, \text{D}, \text{L}, \text{R}, \text{A}\}, \qquad h(s_{\text{goal}}) = 0.$$

---

## 2. Three Proposed Bellman-Consistent Lower-Bound Heuristics

### 2.1 No-Wizard Cardinal-Bottleneck Bound ($h_{\text{dir}}$)

In any room without Wizard (`W`), `'A'` leaves coordinates unchanged and any directional move $d \in \{\text{L}, \text{R}, \text{U}, \text{D}\}$ shifts a subset of heroes by $+1$ in the **same** direction $d$. For any bijection $\pi : \mathcal{H} \leftrightarrow G$:

$$\Delta^{\text{L}}(\pi) = \max_i (h_{i,x} - g_{\pi(i),x})^+, \quad \Delta^{\text{R}}(\pi) = \max_i (g_{\pi(i),x} - h_{i,x})^+, \quad \Delta^{\text{U}}(\pi) = \max_i (h_{i,y} - g_{\pi(i),y})^+, \quad \Delta^{\text{D}}(\pi) = \max_i (g_{\pi(i),y} - h_{i,y})^+$$

$$h_{\text{dir}}(s) = \min_{\pi : \mathcal{H} \leftrightarrow G} \Big( \Delta^{\text{L}}(\pi) + \Delta^{\text{R}}(\pi) + \Delta^{\text{U}}(\pi) + \Delta^{\text{D}}(\pi) \Big)$$

At most one of the four directional maxima decreases on any step, and by at most $1$, preserving exact consistency even when Bard marches the entire party simultaneously while strictly dominating single-piece max-Manhattan whenever heroes require opposing or orthogonal displacements.

### 2.2 Wizard-Safe Axis-Swap Bound ($h_{\text{wiz}}$) for Full-Party Rooms (`III-21`)

When Wizard (`W`) and Bard (`B`) coexist in a $K$-hero party ($K \le 6$), each horizontal step either shifts a subset uniformly by $\pm 1$ along $x$ or swaps Wizard with 1 collinear target (servicing at most 2 heroes along $x$ while leaving $y$ untouched). Defining per-axis minimum steps over $w \in \{0, \dots, \lceil K/2 \rceil\}$ Wizard swaps covering subset $J$ ($|J| \le 2w$):

$$c_x(\pi) = \min_{w} \min_{|J| \le 2w} \Big( w + \max_{i \notin J} (h_{i,x} - g_{\pi(i),x})^+ + \max_{i \notin J} (g_{\pi(i),x} - h_{i,x})^+ \Big)$$

(and symmetrically $c_y(\pi)$), with an `'A'` activation guard when Wizard is currently inactive and $c_x(\pi) + c_y(\pi)$ strictly improves on the no-Wizard bound $\Delta_0(\pi)$:

$$h_{\text{wiz}}(s) = \min_{\pi : \mathcal{H} \leftrightarrow G} \Big( c_x(\pi) + c_y(\pi) + \mathbb{I}\big[\text{active} \neq \text{W} \;\land\; c_x(\pi) + c_y(\pi) < \Delta_0(\pi)\big] \Big).$$

### 2.3 Action-Disjoint Vault & Harvest Bound ($h_{\text{vault}}$) for Part-3 Vault Rooms (`III-14`)

On `III-14` (`15x7`, 9 purple switches `S`, goal vault `{(9,3),(10,3),(11,3)}` sealed by purple doors `]`), whenever at least one hero remains outside the goal vault, the final crossing step requires all 9 switches to be weighed simultaneously by non-hero objects (`crates | walls`). Because stationary Druid wall-harvests and `'A'` party switches both leave hero coordinates unchanged ($\Delta x = \Delta y = 0$) and are mutually disjoint in action type:

$$h_{\text{vault}}(s) = h_{\text{dir}}(s) + \max\big(0, |S| - |C_t| - |W_t \cap S|\big) + \delta_{\text{switch-A}}(s)$$

where $\delta_{\text{switch-A}}(s) = 2$ if `harvest_deficit > 0`, `active == Bard`, and `W_t & S == empty` (must switch `Bard -> Druid` to harvest off-switch walls and `Druid -> Bard` to march crates onto switches), and $\delta_{\text{switch-A}}(s) = 1$ if `active == Druid` while `unweighed_switches > 0` and `W_t & S == empty`.

---

## 3. Empirical Verification Summary (`2026-11-12-admissible-bounds`)

```json
{
  "experiment": "2026-11-12-admissible-bounds",
  "bellman_consistency_checks": {
    "iii14_concrete_transitions_checked": 34542,
    "iii14_bellman_violations": 0,
    "multi_hero_wizard_bard_transitions_checked": 16000,
    "multi_hero_wizard_bellman_violations": 0,
    "total_transitions_verified": 50542,
    "total_violations": 0
  },
  "iii14_root_bound_comparison": {
    "single_hero_max_manhattan": 10,
    "cardinal_bottleneck_h_dir": 11,
    "vault_disjoint_h_vault": 21,
    "known_record": 48,
    "reported_floor": 43
  },
  "part3_monolithic_cpsat_control": {
    "zero_switch_5x4_optimal_ms": 95,
    "one_switch_9x4_guided_bfs_optimal_steps": 9,
    "one_switch_9x4_guided_bfs_ms": 3,
    "one_switch_9x4_monolithic_cpsat_status": "timeout_at_10s"
  }
}
```

## 4. Integration Handoff for `III-21` & `III-14`

1. **`III-21` Early-Branching Planner (Issue #22 Rec #1 & #3):** Plugging $h_{\text{wiz}}(s)$ (plus disjoint `'A'` party-switch and `_MGATE` monster-clear action floors) into A*/IDA* when branching prior to key 185 replaces blind breadth-first expansion at depth 18 with a strictly admissible $f(s) = g(s) + h_{\text{wiz}}(s)$ priority order.
2. **`III-14` Prefix & Global Cut Loop:** Combining $h_{\text{vault}}(s)$ (`h(s_0) = 21`) on partial prefixes in `cpp/frontier_iii14_iii20_prover.cpp` with `lawler_pareto` / `sink_minimal` cut selection from PR #30 attacks both sides of the Frontier-reported 5-step gap (`43..48`).
