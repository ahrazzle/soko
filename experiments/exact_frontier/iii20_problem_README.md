# Reusable unrestricted III-20 problem

```python
from experiments.exact_frontier import iii20_problem
contract = iii20_problem.MODEL_CONTRACT
calibration = iii20_problem.calibrate(initial_samples=500, near_samples=100)
solver, actions, states = iii20_problem.build_problem(horizon)
```

The builder reads the canonical original 15×9 III-20 grid from the shipped
catalog. Its formula depends on that initial state, game transitions, and the
requested horizon. It contains no reference-route, prefix, switch-time, guide,
milestone, external lower-bound, or neighborhood restrictions. The reference
route is used only by the separate calibration routine.

Every step has native Boolean U/D/L/R/A aliases named `action_<step>_<key>`.
Each state contains five hero masks, goblins, crates, walls (all 135 bits), and
the active-role index (three bits, explicitly constrained to 0…4). Fighter
chains and Wizard rays use logarithmic bitvector propagation. Combat and Priest
shielding are simultaneous. Actual blocked inputs preserve the board. Druid
petrification of inactive heroes is represented, and Action skips vanished
roles. No losing hero-sacrifice states are silently treated as blocked inputs.
Hero death in combat is rejected. Once all five goals contain heroes, the state
absorbs remaining actions; therefore the formula asks for a first win at or
before the horizon. A decoded route must be trimmed to its first win and replayed
in the pinned original PuzzleScript build.

Default concrete calibration checks all 84 reference transitions, 500 seeded
stateful walk steps starting at the initial board, and 100 random one-step
branches from reference frames against `PuzzleScriptOracle`. Dedicated controls
cover Wizard petrification, five switches after a role disappears, simultaneous
death of two goblins during a Fighter/Priest chain push, and three subsequent
inputs. These are empirical model checks, not a proof of equivalence.

`iii20_problem_contract_check.json` records package import, native Boolean action
aliases, and an unrestricted zero-horizon UNSAT control through the shared CNF
converter and CaDiCaL. The separate reference control fixes the known route and
its independently replayed state sequence in the unrestricted builder; it does
not search for another route.

The model depends on `iii20_bitvector.py`. Both files belong in any immutable
problem bundle. For the large global five-role formula, streaming DIMACS clauses
to the backend avoids retaining both a Python list of every clause and the full
DIMACS string alongside the Z3 AST. The caller owns solver budgets, CNF/proof
artifacts, and original-build validation; this module never launches search.

Earlier scoped optimization attempts remain in `iii20_bitvector_*.json`. The
active global attempt was interrupted when the user redirected work toward the
reusable system; no further record searches were run.
