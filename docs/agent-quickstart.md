# Fresh-agent quickstart

Work from the repository root. The Python core has no third-party dependencies. For original browser replay, install the optional browser extra and use an existing Chromium or install Playwright's copy:

```sh
python3 -m pip install -e '.[browser]'
# Only if no usable Chromium is already available:
python3 -m playwright install chromium
```

Original replay downloads the source HTML into a cache; source HTML is not vendored. The browser checker supports `--cache-dir PATH` when you want an explicit cache location. The replay tool may need network access on its first run. See [original-engine checker setup](../experiments/original_engine/README.md).

## Start with the canonical room

```sh
python3 -m soko_mcp catalog
python3 -m soko_mcp get-room --room I-2
```

Catalog entries include all 66 source-pinned original rooms and dated reference baseline provenance. Spoilers, including reference routes, are included. Original I-1 is an eight-key rightward opening. The legacy nine-key room is addressed explicitly as `fixture:I-1`; do not use it as the original puzzle. Baseline lengths and captured routes are historical references, not current records.

## Play and preserve state

For example, play one key in original I-2 and save the portable checkpoint:

```sh
python3 -m soko_mcp play --room I-2 --keys R --checkpoint-out /tmp/i2-play.json
python3 -m soko_mcp play --checkpoint-in /tmp/i2-play.json --action observe
python3 -m soko_mcp play --checkpoint-in /tmp/i2-play.json --action undo --checkpoint-out /tmp/i2-undo.json
python3 -m soko_mcp play --checkpoint-in /tmp/i2-play.json --action reset --checkpoint-out /tmp/i2-reset.json
```

Checkpoints bind the room, pinned sources and complete key route. `step` appends `--keys`; `undo` removes one key; `reset` returns to the initial state; `observe` replays the same route. The tool reconstructs hidden game state from the route on each call. It rejects keys after a win or death. An execution cutoff does not create a checkpoint; recover from the previous checkpoint instead.

## Calibrate before searching

Replay known original routes in the pinned game to check browser setup and puzzle identity:

```sh
python3 -m soko_mcp replay-original --room I-1 --baseline
python3 -m soko_mcp replay-original --room I-22 --baseline
```

These demonstrate original-engine acceptance for those baselines. They do not establish optimality or prove parity for every room. The three current open Frontier proof gaps are III-14, III-20 and III-21 (dated status and references are in [the evaluation](original-eval-and-frontier.md)).

Local verification is a different check. For instance, verify the known original I-1 route locally, then run a deliberately bounded local search on I-2:

```sh
python3 -m soko_mcp verify --room I-1 --route RRRRRRRR
python3 -m soko_mcp solve --room I-2 --budget-sec 5 --beam-width 40000 --max-depth 30
```

The first compares local interpreters. Only `replay-original` invokes the pinned original browser engine. A bounded solve may stop on depth, time or state cap; inspect its termination and completed depth. Do not report baseline reproduction as a new record.

## Research loop

All 66 dated baseline routes have passed [original and local replay comparisons](../evidence/2026-11-12-trilogy-corpus-parity/README.md), including every settled frame's persistent layers. The [installed-agent smoke record](../evidence/2026-11-12-agent-workflow/README.md) exercises real CLI/MCP calls and cross-process checkpoint recovery. These checks cover specific routes; additional strategies still require original replay.

Choose one puzzle and read its tutorial, source pin and baseline using `get-room`; consult the source/evaluation material before assuming a mechanic. Reproduce a known route in the original engine. Make small probes for uncertain rules, then state a hypothesis, control, predicted observation and decision rule. Try bounded local search for subgoals or candidate generation, inspect limits, and validate every complete candidate with `replay-original`. Keep route, source pins, command, parameters, outputs and negative results together. A local `verify` pass is useful differential evidence; it does not replace original replay. A bounded search is not an exhaustive lower-bound proof unless it reports completed depths under the documented contract.

For reusable experiment records, see the [research loop](research-loop.md), including `experiments/record_run.py` and its plans. Preserve source integrity and evidence scope when changing or reporting results; see the README's [portable source integrity](../README.md#portable-source-integrity) notes.
