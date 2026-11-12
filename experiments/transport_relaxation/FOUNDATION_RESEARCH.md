# Foundation-0 techniques applied to global Sokoban cuts

Source inspection date: 2026-11-12 UTC. This is a source-grounded design assessment, not an independent replay of the upstream results. The repositories below were cloned at the listed commits and their README, proof, checker source and certificate formats were inspected. No downloaded program was executed and no external message was posted.

## The three useful transfers

### 1. Prove the global domain, then verify finite witnesses

[finite-state-proofs, PROOF.md sections 2–3](https://github.com/Foundation-0/finite-state-proofs/blob/9eeb3da2cdd6ba6b100ac24d23b32c369c0db8ec/PROOF.md) separates the state-to-object correspondence from the finite arithmetic certificate. Its recurrence argument reaches a zero **vector**, which implies all later residuals vanish; agreement with many initial scalar observations would not suffice. The [independent checker](https://github.com/Foundation-0/finite-state-proofs/blob/9eeb3da2cdd6ba6b100ac24d23b32c369c0db8ec/verify_independent.py) constructs a different state matrix without importing the original transitions, and [tests](https://github.com/Foundation-0/finite-state-proofs/blob/9eeb3da2cdd6ba6b100ac24d23b32c369c0db8ec/tests/test_verify.py) reject corrupted coefficients, onset indices and certificates.

For Sokoban, the transferable technique is the proof boundary: establish that every concrete win of at most H inputs has a master schedule plus a feasible nine-unit material flow. Search all such master schedules from the initial board; do not infer a lower bound from the incumbent trajectory or finitely many selected schedules. SAT witnesses need replay, while global UNSAT needs the complete master domain and valid cuts. Tests should exhaust tiny domains and compare a direct token/flow calculation with the decomposed model, then corrupt a certificate and require rejection. Small tests support the implementation; the projection and cut theorem supply the quantified implication.

The upstream result is a proposed exact computer-assisted recurrence proof, with human review pending. It is not a Sokoban algorithm and does not prove the Sokoban encoding sound.

### 2. Let search discover obstructions; check their exact inequalities independently

[gfq-codes tools/README.md](https://github.com/Foundation-0/gfq-codes/blob/9200a06be239d6cc70ec94ed82f681e75b9bc718/tools/README.md) describes two exact certificate checkers: [binomial sums](https://github.com/Foundation-0/gfq-codes/blob/9200a06be239d6cc70ec94ed82f681e75b9bc718/tools/check_bound.py) and [generating-polynomial multiplication](https://github.com/Foundation-0/gfq-codes/blob/9200a06be239d6cc70ec94ed82f681e75b9bc718/tools/check_bound_independent.py). The exploratory [LP search](https://github.com/Foundation-0/gfq-codes/blob/9200a06be239d6cc70ec94ed82f681e75b9bc718/scripts/delsarte_lp.py) uses numerical optimization to find candidates and reconstructs integer coefficients before a result is certified. The final check uses exact inequalities, not optimizer tolerances. Its parsers also reject duplicate keys, duplicate IDs and non-exact numbers.

The Sokoban application is a symbolic min-cut certificate. Use a fixed universal time-expanded vertex and edge universe, with an exact Boolean capacity gate c_e(m) for each edge under master schedule m. For any source-side set S containing source but not sink, every nine-unit flow requires

    sum(c_e(m) for e=(u,v), u in S, v outside S) >= 9.

A failed allocation finds S; the learned master constraint is that exact crossing-capacity inequality. The inequality holds for every master schedule, because every source-to-sink flow crosses every source/sink cut. Search can use integer max flow, but a certificate verifier should rebuild the crossing edges and evaluate their gates from the normalized master assignment, not trust residual capacities or a stored crossing list. Sorting universal edge IDs and source-side labels produces stable, reproducible cuts. An independently written checker is stronger than a second call to the same flow constructor.

Crucial implementation detail: rebuilding only edges enabled in the failed schedule is unsound for generalization. A different schedule may enable edges missing from that graph. Likewise, the existing conditional flow builder omits hero-occupied cell vertices; generalized cuts need the universal vertex set, with hero occupancy encoded in capacities rather than changing the cut domain. A Hall-deficient set for one fixed schedule alone does not justify excluding unrelated schedules.

Mutation tests should flip a crossing-edge gate, remove an enabled edge from the claimed list, change source-side membership, or alter the horizon and require rejection. A tiny exhaustive comparison should show that every feasible master survives every generated generalized cut, including masters different from the rejected one.

The Delsarte/Krawtchouk bound itself is not a relevant Sokoban bound, and this assessment does not claim that it supplies a search speedup. The relevant transfer is exact dual-certificate architecture.

### 3. Bind evidence to the statement actually established

[formal-claims-audit README](https://github.com/Foundation-0/formal-claims-audit/blob/bacf05953c10bf5105fa1209a127392d395e2f92/README.md) and [verdict format](https://github.com/Foundation-0/formal-claims-audit/blob/bacf05953c10bf5105fa1209a127392d395e2f92/verdicts/README.md) distinguish a claim from the formal statement, and pin source commit, theorem, tool, command, output and assumptions. Its [JSON checker](https://github.com/Foundation-0/formal-claims-audit/blob/bacf05953c10bf5105fa1209a127392d395e2f92/scripts/check_verdicts.py) explicitly checks structure only. The repository reports no completed research verdicts at this commit.

For Sokoban, evidence should record the original board and mechanics hashes, horizon, master encoding version, cut-schema version, solver/proof checker versions, exact command, final status and supporting files. Keep `SAT abstract witness`, `conditional allocation failure`, `global master UNSAT`, `timeout` and `proof checked` distinct. A sampled-control campaign or timeout proves neither a global lower bound nor a new playable upper bound. Even a checked UNSAT formula still depends on the written concrete-to-relaxation implication and encoding correctness. Only a completed global UNSAT run, with that implication and all cuts justified, supports the bounded lower-bound conclusion.

## Implemented transfers and test evidence

These transfers are implemented in this repository, with no upstream code copied:

| Source lesson | Implemented application | Verification |
|---|---|---|
| finite-state-proofs: cover the entire domain and reconstruct it independently | `cut_certificate.check_universe_spec` independently derives every potential node and arc from the board and horizon | `ProductionUniverseSpecTests` removes a disabled release edge, invents a nonadjacent move and changes source predicates; each is rejected. `TinyCutLoopTests` exhausts all assignments in four finite networks. |
| gfq-codes: separate discovery from exact certificate checking | `universal_flow.evaluate_flow` discovers cuts; `cut_certificate.check_cut_certificate` independently rebuilds full boundaries and exact integer capacities | `GlobalCutCertificateTests` rejects altered partitions, missing edges, capacity changes and source mismatches; checks do not call the flow solver or its capacity evaluator. All nine cuts from the recorded runs were rechecked from persisted artifacts. |
| formal-claims-audit: bind evidence to the precise claim | `global_search.search` records source hashes, universe identity, search restrictions, proof status and explicit `record_claim: false` | `SearchLimitTests` exercises iteration limits, short CLI budgets and a deadline exceeded during witness replay. The real 47-key timeout remains `unknown`; the separate one-input CNF control has a checked DRAT certificate. |

See the [execution evidence](../../evidence/2026-11-12-global-cuts/README.md).
This is tested implementation evidence, not a claim that the mathematical
projection or Python/CNF translation has been formalized in a proof assistant.

## Candidate that does not supply an implemented technique

[covering-min-modulus README](https://github.com/Foundation-0/covering-min-modulus/blob/e8ecf1b53e337b9267831779c3760bd8dfe0feaa/README.md) proposes checking an enormous periodic domain by factoring its least common multiple through the Chinese remainder theorem. At this commit its status is **not started**; [systems/README.md](https://github.com/Foundation-0/covering-min-modulus/blob/e8ecf1b53e337b9267831779c3760bd8dfe0feaa/systems/README.md) defines a data format, and no completed independent coverage checkers or record certificates were present. This is an analogy for factoring a global proof into exact components, not evidence of a completed algorithm or a Sokoban performance improvement. Conditional material flow is already the more direct factorization here.

## Provenance and licensing

| Repository | Inspected commit | License at inspected revision | Reuse in Sokoban |
|---|---|---|---|
| finite-state-proofs | `9eeb3da2cdd6ba6b100ac24d23b32c369c0db8ec` | No repository-wide grant; NOTICE.md separately attributes OEIS source facts under CC BY-SA 4.0 | Cite the standard method and proof architecture; do not copy source code or exposition under an invented software license |
| covering-min-modulus | `e8ecf1b53e337b9267831779c3760bd8dfe0feaa` | Apache-2.0 | Conceptual assessment only |
| gfq-codes | `9200a06be239d6cc70ec94ed82f681e75b9bc718` | Apache-2.0 | Conceptual exact-certificate pattern; no code copied |
| formal-claims-audit | `bacf05953c10bf5105fa1209a127392d395e2f92` | Apache-2.0 | Conceptual evidence-schema pattern; no code copied |

The licensing caveat for finite-state-proofs is stated in its [NOTICE.md](https://github.com/Foundation-0/finite-state-proofs/blob/9eeb3da2cdd6ba6b100ac24d23b32c369c0db8ec/NOTICE.md). It does not apply the OEIS license to unrelated software. The general techniques—finite-state correspondence, independent exact checking, max-flow/min-cut and explicit claim scope—are standard, not claimed as Foundation-0 inventions. This Sokoban adaptation is independent implementation work, informed by the cited examples. Source inspection was performed by OpenAI Codex for Ahraz Arifuddin; it is not human sign-off or proof-assistant verification.
