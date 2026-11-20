# The public III-21 records are three plans, and all 30 make their first kill with the same move (2026-11-20)

**Result.** The Frontier publishes every record route. We replayed all 46 public routes for the three open rooms in the spec oracle and compared their plans. A plan here is the list of irreversible changes a route makes, in order: which walls it opens, which goblins it kills, and which cells it turns into walls.

- The 30 public III-21 routes, by 7 authors, are **3 plans and 1 hybrid**. That holds at every overlap threshold from 0.6 to 0.8. At 0.81 route 333 splits off, so 0.8 is near the edge. The record (316) is the best of plan C. The best route of plan B is 333, and of plan A 379.
- Later authors build on earlier routes. Consecutive III-21 records by *different* authors share up to 97% of their exact board states. 19 of the 29 record steps on III-21 kept the milestone set unchanged.
- **Every route makes its first kill with the same move.** In all 30 routes the Fighter stands at (12,6) and presses Down, pushing the Priest at (12,7) and the goblin at (12,8). The goblin that started at (11,4) dies, and so does the one that started at (13,9), on the same key. Since the 433-key record that key falls between 153 and 167.
- The work around the kill was reordered, though. The 333 and the 316 move the Druid's exit at (18,10) ahead of the kill, to keys 49 and 103. Routes that kill first shortened their opening from 162 keys to 153 (routes 151 and 153 to 155). The opening has been reshuffled, but the kill move itself has never varied.
- The cold-start macro search cannot reach any goblin-pair kill under either filter. So no route, public or ours, has tested a different way to make the first kill.

