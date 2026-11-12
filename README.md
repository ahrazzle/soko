# soko (`soko-verified-mcp` v0.3.0 — Domain-General Formal-Systems & Verified-Bar MCP Server)

Model Context Protocol (MCP) server and C++20 verification/search/prover toolkit implementing the [Foundation-0 Repository Standard](https://github.com/Foundation-0) and [Proven-Commons Verified Bar](https://github.com/Proven-Commons/mission/blob/main/playbook/verified-bar.md) across **arbitrary discrete state systems** (`formal_*` suite) as well as Jonah Ostroff's PuzzleScript trilogy. The canonical catalog contains all 66 original rooms (I-1 through III-22), with dated source, tutorial and baseline provenance. See [Agent quickstart](docs/agent-quickstart.md) and [trilogy corpus parity evidence](evidence/2026-11-12-trilogy-corpus-parity/README.md). ([Part I](https://www.puzzlescript.net/editor.html?hack=6860122), [Part II: Monsters](https://www.puzzlescript.net/editor.html?hack=6910207), [Part III: The Bard and The Druid](https://www.puzzlescript.net/editor.html?hack=7072276)) on the [Sokoban Eval Frontier](https://soko.banteg.xyz/frontier/) benchmark ([write-up](https://banteg.xyz/posts/sokoban/)).

Zero third-party Python packages are required (`python >= 3.10` standard library only). On first Sokoban tool call, `soko_mcp` automatically compiles the C++20 engine (`cpp/soko_engine.cpp`) via `g++` or `clang++` (`-O3 -pthread -std=c++20`), while maintaining fail-closed dual-Python verification (`PuzzleScriptOracle` + zero-shared-code `FlatBitmaskOracle`) and honest capability reporting (`soko_capabilities`) even when no C++20 compiler is present.

## What's New in v0.3.0

1. **`PairAtomQuotientPDB` + Multi-Core Exact-State Bucketed A* (`soko_prove_floor`):**
   - Adds a 39.7M-state **2-Atom Quotient Homomorphism Pattern Database (`PairAtomQuotientPDB`)** modeling unordered pairs of created weighing atoms (`{crate@cell, interior_wall@cell, UNBORN, SPARE}`), explicitly accounting for both rigid Bard 5x5 aura co-translation and wall-blocked/moving charmed crate pairs (including step 25 of `III-14`'s 48-key route), Druid `# <-> *` transmutations, border re-petrification, and 10th-crate `SPARE` creation.
   - Replaces per-iteration IDA* re-expansion on grids `<= 128` cells with **Multi-Core Exact-State Bucketed A*** (`CompactNode` full-state equality, zero hash-collision pruning, live collision counter, and runtime `h(s) <= 1 + h(s')` edge checks), raising the built-in MCP certified floor on `III-14` from `29` (in `v0.2.0`) to **`>= 33` in ~6.6s** and **`>= 35` in ~35s** with 100% exact-state deduplication.
   - Adds **`WizardRayGoalBound`** for rooms with Wizard warpballs (`III-15`, `III-20`, `II-22`), eliminating the prior `floor = 1` fallback on Wizard rooms.
2. **Automatic Inductive Invariant & Deadlock-Trap Synthesis (`formal_synthesize_invariant`):**
   - Adds a 7th universal `formal_*` primitive supporting both **Houdini greatest-fixpoint inductive safety invariant synthesis** (`synthesis_mode='houdini_safety'`) and **irreversible forward-closed deadlock-trap synthesis** (`synthesis_mode='deadlock_trap'`) over reachable concrete subgraphs or explicit universal state domains (`universe_code`).
3. **Executable Capability Contract & Review Hardening (`soko_capabilities` + Blocking Fixes):**
   - Adds `soko_capabilities` to report compiler/backend readiness and distinguish `BACKEND_UNAVAILABLE` from `UNSOLVED_WITHIN_BUDGET`.
   - Enforces strict `REPO_ROOT` path confinement (`unconfined_paths`) and mandatory `checker_pins` checks in `soko_verify_tcb_lock`, fail-closed C++ epistemic/witness validation in `soko_prove_floor`, and exact 9-step (`RRRRRRRRR`) `I-1` benchmark metadata.

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

## Exposed MCP Primitives (16 Tools, 5 Resources, 4 Prompts)

| Suite | Primitive | Name | Purpose |
| :--- | :--- | :--- | :--- |
| **Formal** | **Tool** | `formal_define_system` | AST-sandboxed dual-checker registration (`spec_code` != `impl_code` skeleton), negative controls, mutation kills & BFS fuzzing |
| **Formal** | **Tool** | `formal_verify_trace` | Dual-checker step-by-step trace replay with rolling SHA-256 transcript digest and premise assertions |
| **Formal** | **Tool** | `formal_solve_system` | Exact Dijkstra/BFS (goal synthesis or `find_invariant_violation` bug hunting), Diversified Beam, & Sliding-Window LNS |
| **Formal** | **Tool** | `formal_certify_lower_bound` | Zero-trust `PROVEN` lower bounds via finite Quotient Homomorphisms (`project`) or Inductive Potentials (`potential`) |
| **Formal** | **Tool** | `formal_synthesize_invariant` | Automatic Houdini inductive safety invariant synthesis (`houdini_safety`) & irreversible deadlock-trap synthesis (`deadlock_trap`) |
| **Formal** | **Tool** | `formal_triage_portfolio` | Expected-verified-gain priority ranking across open instances |
| **Formal** | **Tool** | `formal_export_ledger` | Export SHA-256-pinned `PROVEN` / `VERIFIED` / `KNOWN` / `CONJECTURE` claim ledger |
| **Sokoban** | **Tool** | `soko_capabilities` | Inspect executable backend readiness, oracle count, lower-bound abstractions, and TCB manifest status |
| **Sokoban** | **Tool** | `soko_list_rooms` | List built-in Frontier rooms (`I-1`, `II-22`, `III-14`, `III-14-15x7`, `III-15`, `III-20`, `III-22`) |
| **Sokoban** | **Tool** | `soko_inspect_room` | Detect `X`/`Y`/`180`-degree symmetries, hero-switch chirality, switch deficits, and Bard constraints |
| **Sokoban** | **Tool** | `soko_verify_route` | Triple-oracle (`PuzzleScriptOracle` + `FlatBitmaskOracle` + `C++20`) per-frame trajectory digest verifier |
| **Sokoban** | **Tool** | `soko_optimize_route` | Shorten seed routes via Sliding-Window Exact BFS + Chiral-Mirror Tube Beam + Iterative Refinement |
| **Sokoban** | **Tool** | `soko_solve_room` | Solve `(part, grid)` rooms from scratch via bucket-diversified C++20 beam search |
| **Sokoban** | **Tool** | `soko_prove_floor` | Multi-Core Exact-State Bucketed A* / Exact-TT IDA* + `PairAtomQuotientPDB` + `BardDruidQuotientPDB` + `WizardRayGoalBound` |
| **Sokoban** | **Tool** | `soko_run_planted_bug_audit` | Cross-oracle baseline parity + 10-mutation Proven-Commons Planted-Bug Suite (`10/10` caught) |
| **Sokoban** | **Tool** | `soko_verify_tcb_lock` | Path-confined runtime `SHA256SUMS` manifest verification and SHA-256 checker pin inspection |

## Verified Frontier Route Ledger (`a1kindus`)

| Room | Keys | Status | SHA-256 (12) | Notes & Submission String |
| :--- | :---: | :---: | :---: | :--- |
| **`III-20` (Primary)** | **`84`** | **`VERIFIED`** | `eecbea96b091` | Live Frontier record (floor `74`): `ADDDRRADAAADRULARADAAADDLLALAAAARRRRUULAAUALLRADRRRRADRULRURRRRRARRUURURAURRRDDRAUUR` |
| **`III-20` (Alt)** | **`84`** | **`VERIFIED`** | `4edff1ad8c90` | Alternate 84-key ending (`URU`): `ADDDRRADAAADRULARADAAADDLLALAAAARRRRUULAAUALLRADRRRRADRULRURRRRRARRUURURAURRRDDRAURU` |
| **`III-14` (`14x7` & `15x7`)** | **`48`** | **`VERIFIED`** | `cd934d25a629` | Matches 48 shortest known (`>= 35` exact-state Pair-Atom PDB floor): `LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR` |
| **`II-22`** | **`94`** | **`VERIFIED`** | `d5e82e8e3c65` | Verified baseline (`92` closed optimal on Frontier): `ADDUUULDDRDDLDULDDRLLLLULURDLDRURUAAUUULLLLLLLAAAULURUARRRARRRDRUUDRRRDLLLDDDLDRLALUADDDRDRRUR` |
| **`III-15`** | **`69`** | **`VERIFIED`** | `76e195c497c1` | Proven optimal: `AULADDALAULDRALAULDALALURALADLUALALDRALAULDALALURALADLUALALDLRAUAULLU` |
| **`I-1` / `III-22`** | **`9`** | **`VERIFIED`** | `179f01ec4093` | Proven optimal opening & finale: `RRRRRRRRR` |

## CLI & Test Quickstart

```bash
# Verify SHA256SUMS lock and run all unit & regression test suites
sha256sum -c SHA256SUMS
python3 -m unittest discover -s tests -v

# Run CLI commands directly
python3 -m soko_mcp capabilities
python3 -m soko_mcp tcb-lock
python3 -m soko_mcp audit
python3 -m soko_mcp prove-floor --room III-14 --max-bound 33 --budget-sec 10
python3 -m soko_mcp verify --room III-20 --route ADDDRRADAAADRULARADAAADDLLALAAAARRRRUULAAUALLRADRRRRADRULRURRRRRARRUURURAURRRDDRAUUR
```
