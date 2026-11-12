# Soft action-priority decisions

`ActionPriority` is an optional PySAT/CaDiCaL 3.0 IPASIR-UP decision callback.
`action_preferences(aliases, hint)` orders all five action variables per frame:
it prefers the hinted action true first, and then the other actions false. This
only suggests decisions. It does not pin actions, add clauses, propagate
literals, or alter the CNF. A rejected hint is explored through normal solver
backtracking. The callback accepts every complete model; independently check
all clauses and replay any route in the original game.

Attach before solving and observe each preferred variable (observation freezes
it against elimination):

```python
from pysat.solvers import Solver
from experiments.exact_frontier.action_priority import ActionPriority, action_preferences

preferred = action_preferences(aliases, hint)
with Solver(name='cadical300', with_proof=True) as solver:
    solver.configure({'lucky': 0})
    engine = ActionPriority(preferred)
    solver.connect_propagator(engine)
    for literal in preferred:
        solver.observe(abs(literal))
    for clause in clauses:  # stream the unchanged DIMACS clauses
        solver.add_clause(clause)
    sat = solver.solve()
```

The caller owns wall-clock limits, DIMACS parsing, CNF hashing, assignment
checking, proof extraction and independent DRAT checking. This callback is not
itself a certificate. For UNSAT, only an independently verified proof supports
an encoded-CNF claim; original-game completeness requires separate evidence.

Control evidence (2026-11-12): a strengthened III-14 unrestricted horizon-48
CNF, SHA-256 `5e0a8c163be29b878ad63f0779e18690554ad7c9a3903fb792961cc6cf6eb07c`,
used the known 48-input route only as decision hints. The worker reported SAT
in 46.6 seconds including input loading, 47 external decisions and no
backtracks. An independent full-clause check passed, and browser replay in the
original game verified the known 48-input winning route. This is a positive
control, not a record. There was no matched default-solver horizon-48 run, so it
does not establish a speedup. The route and complete replay report are in the
local control evidence at `/tmp/soko-action-priority/verified.json` and
`/tmp/soko-action-priority/original-replay.json` when available.

`tests/test_action_priority.py` exercises preference validation, assignment
and fixed-literal tracking across backtracks, and satisfiable and unsatisfiable
pigeonhole formulas that require callback decisions and backtracks. The caller
still must validate any production result independently.
