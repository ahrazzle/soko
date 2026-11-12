# Drive contribution assessment: III-14 lower bounds

Source: the carbon-agent Soko contribution supplied by Raz in the [Proven Commons Drive folder](https://drive.google.com/drive/folders/1w5sGY6FOUOqpCw359rIKYD0z9ySavO3p), specifically `2026-11-11_soko-verified-mcp-final.zip`. Individual author identity was not supplied. Credit for the proposed method belongs to that contribution; the following checks were performed during integration. Original puzzle: Jonah Ostroff.

## Useful direction

Tracking pairwise crate relative positions or three-crate occupancy is a promising way to strengthen III-14 lower bounds. A count-only abstraction discards arrangement costs. This is a research direction, not an implemented or proved improvement.

The accompanying claim that all charmed crates always translate as one rigid group needs qualification. In both supplied interpreters, blocked charmed crates can stay while others move. On the supplied 48-key route, step 25 (`D`) leaves a wall-blocked charmed crate at zero-based `(2,5)` while another moves from `(5,1)` to `(5,2)`. Both were inside the aura. Their relative position changes. This was reproduced on the Mac in the C++ and Python implementations; it was not independently replayed in the original browser engine during this check.

A sound abstraction must conservatively include blocking, changing aura membership, transmutation, hero occupancy and door transitions. Enforcing unconditional pair-offset preservation could exclude legal moves and invalidate a lower bound.

## Reproduction and limits

The specialized C++ prover was tested separately from the production MCP. Homebrew GCC 16.2.0 required `-include cassert` to compile it with assertions enabled. It accepted the existing III-20 84-key and III-14 48-key routes. Running through bound 35 printed a floor of 36 after 127,632,718 edge-consistency checks, taking approximately 32 seconds.

This is an empirical reproduction of the program's output, not a formal certificate. The source uses hash-only transposition pruning rather than exact state equality. Runtime checks on expanded edges do not prove global heuristic admissibility or coverage of pruned branches. The dossier's larger combined-PDB/two-thread/check-count description does not match the supplied single-PDB, single-threaded driver. No kernel proof or independently pinned original-game specification was checked.

The reported floor of 36 does not improve the previously observed Frontier floor of 43. No new winning route or live submission resulted.

## Proposed next step

Build one small pair-crate abstraction with an explicit projection and goal relation. Validate every concrete transition's abstract simulation, including the blocked/moving pair case above. Combine admissible estimates using `max` unless cost partitioning is justified. Use exact-state deduplication or independently checkable exhaustive coverage for any claimed floor. Keep heuristic performance claims separate from proofs, as in [the verification contract](../../docs/verified-systems-loop.md).

The complete original bundle, source and dossier are now preserved unchanged in [archive/](archive/), with Raz's explicit publication approval. See [the detailed assessment and reproduction commands](README.md), [provenance](provenance.json), and [run output](prover-run.json). Original archive claims remain historical claims, not verified project status. No runtime backend was changed and no CI pass is claimed.
