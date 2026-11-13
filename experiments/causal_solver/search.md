# Bounded causal search

`python -m experiments.causal_solver.search --horizon 47 --budget-seconds 60 --output result.json`
starts an unrestricted bounded query. It pins neither route nor hero history. The
master uses terminal absorption, so winning prefixes of every length up to the
horizon are represented. Event constraints are disabled by default; `--events`
enables them and `--symmetry` requests the optional normalization. The default
phase order checks exact completion before flow; `--phase-order flow-first`
reverses this. A feasible flow never establishes exact completion.

`--cut-selection sink_minimal` selects the complement of reverse residual
reachability into the sink after the same max-flow solve. The default is
`source_minimal`. Both modes retain every universal boundary arc, including
disabled arcs, and use the same independent certificate checks. The option
affects the flow phase; the default exact-first order can reject a candidate
before any flow call. Narrower predicates do not guarantee faster search;
see the [fixed-input comparison](../../evidence/2026-11-12-residual-cuts/README.md).

The worker builds the universal network and independently checks its complete
specification. Every deficient flow cut is independently checked before it is
installed. An exact contradiction is installed only after independent certificate
rechecking. Unknown or timed-out checks add no cut. A completed master UNSAT is
reported as `solver_global_unsat`: checked certificates are reproducible solver or
deterministic-transition replay recipes, not a standalone proof of global UNSAT.
No record bound is claimed. The exact and flow models depend on the documented
necessary-condition and mechanics assumptions; the symbolic model is not itself
proof of equivalence to the original engine.

Candidates are locally replayed immediately, truncated at the first win, then
replayed in the pinned original engine. Only that final replay can produce
`original_verified_win`. For unrestricted original-verified wins, the program attempts a fresh read-only
Frontier API observation and records its timestamp and response hash. A record
claim requires the observed current length to be strictly greater; API failure
leaves the comparison unavailable. `--html /path/to/part3.html --chromium /usr/bin/chromium`
selects an offline original-engine replay.

`--control reference --horizon 48` pins the known route, heroes and landmark,
and requires a nine-unit flow, exact SAT and original-engine replay;
`--control spurious --horizon 47` pins the diagnostic shortened route and heroes
at landmark 42. The latter runs exact first and passes only when a verified exact
cut makes that restricted master UNSAT. Neither control establishes a global bound.

The outer worker deadline covers construction, solving, certificate rechecks and
replay, and kills descendant processes including separately sessioned browser
workers. JSON checkpoints contain candidates, certificates, timings and source
hashes; a deadline reports unknown, and a detected source mutation is an error.
The source hash inventory covers the relevant local Python packages. Build and
certificate validation may consume the full budget. An interrupted checkpoint
can omit the currently executing phase but never treats it as successful.
