# Replay in the original trilogy engines

`soko_mcp.original.replay(part, room, route, *, html=None, cache_dir=None, chromium=None, include_frames=False, timeout_sec=30)` executes Jonah Ostroff's original PuzzleScript build in Chromium. Parts 1–3 each have rooms 1–22; routes contain up to 10,000 uppercase U/D/L/R/A keys. Empty and incomplete prefixes return an observation with `valid_winning_route: false`. A winning route must first win on its final key, with no death, restart or unfinished `again` cycle. Replay stops at the first such terminal event. The full execution, including download and browser evaluation, is bounded by the timeout; exceeding it raises `TimeoutError`.

The returned `final_objects` and optional frame `objects` are original column-major PuzzleScript bitfields (`(x * height + y) * stride`); `object_ids` maps names to bit positions. `final_layers` is a row-major list of per-cell object name lists, including goals, notes and background. `final_ascii` shows the highest collision-layer glyph per cell; `?` indicates an object without an original single-character glyph. Prefixes can be replayed from the start to reconstruct a checkpoint; these fields do not assert that objects alone capture all hidden engine state. Results include route, instance, trajectory and certificate hashes, `source_pins`, browser identity, and the executed step count. The checker hash binds the runtime implementation. `--frames` retains each raw executed frame.

The original HTML and embedded source are pinned separately for all three games. HTML is fetched with normal TLS verification into `$XDG_CACHE_HOME/soko-original` (or `~/.cache/soko-original`), never vendored here. Changed files fail closed. Pin updates require source review and revalidation. Browser networking is restricted to the pinned page on an ephemeral loopback server.

The optional runtime needs Python Playwright and Chromium. Install Playwright and either use system Chromium or run `python3 -m playwright install chromium`. Browser selection is explicit `chromium`, `SOKO_CHROMIUM`, system Chromium, then Playwright's installed browser. `curl` is used to download the source.

```sh
python3 experiments/original_engine/check.py --part 3 --room 20 \
  --instance evidence/2026-11-12-frontier/iii20-live-instance.json \
  --output /tmp/iii20-original-replay.json
```

`--part` defaults to 3 for compatibility; alternatively supply `--route`, `--html`, `--cache-dir`, `--chromium`, or `--frames`. Instance grids never replace the original room. Exit 0 means a valid final-key win, exit 1 a nonwinning or invalid route, and exit 2 a setup/runtime failure; failures overwrite the report with a `CHECK_FAILED` attempt.

```sh
python3 -m unittest tests.test_original_engine -v
SOKO_ORIGINAL_HTML=/path/to/part3.html \
SOKO_ORIGINAL_HTML_1=/path/to/part1.html SOKO_ORIGINAL_HTML_2=/path/to/part2.html \
SOKO_ORIGINAL_HTML_3=/path/to/part3.html python3 -m unittest tests.test_original_engine -v
```

The browser tests cover the recorded Part III baselines (48, 84, and 316 keys), premature win, death and truncated routes, as well as all three pinned builds and Part I room 22's ten-key win with three active heroes. The results are local original-build replay evidence, not public-service acceptance or an optimality proof.

Source and puzzle credit: [Jonah Ostroff](https://sites.math.washington.edu/~ostroff/puzzles/Heroes_of_Sokoban.html), [Part II](https://sites.math.washington.edu/~ostroff/puzzles/Heroes_of_Sokoban_II_Monsters.html), [Part III](https://sites.math.washington.edu/~ostroff/puzzles/Heroes_of_Sokoban_III_The_Bard_and_The_Druid.html). The pinned builds execute unchanged; this wrapper observes transitions, win, corpse and restart behavior. Assets and their license/redistribution scope are not supplied here.
