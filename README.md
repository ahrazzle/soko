# soko: Sokoban MCP replay and bounded search

`soko-verified-mcp` provides nine MCP tools for Jonah Ostroff's [Heroes of Sokoban trilogy](https://www.puzzlescript.net/editor.html?hack=7072276) and locally captured [Sokoban Eval Frontier](https://soko.banteg.xyz/frontier/) instances. Python >=3.10 and its standard library are sufficient for replay and fallback optimization. A C++20 compiler enables native search and a third replay engine; the engine builds on first use into ignored `cpp/build/`.

This project has **not passed the Proven Commons Verified Bar**. `VERIFIED` in a route response means agreement between local interpreters, not a formal proof, externally accepted record, or matching source lock. The experimental `formal_kernel.py` is not exposed as `formal_*` MCP tools.

Read [the original evaluation and Frontier assessment](docs/original-eval-and-frontier.md) before using these fixtures as benchmark inputs. In particular, the local `I-1` differs from Ostroff's original eight-key opening room. The MCP exercise is a regression demonstration, not progress on the live Frontier.

## Connect

Run from the repository root:

```sh
python3 -m soko_mcp
```

For a client with `mcpServers` configuration:

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

The client owns the stdio process. Clients without a `cwd` option can use a shell launcher that changes to the checkout first. A local client registration does not automatically attach the server to a hosted chat.

## Shipped tools

| Tool | Behavior |
| --- | --- |
| `soko_capabilities` | Report available backends |
| `soko_list_rooms` | List historical room metadata and reference routes |
| `soko_inspect_room` | Analyze board symmetry and constraints |
| `soko_verify_route` | Compare two independent Python interpreters, plus C++ when available |
| `soko_optimize_route` | Try a shorter route with bounded exact BFS, then independently replay it |
| `soko_solve_room` | Bounded exact-state BFS from the starting room |
| `soko_prove_floor` | Report fully exhausted goal depths under local C++ transition rules |
| `soko_run_planted_bug_audit` | Run the ten-mutation replay audit |
| `soko_verify_tcb_lock` | Check complete source-manifest consistency; report binary provenance separately |

The server also lists three resources and two prompts. It does not implement the previously advertised PDB heuristic, tube-beam optimizer or general formal-systems MCP suite.

## Search and evidence contracts

Inputs are canonical rectangular ASCII starting rooms of at most 512 cells: exactly one active hero, distinct hero identities and one goal per hero. The format cannot represent a hero initially standing on a goal. Empty/vacuously winning rooms, unsupported symbols and malformed routes are rejected before native execution. Routes accept U/D/L/R/A (normalized to uppercase).

Replay certificates bind the complete normalized problem (part, grid, goal, termination and key-count objective), route and checker hashes. They report `evidence_level: differential_replay`, `formal_proof_checked: false`, and `source_lock_asserted: false`. The 64-bit trajectory digest detects disagreement; it is not a collision-free proof. Agreeing implementations may share a mistaken interpretation.

Native optimization and solving use exact-state BFS, bounded by search time and total stored states. For compatibility, `beam_width` now names the state cap (hard ceiling 200,000), not a beam width. `window_len` applies only to the Python window-BFS fallback. No improvement returns the original independently checked seed. Compilation and replay are additional to the search-phase budget.

Search responses retain `termination_reason`, `completed_depth`, state counts and transition counts. `completed_depth` is the deepest goal depth fully ruled out; a partial next layer does not advance it. The lower bound is `completed_depth + 1`. A shortest witness is independently replayed and has status `VERIFIED`; a witnessless bounded result has status `EXHAUSTIVE_LOWER_BOUND`. Zero budget supports only the trivial floor 0. Rejected backend claims expose no accepted `proven_floor` or guarantee. These are local executable search results, not kernel-checked theorems or external-engine proofs.

## Reproduce the exercise

```sh
python3 -m unittest discover -s tests -v
python3 -m soko_mcp optimize --room I-1 --route URRRRRRRRRD --budget-sec 2
python3 -m soko_mcp prove-floor --room I-1 --max-bound 9 --budget-sec 2
python3 experiments/mcp_smoke.py --help
```

The [recorded MCP exercise](evidence/2026-11-12-mcp-exercise/README.md) includes full stdio requests/responses before and after the change. The old optimizer returned the 11-key I-1 detour unchanged; the bounded BFS returns the known 9-key solution, replayed by three engines. A small-budget III-14 run retained its 48-key seed. Neither result is a new public record.

Built-in floors/records are historical metadata, not fresh claims. For example, the prior [Frontier capture](docs/verified-systems-loop.md) already recorded II-22 closed at 92, while the registry still retains its 94-key reference route. Preserve attribution: puzzles by Jonah Ostroff, captured III-20 route by a1kindus, captured III-21 route by futarchist. See [experiment provenance](experiments/frontier_mac/README.md) and the evidence folders for sources and limitations.

## Portable source integrity

`SHA256SUMS` covers the fixed list of runtime sources in `soko_mcp/integrity.py`, including native source and certificate acceptance code. It excludes compiler-dependent generated binaries. Missing, duplicated, malformed, unexpected or escaping entries fail closed. Check it with:

```sh
python3 -m soko_mcp.integrity
sha256sum -c SHA256SUMS
```

After reviewing an intentional source change, regenerate explicitly with `python3 -m soko_mcp.integrity --write` and review the manifest diff together with the source diff. Normal checks never refresh it automatically.

The compatibility fields `tcb_locked` and `epistemic_status: VERIFIED` on the lock tool mean **source-manifest consistency only** (`lock_scope: source_manifest`). A repository-owned manifest is not a signature or independent approval. The actual compiled binary hash is recorded as provenance with `verified_by_manifest: false`; this is not a reproducible-build guarantee. Route replay and source integrity are separate checks.
