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

## Recorded runs (2026-11-14)

| Room | Seed | Depth / node cap per L | Result | Wall time |
| --- | --- | --- | --- | ---: |
| I-1 fixture | `URRRRRRRRRD` (11) | 10 / 100k | 9 (`RRRRRRRRR`), positive control | <0.01 s |
| III-20 | prior 87-key record | 11 / 2M | no shortcut; the 87 → 84 gain needs a plan change (mirrored guide) | 2.6 s |
| III-21 | 316-key record (@futarchist) | 12 / 1.5M | no shortcut | 82 s |

A negative result holds only within its depth and node cap. It does not show the route is optimal.
