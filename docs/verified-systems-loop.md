# From a puzzle solver to checked problem solving

An MCP server can give a model tools to state a problem, propose answers, and check the evidence. The server cannot make an arbitrary real-world problem formally verified by naming it a state system. The model of the problem, the claims, and the connection to the running system need their own checks.

## What the local Frontier test established

On November 12, the live page showed III-20 at 84 keys, held by a1kindus. The stored route reproduced in the two current Python interpreters and the recovered C++ engine. Its public browser replay showed the same final placement of heroes. This is a successful reproduction, not a new record or an optimality proof.

The live queue differs from the stored queue. II-22 is closed at 92. The remaining gaps were III-14 at 43 to 48, III-20 at 74 to 84, and III-21 at 268 to 316. The III-21 input and 316-key route were captured from the original puzzle editor and public Frontier page, then replayed in all three local implementations. The route belongs to futarchist.

A 60-second configured search found no shorter route for either III-20 or III-21. The III-21 run took 83.96 seconds because the existing budget does not bound the whole optimizer. No improvement from a heuristic search is evidence only about that search. It does not prove that no shorter route exists.

A later every-start window scan performed 39,495,921 state expansions in 177.119 seconds without an improvement. It completed all III-20 starting offsets for widths 12, 16 and 20. For III-21 it completed width 12 and part of width 16. There were 118 node-cap truncations. These limits are retained with the source and logs, so future work need not repeat the covered scan.

## The reusable contract

Keep candidate generation separate from acceptance. A fast solver, a language model, or a human can propose a candidate. A small checker decides which precisely stated claim the candidate supports.

| Operation | Required output | What it must not imply |
| --- | --- | --- |
| Capture | Original source, capture time, normalized instance, content hash, attribution | A transcription is correct merely because it parses |
| Specify | State, actions, transition rules, initial conditions, goal, objective, scope | Real-world meaning is settled by types |
| Propose | Candidate, generator revision, limits, random seed when used | Search failure proves impossibility |
| Replay | Every accepted transition, survival, termination, goal result | A valid candidate is optimal |
| Compare | Independent implementation results and first disagreement | Two agreeing implementations prove a shared interpretation |
| Prove | Named theorem, precise statement, proof artifact, kernel result | An internal status label satisfies the Verified Bar |
| Review | Independent approval tied to the full specification and claim hashes | An old approval covers changed claims or code |
| Publish | Evidence, limitations, current external validation and attribution | A local result has been accepted by the live service |

Each operation should return a typed state: unavailable, invalid input, failed check, timeout, accepted candidate, or checked proof. Errors should not become an empty successful result. An absent C++ backend previously appeared as a completed unsuccessful search in this checkout. The capability patch separates those states.

The raw interpreter accepts an empty route on a grid containing only walls: no hero cells and no goal cells satisfy its equality test without doing any work. `vacuous-raw-replay.json` records this reproduced case. Canonical starting-room validation now rejects it at the MCP replay and search entry points. Direct use of the raw interpreter still needs that validation boundary.

## Evidence identity and invalidation

A reusable result needs more than a route hash. Bind it to the normalized instance, rule version, goal, cost model, termination policy, checker code and proof statement. Keep the complete evidence content hash as well. Changing any of these invalidates the relevant result. An updated live record changes the comparison claim without changing whether the route wins.

`experiments/frontier_mac/replay_instance.py` makes a small executable step toward this contract. It binds the part, grid, goal, termination policy and route to SHA-256 hashes, preserves checker hashes, and labels the result `differential_replay`. It explicitly says that no formal proof or pinned external specification was checked. The URL is attribution, not an immutable specification pin.

The current 64-bit trajectory digest is useful for finding disagreement. It is not a collision-free proof of identical states. A proof-producing system should use exact state comparison or state commitments with their assumptions stated. A source hash shows which checker ran. It does not prove the checker implements the intended rules.

## Applying the Verified Bar

The governing standard is [Verified Bar version 2](https://github.com/Proven-Commons/mission/blob/main/playbook/verified-bar.md). The current project does not meet it.

| Bar item | Remaining work |
| --- | --- |
| Independent pinned specification | Add plain-language and theorem specifications, covered-file hashes, and independent reviewer approval |
| Claims match statements | Distinguish route feasibility, optimality, bounded search and backend availability. Test whether a useless implementation could still satisfy each claim |
| Kernel-checked proofs | Add pinned Lean challenge and proof modules, comparator coverage and `lake comparator --paranoid` results |
| Executed code matches proved code | Make entry points call the proved definitions. Audit compiler escapes, unproved copies and exceptions |
| Differential testing | The [original-engine wrapper](../experiments/original_engine/README.md) now pins the Part III build and checks known routes plus negative controls. Add seeded random and mutated inputs, first-divergence records and coverage beyond those controls |
| Public limits and trust | List unproved semantics, compiler/runtime/hardware, dependencies and exceptions. Keep status consistent with the manifest |
| Release gate | Add the required workflow and independent branch protection. Do not infer protection from a green local run |

Browser inspection validated existing public replays, not the entire transition system. The live site says submissions replay in Jonah Ostroff's original build. The current editor emitted compatibility warnings while loading the source. Any original-engine differential harness must pin the build actually used by the evaluator, not whichever editor version happens to load today.

The [later campaign](../evidence/2026-11-12-frontier-campaign/README.md) replayed the three baseline routes in the pinned original Part III HTML and matched public initial bitfields for III-14 and III-20. That is narrower than proving the server runs identical code for every transition. The [research loop](research-loop.md) turns these checks and the unsuccessful searches into explicit controls and next experiments.

## Next implementation boundary

Start with finite deterministic systems whose states and transitions can be serialized exactly. Require adapters to expose complete state, including hidden rule state such as Bard notes and door state. Hashing the rendered board alone can conflate states with different futures.

Support three separate acceptance levels: externally replayed witness, finite exhaustive certificate, and kernel-checked theorem. An exhaustive search needs checked coverage and exact deduplication, including its treatment of hash collisions. A heuristic beam cannot produce that certificate by reporting its visited count.

For scheduling, planning or software repair, the same interface can carry a domain-specific witness and checker. Only the modeled claim transfers. Whether a schedule reflects real availability, a plan has the intended effect, or a formal program is the deployed one remains an explicit boundary to validate.
