# Carbon-agent Drive insight: III-14 abstraction refinement

## Source and attribution

Raz supplied the [Drive folder](https://drive.google.com/drive/folders/1w5sGY6FOUOqpCw359rIKYD0z9ySavO3p) as a carbon agent's contribution that could not be put directly in the repository. The relevant artifact is [2026-11-11_soko-verified-mcp-final.zip](https://drive.google.com/file/d/1JRV4b1EmWqxuPpBM56xUtR3ySQ9sPo4e/view), uploaded November 12 at 11:57 UTC. Its author was not individually identified. Credit for the recovered method belongs to that contribution; the checks and qualifications below are this ingestion's work. The original puzzle is Jonah Ostroff's Heroes of Sokoban III.

The complete 15-file ZIP payload is preserved unchanged in `archive/`, including its original directory layout and SHA256SUMS. It is an inert research snapshot, not an installed MCP configuration. Their historical claims are not adopted as verified project status. `provenance.json` records hashes. All 14 entries in the package's SHA256SUMS matched. The ZIP is the same package recovered for the earlier Mac experiment, but that experiment did not import or test this specialized prover or dossier. This addition therefore preserves missing evidence rather than replacing the current MCP code.

## Useful insight and its boundary

The dossier proposes improving III-14's lower-bound abstraction by tracking pairwise crate relative positions or three-crate row/column occupancy. The current abstraction tracks hero positions, active hero, a capped count of created objects, adjacent initial walls and door state. It loses much of the cost of arranging crates on the 3-by-3 switch area. Relative-position information is a plausible way to retain more of that cost.

However, the dossier's stronger statement that **all charmed crates translate rigidly together** is false in its own implementation. Blocked charmed crates can remain still while others move. This is not just an arbitrary synthetic state: the supplied 48-key route reaches a counterexample.

- Replay prefix `LLULULULRURURURURUAUDRRD` (24 keys), then press `D`.
- Before step 25 the active Bard is at `(4,3)`; zero-based coordinates.
- Charmed crate `(2,5)` is blocked by wall `(2,6)` and stays put.
- Charmed crate `(5,1)` moves to `(5,2)`.
- Both are in the pre-step aura. Their relative displacement changes from `(3,-4)` to `(3,-3)`.

The archived C++ engine and archived Python oracle both reproduce this. `counterexample.cpp` finds the wall-blocked instance on the supplied route. No new live-browser replay or formal semantics proof was performed for this counterexample. It refutes the unconditional rigid-group claim in the supplied implementations, not their agreement with the original game.

Thus a pair-pattern abstraction must include or conservatively permit blocking, changes in aura membership, wall/crate transmutation, hero occupancy, and door transitions. Simply preserving every pair's offset could remove legal concrete transitions and produce an invalid lower bound.

## What the recovered prover actually reproduces

On the Mac, Homebrew GCC 16.2.0 failed to compile the unmodified source because `assert` was undeclared. Adding the compiler option `-include cassert` (not modifying the archive) made it compile. With assertions enabled:

- `--verify` accepts the existing III-20 84-key and III-14 48-key routes.
- `--prove-iii14 35` completes bounds 25 through 35, printing `UNSAT (floor >= 36)`.
- It runs 127,632,718 edge-consistency checks in approximately 32.3 seconds in this invocation.
- `prover-run.json` retains the actual output and flags. These are this program's empirical results, not a kernel-checked floor certificate.

The dossier describes a 3.26-million-state combined abstraction, a second 2,112,880-state joint PDB, a two-thread run and 295,031,739 checks. The supplied source instead contains one `98 * 98 * 2 * 10 * 3 * 2 = 1,152,480`-entry PDB and an additional hand-derived heuristic (`best_c`); this IDA* driver is single-threaded. The second database is not present. Our observed check count differs. The dossier's larger run cannot be reproduced from this source as stated.

There are further proof boundaries:

1. The transposition table compares a hash-derived tag and bucket, not exact complete states. A hash collision can prune a distinct state. Runtime consistency assertions do not repair that coverage risk.
2. Checking consistency only on expanded edges does not establish a global abstraction homomorphism or the admissibility of branches that were pruned before expansion.
3. There is no independently pinned game specification, proof of transition fidelity, kernel-checked abstraction theorem, or independently checked exhaustive coverage certificate in this artifact.
4. The floor of 36 is below the 43 floor displayed in the earlier browser capture. It is a reproducibility result, not a new Frontier bound or solution.

## Next implementation step

Implement one small two-crate abstraction as an experiment, keeping candidate search separate from acceptance. Specify the projection, abstract goal set and complete permitted transitions, including the blocking counterexample above. Prove or exhaustively check transition simulation and goal preservation on the intended domain. Compute exact backward distances, and combine admissible bounds with `max` unless a separately justified cost partition permits addition.

For any claimed exhaustive floor, use exact state equality in duplicate detection (or an independently checkable coverage certificate), preserve resource-limit and completion evidence, and pin the rules/checker/proof identity. Keep a useful search heuristic explicitly labeled heuristic until these obligations are met. The existing `docs/verified-systems-loop.md` acceptance levels remain applicable.

## Reproduce locally

From this directory, with Homebrew GCC available:

```sh
g++-16 -O2 -pthread -std=c++20 -include cassert archive/cpp/frontier_iii14_iii20_prover.cpp -o /tmp/soko-archived-prover
/tmp/soko-archived-prover --verify
/tmp/soko-archived-prover --prove-iii14 35
g++-16 -O2 -pthread -std=c++20 counterexample.cpp -o /tmp/soko-blocking-counterexample
/tmp/soko-blocking-counterexample
```

Do not compile with `-DNDEBUG`: the archive uses assertions for its checks. These commands test the imported research artifact, not the production MCP or full repository suite. No code from the archive was installed into the runtime backend, no CI pass is claimed, and no new route was submitted.
