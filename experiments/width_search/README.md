# Width-based search (IW, novelty beams)

Planners that play Atari games from a simulator, with no reward shaping, use
*novelty* rather than a heuristic to decide which states to keep: IW(k)
(Lipovetzky & Geffner 2012; Lipovetzky, Ramirez & Geffner 2015) and BFWS
(Lipovetzky & Geffner 2017). A state is kept only if it makes some tuple of at
most k atoms true for the first time. These files test whether that helps where
`experiments/bounded_beam` failed: the beam loses III-14's 48-key route on a
heuristic plateau around g = 30.

```sh
g++ -O3 -pthread -std=c++20 experiments/width_search/iw.cpp -o /tmp/iw
# stdin: part w h k max_depth, then the grid rows
g++ -O3 -pthread -std=c++20 experiments/width_search/novelty_beam.cpp -o /tmp/novelty_beam
# stdin: part w h bound width seed share, then the grid rows
# (seed 0: read a reference route after the grid and report whether each of its states is kept)
```

Every route printed here is only a candidate for the Python oracles and the pinned
original build. Neither tool proves anything.

## IW(k)

Atoms are (cell, object) facts, Bard note cells and door flags; walls are left out
when the room has no druid. IW is breadth-first, so the first route it finds is the
shortest among the states it kept.

| Room | Optimum | IW(1) | IW(2) |
|---|---:|---|---|
| I-1 | 8 | 8 (25 states) | 8 (25 states) |
| I-22 | 10 | 10 | 10 |
| III-22 | 9 | 9 | 9 |
| III-15 | 69 | exhausted at depth 3 | 72 (3,114 states, 0.02 s) |
| II-12 | 26 | exhausted at depth 6 | exhausted at depth 27 (2,604 states) |
| II-22 | 92 | exhausted at depth 7 | exhausted at depth 149 (160,781 states) |
| III-14 | 48 (record) | exhausted at depth 21 | exhausted at depth 78 (39,589 states) |
| III-20 | 84 (record) | exhausted at depth 9 | exhausted at depth 19 (1,099 states) |
| III-21 | 316 (record) | exhausted at depth 28 | exhausted at depth 107 (21,864 states) |

IW(2) is cheap and sometimes close to optimal, but the open rooms are wider than 2.

## Novelty-first bounded beam

`novelty_beam.cpp` is `bounded_beam` with a different selection. The g + h > B
pruning (admissible, so it never cuts a route of length <= B) and the exact
deduplication are unchanged. Each candidate gets a novelty w: 1 for a new atom, 2
for a new pair of atoms, 3 otherwise, counted among kept states with the same h, as
in BFWS. Atoms are only the cells that differ from the start position. A share
`s` of the width is filled in (w, h) order and the rest in h order.

Positive control: III-14 at bound 48, width 200,000, tracking the known 48-key
route.

| Novelty share | Last layer that keeps the 48-key route |
|---:|---:|
| 0% (pure h) | 31 |
| 10% | 29 |
| 30% | 29 |
| 50% | 29 |
| 100% (pure novelty first) | 17 |

Novelty makes it worse. With pure novelty-first selection, states with a new pair of
atoms fill the whole beam by g = 18, and the route's state isn't among them. None of
these runs finds a route of 48 or less.

## Why: the heuristic is blind to the setup

Along the 48-key route, h (the `prove_lb` heuristic) and the true remaining
distance 48 - g are:

```
g      0   8  17  24  30  36  40  44  48
h     22  17  13   7   8   8   6   4   0
48-g  48  40  31  24  18  12   8   4   0
```

h is 22 at the start against a proven 44, and it stays flat at 7 or 8 from key 24 to
key 39 while the route closes a gap of 17 down to 2. Those keys are the setup: the
Druid turns border walls into crates, the Bard's aura herds them onto the nine purple
switches, and the Druid sets them as walls in column 6. Only then do the doors around
the goals open. Neither a lowest-h beam nor a novelty beam can tell those keys from
dead ends, so the next step is a better bound, not a different beam: pattern
conflicts as in Rolling Stone, or switch and object-source landmarks (issue #53,
section E).
