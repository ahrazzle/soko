# Selected-direction transition

`encoding.trans` preserves the seven bitmask/Boolean components and one-hot
UDLRA interface of `iii14_compact.trans`. Material has no individual token
identities: walls and crates remain unlabeled masks. The selected direction is
applied at each fixed-point blocker propagation stage, so all four directions
share the same propagation chain. For each jump, precomputed source masks make
the constant-distance bit shifts exactly equal to repeated edge-masked shifts,
including for arbitrary bit patterns. The inherited shared late phase handles
note aura, Bard cancellation, switch/door state and door deletion. `build`
preserves the original initial state, hero cardinality, action names and
absorbing goal. It adds no landmark or board-reachability assumptions.

`tests/test_causal_encoding.py` checks five fixed one-hot actions on arbitrary
seven-component symbolic states, including illegal states and transitions;
all five difference queries against `iii14_compact.trans` returned UNSAT with
Z3's 10 second per-query timeout. It also replays the full original reference
route against the Python oracle, and checks builder and absorbing behavior.
This is a proof of the transition refactor relative to the compact model, not
an independent proof of that model against the original game.

Short-horizon full-builder measurements using `cnf_search.compile_cnf` with
Z3 in `/tmp/soko-exact-venv` on this workspace (no landmark constraints):

| Horizon | Encoding | Build seconds | Compile seconds | Variables | Clauses |
|---:|---|---:|---:|---:|---:|
| 1 | compact | 0.138 | 0.067 | 0 | 1 |
| 1 | causal | 0.164 | 0.146 | 0 | 1 |
| 3 | compact | 0.287 | 0.483 | 10,709 | 80,081 |
| 3 | causal | 0.330 | 1.117 | 13,008 | 83,072 |
| 5 | compact | 0.285 | 0.858 | 24,666 | 199,055 |
| 5 | causal | 0.426 | 2.113 | 28,146 | 183,931 |

Horizon 1 simplifies to an immediate contradiction in both cases. At horizon 5,
the new circuit has 7.6% fewer clauses but more variables and took longer to
compile; horizon 3 has more of both. These measurements do not establish
solver speed or performance at longer horizons.