This sharpens [issue 53](https://github.com/ahrazzle/soko/issues/53)'s splice result (C4). "Each record is already the best recombination of every published plan" is true, but the published plans are three, and all three make the first kill the same way. Under the [2026-11-13 stall result](../2026-11-13-seeded-search-stall/README.md), the 316 is one observation of that kill and three of the plan that follows.

**Correction, 2026-11-20.** A second reviewer, asked to disprove this note before it was filed, found that the first version's goblin-death detector invented kills: on chain pushes, on Wizard swaps, and on Druid petrifications, which it also counted as walls. `lineage.py` now gives every goblin an identity and records deaths where the oracle removes them. Its minimal reproductions are tests in `tests/test_route_lineage.py`. The reviewer also showed two claims in the first version were too strong: that all progress came after the kill, and that nobody had redrawn the opening. Both have been replaced by the two bullets above. Family counts on III-21 and III-14 did not change; III-20 went from 5 families to 6. Plan B's right-hand goblins, first reported as one kill, in fact both survive.

## Experiment record

- **Question.** Are the public routes independent draws, which would make the splice's negative result broad? Or are they one lineage, which would make it narrow?
- **Hypothesis.** They are mostly one lineage. Public routes are visible to every player, and the [2026-11-13 test](../2026-11-13-seeded-search-stall/README.md) predicts that polishing visible incumbents converges on their plan.
- **Intervention.** `experiments/route_lineage/lineage.py` replays each route and lists its milestones: `open x,y` (a wall stops being a wall), `wall x,y` (a cell becomes a wall), `kill x,y` (the goblin that started at (x,y) dies) and `petrify x,y` (that goblin is turned into a wall). Goblins are tracked by identity through every push, swap and carry. It then compares routes three ways: Jaccard overlap of milestone sets, order agreement on shared milestones, and Jaccard overlap of exact board states visited.
- **Known answers.** These are in `controls.json` and `controls_lineage.json`.
  - The 316 with a no-op lap inserted (`AAAAAA`, six switches back to the same hero) scores milestones 1.00, order 1.0, states 0.997.
  - The III-16 seed (84) against its optimizer stop (77), a seed and its polish, scores milestones 0.94, states 0.51.
  - The III-16 stop (77) against the proven 47, two plans already known to differ by 15 against 7 hero segments, scores milestones 0.18, states 0.008.
- **Null control.** Independent draws: cold-start routes that never read a reference, against each room's reference. Shared states are 0.007 to 0.05 on III-12, III-13, III-14, III-15 and III-16. The exception is III-10 (below).
- **Decision rule.** If most III-21 records keep their predecessor's milestones and the families number far fewer than the authors, treat the splice and shortcut results as covering only the published plans. The next search should then target the part of the route the families share.

## Results

Full tables: `report-III-21.md`, `report-III-20.md` and `report-III-14.md`.

### III-21 plan families (best route of each)

| Choice | A (best 379; 16 routes, 5 authors) | B (best 333; 6 routes, 3 authors) | C (best 316; 7 routes, 1 author) |
| --- | --- | --- | --- |
| Goblins from (11,4) and (13,9) | killed together at key 163, by the Fighter's push from (12,6) | the same push, at key 159 | the same push, at key 163 |
| Druid's way out | (18,10) | (18,10), at key 49 | (18,10), at key 103 |
| Way into the bottom exits | (11,10) | (12,10) | (12,10), then (10,10) |
| Link to the Bard's region | (13,6), (13,7) | (17,9) | (17,9), (16,9), (13,7), (9,6) |
| Left goblins from (5,5) and (5,7) | turned to wall by the Druid | killed together at key 254 | left alive |
| Right goblins from (17,5) and (17,7) | left alive (the first plan A route, 589, killed them) | left alive | killed together at key 228 |
| Wizard's box | (2,8), (2,9) | (2,8), (2,9), (1,8); also (3,7), (4,7), (6,7) | (1,8), (2,8), (1,9) |
| Other cells turned to wall | none | (11,9) | (11,8) |

The hybrid (335, plan C's right side with plan A's left side) is its own family. Each row offers two or three published choices, and the families combine them in only three ways. Untested combinations are not claims of improvement; some may be infeasible.

### Inheritance across the three open rooms

| Room | Routes, authors | Families at 0.7 | Record steps that kept the milestone set | Gap |
| --- | --- | ---: | ---: | --- |
| III-21 | 30, 7 | 4 | 19 of 29 | 270 to 316 |
| III-20 | 9, 3 | 6 | 0 of 8 | 77 to 84 |
| III-14 | 7, 4 | 3 | 1 of 6 | 44 to 48 |

III-21's record history is by far the most inherited of the three, and it has the largest gap, in keys and as a share (15% against 8% and 8%). Three rooms cannot separate inheritance from room size, so this is consistent with the stall result, not evidence for it.

### The opening cannot be reached cold

`experiments/cold_start_macro/strat.cpp --goal-gob 4` stops at the first state with at most 4 of the 6 goblins left, instead of at the room's win (`subgoal/`).

| Flags | Result |
| --- | --- |
| `--K 8 --nov 1`, default filter | Exhausted at cost cap 220 without reaching 4 goblins; 95,831 expanded, the same 1,584 progress cells as the full-room run |
| `--K 4 --nov 1 --freedom 1 --rel-all 1` | Stopped at the 9,000,000-state cap at cost 57; 271,459 expanded, 7,077 cells |

This is where the 2026-11-13 cold runs on III-21 died too: they never got past the first kill. Every public route reaches that kill with the same Priest-shield push.

A narrower exact run lets only the Fighter and the Priest act (`--heroes 9 --K 100000000 --nov 0 --rel-all 1`). It expanded every state up to cost 89 (1,574,289 states, 600 s) and found no goblin-pair kill. With only those two heroes, then, the kill takes at least 91 keys, assuming the macro model is complete under `--rel-all 1` and no 128-bit hash collisions occurred. This does not bound the real opening: in the record the Thief first pulls the crate at (12,9) to (11,9), clearing the cell the goblin is pushed into.

## Where it stops holding

- **Shared states mean shared lineage only on rooms with room to move.** On III-10, a cold route that never read the reference shares 45% of its states with it, because the room forces most of the route. On III-21, routes in different families share a median 6% of their states. The range runs from 2% up to 48%. The 48% is the hybrid 335 against routes by the same author, mostly states before the first kill. Leaving out the hybrid, the maximum is 15%. A value near 1 shows a copy plus a polish: the 432 shares 97% of its states with the 433 it replaced, one key shorter and by another author. A middling value proves neither copying nor independence.
- **Heavy polishing erases the trace.** The optimizer turned the III-14 cold 91 into 52 and kept only 0.7% of its states. Low state overlap does not prove independent origin.
- **Milestones are a coarse plan.** Two routes with equal milestone lists can still differ in who moves when. The test can split plans, not certify that two plans are identical in every respect.
- **The opening result is about the double kill.** It says nothing about whether 163 keys is close to the least possible. Settling that takes a bound on the opening, or a planner that reaches the kill differently.

## What this suggests

1. **Bound the opening.** Find the fewest keys from the start to any state where the goblins from (11,4) and (13,9) are dead and every hero lives. If that floor is near 150, the opening is spent and the gap is in the second half. If it is far lower, the opening holds the slack.
2. **Draw the opening a second time.** Use a planner that can express the shield push, so the Priest stays next to whoever is near a goblin. Then complete the route with the existing suffix tools (macro scheduler, splice) from the new state.
3. **Search plan-level combinations (#53 C9) over the table above,** filling each leg with exact search.

## Reproduce

```sh
python3 experiments/route_lineage/fetch_public.py --output /tmp/public_routes.json   # or use public_routes.json here
python3 experiments/route_lineage/lineage.py evidence/2026-11-20-public-route-lineage/public_routes.json --output /tmp/lineage.json
python3 experiments/route_lineage/report.py /tmp/lineage.json --room III-21
python3 experiments/route_lineage/lineage.py evidence/2026-11-20-public-route-lineage/controls.json --output /tmp/controls.json
g++ -O2 -std=c++20 experiments/cold_start_macro/strat.cpp -o /tmp/strat
/tmp/strat --K 8 --nov 1 --goal-gob 4 --gmax 220 --time 900 --maxn 9000000 < iii21.in
/tmp/strat --K 100000000 --nov 0 --rel-all 1 --heroes 9 --goal-gob 4 --gmax 200 --time 600 --maxn 20000000 < iii21.in
```

`lineage.py` takes about 3 seconds for all 46 routes. Routes were fetched from `soko.banteg.xyz/api` on 2026-11-20 at about 01:20 UTC. All 46 win in the spec oracle, and each length matches the Frontier list. Base commit: `41b6f9c`, merged into this branch.

Source hashes (first 12 hex of SHA-256): `lineage.py` `393c90cd5c39`, `report.py` `27ab1f9ba295`, `fetch_public.py` `a078cddb35ea`, `strat.cpp` `029444223c30`. The only changes to `strat.cpp` are two new flags, `--goal-gob` and `--heroes`; the default build still reproduces the 2026-11-13 III-16 cold seed byte for byte.

The splice README in `experiments/long_shortcut` gives 8 authors for these 30 routes. The public list on 2026-11-20 has 7 distinct handles.
