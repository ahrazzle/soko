# Local Frontier reproduction

These experiments replay captured puzzle instances and run a recovered candidate generator. They do not claim formal verification or install the recovered engine as the production MCP backend.

## Sources

The C++ source came from the team's `2026-11-11_soko-verified-mcp-final.zip` package. Its SHA-256 was `518c36ca4ed2f4a3fe310e84fb2355fd3ecf7a5a32710057e6fca3703e855661`. The original engine source SHA-256 was `6d86e0f1068053019fe50d9766c50d1cd84c95152c7ce117c7fbb63b9e5e741d`.

`recovered_engine.cpp` changes only the GNU-only `bits/stdc++.h` include to explicit standard headers. Apple clang 21 failed on the original include. Both the portable clang build and the original source with installed GCC 16 compiled locally. The portable source SHA-256 is `7fb10fc6c80139ba6a7440bdc097c175c65d71c50ac547421a392c8b137f27b6`.

The recovered engine predates the current repository's trajectory-digest interface. It is used only to propose candidates. Every candidate is replayed with the current repository's two Python interpreters. Do not copy it into `cpp/soko_engine.cpp` without porting and testing that interface.

The replay adapter accepts canonical starting rooms with one active hero, distinct hero identities and one goal per hero. Its flat grid cannot represent a hero initially sharing a cell with a goal. Empty or already-overlapping starting problems are outside this adapter.

## Re-run

From the repository root:

```sh
python3 experiments/frontier_mac/replay_instance.py \
  evidence/2026-11-12-frontier/iii21-live-instance.json
python3 experiments/frontier_mac/run_search.py \
  evidence/2026-11-12-frontier/iii21-live-instance.json \
  --budget-sec 60 --beam-width 40000 --window 18 \
  --output /tmp/iii21-search.json
python3 -m unittest discover -s tests -v
```

The search runner adds a process timeout because the recovered optimizer's budget covers beam phases, not the initial and final window searches. No improvement means only that this run returned its seed. It does not narrow the mathematical optimum.

Puzzle design and source are by Jonah Ostroff. The captured III-21 route is by futarchist. The existing III-20 84-key route is held by a1kindus. The evidence folder records the capture URLs and claim scope.

## Every-start window search

`window_search.cpp` scans every route offset instead of stepping by one third of the window size. It tries window widths 12, 16 and 20, retains a 300,000-state cap per window, and reports both candidates and interrupted coverage as JSON lines. `window_search_continue.cpp` resumes III-21 at width-12 offset 295, then starts width 16. These programs expect only the supplied, validated input fixtures.

```sh
clang++ -O3 -std=c++20 experiments/frontier_mac/window_search.cpp -o /tmp/soko-window
/tmp/soko-window < evidence/2026-11-12-frontier/window-search/III-20.in
/tmp/soko-window < evidence/2026-11-12-frontier/window-search/III-21.in
clang++ -O3 -std=c++20 experiments/frontier_mac/window_search_continue.cpp -o /tmp/soko-window-continue
/tmp/soko-window-continue < evidence/2026-11-12-frontier/window-search/III-21-extension.in
```

The recorded runs used one search process at a time. Capped breadth-first search with hash-based deduplication cannot establish optimality. The complete tested sources, fixture inputs, output events and file hashes are retained. Timed coverage can differ across machines.
