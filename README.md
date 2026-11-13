# soko (`soko-verified-mcp` v0.4.0 — Domain-General Formal-Systems & Verified-Bar MCP Server)

Model Context Protocol (MCP) server and C++20 verification/search/prover toolkit implementing the [Foundation-0 Repository Standard](https://github.com/Foundation-0) and [Proven-Commons Verified Bar](https://github.com/Proven-Commons/mission/blob/main/playbook/verified-bar.md) across **arbitrary discrete state systems** (`formal_*` suite) as well as Jonah Ostroff's PuzzleScript trilogy ([Part I](https://www.puzzlescript.net/editor.html?hack=6860122), [Part II: Monsters](https://www.puzzlescript.net/editor.html?hack=6910207), [Part III: The Bard and The Druid](https://www.puzzlescript.net/editor.html?hack=7072276)) on the [Sokoban Eval Frontier](https://soko.banteg.xyz/frontier/) benchmark ([write-up](https://banteg.xyz/posts/sokoban/)).

Zero third-party Python packages are required (`python >= 3.10` standard library only). On first Sokoban tool call, `soko_mcp` automatically compiles the C++20 engine (`cpp/soko_engine.cpp`) via `g++` or `clang++` (`-O3 -pthread -std=c++20`), while maintaining fail-closed dual-Python verification (`PuzzleScriptOracle` + zero-shared-code `FlatBitmaskOracle`) and honest capability reporting (`soko_capabilities`) even when no C++20 compiler is present.

## What's New in v0.4.0 (Two-Way `Foundation-0` Synthesis)

1. **`Foundation-0/gfq-codes` Exact Rational LP Dual & Cost-Partitioned Quotient Certificates (`formal_certify_lower_bound`):**
   - Adds `proof_mode='cost_partitioned_quotients'` (exact `fractions.Fraction` additive action-cost partitioning $\sum_m w_m(s,a,s') \le \text{cost}(s,a,s')$ across $M \ge 2$ Quotient Graph Homomorphisms, strictly dominating pointwise $\max_m h_m$) and `proof_mode='rational_lp_dual'` (exact `fractions.Fraction` state-equation / operator-counting Farkas dual multiplier verification $y \ge 0$, $y^\top(F(s')-F(s)) \le \text{cost}(s,a,s')$ with **zero floating-point LP solver in the TCB**).
2. **`Foundation-0/finite-state-proofs` Exact 4-Cell Row Strip Automaton (`FastRowStripPDB`) & `F-11`/`F-12` Soundness Audit (`cpp/frontier_iii14_iii20_prover.cpp`):**
   - Stress-testing `v0.3.0`'s hand-written analytical `h_iii14_fast` across 15.5M concrete transitions uncovered two subtle inadmissibility hazards: **`F-11`** (assuming 9 switch-weighing atoms instead of 7/8-atom hero tandem entry when `open_pdoors != 0`) and **`F-12`** (independent `xs`/`ys` order-statistic window slicing dropping `10 -> 8` on a single Druid transmutation).
   - Replaces hand-written analytical formulas completely with a **100% pure 5-Quotient-PDB Homomorphism Suite** (`FastRowStripPDB` tracking `{empty, crate, wall}^4` on `(4..7, y)` across `y = 2, 3, 4` via `y <-> 6 - y` vertical symmetry + `PairAtomHomPDB` + `HarvestColPDB` + `BardDruidQuotientPDB`), certifying **`proven_floor >= 34`** across **`81,439,505` exact `Packed14` states**, catching **`23,879` live 64-bit hash collisions**, and passing **`127,373,463` runtime `h(s) <= 1 + h(s')` edge checks with `0` violations**.
   - Unlocks `M.n <= 256` Multi-Core Exact-State Bucketed A* in `cpp/soko_engine.cpp` (covering `III-20` `15x9=135` and `II-22` `13x13=169`), raising the generic MCP certified floor on `III-20` from `25` (`v0.3.0`) to **`>= 48` in 30.1s** (`8,475,805` nodes expanded, **`77,437` live 64-bit hash collisions caught**, `25,096,136` runtime edge checks with `0` violations).
3. **`Foundation-0/formal-claims-audit` Static AST Soundness & Anti-Tautology Tool (`formal_audit_checkers` — 17th MCP Tool):**
   - Synchronized with `Foundation-0/formal-claims-audit#16` (alongside `Foundation-0/math0#9` and `Foundation-0/f0#36`): audits single or dual Python checkers for `F-01` optimistic `True` flags, IEEE-754 float drift, vacuous stubs, and alpha-renamed copy-paste tautologies.
4. **`Foundation-0/incentre-lattices` Locked-Checker `tracks/` Harness (`tracks/iii-14/`, `tracks/iii-20/`):**
   - Adds standalone dual-oracle `verify.py` scripts and append-only `results.tsv` ledgers logging both breakthroughs and negative high-width LNS runs.

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

## Exposed MCP Primitives (17 Tools, 5 Resources, 4 Prompts)

| Suite | Primitive | Name | Purpose |
| :--- | :--- | :--- | :--- |
| **Formal** | **Tool** | `formal_define_system` | AST-sandboxed dual-checker registration (`spec_code` != `impl_code` skeleton), negative controls, mutation kills & BFS fuzzing |
| **Formal** | **Tool** | `formal_verify_trace` | Dual-checker step-by-step trace replay with rolling SHA-256 transcript digest and premise assertions |
| **Formal** | **Tool** | `formal_solve_system` | Exact Dijkstra/BFS (goal synthesis or `find_invariant_violation` bug hunting), Diversified Beam, & Sliding-Window LNS |
| **Formal** | **Tool** | `formal_certify_lower_bound` | Zero-trust `PROVEN` lower bounds via Quotient Homomorphisms, Inductive Potentials, Rational Cost-Partitioned Quotients, or Rational LP Duals |
| **Formal** | **Tool** | `formal_synthesize_invariant` | Automatic Houdini inductive safety invariant synthesis (`houdini_safety`) & irreversible deadlock-trap synthesis (`deadlock_trap`) |
| **Formal** | **Tool** | `formal_triage_portfolio` | Expected-verified-gain priority ranking across open instances |
| **Formal** | **Tool** | `formal_export_ledger` | Export SHA-256-pinned `PROVEN` / `VERIFIED` / `KNOWN` / `CONJECTURE` claim ledger |
| **Formal** | **Tool** | `formal_audit_checkers` | Static AST soundness & alpha-normalized anti-tautology auditor for single or dual Python checkers |
| **Sokoban** | **Tool** | `soko_capabilities` | Inspect executable backend readiness, oracle count, lower-bound abstractions, and TCB manifest status |
| **Sokoban** | **Tool** | `soko_list_rooms` | List built-in Frontier rooms (`I-1`, `II-22`, `III-14`, `III-14-15x7`, `III-15`, `III-20`, `III-22`) |
| **Sokoban** | **Tool** | `soko_inspect_room` | Detect `X`/`Y`/`180`-degree symmetries, hero-switch chirality, switch deficits, and Bard constraints |
| **Sokoban** | **Tool** | `soko_verify_route` | Triple-oracle (`PuzzleScriptOracle` + `FlatBitmaskOracle` + `C++20`) per-frame trajectory digest verifier |
| **Sokoban** | **Tool** | `soko_optimize_route` | Shorten seed routes via Sliding-Window Exact BFS + Chiral-Mirror Tube Beam + Iterative Refinement |
| **Sokoban** | **Tool** | `soko_solve_room` | Solve `(part, grid)` rooms from scratch via bucket-diversified C++20 beam search |
| **Sokoban** | **Tool** | `soko_prove_floor` | Multi-Core Exact-State Bucketed A* (`<= 256` cells) + `PairAtomQuotientPDB` + `RowStripQuotientPDB` + `BardDruidQuotientPDB` + `WizardRayGoalBound` |
| **Sokoban** | **Tool** | `soko_run_planted_bug_audit` | Cross-oracle baseline parity + 10-mutation Proven-Commons Planted-Bug Suite (`10/10` caught) |
| **Sokoban** | **Tool** | `soko_verify_tcb_lock` | Path-confined runtime `SHA256SUMS` manifest verification and SHA-256 checker pin inspection |

## Verified Frontier Route Ledger (`a1kindus`)

| Room | Keys | Status | SHA-256 (12) | Notes & Submission String |
| :--- | :---: | :---: | :---: | :--- |
| **`III-20` (Primary)** | **`84`** | **`VERIFIED`** | `eecbea96b091` | Live Frontier record (floor `74`): `ADDDRRADAAADRULARADAAADDLLALAAAARRRRUULAAUALLRADRRRRADRULRURRRRRARRUURURAURRRDDRAUUR` |
| **`III-20` (Alt)** | **`84`** | **`VERIFIED`** | `4edff1ad8c90` | Alternate 84-key ending (`URU`): `ADDDRRADAAADRULARADAAADDLLALAAAARRRRUULAAUALLRADRRRRADRULRURRRRRARRUURURAURRRDDRAURU` |
| **`III-14` (`14x7` & `15x7`)** | **`48`** | **`VERIFIED`** | `cd934d25a629` | Matches 48 shortest known (`>= 34` pure 5-Quotient-PDB floor across `81.44M` exact states): `LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR` |
| **`II-22`** | **`94`** | **`VERIFIED`** | `d5e82e8e3c65` | Verified baseline (`92` closed optimal on Frontier): `ADDUUULDDRDDLDULDDRLLLLULURDLDRURUAAUUULLLLLLLAAAULURUARRRARRRDRUUDRRRDLLLDDDLDRLALUADDDRDRRUR` |
| **`III-15`** | **`69`** | **`VERIFIED`** | `76e195c497c1` | Proven optimal: `AULADDALAULDRALAULDALALURALADLUALALDRALAULDALALURALADLUALALDLRAUAULLU` |
| **`I-1` / `III-22`** | **`9`** | **`VERIFIED`** | `179f01ec4093` | Proven optimal opening & finale: `RRRRRRRRR` |

## CLI & Test Quickstart

```bash
# Verify SHA256SUMS lock and run all unit & regression test suites
sha256sum -c SHA256SUMS
python3 -m unittest discover -s tests -v

# Run locked track verifiers (Foundation-0 / incentre-lattices pattern)
python3 tracks/iii-14/verify.py
python3 tracks/iii-20/verify.py
```
