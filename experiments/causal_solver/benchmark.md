# Bounded solver comparisons

Run from the repository root in a dedicated Python environment containing `z3-solver`, `python-sat` and, optionally, `ortools`:

```sh
python -m experiments.causal_solver.benchmark --output /tmp/causal-results.json --budget 10 --events
```

The CLI runs configurations sequentially, in separate process groups, with the same per-run wall budget. It compares the retained exact compact encoding with the causal encoding on the same III-14 board, horizon, goal and action pins. Goal controls are unrestricted horizons 0, 1 and 2; the additional pinned `A` transition control removes only the terminal goal and checks satisfiable transition behavior. `--events` adds the event/bound ablation to goal cases. Set `--horizons`, `--encodings`, `--backends`, and `--repetitions` to change the comparison. Source hashes, runtime and package versions, command templates, model status, phase times, and child peak RSS are recorded in JSON. Source changes abort the experiment. Timeout kills the process group and is `unknown`, never UNSAT. A timed-out phase has incomplete timing; peak RSS is sampled while the worker runs.

SMT models are checked against the assertions. SAT and CP-SAT models are checked against every generated CNF clause, then the extracted action sequence is checked against the local concrete transition oracle. CNF conversion uses the existing propositionality-checked compiler. An UNSAT result is an unchecked solver result, not a proof certificate; independent original-engine replay is still required for a winning claim. Missing packages yield `unavailable`. CP-SAT runs with one search worker; CaDiCaL is the PySAT backend. Time measurements include Python startup in wall time and should not be generalized to other workloads or hardware.

The exploratory allocation chooses a configuration only when at least three completed same-workload repetitions agree on status, the budget is identical, and its median wall time is at least 20% faster than the next completed configuration. Otherwise the decision is inconclusive. This simple threshold is a scheduling heuristic, not a statistical guarantee or evidence of a general speedup. Look at phase profiles and rerun representative larger horizons before allocating substantial compute. Unavailable and timed-out configurations cannot win.
