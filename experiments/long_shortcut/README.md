# Long-range trajectory shortcuts

`long_shortcut.cpp` runs a bounded exact BFS from every position `L` of a winning
route and looks up each reached state among *all* later trajectory states. Reaching
`traj[k]` at depth `d` with `k - L > d` shortens the route by `k - L - d`.
`exact_window_shortcut` in the engine only replaces a segment that is at most the
BFS depth long. This search can replace a long stretch with a short detour. It reuses the
native engine (`cpp/soko_engine.cpp`) and its step function, which the catalog-wide
differential test checks against the readable oracle.

```sh
g++ -O3 -pthread -std=c++20 experiments/long_shortcut/long_shortcut.cpp -o /tmp/long_shortcut
# stdin: part w h depth node_cap threads, then the grid rows, then the route
```

The tool only proposes candidates. Each one still needs Python oracle replay and the
pinned original build before anyone claims it.

## Splicing public routes

`splice.cpp` merges the trajectories of many winning routes into one graph of exact
native states. The shortest start-to-win path through that graph recombines prefixes
and suffixes of different routes wherever they meet. It then runs a bounded BFS
"bridge" from every state in the graph and looks for any state with a known cost to
win. Improvements are folded back in and the search repeats.

```sh
g++ -O3 -pthread -std=c++20 experiments/long_shortcut/splice.cpp -o /tmp/splice
# stdin: part w h depth node_cap threads n_routes, then the grid rows, then one route per line
```

## Recorded runs (2026-11-14)

| Room | Seed | Depth / node cap per L | Result | Wall time |
| --- | --- | --- | --- | ---: |
| I-1 fixture | `URRRRRRRRRD` (11) | 10 / 100k | 9 (`RRRRRRRRR`), positive control | <0.01 s |
| III-20 | prior 87-key record | 11 / 2M | no shortcut; the 87 → 84 gain needs a plan change (mirrored guide) | 2.6 s |
| III-21 | 316-key record (@futarchist) | 12 / 1.5M | no shortcut | 82 s |
| III-20 | 84-key record (@a1kindus) | 14 / 2M | no shortcut | 61 s |
| III-21 | 316-key record (@futarchist) | 16 / 3M | no shortcut | 2,078 s |
| III-14 | 48-key record (@SJanuskas) | 16 / 2M | no shortcut | 456 s |

Splicing every public record replay (`soko.banteg.xyz/api/rooms/<part>/<room>`, then `/api/replay/<id>`):

| Room | Routes (lengths) | Union states | Union shortest | Bridges (depth / cap per state) | Result |
| --- | --- | ---: | ---: | --- | --- |
| III-21 | 30 (316–589, 8 authors) | 4,551 | 316 | 8 / 40k | 316, 59 s |
| III-20 | 9 (84–145) | 725 | 84 | 12 / 400k | 84, 58 s |
| III-14 | 7 (48–116) | 409 | 48 | 14 / 400k | 48, 307 s |

Each record is already the best recombination of every published plan for its room,
and no bridge within these limits improves it.

The engine's own `optimize` mode (mirror-guided tube beam, width 200,000, window 16,
900 s budget), run on the current records after the state-hash fix in `ba0c864`, also
finds nothing: III-20 stays at 84 (69 s) and III-21 at 316 (142 s).

A negative result holds only within its depth and node cap. It does not show the route is optimal.
