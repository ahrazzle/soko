# Full-mechanics tractability: implementation and measured evaluation

This plan is shared before implementation, following document → share → implement
→ test → share results. It builds on merged PR #19, at `52f77d3`, and covers all
nine user-requested work items. A completed implementation does not imply that
an unobserved shorter route exists or that every horizon becomes easy to solve.

## Waves and ownership

1. **Contracts and independent components.** Terra implements a factored causal
   transition encoding covering all material, Sol implements exact completion
   and checked contradiction learning, Sol implements necessary event/resource
   bounds and sound redundant-choice removal. Astra checks their mathematical
   scope. Root coordinates interfaces and terminal semantics.
2. **Integration.** Root connects an absorbing hero/action master, material
   flow, and exact full-state completion. Shorter wins must remain represented:
   the previous abstraction's artificial initial padding cannot silently be
   treated as legal original-game inputs. SAT candidates require original replay;
   timeout is never a contradiction or bound.
3. **Measurement.** Terra implements reproducible SMT/SAT/constraint-programming
   adapters and profiles each phase under identical controls and budgets. Sol
   expands the benchmark with valid/spurious routes, small exhaustive cases,
   planted errors, and certificate tampering. No unmeasured default speedup claim.
4. **Review, bounded execution and publication.** Integrate all passing components,
   run matched ablations and one evidence-driven bounded global query, archive
   certificates/results, and publish the final implementation and measured
   outcomes. A new original-engine-verified record is reported immediately.

Use GPT-6.1 Terra and Sol for code and routine controls; use GPT-6 Astra for
quantified soundness and final review. Keep CPU-heavy jobs bounded and coordinated
on the shared machine. Agents own separate modules/tests; integration is serial.

## Deliverables and acceptance checks

| Requested item | Deliverable | Required evidence |
|---|---|---|
| 1. Compact movement causes | Alternative exact causal circuit | Symbolic one-step equivalence to retained exact model; oracle controls; measured formula/build cost |
| 2. All relevant material | Full board wall/crate state in exact completion, including unselected blockers | Cases where omitted material changes movement; conversion, cancellation and door-removal checks |
| 3. Events and dependencies | Source-guarded event variables and necessary ordering clauses | Known route accepted; independent concrete event extraction; invalid event claims rejected |
| 4. Remaining-input bounds | Joint-action-aware resource/travel bounds | Written quantified argument plus exhaustive finite controls; no double charging simultaneous movement |
| 5. Automatic exact refinement | Full-state assumption checks, generalized contradiction certificates and master feedback | Spurious route rejected, known route retained, altered/timeout certificates rejected, multiple assignments excluded when justified |
| 6. Equivalent choices | Material identity quotient and proven redundant-input normalization | Concrete-state/key-cost preservation argument and exhaustive small trace checks; no unsupported board symmetry |
| 7. Encoding/solver choice | Comparable exact SMT, SAT and CP-SAT adapters plus event ablation | Same instance/assumptions/budget, status and model checks, version and memory/time metrics |
| 8. Diagnostic benchmark | Reusable controls and planted-error suite | Known 48-key original replay, spurious 47-key controls, exact small horizons, deliberate error detection |
| 9. Compute allocation | Phase profile and budgeted scheduling policy | Measured bottleneck, bounded process groups, source/command pins, honest unknown outcomes |

## Trust and scope

The initial integration targets original III-14. It must preserve existence of
every bounded legal win and use the incumbent only as the input budget. It must not
fix a prefix, hero-switch schedule, material count, transport pattern, or goal
assignment. The existing unlabeled wall/crate bitmasks already remove artificial
material-label permutations; further pruning requires a preservation argument.

Equivalence to a retained symbolic model and sampled original-engine agreement
are separate evidence. Full game-to-model equivalence is not thereby formally
proved. Every learned contradiction must be replayable against pinned sources.
An exact-subproblem timeout must remain unknown and must not exclude a candidate.
Full-model SAT is still a candidate until original-engine replay. A current
record claim also requires a fresh benchmark observation.

This file will be updated with implemented module names, commands, measured
results, and any failed optimization experiments. Tested negative results are
reported as such; no declared work item is completed merely by documenting it.

## Measured follow-up within wave four

The first integrated unrestricted run spent its 120-second budget in the hero
master before producing an assignment. Exact completion already accepts the
known 48-key projection in 0.53 seconds and rejects the spurious 47-key projection
in 0.29 seconds, so more compute for exact completion would miss the bottleneck.

The next implementation preserves every event inequality while replacing the
master's mixed bitvector/integer arithmetic with widened finite bitvectors.
Coordinates are zero-extended before signed subtraction. All prefix sums are
at most H+80, and suffix bounds at most 50; choose signed width w such that
2^(w-1)>max(H+80,50). No sum or difference may use the original narrow width.
The integer implementation remains a reference. Require symbolic/exhaustive
equivalence controls, independent overflow review, and a matched master query
before selecting a default. This is representation work within items 1, 4,
7 and 9, not a change to legal strategies or the objective.

## Completion

All nine deliverables are implemented and tested; the
[package implementation map](README.md#implementation-map) links each to code
and verification. Work used Terra for encoding/integration/measurement, Sol for
refinement/events, and Astra for independent soundness review. All code and
results were shared through this PR after the plan was published first.

The measured default keeps the compact exact circuit and disables the optional
numeric event bounds. It retains complete material mechanics and independently
checked contradiction learning. The alternative causal circuit and widened
event arithmetic are tested experiments with no demonstrated global solve
advantage; they remain explicit options rather than unsupported default upgrades.

The final selected H47 run produced 151 candidates and accepted 150 checked
exact contradictions in 120 seconds, compared with no candidate from the
integer-bound master in the preceding 120-second run. Both runs ended unknown;
no new record or stronger game bound resulted. Known48 exact completion took
0.526 seconds, spurious47 rejection 0.293 seconds; general guarded SMT controls
remained unknown at 35 seconds. The reference passed full original-game replay.

See [archived evidence](../../evidence/2026-11-12-causal-tractability/README.md)
for the final focused tests, unchanged baseline failures, solver comparisons,
all accepted certificates and a no-search rechecker.
