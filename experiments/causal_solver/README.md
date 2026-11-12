# Full-mechanics tractability experiments

This package implements the nine workstreams in [PLAN.md](PLAN.md), shared in
[PR #21](https://github.com/ahrazzle/soko/pull/21) before implementation. It targets
original III-14 and preserves the bounded objective: find any win in at most H
inputs. It does not fix a route, control schedule, material count, or packing
pattern. The separately labeled controls deliberately fix reference traces.

## Run the integrated system

```sh
python -m venv .venv-causal
.venv-causal/bin/pip install -r experiments/causal_solver/requirements.txt
.venv-causal/bin/python -m playwright install chromium

# Positive and negative controls:
.venv-causal/bin/python -m experiments.causal_solver.search --horizon 48 --budget-seconds 30 --control reference --output /tmp/causal-reference.json
.venv-causal/bin/python -m experiments.causal_solver.search --horizon 47 --budget-seconds 30 --control spurious --output /tmp/causal-spurious.json

# One unrestricted bounded query:
.venv-causal/bin/python -m experiments.causal_solver.search --horizon 47 --budget-seconds 120 --symmetry --output /tmp/causal-global.json
```

Pass `--html PATH --chromium PATH` to use a cached, hash-checked original build
and a system browser. Without a supplied HTML file the existing original-engine
adapter uses its pinned download/cache mechanism. Use a new output path per run.

The master chooses actions, both heroes and a common material landmark. An
absorbing terminal frame preserves positions **and active identity**, so a real
shorter win can be padded after victory. The old flow master's artificial
initial held inputs are not used as original-game steps.

With `--phase-order exact-first`, each complete proposed input sequence gets
full-material exact completion. A fixed sequence determines all walls, crates,
notes, doors and heroes; this is direct propagation, not a new existential SAT
problem. A mismatched hero assertion produces a prefix contradiction. Its
independent checker replays the retained transition and Python oracle before
the master receives a clause excluding that prefix/assertion combination and
all of its suffixes. A timeout never produces a clause.

`--phase-order flow-first` runs the universal material-flow subproblem first,
adding an independently checked capacity cut when fewer than nine paths exist.
Feasible flow proceeds to exact completion. A locally winning route is always
sent to the pinned original engine; unrestricted wins additionally trigger a
fresh Frontier comparison before any record claim. The reference control
explicitly checks flow, exact completion and original replay.

## Implementation map

| Requested work | Implementation | Verification |
|---|---|---|
| 1. Compact movement causes | [encoding.py](encoding.py): select direction before shared blocker propagation | Five action-partitioned arbitrary-state equivalence queries, all UNSAT against retained compact transition |
| 2. Every relevant material | Complete seven-field bitmask state in exact transitions and [refinement.py](refinement.py) | Additional wall/crate blocker fixtures, conversion, cancellation, notes, door deletion and hero loss |
| 3. Necessary events | [events.py](events.py): guarded release/seen recurrence, landmark readiness and control events | Independent concrete event extraction and planted premature event claims |
| 4. Remaining-input bounds | Joint hero travel plus disjoint release/control costs | [Quantified argument](event_bounds.md), exhaustive small movement checks and reference acceptance |
| 5. Automatic exact refinement | Typed prefix/core certificates, independent replay and master clauses | Known 48 accepted, spurious 47 rejected, changed certificates/unknowns cannot cut |
| 6. Equivalent choices | Unlabeled material bitmasks, complete state keys, optional proven AA/no-op normalization | Settled-state AA identity, exhaustive short trace endpoint/cost checks; no unsupported spatial symmetry |
| 7. Solver/encoding selection | [benchmark.py](benchmark.py), [backends.py](backends.py): SMT, SAT and CP-SAT with event ablation | Identical workload/pins/budget; checked models, measured build/compile/solve phases |
| 8. Diagnostic benchmark | [controls.py](controls.py) | 150 exhaustive short transitions, ten planted errors, reference and spurious route checks |
| 9. Compute allocation | Bounded worker process groups, durable phase profiles, conservative measured-choice policy | Timeout tests; three repetitions required and a 20% median margin before a same-workload winner is suggested |

`--symmetry` is an existence-preserving normalization, not a claim that every
raw action trace satisfies it. It removes preterminal AA pairs in the master;
the exact event adapter can additionally remove complete-state no-ops. A hero
hold alone is never removed: it may perform an essential conversion.

## Measure instead of assuming a speedup

```sh
python -m experiments.causal_solver.controls --output /tmp/mechanics-controls.json
python -m experiments.causal_solver.benchmark --output /tmp/backend-comparison.json --horizons 5 --pins AAAAA --mode transition --budget 8 --repetitions 3
python -m experiments.causal_solver.benchmark --output /tmp/event-comparison.json --horizons 0,1 --events --budget 3 --repetitions 3
python -m unittest discover -s tests -p 'test_causal_*.py'
python -m unittest tests.test_exact_refinement
```

CP-SAT here receives the same Boolean CNF used for the SAT comparison; this
isolates backend behavior. It is not a bespoke high-level scheduling encoding.
The alternative causal circuit is optional: fewer clauses on one short horizon
did not translate into lower total time in the recorded controls. The compact
encoding remains the default. Small pinned controls cannot establish which
backend will solve the unrestricted 47-input query fastest.

The measured default leaves optional numeric event bounds disabled. A matched
47-input master query produced an assignment in 1.87 seconds without them;
both integer and equivalent finite-bitvector bounds reached their 20-second
budgets without an assignment. Enable them explicitly with `--events`, or
`--events --event-encoding bitvector`. They remain implemented, checked and
available for ablation. Full exact mechanics and certificate checks are always
required. The `--symmetry` normalization works independently of these bounds.

See [execution evidence](../../evidence/2026-11-12-causal-tractability/README.md)
for measured outcomes, regression results and archived certificate replay.

## Claim boundaries

Deterministic prefix certificates establish contradictions by exact propagation
under pinned modeled mechanics, independently compared with a Python oracle.
Partial-assumption SMT certificates are replay recipes checked in a fresh
unpinned solver. They are not standalone DRAT proofs. Master UNSAT is labeled
`solver_global_unsat`, with no independently proved bound claimed by this driver.
Resource limits remain `unknown`. Symbolic one-step equivalence to a retained
encoding does not prove that either encoding equals the original game for all
histories. Original-engine replay is mandatory for winning-route claims.
