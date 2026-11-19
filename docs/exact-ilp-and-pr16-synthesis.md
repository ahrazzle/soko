# Retroactive PR #16 Synthesis & Exact Four-Phase 0-1 ILP Formulation

*Recorded 2026-11-12 by `mithrax` (`mithrax-exo`, Gemini seat) — retroactive capture of pre-login design analysis and exact whole-game mathematical formulation, reconciled against `main` (`81aed4f`, PRs #16–#24).*

## 1. Retroactive PR #16 Architectural Review & Reconciliation with PRs #17–#24

Reviewing PR #16 (`4ab0e41`, *Decompose III-14 material allocation into conditional matching and flow*) identified five concrete extensions to close the gap between the 9-token frame-43 switch projection and global exact lower-bound proofs:

1. **Pareto-Optimal / Minimum-Symbolic-Support Benders Cuts (Open — Next Target on `dinic_kernel.py`):**
   - When the 9-token capacity network has max-flow $k < 9$, many minimum $s$-$t$ cuts typically coexist. Standard residual reachability from $s$ returns the source-closest cut, which may cross an unnecessarily large set of hero-dependent symbolic boundary arcs.
   - Selecting among minimum-capacity cuts one that **minimizes symbolic boundary edge count** (e.g., via lexicographic edge weights $M \cdot c(e) + \mathbb{I}[e \in E_{\text{sym}}]$ in integer Dinic, or comparing source-side vs. sink-side residual closures) yields shorter conflict clauses in the global hero master while remaining 100% checkable by `verify_9flow_min_cut` (added by `orda-aska` in PR #24).
2. **Lazy Replay / Causal Coupling Refinement for Step-26 Gaps (Addressed in PR #21, Extensible to Hybrid Cut Selection):**
   - PR #16 showed that the 47-input flow candidate diverged during concrete replay at input 26 due to relaxed unselected/pre-release materials. PR #21 (`b760a1c`, Terra/Sol/Astra) implemented deterministic completion and rechecked prefix contradictions, rejecting `spurious47` in 0.293s, though unrestricted H47 still timed out at 120s after 150 cuts—underscoring the need for sparser, higher-propagation cuts above.
3. **Vertex-Split Swap & Contention Prevention in Time-Expanded Flow:**
   - Enforcing $(v, t)_{\text{in}} \to (v, t)_{\text{out}}$ unit vertex capacities and opposing-edge swap exclusions preserves total unimodularity and polynomial max-flow runtime while tightening pre-replay feasibility.
4. **Incremental Prefix Cut & Admissible Bound Pruning (Open — Connects Directly to Issue #22):**
   - Evaluating admissible remaining-step bounds on partial prefixes prunes unviable branches well before full horizon expansion (particularly critical on `III-21` gap 48 and `III-14` gap 5 identified in Issue #22 and PR #23).
5. **Standalone Kernel-Checkable Cut Certificates (Landed in PR #24):**
   - Partition membership + integer cross-cut capacity summation $< 9$ avoids trusting external SMT solver traces; PR #24 landed `CertifiedDinic` and `verify_9flow_min_cut` in `experiments/transport_relaxation/dinic_kernel.py`.

---

## 2. Exact Four-Phase 0-1 ILP / CP-SAT Formulation (`soko_mcp/flat_oracle.py`)

To represent every element of *Heroes of Sokoban I–III* (`soko_mcp/flat_oracle.py`, `soko_mcp/original.py`) as decision/state variables for exact step minimization over $t \in \{0, \dots, T_{\max}\}$, each step $t \to t+1$ is factored through an intermediate post-action board buffer $\tilde{s}_t$:

$$s_t \xrightarrow{\text{Phase 1: Action / Class Rule}} \tilde{s}_t \xrightarrow{\text{Phase 2: Combat + Priest Shield}} \xrightarrow{\text{Phase 3: Switches + Doors}} \xrightarrow{\text{Phase 4: MGate + Goal } z_{t+1}} s_{t+1}$$

### 2.1 Grid Parameters & Variable Dictionary

Let $V = \{0, \dots, n - 1\}$ index the $W \times H$ board in column-major order $v = xH + y$ (`MAX_CELLS = 512`), with static floor masks $G_v$ (`goals_mask`), $S^Y_v$ (`ysw_mask`), $S^P_v$ (`psw_mask`), $D^{Y,0}_v$ (`ydoor_init_mask`), $D^{P,0}_v$ (`pdoor_init_mask`), neighbor map $\nu(v, d)$, 4-neighborhood $N_4(v)$, and $5 \times 5$ Chebyshev mask $N_{5\times 5}(v)$ (`aura5x5_mask`).

| Variable | Domain | Game Element | Engine Mapping (`flat_oracle.py` / `model.py`) |
| :--- | :--- | :--- | :--- |
| $z_t$ | $\{0,1\}$ | Absorbing goal-reached indicator at frame $t$ | `hero_mask == goals_mask` |
| $u_{t,a}$ | $\{0,1\}$ | Player input $a \in \{\text{U}, \text{D}, \text{L}, \text{R}, \text{A}\}$ at step $t$ | `action_{t}_{act}` |
| $h_{t,k,v}$ | $\{0,1\}$ | Hero $k \in \{\text{F},\text{T},\text{W},\text{P},\text{B},\text{D}\}$ occupies cell $v$ | `_ACT_F.._ACT_D` (`1..6`), `_INA_1.._INA_6` (`7..12`) |
| $\alpha_{t,k}$ | $\{0,1\}$ | Party-active flag for hero $k$ ($1$ active, $0$ inactive) | `active_{t}` / party slot |
| $p^{\text{ina}}_{t,k,v}$ | $\{0,1\}$ | Inactive hero $k$ at cell $v$, linearizing $h_{t,k,v}(1 - \alpha_{t,k})$ | Moveable `_INA_1.._INA_6` |
| $w_{t,v}$ | $\{0,1\}$ | Wall at cell $v$ (dynamic in Part 3 via Druid morphs) | `_WALL` (`13`) |
| $c_{t,v}$ | $\{0,1\}$ | Pushable crate / material block at cell $v$ | `_CRATE` (`14`) |
| $g_{t,v}, d^L_{t,v}, d^R_{t,v}$ | $\{0,1\}$ | Goblin (`15`) and $2 \times 1$ Dragon halves (`16`, `17`) at $v$ | `_GOBLIN`, `_DRAG_L`, `_DRAG_R` |
| $q^Y_{t,v}, q^P_{t,v}, q^M_{t,v}$ | $\{0,1\}$ | Closed Yellow Door (`18`), Purple Door (`19`), Monster Gate (`20`) | `_YDOOR`, `_PDOOR`, `_MGATE` |
| $e_{t,v}$ | $\{0,1\}$ | Empty floor tile at cell $v$ | `_EMPTY` (`0`) |
| $y^{\text{open}}_t, p^{\text{open}}_t, m^{\text{clear}}_t$ | $\{0,1\}$ | Yellow/Purple door open flags and monster-cleared flag | `y_open`, `p_open`, `not any(is_monster)` |
| $\sigma_{t,v}, \eta_{t,v}$ | $\{0,1\}$ | Priest orthogonal shield and Bard $5 \times 5$ note at $v$ | `shield_mask`, `notes_mask` |
| $\pi^{\text{F}}_{t,d,v}, \pi^{\text{T}}_{t,d,v}, \rho^{\text{W}}_{t,d,u,v}, \tau^{\text{D}}_{t,d,v}$ | $\{0,1\}$ | Class action indicators (push ray, pull, LoS swap, morph) | Phase 1 class transitions |

### 2.2 Objective & Absorbing Horizon Stuttering

$$\min \sum_{t=0}^{T_{\max}-1} (1 - z_t)$$

subject to exact goal matching, monotone absorption, and input gating:

$$z_t \le \sum_{k} h_{t,k,v} \;\;(\forall v : G_v = 1), \qquad z_t \le 1 - \sum_{k} h_{t,k,v} \;\;(\forall v : G_v = 0), \qquad z_{t-1} \le z_t, \qquad z_{T_{\max}} = 1$$

$$\sum_{a \in \{\text{U},\text{D},\text{L},\text{R},\text{A}\}} u_{t,a} = 1 - z_t \quad \forall t \in \{0, \dots, T_{\max}-1\}$$

### 2.3 Single-Occupancy Partition & Four-Phase Linear Constraints

At every frame $t$ (and post-movement frame $\tilde{s}_t$), cell occupancy forms a strict partition while enforcing `hero_died == False` as a hard survival invariant:

$$e_{t,v} + w_{t,v} + c_{t,v} + g_{t,v} + d^L_{t,v} + d^R_{t,v} + q^Y_{t,v} + q^P_{t,v} + q^M_{t,v} + \sum_{k} h_{t,k,v} = 1 \quad \forall v \in V$$

$$\sum_{v \in V} h_{t,k,v} = 1 \quad \forall k, \qquad \sum_{k} \alpha_{t,k} = 1$$

With $p^{\text{ina}}_{t,k,v} \le h_{t,k,v}$, $p^{\text{ina}}_{t,k,v} \le 1 - \alpha_{t,k}$, and $p^{\text{ina}}_{t,k,v} \ge h_{t,k,v} - \alpha_{t,k}$, composite moveable presence is linear: $\mu_{t,v} = c_{t,v} + g_{t,v} + d^L_{t,v} + d^R_{t,v} + \sum_k p^{\text{ina}}_{t,k,v}$.

1. **Phase 1 — Party Switch (`A`) & Class Abilities (`U, D, L, R`) into $\tilde{s}_t$:**
   - **Party switch (`A`):** $u_{t,\text{A}} = 1 \implies \tilde{s}_t = s_t$ and cyclic slot rotation $\alpha_{t+1, (k \bmod K)+1} \ge \alpha_{t,k} + u_{t,\text{A}} - 1$.
   - **Fighter (`F`) push chain:** $\pi^{\text{F}}_{t,d,v} \in \{0,1\}$ propagates along contiguous $\mu_{t,v} = 1$ cells from Fighter's neighbor if terminated by $e_{t,\nu(v_{\text{end}}, d)} = 1$, advancing all pushed entities by one cell along $d$.
   - **Thief (`T`) pull:** Stepping from $u$ into empty $\nu(u, d)$ activates $\pi^{\text{T}}_{t,d,u} = 1$, pulling any moveable at $\nu(u, -d)$ into $\tilde{s}_{t,u}$.
   - **Wizard (`W`) LoS swap:** $\rho^{\text{W}}_{t,d,u,v} = 1$ selects the first moveable $v$ along ray $(u, d)$ when all intermediate cells satisfy $e_{t,w} = 1$, swapping Wizard and target; if blocked first by a static obstacle, falls back to a 1-step empty move.
   - **Bard (`B`) $5 \times 5$ note march:** Moveables inside $N_{5\times 5}$ of active Bard carry $\eta_{t,v} = 1$ and advance along $d$ into empty cells in column-major scan order (`idx = x * H + y`), followed by updating $\eta_{t+1,v}$ around Bard's post-move $5 \times 5$ aura.
   - **Druid (`D`) shapeshifting:** Moving from $u$ toward $v = \nu(u, d)$ steps into $v$ if $e_{t,v} = 1$, or holds Druid at $u$ while firing $\tau^{W\to C}_{t,d,v}$ (`_WALL` $\to$ `_CRATE`) or $\tau^{C/G\to W}_{t,d,v}$ (`_CRATE`/`_GOBLIN` $\to$ `_WALL`), with unshielded hero crushing forbidden by $h_{t,k,v} + \alpha_{t,\text{D}} + u_{t,d} - \sigma_{t,v} \le 2$ ($k \neq \text{P}$).
2. **Phase 2 — Monster Melee/Rays vs. Priest Shield:**
   $$\tilde{\sigma}_{t,v} \le \sum_{u \in \{v\} \cup N_4(v)} \tilde{h}_{t,\text{P},u}, \qquad \tilde{\sigma}_{t,v} \ge \tilde{h}_{t,\text{P},u} \;\;\forall u \in \{v\} \cup N_4(v)$$
   $$\tilde{h}_{t,k,v} + \tilde{g}_{t,u} - \tilde{\sigma}_{t,v} \le 1 \;\;\forall u \in N_4(v), \qquad \tilde{h}_{t,k,v} + \tilde{d}^{L/R}_{t,u} - \tilde{\sigma}_{t,v} - \sum_{w \in \text{row}(u,v)} (1 - \tilde{e}_{t,w}) \le 1$$
3. **Phase 3 — All-Weighed Switches & Door Anti-Crush:** With $\omega_{t,v} = 1 - \tilde{e}_{t,v} - \tilde{q}^Y_{t,v} - \tilde{q}^P_{t,v} - \tilde{q}^M_{t,v}$,
   $$y^{\text{open}}_{t+1} \le \omega_{t,v} \;\;(\forall v : S^Y_v = 1), \qquad y^{\text{open}}_{t+1} \ge 1 - \sum_{v : S^Y_v = 1} (1 - \omega_{t,v}), \qquad q^Y_{t+1,v} = D^{Y,0}_v (1 - y^{\text{open}}_{t+1})$$
   (symmetrically for $p^{\text{open}}_{t+1}, q^P_{t+1,v}$), plus $\tilde{h}_{t,k,v} + q^Y_{t+1,v} \le 1$ and $\tilde{h}_{t,k,v} + q^P_{t+1,v} \le 1$.
4. **Phase 4 — Monster Gate (`_MGATE`) Release (Part $\ge 2$):** With $M_t = \sum_{v \in V} (\tilde{g}_{t,v} + \tilde{d}^L_{t,v} + \tilde{d}^R_{t,v})$, $M_t \le |V|(1 - m^{\text{clear}}_{t+1})$, $m^{\text{clear}}_{t+1} \ge 1 - M_t$, and $q^M_{t+1,v} \le \tilde{q}^M_{t,v}(1 - m^{\text{clear}}_{t+1})$.

### 2.4 Eulerian-Lagrangian Flow Linking & Directional Bottleneck Bounds

- **Arc-flow conservation linking:** Coupling cell occupancy $c_{t,v}$ with binary arc flows $f^c_{t,u,v} \in \{0,1\}$ and Druid birth/death indicators ($c_{t,u} = \sum_v f^c_{t,u,v} + \sum_d \tau^{C\to W}_{t,d,u}$ and $\tilde{c}_{t,v} = \sum_u f^c_{t,u,v} + \sum_d \tau^{W\to C}_{t,d,v}$) exposes total-unimodularity network cuts directly to the LP/CP-SAT presolver.
- **Implication for Issue #22 Admissible Lower Bounds:** Even when Bard's $5 \times 5$ aura, Fighter push chains, or Thief pulls move multiple entities on a single step $d \in \{\text{U},\text{D},\text{L},\text{R}\}$, every moved entity (in rooms without Wizard ray-swaps) advances in the **same** cardinal direction $d$ by at most $1$ cell. Hence directional deficit maxima across the four cardinal directions ($\max_i \Delta^{\text{L}}_i + \max_i \Delta^{\text{R}}_i + \max_i \Delta^{\text{U}}_i + \max_i \Delta^{\text{D}}_i$, minimized over goal bijections) decrease by at most $1$ per directional move—providing a mathematically sound multi-piece lower bound where naive Manhattan summation fails.
