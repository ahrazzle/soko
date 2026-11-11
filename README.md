# soko (`soko-verified-mcp`)

Model Context Protocol (MCP) server and C++20 verification/search toolkit applying the [Proven-Commons Verified Bar](https://github.com/Proven-Commons/mission/blob/main/playbook/verified-bar.md) methodology to Jonah Ostroff's PuzzleScript *Heroes of Sokoban* trilogy (Parts I, II, and III) and the [Sokoban Eval Frontier](https://soko.banteg.xyz/frontier) benchmark.

Zero third-party Python packages are required (`python >= 3.10` standard library only). On first tool call, `soko_mcp` automatically compiles the zero-allocation C++20 engine (`cpp/soko_engine.cpp`) via `g++` or `clang++` (`-O3 -pthread -std=c++20`), falling back cleanly to pure Python if no C++20 compiler is installed.

## Why This Architecture Works

Applying the [Proven-Commons Verified Bar](https://github.com/Proven-Commons/mission/blob/main/playbook/verified-bar.md) to combinatorial puzzle search separates specification truth from fast bit/array search:

1. **Spec / Implementation Separation:** `soko_mcp/oracle.py` (`PuzzleScriptOracle`) is a readable, declarative Python specification of Parts I, II, and III; `cpp/soko_engine.cpp` is a zero-allocation C++20 search engine over arbitrary rectangular grids up to 512 cells.
2. **Dual-Oracle Differential Verification:** Every candidate route returned by the solver or optimizer is replayed key-by-key through BOTH engines and receives `"epistemic_status": "VERIFIED"` only when survival, exact final-step win, and final ASCII board states match.
3. **10-Mutation Planted-Bug Audit (`10/10` Caught):** `soko_run_planted_bug_audit` injects 10 realistic PuzzleScript physics bugs (single-crate push collapse, rule-order swap, Bard Manhattan vs Chebyshev radius, Bard post-move charm, non-weighing walls in Part III, Wizard adjacent swap, inactive Priest heal, sequential Goblin kill, `OBJECTS` vs `LEGEND` switch order, and missing `Cancel` on Part I/II blocked moves) and verifies `10/10` detection.
4. **Symmetry & Chiral-Mirror Tube Beam (`87 -> 86 -> 84` on [Room III-20](https://soko.banteg.xyz/frontier/?room=III-20)):** `soko_inspect_room` detects exact `X`, `Y`, and `180`-degree dungeon symmetries paired with chirally asymmetric hero placements. `soko_optimize_route` automatically projects any seed route across the symmetry axis into a role-agnostic target tube, runs iterative tube refinement, and polishes with exact sliding-window BFS.
5. **Step-Consistent Lower Bounds:** `soko_prove_floor` checks `h(s) <= 1 + h(s')` at runtime on every expanded state transition so heuristic bugs fail closed.

## Connect as an MCP Server

### Claude Code
```bash
claude mcp add soko-verified -- python3 -m soko_mcp
```

### Gemini CLI / Cursor / Claude Desktop (`mcpServers` JSON)
```json
{
  "mcpServers": {
    "soko-verified": {
      "command": "python3",
      "args": ["-m", "soko_mcp"],
      "cwd": "/path/to/soko"
    }
  }
}
```

## Exposed MCP Primitives

| Primitive | Name | Purpose |
| :--- | :--- | :--- |
| **Tool** | `soko_list_rooms` | List built-in Frontier rooms, proven floors, targets, live records, and C++20 engine readiness |
| **Tool** | `soko_inspect_room` | Detect `X`/`Y`/`180`-degree symmetries, hero-switch chirality, switch deficits, and Bard constraints on any `(part, grid)` |
| **Tool** | `soko_verify_route` | Dual-oracle (`Python` + `C++20`) differential replay returning SHA-256 `VERIFIED` certificate and final ASCII board |
| **Tool** | `soko_optimize_route` | Shorten any valid route via Sliding-Window Exact BFS + Chiral-Mirror Tube Beam + Iterative Tube Refinement |
| **Tool** | `soko_solve_room` | Solve a custom or Frontier `(part, grid)` room from scratch via bucket-diversified C++20 beam search |
| **Tool** | `soko_prove_floor` | Prove a machine-checked lower bound (`floor >= B`) via IDA* with runtime `h(s) <= 1 + h(s')` edge checks |
| **Tool** | `soko_run_planted_bug_audit` | Run the 10-mutation Proven-Commons Planted-Bug Suite (with optional custom regression vectors) |
| **Resource** | `soko://methodology/verified-bar` | Mapping between Proven-Commons Verified Bar v2 and Sokoban solver/prover design |
| **Resource** | `soko://benchmarks/frontier` | JSON benchmark registry of Frontier rooms, bounds, and verified routes |
| **Resource** | `soko://rules/puzzlescript-trilogy` | Reference rules for Heroes of Sokoban Parts I, II, and III |
| **Prompt** | `break_room_record` | Guided multi-step agent workflow to inspect, verify, chiral-optimize, and certify a new room record |
| **Prompt** | `certify_room_floor` | Guided workflow to audit engine mutations and certify a step-consistent lower bound |

## Verified Frontier Route Ledger (`a1kindus`)

| Room | Keys | Status | SHA-256 (12) | Notes & Submission String |
| :--- | :---: | :---: | :---: | :--- |
| **`III-20` (Primary)** | **`84`** | **`VERIFIED`** | `eecbea96b091` | Beats prior 87 record & 85 holdout target: `ADDDRRADAAADRULARADAAADDLLALAAAARRRRUULAAUALLRADRRRRADRULRURRRRRARRUURURAURRRDDRAUUR` |
| **`III-20` (Alt)** | **`84`** | **`VERIFIED`** | `4c9956790f0a` | Alternate 84-key ending (`URU`): `ADDDRRADAAADRULARADAAADDLLALAAAARRRRUULAAUALLRADRRRRADRULRURRRRRARRUURURAURRRDDRAURU` |
| **`III-14`** | **`48`** | **`VERIFIED`** | `cd934d25a629` | Matches 48 shortest known (`>= 36` Quotient-PDB floor): `LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR` |
| **`II-22`** | **`94`** | **`VERIFIED`** | `d5e82e8e3c65` | Verified baseline (open 92 target): `ADDUUULDDRDDLDULDDRLLLLULURDLDRURUAAUUULLLLLLLAAAULURUARRRARRRDRUUDRRRDLLLDDDLDRLALUADDDRDRRUR` |
| **`III-15`** | **`69`** | **`VERIFIED`** | `76e195c497c1` | Proven optimal: `AULADDALAULDRALAULDALALURALADLUALALDRALAULDALALURALADLUALALDLRAUAULLU` |
| **`III-22`** | **`9`** | **`VERIFIED`** | `179f01ec4093` | Proven optimal finale: `RRRRRRRRR` |

## CLI & Test Quickstart

```bash
python3 -m unittest discover -s tests -v
python3 -m soko_mcp audit
python3 -m soko_mcp inspect --room III-20
python3 -m soko_mcp optimize --room III-20 --budget-sec 35
```
