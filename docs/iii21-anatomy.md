# III-21: how the room is built (2026-11-13)

III-21 is the last open Frontier room with a large gap: the record is 316 keys (futarchist) and the accepted floor is 269 (banteg, observed 2026-11-13 08:40 UTC from `/api/frontier`). This note lists facts about the room that any new plan has to respect. Each fact was computed from the pinned grid or from replaying the 316 record in the spec oracle; the commands are at the end.

## The board

```text
x:           1111111111222
   01234567890123456789012
 0 #######################
 1 #.F.*....#G.G#....*.4.#      F Fighter (active)   4 Priest
 2 #...#....#...#....#...#
 3 #######.........#######
 4 #####.#####O#####.#####      O goblin
 5 #..##O#..#...#..#O##..#
 6 #.2.*....#G.G#....*.5.#      2 Thief   5 Bard   G exit
 7 #..##O#..*...#..#O##..#
 8 #####.####...####.#####
 9 #######..#..*O.*#######
10 #...###.#######...#...#
11 #.3.###.##G.G##...#.6.#      3 Wizard   6 Druid
12 #######################
```

Six heroes, six exits, in three pairs: top (10,1) and (12,1), middle (10,6) and (12,6), bottom (10,11) and (12,11).

## Fact 1: nobody can walk to an exit at the start

Counting cells a hero can reach by walking (through empty cells, never stopping next to a goblin): every hero reaches 6 or 7 cells and no exit. The Wizard, the Druid and the Bard are walled in. The bottom exit pair is walled in on all sides. Every route therefore starts by opening the board, and the order of openings is the plan.

## Fact 2: where one wall stands between two regions

The Druid turns a wall into a crate by walking into it. Someone else must then move the crate. These 17 interior walls each separate two regions, so one Druid key plus one crate move joins them:

| Wall | Joins | Note |
| --- | --- | --- |
| (17,3), (14,4), (15,4) | top corridor to the Bard's region | (14,4) and (15,4) open straight down from row 3 |
| (13,5), (13,6), (13,7) | middle exits to the Bard's region | |
| (14,8), (15,8), (17,9) | bottom corridor to the Bard's region | the record uses (17,9) |
| (18,10), (18,11) | Druid's box to the bottom-right area | the Druid's only exits |
| (10,10), (11,10), (12,10) | bottom corridor to the bottom exits | the only way into the bottom pair |
| (7,8), (8,8), (9,9) | a sealed pocket at (7..8,9), (7,10..11) | no exit or hero inside |

The Wizard's box (1..3, 10..11) has no one-wall breach. It needs two walls in the same column, (x,8) and (x,9) with x = 1 or 2, opened from the Thief's area. That is why the Wizard is among the last heroes out in the 316 route.

## Fact 3: switching cost is counted in laps

`A` always hands control to the next hero in the fixed order Fighter, Thief, Wizard, Priest, Bard, Druid, skipping absent heroes. No hero can leave III-21 and still win, so all six stay present and each `A` advances exactly one place. Two consequences:

- The number of `A` presses always has the same remainder, mod 6, as (final hero's place − Fighter's place). The record ends on the Priest, so its `A` count is 3 more than a multiple of 6: 75 = 6 × 12 + 3.
- Going from hero i to hero j costs (j − i) mod 6 presses. Any back-and-forth between two heroes costs a full lap of 6 presses, whichever two they are.

The record has 37 hero segments and wraps around the order 12 times. Its 316 keys are 241 moves plus 75 switches, so about a quarter of the route is switching. Moves per hero: Fighter 100, Bard 39, Druid 37, Priest 29, Thief 27, Wizard 9.

A plan with fewer laps saves 6 keys per lap removed. Laps are forced by dependencies of the form "hero A acts, then hero B must act, then hero A again". Escort and breach steps are the usual cause: the Druid makes a crate, a helper moves it, the Druid walks through.

## Fact 4: two tricks the record relies on

- **The Priest as a pushed shield (keys 48 to 55).** Goblins kill any adjacent hero unless a Priest is next to that hero; the Priest itself is immune. The Fighter pushes the inactive Priest ahead of it, then pushes the Priest and the goblin together down the (11,4) shaft. The Fighter is only ever next to the Priest, so no switch to the Priest is needed during the push.
- **Pushing one goblin into another (key 228).** A goblin next to another goblin dies, and so does the other one. After the Druid turns (17,9) into a crate, one Fighter push moves the crate into the goblin at (17,7). That goblin moves up next to the goblin at (17,5) and both die. The goblins at (11,4) and (13,9) are removed the same way earlier (keys 162 to 163).

## What has been tried

Searches started from the 316 route have all returned 316: window scans, suffix replanning, the exact FIFO macro scheduler (see [the scheduler README](../experiments/macro_scheduler/README.md) and [issue 22](https://github.com/ahrazzle/soko/issues/22)). The [2026-11-13 known-answer test](../evidence/2026-11-13-seeded-search-stall/README.md) shows why that result is not evidence that 316 is close to optimal: the same optimizer stops 30 keys above the proven optimum on III-16 and gives the same "no improvement" answer it gives on the optimal route.

A cold-start search that never reads the record ([experiments/cold_start_macro](../experiments/cold_start_macro/README.md)) does not yet reach a win on III-21 within its limits. See that README for the measured runs.

## Reproduce

```sh
python3 -m soko_mcp get-room --room III-21          # grid and the 316 route
python3 experiments/cold_start_macro/plan.py FILE    # replay a plan script in the spec oracle
python3 experiments/cold_start_macro/iii21_facts.py  # recompute the counts in this note
```

The region, breach and lap counts above come from `python3 experiments/cold_start_macro/iii21_facts.py`.
