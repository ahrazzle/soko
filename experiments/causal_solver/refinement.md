# Exact completion and checked contradiction learning

`refinement.py` retains all walls and crates on the original board. It never
assumes that the abstraction's selected-token landmark is an exact all-material
landmark. `ExactRefiner(H, encoding='compact')` accepts `compact`, `legacy` and
`causal`; optional event and global landmark clauses are absent.

`check(assignment, timeout_seconds)` takes a complete route and H+1 hero frames.
A complete route determines every exact material state from the fixed initial
state. The implementation therefore evaluates the selected exact transition on
constants, in linear time in route length for this fixed board. Goal frames
absorb every state component, including active hero. The first inconsistent
hero/active frame yields the action prefix and offending equality as a core;
an illegal hero loss yields its action prefix; failure of the terminal goal
yields all H actions. SAT means the exact modeled route wins, and still requires
original-engine replay before reporting a puzzle record.

The quantified reason these cuts are sound is determinism. For every exact
winning history of horizon H, fixing actions 0 through t-1 fixes frame t,
including all unselected material. If this unique frame differs from the stated
hero equality, no suffix can repair that equality. Thus E_H AND core is UNSAT,
and the disjunction of negated core equalities is necessary for every exact
winning history. The same argument rejects a prefix losing a required hero,
or a fully fixed route with a false terminal goal. This is generalization over
all omitted hero choices and all omitted suffix actions, not a claim that a
shorter winning route was ruled out.

For arbitrary partial assumptions, `check_assumptions(descriptors, timeout)`
builds the full bounded SMT problem lazily. Fresh assumption literals imply
individual exact equalities, and `solver.check(*assumptions)` supplies its core.
Redundant prefix-to-state implications expose deterministic constant propagation
hidden by guarded assumptions. Their hypotheses are only the corresponding
exact action prefix, so they add no search restriction. A fresh certificate
solver reconstructs these implications using only the actions in its core.

Certificates pin the original source identifier, actual board hash, horizon,
encoding, mechanics files, catalog, frontier snapshot, and checker source.
Payload hashes detect corruption. Recorded `validation` strings grant no trust.
`check_certificate` rechecks only the core: SMT cores require UNSAT in a fresh
full solver; deterministic prefix cores require a fresh retained exact
transition replay and framewise agreement with the independent Python oracle.
The latter is an executable deterministic proof that E_H AND core is UNSAT,
without invoking a global SMT search. It is not a standalone SAT proof file or
a proof of full original-game/model equivalence.

`add_core_cut(master, certificate, timeout)` repeats this independent check,
then maps core equalities to the master's actions, coordinates and active hero.
Rejected, open, SAT and unknown rechecks never mutate the master. Zero budgets
remain unknown. No original-game input is invented to pad a prefix.

Controls are in `tests/test_exact_refinement.py`: the known 48-input execution
is retained; the constructed 47-input projection is rejected and independently
rechecked; absorbing goal activity and Druid petrification are tested; small
partial-core examples exclude multiple assignments; corrupt, rehashed
satisfiable, and timeout certificates cannot install cuts.

Run:

```sh
/tmp/soko-exact-venv/bin/python -m unittest tests.test_exact_refinement -v
```
