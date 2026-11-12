# soko: original trilogy replay and bounded search

`soko-verified-mcp` provides MCP tools and a JSON CLI for Jonah Ostroff's [Heroes of Sokoban trilogy](https://www.puzzlescript.net/editor.html?hack=7072276). The canonical catalog contains all 66 original rooms (I-1 through III-22), with dated source, tutorial and baseline provenance. The historical `fixture:I-1` is separate: it retains the nine-key regression room and is not original I-1.

Python >=3.10 and its standard library are sufficient for catalog access, local replay and fallback optimization. C++20 enables native search. Original browser replay uses Playwright and Chromium; see [Agent quickstart](docs/agent-quickstart.md). All 66 captured baselines pass original replay, with 3,129 initial and settled states matching the local persistent-layer comparison. See the [reproducible parity evidence](evidence/2026-11-12-trilogy-corpus-parity/README.md). This covers the recorded routes, not every possible trajectory or an optimality proof. A bounded search result reports its limits; baseline reproduction is not a new record.

This checkout has **not completed Proven-Commons Verified Bar review**. `VERIFIED` on a local route means at least two checkers agreed on survival, exact win, steps, final grid and trajectory digest with checker hashes present. The stdio server exposes twelve `soko_*` tools; `formal_kernel.py` ships in the manifest only. Local agreement is separate from original-engine replay and source-manifest consistency.

Read [the original evaluation and Frontier assessment](docs/original-eval-and-frontier.md) before using these fixtures as benchmark inputs. Follow the [research loop](docs/research-loop.md): pin an instance and dated baseline, calibrate checker and generator, state a hypothesis and control, run a bounded experiment, and use the result to choose the next test. The [Frontier campaign record](evidence/2026-11-12-frontier-campaign/README.md) preserves negative coverage and findings. The [original-engine checker](experiments/original_engine/README.md) validates candidate routes independently of local oracles.

## Connect

From the repository root, run `python3 -m soko_mcp` for MCP JSON-RPC over stdio. A client can register it as:

```json
{
  "mcpServers": {
    "soko-verified": {
      "command": "python3",
      "args": ["-m", "soko_mcp"],
      "cwd": "/absolute/path/to/soko"
    }
  }
}
```

The client owns the stdio process. A local client registration does not automatically attach the server to a hosted chat.

The MCP server exposes capabilities, catalog/get-room, inspection, local verify/solve/optimize/prove-floor, original replay/play, audit and source-lock tools. The exact names and request schemas are in `soko_mcp/server.py`; matching CLI commands are listed by `python3 -m soko_mcp --help`.

## Search and evidence contracts

Local search inputs are rectangular ASCII starting rooms of at most 512 cells: at least one active hero, distinct hero identities and one goal per hero. Multiple active heroes are supported, including original I-22. The format cannot represent a hero initially standing on a goal. Empty/vacuously winning rooms, unsupported symbols and malformed routes are rejected before native execution. Routes accept U/D/L/R/A (normalized to uppercase).

Replay certificates bind the complete normalized problem (part, grid, goal, termination and key-count objective), route and checker hashes. They report `evidence_level: differential_replay`, `formal_proof_checked: false`, and `source_lock_asserted: false`. The 64-bit trajectory digest detects disagreement; it is not a collision-free proof. Agreeing implementations may share a mistaken interpretation.

Native optimization and solving use exact-state BFS, bounded by search time and total stored states. For compatibility, `beam_width` now names the state cap (hard ceiling 200,000), not a beam width. `window_len` applies only to the Python window-BFS fallback. No improvement returns the original independently checked seed. Compilation and replay are additional to the search-phase budget.

Search responses retain `termination_reason`, `completed_depth`, state counts and transition counts. `completed_depth` is the deepest goal depth fully ruled out; a partial next layer does not advance it. The lower bound is `completed_depth + 1`. A shortest witness is independently replayed and has status `VERIFIED`; a witnessless bounded result has status `EXHAUSTIVE_LOWER_BOUND`. These are local executable search results, not kernel-checked theorems or external-engine proofs.

## Portable source integrity

`SHA256SUMS` covers the fixed list of runtime sources in `soko_mcp/integrity.py`, including native source and certificate acceptance code. It excludes compiler-dependent generated binaries. Missing, duplicated, malformed, unexpected or escaping entries fail closed. Check it with:

```sh
python3 -m soko_mcp.integrity
sha256sum -c SHA256SUMS
```

After reviewing an intentional source change, regenerate explicitly with `python3 -m soko_mcp.integrity --write` and review the manifest diff together with the source diff. Normal checks never refresh it automatically.

The compatibility fields `tcb_locked` and `epistemic_status: VERIFIED` on the lock tool mean **source-manifest consistency only** (`lock_scope: source_manifest`). A repository-owned manifest is not a signature or independent approval. The actual compiled binary hash is recorded as provenance with `verified_by_manifest: false`; this is not a reproducible-build guarantee. Route replay and source integrity are separate checks.
