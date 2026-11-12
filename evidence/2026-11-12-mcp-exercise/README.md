# A bounded exercise of the production MCP

This experiment uses the server's public stdio interface rather than calling its
Python functions directly. The aim is to check whether a tool that advertises
route optimization actually searches, and to retain the limits of a harder run.
It does not claim a public benchmark record or a kernel-checked proof.

**Original-source correction:** a later check found that the repository's `I-1`
fixture is not the original opening room. Original I-1 is 13-by-5 and takes eight
rights; this recorded 12-by-5 fixture takes nine. The canary below remains a local
regression test. See [the source assessment](../../docs/original-eval-and-frontier.md)
for the original evaluation conditions, current Frontier gaps and provenance.

## Inputs and attribution

The complete room registry, grids, request parameters and responses are in each
JSON file. `I-1` and `III-14` mean the **repository fixtures**, not independently
recaptured live benchmark instances. Both have one active hero, distinct hero
identities, and one goal per hero. They satisfy the adapter's canonical starting
room constraints. The Heroes of Sokoban puzzle rules and original puzzles are
by Jonah Ostroff.

For I-1, the experiment deliberately inserts a two-key detour into the known
nine-key route: `URRRRRRRRRD` (11 keys). This artificial seed is a canary for
the optimizer, not a previous public record. The direct route `RRRRRRRRR` is
already recorded in the repository. III-14 uses the repository's existing
48-key seed, attributed there to a1kindus.

## Baseline

`before.json` was collected from an exported checkout of merged main `55380b1`.
The production C++ backend returned the unchanged input and `stages: ["identity"]`
for both optimization calls. It did not run a search. Independently, its solve
tool found I-1's nine-key route. The original and returned routes replayed with
agreement across all three engines.

The III-14 proof call had a two-second budget and returned `CONJECTURE`. Its
old `guarantee` prose nonetheless described heuristic consistency checks and an
IDA* implementation that the production code did not contain. There was no
completed-depth or termination field to interpret the result. This is a reporting
defect, not a demonstrated false numerical bound: an interrupted iteration at
depth N can still inherit a floor of N from a completed iteration at N-1.
We retain the raw output as a diagnostic, not a kernel-checked proof.

## After replacing the identity optimizer

`after.json` records the working-tree source hashes, so the measurement is bound
to the actual implementation rather than only the parent commit.

| Call | Baseline | Updated implementation |
| --- | --- | --- |
| I-1 optimize, artificial 11-key seed | Returned 11; identity stage | Returned 9; exact BFS expanded 25 states, retained 27 |
| I-1 solve from scratch | Found known 9-key route | Found the same 9-key route, with completed depth 8 |
| III-14 optimize, existing 48-key seed | Returned 48; identity stage | Returned 48 after reaching the explicit 2,000-state cap |
| III-14 lower-bound search, two-second budget | `CONJECTURE`, no completion metadata | Completed depth 11, then the 100,000-state cap; reported local floor 12 |

The optimizer now has a demonstrated effect: it removes two unnecessary keys,
and the result independently replays through all three engines. This is a
regression-sized capability demonstration, **not a new Sokoban record**.

The harder fixture did not improve. Its optimization run expanded 837 states
before reaching the cap. The reported local floor is below the registry's
existing 43-key floor, so it does not advance that benchmark either. The useful
change is that search coverage and termination are explicit. Timing-dependent
coverage can vary on reruns; consult the complete response in each output file.

The final capture's source manifest matched all 11 pinned source files. Its
SHA-256 is `52e61187fa3eb45b4c98e3164a8eaa970d43364d3e7cfa5c3bffbdab778fce51`.
The manifest check is an integrity observation about this checkout, not an
independent approval of the rules or the search claims.

## Reproduction

From the repository root:

```sh
python3 experiments/mcp_smoke.py --output /tmp/soko-mcp-exercise.json
```

To compare an earlier revision, export it to a temporary directory and pass
`--checkout /path/to/export --source-revision <commit>`. The server builds its
C++ backend in that directory if needed. No dependency installation is needed.
The runner permits 45 seconds per request and terminates the entire process group
on failure. It records source hashes before and after, runner hash, Python
version, wall times, full JSON-RPC messages, and returned checker hashes. Every
candidate is submitted to the MCP verifier again, and disagreement makes the
runner exit nonzero. Server errors and source changes also make it exit nonzero.

## Limits

- The independent interpreters can share a mistaken interpretation of the rules.
- These fixtures have not been compared with a newly captured public original.
- The 64-bit trajectory digest is a useful differential check, not a collision-free proof.
- A winning route is not automatically shortest; a bounded search failure is not impossibility.
- A matching source manifest identifies local code; it is not independent specification review.
- No route was submitted to the public evaluator, and no benchmark record is claimed.
