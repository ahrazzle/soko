# Cold-start macro search (2026-11-13)

This is a route search for Part III rooms that never reads a reference route. It exists to test plans that the record route does not use. Every other search in this repository starts from the record. Results are candidates only. Accept a route only after original-engine replay.

## What a step is

A search step is a **macro**:

1. Press `A` until hero *h* is active. The cost is the actual number of presses.
2. Walk *h* along a shortest path where each key moves only *h*: nothing else changes and nobody dies.
3. Then either
   - press one key that changes something besides *h*'s own position: a push, pull, swap, petrification, Bard carry or door change. This is an **effect**.
   - or stop the walk on a cell that passes the relevance filter. This is **positioning**.

Cost is exact key count. Transitions use the team's native engine, `../macro_scheduler/native_engine.hpp`, which replays all 317 frames of the III-21 record. `macro.hpp` builds the steps; `strat.cpp` searches over them.

The model can represent any route only when every walk endpoint counts as relevant (`--rel-all 1`). The default filter keeps only exit cells, cells next to an inactive hero and cells inside an inactive Bard's 5-by-5 area. That filter cannot express a hero stepping aside. III-9's optimal route needs exactly that at key 6, so with the default filter the uncapped search finds 60 there, not the optimal 46. With `--rel-all 1`, the 46-key optimal route breaks into 37 macros.

## How the search chooses

States are expanded in order of exact cost. Each state is mapped to a **progress cell**, an order-free summary built from five parts:

- which heroes are on exits;
- which heroes can walk to an exit without stopping next to a goblin;
- goblins left;
- interior walls removed and crates present;
- which hero is active.

`--freedom 1` adds a bucket for how many cells each hero can walk to.

At most `--K` states are expanded per cell. With `--nov 1` a state beyond that cap is still expanded if it puts some object on some square for the first time within its cell. This is the novelty test from width-based planning (Lipovetzky and Geffner). The search never reads a reference route, and every win it prints is replayed by the caller.

```sh
g++ -O2 -std=c++20 strat.cpp -o /tmp/strat
python3 -m soko_mcp get-room --room III-16 | python3 -c "import json,sys; d=json.load(sys.stdin); g=d['grid']; print(len(g[0]), len(g)); print('\n'.join(g))" > /tmp/iii16.in
/tmp/strat --K 4 --nov 1 --time 60 < /tmp/iii16.in      # prints WIN/ROUTE lines, then STOP or EXHAUSTED
```

## Calibration on rooms with proven optima

Uncapped (`--K 1000000 --nov 0`, default filter), the search recovered the proven optimum on III-1 (27), III-4 (18) and III-6 (36). On III-10 it ran out of time at cost 28.

Capped runs, best route within the time limit:

| Room | Proven | Default flags, K 4, 80 s | `--freedom 1 --rel-all 1`, K 4, 70 s |
| --- | ---: | ---: | ---: |
| III-9 | 46 | none (search exhausted) | none (search exhausted) |
| III-10 | 45 | 47 | 47 |
| III-12 | 44 | 61 | 62 |
| III-13 | 57 | 67 | 69 |
| III-15 | 69 | 89 | 89 |
| III-16 | 47 | 84 | 60 |
| III-18 | 63 | none (search exhausted) | not finished |

The capped search finds routes, not optimal ones. That made it useful as a seed generator for the [known-answer test](../../evidence/2026-11-13-seeded-search-stall/README.md): there, the repository's optimizer stopped 30 keys above the optimum on III-16 and reported no improvement.

## III-21 runs

| Flags | Result |
| --- | --- |
| K 2, default | Exhausted at cost cap 900 without a win; 92,928 expanded, 1,584 progress cells |
| K 24, default | Exhausted at cost cap 900 without a win; 113,812 expanded, the same 1,584 cells |
| K 8, `--freedom 1 --rel-all 1` | See the dated note below |

The default cells saturate on III-21. Every hero starts sealed in, so "can walk to an exit" stays false for all six through most of any route. The search therefore cannot tell "Priest freed" from "nothing happened". See [docs/iii21-anatomy.md](../../docs/iii21-anatomy.md) for the room's structure.

## III-21 facts

`iii21_facts.py` recomputes the counts in the anatomy note from `get-room` output:

- **Walkable cells per hero:** a flood fill through `.` and `G` cells, refusing any cell next to a goblin.
- **One-wall breaches:** interior walls whose two opposite neighbours lie in different non-wall regions.
- **Laps:** hero segments taken from replaying the record in `soko_mcp/oracle.py`, counting each step to a hero at the same or an earlier place in the order Fighter, Thief, Wizard, Priest, Bard, Druid.

## Plan scripts

`plan.py` replays a plan written as hero lines through the spec oracle. Each line names a hero and an action:

- `F: RRRD` presses keys, inserting the `A` presses needed to reach the Fighter.
- `P>14,3` walks the Priest to cell (14,3) by the shortest walk that changes nothing else.

It prints the board, the key count and the route, and stops with the board shown at the first death.

## Limits

- The capped search is not exhaustive. An exhausted run means only that no win was found within its caps and cells.
- `--rel-all 1` makes the step model complete, at much higher branching.
- Transposition uses 128-bit hashes without full state comparison. A collision can drop a state. It cannot create a false win, because every printed route is a key sequence for the caller to replay.
