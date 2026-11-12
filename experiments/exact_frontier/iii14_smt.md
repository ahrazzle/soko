# III-14 bounded bitvector experiment

Run with Python with `z3-solver` installed from the repository root:

```
python experiments/exact_frontier/iii14_smt.py --validate
python experiments/exact_frontier/iii14_smt.py --n 48 --prefix LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR
python experiments/exact_frontier/iii14_smt.py --n 47 --timeout 60000
```

The model covers the original 15x7 board, including mutable boundary walls. Each frame has 105-bit wall, crate, Bard, Druid, and note masks, active-hero and door-open booleans, and five one-hot Boolean actions. Druid transforms first; Bard movement is a bounded fixed point, so blocked charmed objects can remain independently. A Bard unable to move cancels the whole turn. Notes are computed before the late door phase and surviving notes retained. Closing doors erase nonhero objects and kill heroes; hero death and petrification of the Bard are excluded because the two distinct heroes are needed to occupy both goal cells. All other cells, including border cells, are modeled. Door actions are based on weights on all nine switches.

The goal is absorbing: horizon N represents a first win at or before N, with extraction truncated at first win. A solver timeout is `unknown`, never a proof of impossibility. The external public lower bound is not assumed. Fixed prefixes and positional Hamming neighborhoods (`--prefix`, `--guide`, `--distance`) intentionally restrict the search and cannot support an unrestricted impossibility claim. For prefix efficiency, its exact Python-oracle states are asserted alongside model transition equations. The programmatic `build(..., construct_only=True)` returns solver, per-step one-hot actions named `action_{step}_{letter}`, and state variables.

Calibration: the baseline and 410 seeded random surviving short traces matched the Python oracle at every frame (seed 7314, 500 attempted, lengths 1–30); losing branches are intentionally pruned. A 48-step pinned baseline with every oracle frame asserted was SAT (2.66s solve, 2.02s build). The reference solution is a public accepted original-game record. These checks are empirical calibration and do not prove full semantic equivalence.

Unrestricted Z3 checks with a 60,000 ms timeout returned `unknown` for N=48 (66.02 s wall solve) and N=47 (64.96 s wall solve); neither establishes a bound. These queries made no assumptions about the number of crates or final door state.

The fixed prefix `LLULULULURURURURU` and positional Hamming distance <=6 to `LLULULULURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR`, at N=47, also timed out as unknown (63.88 s). This neighborhood is incomplete.

`--milestone` changes the final condition: switches (6,3), (6,4) are walls and the other seven switches are crates; active Bard is at (6,5), inactive Druid at (8,5), and doors are open. On success the program appends `RRRUU`, validates the complete route, and requires first win on its last input. The milestone is a deliberately narrow witness search, so failure proves nothing about other winning configurations.

The milestone at N=42 with prefix `LLULULULRURURURURUAUDRRDDRRDRUL` returned unknown after 61.22 s (60 s solver budget). The prefix ends in a reachable early-open position and is useful for further suffix search.

The unrestricted <=47 suffix from the same 31-input prefix returned unknown after 61.55 s. After these runs, the Bard fixed point was replaced by four doubling stages; this version also matched the baseline and all 410 surviving seeded random traces. The pinned 48 control with `--onehot` returned SAT (1.74 s build, 0.75 s solve). `--onehot` adds redundant one-hot hero constraints and is intended as a solver performance option.

A further 100 baseline-prefix random-suffix tests (seed 149314) included door-open positions; 89 survived the loss checks and matched every frame. Run `--validate-near` to repeat them. A scoped N=40 query from the same 31-input prefix with `--onehot` returned unknown after 30.62 s. Full machine-readable settings and outcomes are in `iii14_smt_runs.json`.
