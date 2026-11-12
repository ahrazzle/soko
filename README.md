# soko (`soko-verified-mcp` v0.2.0 — Domain-General Formal-Systems & Verified-Bar MCP Server)

Model Context Protocol (MCP) server and C++20 verification/search toolkit implementing the [Foundation-0 Repository Standard](https://github.com/Foundation-0) and [Proven-Commons Verified Bar](https://github.com/Proven-Commons/mission/blob/main/playbook/verified-bar.md) across **arbitrary discrete state systems** (`formal_*` suite) as well as Jonah Ostroff's PuzzleScript trilogy ([Part I](https://www.puzzlescript.net/editor.html?hack=6860122), [Part II: Monsters](https://www.puzzlescript.net/editor.html?hack=6910207), [Part III: The Bard and The Druid](https://www.puzzlescript.net/editor.html?hack=7072276)) on the [Sokoban Eval Frontier](https://soko.banteg.xyz/frontier/) benchmark ([write-up](https://banteg.xyz/posts/sokoban/)).

Zero third-party Python packages are required (`python >= 3.10` standard library only). On first Sokoban tool call, `soko_mcp` automatically compiles the hardened C++20 engine (`cpp/soko_engine.cpp`) via `g++` or `clang++` (`-O3 -pthread -std=c++20`), while maintaining fail-closed dual-Python verification (`PuzzleScriptOracle` + zero-shared-code `FlatBitmaskOracle`) even when no C++20 compiler is present.

## What's New in v0.2.0 (`fdn0-eval` Audit & Generalization Release)

1. **6 Universal `formal_*` MCP Tools for Arbitrary Problems:** Agents can now approach *any* planning, scheduling, protocol verification, or combinatorial optimization task by registering two independent AST-sandboxed Python checkers (`spec_code` + `impl_code` with distinct alpha-normalized AST skeletons, bridged via `project_obs`), mandatory `must_fail_controls`, and `planted_mutations` (`formal_define_system`), then solving or model-checking (`formal_solve_system`), certifying zero-trust **Quotient Homomorphism** or **Inductive Potential** lower bounds (`formal_certify_lower_bound`), triaging open portfolios (`formal_triage_portfolio`), and exporting SHA-256-pinned epistemic ledgers (`formal_export_ledger`).
2. **Hardened Triple-Oracle Fail-Closed Sokoban Verification (`F-01` & `F-02` Fixes):**
   - Added zero-shared-code `soko_mcp/flat_oracle.py` (`FlatBitmaskOracle`) alongside `soko_mcp/oracle.py` and `cpp/soko_engine.cpp`.
   - `verify_route_dual` starts fail-closed (`differential_match = False`), requires `>= 2` independent engines, and checks **64-bit FNV-1a per-frame trajectory digests (`traj_fnv64`)** across every step `t = 0..L` (including Bard `Note` bitmasks and open-door layers).
3. **Runtime `SHA256SUMS` & Cross-Oracle Mutation Gate (`F-03` Fix):** Added `soko_verify_tcb_lock` and cross-engine baseline parity checks inside `soko_run_planted_bug_audit`.
4. **Collision-Free Exact-State TT & Built-In Quotient-PDB in `soko_prove_floor` (`F-04` Fix):** Replaced 48-bit tag-only TT pruning with full `DynState` equality verification and integrated automatic backward-BFS Quotient-PDB construction for Bard+Druid+PurpleSwitch rooms (including both `14x7` and `15x7` `III-14` variants).

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

## Exposed MCP Primitives (14 Tools, 5 Resources, 4 Prompts)

| Suite | Primitive | Name | Purpose |
| :--- | :--- | :--- | :--- |
| **Formal** | **Tool** | `formal_define_system` | AST-sandboxed dual-checker registration (`spec_code` != `impl_code` skeleton), negative controls, mutation kills & BFS fuzzing |
| **Formal** | **Tool** | `formal_verify_trace` | Dual-checker step-by-step trace replay with rolling SHA-256 transcript digest and premise assertions |
| **Formal** | **Tool** | `formal_solve_system` | Exact Dijkstra/BFS (goal synthesis or `find_invariant_violation` bug hunting), Diversified Beam, & Sliding-Window LNS |
| **Formal** | **Tool** | `formal_certify_lower_bound` | Zero-trust `PROVEN` lower bounds via finite Quotient Homomorphisms (`project`) or Inductive Potentials (`potential`) |
| **Formal** | **Tool** | `formal_triage_portfolio` | Expected-verified-gain priority ranking across open instances |
| **Formal** | **Tool** | `formal_export_ledger` | Export SHA-256-pinned `PROVEN` / `VERIFIED` / `KNOWN` / `CONJECTURE` claim ledger |
| **Sokoban** | **Tool** | `soko_list_rooms` | List built-in Frontier rooms (`I-1`, `II-22`, `III-14`, `III-14-15x7`, `III-15`, `III-20`, `III-22`) |
| **Sokoban** | **Tool** | `soko_inspect_room` | Detect `X`/`Y`/`180`-degree symmetries, hero-switch chirality, switch deficits, and Bard constraints |
| **Sokoban** | **Tool** | `soko_verify_route` | Triple-oracle (`PuzzleScriptOracle` + `FlatBitmaskOracle` + `C++20`) per-frame trajectory digest verifier |
| **Sokoban** | **Tool** | `soko_optimize_route` | Shorten seed routes via Sliding-Window Exact BFS + Chiral-Mirror Tube Beam + Iterative Refinement |
| **Sokoban** | **Tool** | `soko_solve_room` | Solve `(part, grid)` rooms from scratch via bucket-diversified C++20 beam search |
| **Sokoban** | **Tool** | `soko_prove_floor` | Collision-free exact-`DynState` TT + Quotient-PDB IDA* lower-bound prover with runtime `h(s) <= 1 + h(s')` checks |
| **Sokoban** | **Tool** | `soko_run_planted_bug_audit` | Cross-oracle baseline parity + 10-mutation Proven-Commons Planted-Bug Suite (`10/10` caught) |
| **Sokoban** | **Tool** | `soko_verify_tcb_lock` | Runtime `SHA256SUMS` manifest verification and SHA-256 checker pin inspection |

## Verified Frontier Route Ledger (`a1kindus`)

| Room | Keys | Status | SHA-256 (12) | Notes & Submission String |
| :--- | :---: | :---: | :---: | :--- |
| **`III-20` (Primary)** | **`84`** | **`VERIFIED`** | `eecbea96b091` | Beats prior 87 record & 85 holdout target: `ADDDRRADAAADRULARADAAADDLLALAAAARRRRUULAAUALLRADRRRRADRULRURRRRRARRUURURAURRRDDRAUUR` |
| **`III-20` (Alt)** | **`84`** | **`VERIFIED`** | `4edff1ad8c90` | Alternate 84-key ending (`URU`): `ADDDRRADAAADRULARADAAADDLLALAAAARRRRUULAAUALLRADRRRRADRULRURRRRRARRUURURAURRRDDRAURU` |
| **`III-14` (`14x7` & `15x7`)** | **`48`** | **`VERIFIED`** | `cd934d25a629` | Matches 48 shortest known (`>= 36` Quotient-PDB floor): `LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR` |
| **`II-22`** | **`94`** | **`VERIFIED`** | `d5e82e8e3c65` | Verified baseline (open 92 target): `ADDUUULDDRDDLDULDDRLLLLULURDLDRURUAAUUULLLLLLLAAAULURUARRRARRRDRUUDRRRDLLLDDDLDRLALUADDDRDRRUR` |
| **`III-15`** | **`69`** | **`VERIFIED`** | `76e195c497c1` | Proven optimal: `AULADDALAULDRALAULDALALURALADLUALALDRALAULDALALURALADLUALALDLRAUAULLU` |
| **`III-22`** | **`9`** | **`VERIFIED`** | `179f01ec4093` | Proven optimal finale: `RRRRRRRRR` |

## CLI & Test Quickstart

```bash
# Verify SHA256SUMS lock and run all 10 multi-domain MCP verification tests
sha256sum -c SHA256SUMS
python3 -m unittest discover -s tests -v

# Run CLI commands directly
python3 -m soko_mcp tcb-lock
python3 -m soko_mcp audit
python3 -m soko_mcp prove-floor --room III-14 --max-bound 30 --budget-sec 8
python3 -m soko_mcp verify --room III-20 --route ADDDRRADAAADRULARADAAADDLLALAAAARRRRUULAAUALLRADRRRRADRULRURRRRRARRUURURAURRRDDRAUUR
```
