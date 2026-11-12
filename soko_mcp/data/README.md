# Trilogy catalog provenance

`catalog.json` contains all 66 original rooms, in the original part and room order. Canonical IDs run from `I-1` to `III-22`. `soko_mcp.catalog` loads this file without network access and returns independent copies of metadata.

Puzzle design and original PuzzleScript implementation are by **Jonah Ostroff**. Each room identifies the original hosted HTML URL, its SHA256 pin, and the extracted `sourceCode` SHA256. The original HTML is cached externally and is not vendored here. Grid coordinates retain the original top-left origin and row order; there is no rotation, trimming of walls, or room simplification. Original compiled object arrays use column-major order. The zero-based `compiled_level_index` counts intervening message entries, whereas `room` counts playable rooms only. `tutorial_messages` are the message entries immediately before that room; final thanks messages remain in the source's `compiled_entries` metadata.

`baseline` separately credits each public accepted route's named Frontier holder. It records the replay ID, route, length, API and browser URLs, observation timestamp, and SHA256 of the complete API response. `frontier_snapshot.json` preserves the 66 public room records used to select those replay IDs. The reported `proven_floor` and `shortest_known` are public Frontier observations; importing them does not independently establish a lower-bound proof or route optimality. The captured routes total 3,063 keys. No route was submitted during this import.

Rebuild using Python's standard library:

```sh
python tools/import_catalog.py --cache-dir /tmp/soko-catalog-cache
python tools/import_catalog.py --cache-dir /tmp/soko-catalog-cache --offline --output /tmp/rebuilt-catalog.json
cmp soko_mcp/data/catalog.json /tmp/rebuilt-catalog.json
python -m unittest tests.test_catalog -v
```

The first command downloads the three pinned originals and the selected public replay responses, with at most three concurrent replay requests. Existing cache entries are reused. The cache stores response observation timestamps alongside API responses. A source hash mismatch, missing offline response, replay-room mismatch, holder mismatch, or route-length mismatch aborts the import. Preserve the cache for byte-for-byte regeneration, including its observation timestamp sidecars. A fresh cache makes a new dated observation, so its timestamps can differ. To choose a future set of records, supply a new `--frontier` snapshot explicitly and review the resulting catalog changes.

During initial capture on November 12, 2026, all 66 grids were compared with the original extracted source grids, and every compiled index was separately checked against `state.levels` in the three original self-contained HTML builds running in Chromium. Catalog tests pin the resulting grids and index lists. I-22 legitimately begins with three active heroes and is preserved exactly.
