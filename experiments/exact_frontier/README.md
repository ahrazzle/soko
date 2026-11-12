# Global record queries

This is a system for asking one unrestricted bounded question: **does any route
win in fewer inputs than the observed record?** It supports III-14 and III-20.
It has not yet produced a new record. III-21 and the remaining rooms do not yet
have symbolic models here; the main MCP catalog and replay tools cover all 66.

The entry point is `record_system.py`. A record query never fixes a prefix,
hero-switch schedule, excavation pattern, packing plan, or goal assignment.
The incumbent supplies the input budget only. The final state is absorbing,
so a horizon of 47 includes every modeled first win at **or before** 47 inputs.

## Run from a checkout

```sh
python -m venv .venv-exact
.venv-exact/bin/pip install -r experiments/exact_frontier/requirements.txt
.venv-exact/bin/python -m playwright install chromium

# A single global query, with a one-hour solve-and-certificate budget:
.venv-exact/bin/python -m experiments.exact_frontier.record_system run \
  --room III-14 --output /tmp/iii14-global --timeout-seconds 3600
```

Preparation fetches and saves the live Frontier observation, calibrates the
transition model, then compiles `win_by(record - 1)` to CNF. There is no outer
loop of route guesses, repair windows, or randomized restarts. The SAT solver
still branches internally; one formulation does not guarantee a quick answer.
The solve budget covers native solving and certificate checking. Calibration,
CNF compilation, and original browser replay are additional phases.

For reproducibility, `--frontier-snapshot PATH` uses a saved API response.
Such runs can verify a route but cannot label it a current record improvement.
SAT from a live run triggers another Frontier observation before any improvement
claim. The tool does not submit routes or publish anything.

Prepare without starting a record attempt, then solve the unchanged artifact:

```sh
python -m experiments.exact_frontier.record_system prepare \
  --room III-20 --output /tmp/iii20-global
python -m experiments.exact_frontier.record_system solve \
  --output /tmp/iii20-global --timeout-seconds 3600
```

Each directory contains the exact CNF, action-variable mapping, instance,
calibration, dated benchmark response, model contract and source hashes. Solve
rejects changed artifacts or model files. Use a new directory for a new problem.
Large global formulas can require several GB of memory; the native solver loads
clauses as a stream to avoid retaining a duplicate Python clause list.

## Acceptance and proof boundaries

1. Every SAT assignment must satisfy every CNF clause under an independent
   parser and checker.
2. The decoded route is truncated at its first local win and replayed in the
   checksum-pinned original PuzzleScript build. Only an original-engine accepted
   route shorter than the freshly observed record becomes
   `verified_record_improvement`.
3. An UNSAT answer with no independently accepted proof is
   `unverified_unsat_claim`. A successful DRAT check produces
   `certified_cnf_unsat`. This proves the encoded formula unsatisfiable; full
   original-game equivalence and the Z3-to-CNF translation are not formally proved.
4. Timeout remains `unknown`; a rejected certificate or witness is an error.

To independently check UNSAT, build the optional pinned checker:

```sh
git clone https://github.com/marijnheule/drat-trim.git /tmp/soko-drat-trim
git -C /tmp/soko-drat-trim checkout 2e3b2dc0ecf938addbd779d42877b6ed69d9a985
gcc -D_DEFAULT_SOURCE -std=c99 -O2 /tmp/soko-drat-trim/drat-trim.c \
  -o /tmp/soko-drat-trim/drat-trim
```

Pass `--proof-checker /tmp/soko-drat-trim/drat-trim` to `run`, `solve`, or
`check-reference`. Proof and checker hashes are recorded. The checker is an
optional external tool, not vendored code.

## Structural constraints and validation

III-14 includes two necessary conditions shared by every winning plan: a frame
with material on all nine switches, and at least nine wall-to-crate events.
The [landmark arguments](structure_system.md) cover simultaneous Bard carriage,
mutable borders, and doors closing after entrance. Exact grid and source checks
guard these clauses. They do not demand exactly nine crates or a particular
freeze pattern. The argument is human-reviewed mathematics, not a proof-assistant
certificate.

The [III-14](iii14_problem.py) and [III-20](iii20_problem.py) contracts specify
their mechanics and empirical calibration. The models remain independently
implemented research encodings. A correct witness can be verified in the
original game even if the model has an omission; an original-game impossibility
claim requires the stronger completeness obligation.

Test the whole positive path without attempting a record:

```sh
python -m experiments.exact_frontier.record_system check-reference \
  --room III-14 --output /tmp/iii14-control --timeout-seconds 120
python -m unittest tests.test_certified_sat tests.test_record_system \
  experiments.exact_frontier.test_iii14_problem
```

`check-reference` is explicitly labeled a control and pins the known actions
and independently replayed intermediate states.
It can never report a record improvement. Tiny synthetic UNSAT tests exercise
independent proof checking and corrupted-certificate rejection.

## Next system work

The next substantial improvement is a sound, smaller abstraction with a checked
map from every concrete transition, or a stronger admissible lower bound. The
topology relaxation in `structure_system.md` specifies shared wall-cut constraints
without double-counting heroes using the same opening. Simply deleting objects
is unsound: a removed crate may have been a Wizard anchor or a Bard blocker.

The older `iii14_smt`, `iii20_bitvector` CLI experiments and their result files
preserve the exploratory history. They are not the global system's search loop.
Their restricted UNSAT results and timeouts establish no new Frontier record or
original-game lower bound.
