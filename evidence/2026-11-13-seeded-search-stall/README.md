# A stalled optimizer gives the same answer at the optimum and 30 keys above it (2026-11-13)

**Result.** We seeded the repository's own route optimizer (`python3 -m soko_mcp optimize`: window BFS, mirrored tube beam, iterated refinement) with deliberately poor routes on five Part III rooms whose optimum is proven on the Frontier. We reran it on its own output until it reported no improvement. On four rooms it reached the proven optimum. On III-16 it stopped at **77 keys against a proven optimum of 47** and reported `"improved": false`. That is the same verdict it gives when seeded with the optimal 47-key route. Four times the budget and five times the beam did not move it.

So "the optimizer found nothing" happens both at the optimum and far above it. From that output alone you cannot tell which. That bears directly on III-21: every search seeded from the 316-key record has returned 316 ([issue 22](https://github.com/ahrazzle/soko/issues/22), [scheduler](../../experiments/macro_scheduler/README.md), [campaign](../2026-11-12-frontier-campaign/README.md)). Those results show that 316 is a stopping point for those searches. They do not show that 316 is near optimal.

## Experiment record

- **Question.** Does the optimizer's "no improvement" verdict carry information about the distance to the optimum?
- **Hypothesis.** It does not. The optimizer improves within the plan structure of its seed, so its stopping points include routes whose plan differs from the optimal one.
- **Intervention.** Seeds from a cold-start search ([experiments/cold_start_macro](../../experiments/cold_start_macro/README.md)) that never reads a reference route. Its routes are long and use different plans.
- **Null control.** The same optimizer seeded with each room's proven-optimal reference route. It must report no improvement and must never go below the proven floor.
- **Prediction.** At least one room ends at a stopping point above the proven optimum, with output identical in form to the null control.
- **Decision rule.** If even one such stop appears, a stall from a seeded start is not evidence of near-optimality, and III-21 effort should go to a lower bound or to plans that do not start from the record.

## Results

Rooms are the closed Part III rooms where the default cold search found a route, with floor equal to the shortest known route on the Frontier.

| Room | Proven optimum | Cold seed | Optimizer trail (keys after each round) | Stops at | Gap | Null control |
| --- | ---: | ---: | --- | ---: | ---: | --- |
| III-10 | 45 | 47 | 47, 45 | 45 | 0 | 45, no improvement |
| III-12 | 44 | 61 | 61, 52, 45, 44 | 44 | 0 | 44, no improvement |
| III-13 | 57 | 67 | 67, 57 | 57 | 0 | 57, no improvement |
| III-15 | 69 | 89 | 89, 70, 69 | 69 | 0 | 69, no improvement |
| **III-16** | **47** | 84 | 84, 77 | **77** | **30** | 47, no improvement |

Extra checks on III-16:

- Rerun at 240 s and beam 200,000 (defaults 60 s and 40,000): 77, no improvement (`outputs/III-16.big.opt.json`).
- Original-engine replay: the 84-key seed and the 77-key stopping route both win on their final key in the pinned Part III build (`outputs/III-16.seed.original.json`, `outputs/III-16.final.original.json`).
- What separates the two routes is the plan, not the details. The optimal 47 uses 7 hero segments and 6 switches (Bard 11, Druid 4, Bard 9, Druid 3, Bard 2, Druid 2, Bard 10). The 77-key stop uses 15 segments and 14 switches. No window edit converts one into the other.

The first pass (`outputs/*.cold.opt.json`, `*.fix.opt.json`, `*.fix2.opt.json`) was run by hand. The end-to-end rerun by `known_answer.py` reproduced every number (`results.json`, `run.log`).

## Where the result stops holding

- A stall is informative when the search around the seed is exhaustive and reaches far enough to cover a different plan, or when a lower bound matches the route. Neither holds for III-21 today.
- Four of five rooms did reach the optimum. Iterating the optimizer is useful. The point is narrower: its stop signal cannot tell the four from the fifth.
- Five rooms is a small sample. It is enough to refute "a stall means near-optimal", and too small to estimate how often stalls are false.

## Draws on the open rooms (negative, recorded so nobody repeats them)

The test above implies that independent draws are worth more than further polishing from the record. So the same pipeline was run once on the open rooms, with 600 s per cold run and the optimizer iterated to a fixed point at 90 s per round.

| Room | Record | Cold draws | After polishing to a fixed point |
| --- | ---: | --- | --- |
| III-14 | 48 | 91 (`--K 4 --nov 1 --freedom 1`), 97 (`--K 16 --nov 1 --freedom 1 --rel-all 1`) | 52 and 58, both locally verified; no improvement on the next round |
| III-20 | 84 | none: default filter exhausted after 233 states; complete filter hit 9,000,000 states at cost 71 | not run |
| III-21 | 316 | none (see [the cold-start README](../../experiments/cold_start_macro/README.md#iii-21-runs)) | not run |

Routes are in `open-room-draws/`. Two draws are a tiny sample. They show only that this generator's basins on III-14 sit above the record, not that 48 is optimal.

## The same pattern in three other places

Three other records in this group describe the same mechanism without using this repository's words. Each was found independently, and none cites the others.

- `Moissanite-Labs/weft`, `docs/program/experiments/razi-cells-laws-2026-11/IDEAS.md`, law L7: "Inheritance anchors. On compress the blank arm found the ceiling body in 2 of 3 runs and heredity in 0 of 3. A fresh newborn is an independent draw. An heir stays near the first body. Where the best body is a different idea and not a refinement, draws beat inheritance."
- The same file, K11: "'Nothing left to find' and 'nothing tried' look the same from above. ... A part that stopped at +0% after a cheap try is not evidence of no headroom until a stronger try (model, effort, or a note) has also failed."
- `Foundation-0/f0`, `docs/research/gf2m-circuits/index.html`: "Walks within AES's usual way of writing the field stalled at 110." The record came from a sweep over 244,800 ways of writing the field.
- `Foundation-0/f0`, `docs/research/machine-mathematics/index.html`: "The minimum holds only inside that template, not for every possible counterexample."

Stripped of domain words, they share one mechanism. A search that starts from an incumbent explores the incumbent's neighbourhood. Its stop signal is a fact about the pair (incumbent, search), and it is true both at the optimum and at stopping points far from it. So:

1. Searches that share a seed are one observation, however many there are.
2. Only two things measure a gap: a bound that covers the whole space, or draws that do not inherit the seed (a cold start, another representation, another plan order).

`Foundation-0/f0` `deep-fields/scouting/mathematics.md` adds the other half: the quiet places are "the proof and upper-bound side of tables", and "most gaps come from weak upper bounds". On the Frontier, the only accepted floor proofs listed on 2026-11-13 are banteg's three, for III-14, III-20 and III-21. Every player's proof count is 0.

## Defect found on the way (recorded, not fixed here)

The optimizer first rejected every seed, including proven-optimal routes, with `seed_route (len=45) is not a valid winning route ... alive=True, exact_win=True, premature_win=False`. The real status was `REJECTED_TCB_UNLOCKED`. On first use, `ensure_cpp_engine` in `soko_mcp/engine_bridge.py` rebuilt the tracked `cpp/build/soko_engine` because its mtime looked older than the source. That changed its hash, so `sha256sum -c SHA256SUMS` failed. To reproduce deterministically: `touch cpp/soko_engine.cpp`, then run `verify`. Whether a fresh clone hits this depends on checkout timestamps; one clone in this session did, a second did not. The runs above used the committed binary, restored with `git checkout cpp/build/soko_engine`, with `SHA256SUMS` verifying. Under the GitHub SOP's one-gap-per-lane rule it is filed as [issue 49](https://github.com/ahrazzle/soko/issues/49) and not fixed here.

## Reproduce

```sh
sha256sum -c SHA256SUMS          # must pass, or every route is rejected (see above)
python3 experiments/cold_start_macro/known_answer.py --output /tmp/known-answer.json
```

Runtime is about 20 minutes on 4 cores. Environment: base commit `9fcb6cf`, g++ 13.3.0, Python 3.13. Source hashes: `strat.cpp` `02535961c21f`, `macro.hpp` `12c191e36820`, `native_engine.hpp` `8f472c0a0373`.

## Files

- `results.json`, `run.log`: end-to-end run.
- `seeds/`: cold seeds (`*.cold`) and intermediate optimizer outputs (`*.best`).
- `outputs/`: raw optimizer JSON for every run, including null controls, and original-engine replays for III-16.
