# Sokoban Evaluation Domain Pack (`mde:soko-eval`)

`mde_soko` packages a Sokoban evaluation domain (`mde:soko-eval`), a deterministic CPU `float64` `BetaEdit` adapter compiler, and a four-mode benchmark runner inside `ahrazzle/soko`. Every Sokoban rule check and trajectory replay runs through `soko_mcp` without modifying any of the 21 checker and prover files locked in root `SHA256SUMS`.

## Quick Verification (`pytest + numpy` only)

From a fresh clone of this repository:

```bash
python3 -m soko_mcp.integrity
python3 -O -B -m pytest -p no:cacheprovider tests/test_mde_soko.py
python3 -B -m mde_soko verify
python3 -B -m mde_soko prose-check
```

`tests/test_mde_soko.py` runs in under 10 seconds without GPU hardware, `torch`, or network access. It checks the 21 locked TCB source hashes, Plane 1 lineage digests, the 66-room split partition, label-free inference grading, the 4.0-second zero-import Python cell sandbox, certificate detectors `F01` through `F08`, and `9/9`-file `0`-byte CPU `float64` adapter re-derivation.

## Directory Layout

- `mde_soko/spec/`: `plane1_soko_spec.md` (six Sokoban evaluation habits), `zone-manifest.soko_eval.v0.1.json`, and `lineage.json`.
- `mde_soko/datasets/`: `compile.jsonl` (`32` rooms), `validation.jsonl` (`16` rooms), `benchmark_18_rooms.json` (`18` rooms, 6 per part, zero spoiler routes), `hybrid_k0.jsonl` (`512` seeded noise draws + `24` `y = 0` anchors), `manifest.json`, and `SHA256SUMS`.
- `mde_soko/artifacts/`: `harvested_soko_activations.npz` (`908,726` bytes, `<1 MiB`), `p2b/` (`9` deterministic `BetaEdit` artifacts across `GGUF v3` F16, `weft-slab/v0.1` `f16`/`int4_int8`/`int4_f16`, certificates, binding, `warp_bundle.json`, and `wmcp_meta.json`), `p2a/` (unprojected norm-matched control), and `controls/` (low-norm sabotage control).
- `mde_soko/domain_oracle.py`: `SokoDomainOracle` (`DomainOracle` protocol), `SokoPlaySession` (`S2`), `execute_sandbox_cell` (`S3`), and `audit_soko_certificate` (`F01` through `F08`).
- `mde_soko/compiler.py`: closed-form CPU `float64` `BetaEdit` Cholesky + skinny-QR solver, pre-registered integer `GatePolicy`, strict integer JSON certificate parser, and `verify_zero_byte_rederivation`.
- `mde_soko/runner.py`: live `llama-server` evaluation harness across `validation.jsonl` (`16` rooms), `24` `step0` logprob retention anchors, and the 18-room original trilogy benchmark (`S0` through `S3`).
- `mde_soko/CROSS_POLLINATION.md`: inbound and outbound mechanism ledger across `mcproof`, `weft`, `siliquant`, and external verification repositories.

## Pre-Registered Stage 2 Certificate Separation

`PRE_REGISTERED_GATE_POLICY` fixes integer rational bounds (`radix_scale_exp2 = 24`) prior to compilation (`||dW||_F^2 <= 25.0`, `||dW||_2^2 <= 18.0`, `Tr(dW C_K0 dW^T) <= 35.0`, and `max_s <dW, S_s>^2 / ||S_s||_F^2 <= 5e-4`):

| Artifact | `\|\|dW\|\|_F^2` | `K0` leakage (`f16`) | `K0` leakage (`int4/int8`) | `K0` leakage (`int4/f16`) | Max safety dot sq | Gate verdict |
|---|---:|---:|---:|---:|---:|---|
| `P2-B` (`BetaEdit` null-space) | `0.228831` | `5.29e-5` | `4.12e-3` | `5.16e-5` | `5.96e-8` | PASS (`3/3` slabs) |
| `P2-A` (unprojected, norm-matched) | `0.228833` | `330.871` | n/a | n/a | `< 1e-6` | REJECT (`leakage_energy_exceeds_cap`) |
| `Sabotage` (low-norm rank-4 control) | `5.062952` | `447248.18` | n/a | n/a | `0.300256` | REJECT (`leakage` + `safety_dot`) |

## Live `Qwen3.5-4B` Evaluation (`mde_soko/results/soko_eval_live_receipt.json`)

Executed locally on `Qwen3.5-4B-Q8_0.gguf` (`sha256: 10cc391b...`, `llama-server` `0.5.0` commit `7fe450e19`, `temperature = 0.0`, `top_p = 1.0`, `seed = 20261119`, per-slot erase across Gated DeltaNet layers):

- **Live `step0` off-register retention (`24` `y = 0` anchors)**: `P2-B` achieves `24/24` (`100.0%`) top-1 token agreement with `B0` (`mean_abs_top1_logprob_delta = 0.000533`, max `0.002904`), whereas norm-matched unprojected `P2-A` drops to `20/24` (`83.33%`, `mean_abs_top1_logprob_delta = 0.500661`, max `3.965778`, `939x` larger shift).
- **Public `validation.jsonl` (`16` rooms, `1`-shot open-loop)**: `B0` scores `4/16` (`25.0%`, `4/4` on `H_RULE` and `0/12` on `H_ROUTE`/`H_PROBE`/`H_CELL`), while `P2-A` and `P2-B` each score `1/16` (`6.25%`, `1/4` on `H_RULE`). Single-layer rank-8 weight editing preserves off-register behavior (`100%` `step0` agreement) without solving unseen single-shot Sokoban routes at `4B` scale.
- **18-room original trilogy benchmark (`S0` through `S3`, `240`-key unsolved horizon cap)**:

| Condition | Exact wins | Bare JSON / probe rate | Horizon-charged keys (`mean`) | Lexicographic key | Key runtime events |
|---|---:|---:|---:|---|---|
| `S0` (`B0` open-loop) | `0/18` (`0.0%`) | `11/18` (`61.1%` bare JSON) | `4320` (`240.0`) | `[1, 0, -4320]` | `11` `GOALS_NOT_MET`, `7` `MISSING_JSON_KEYS` |
| `S1` (`P2-B` open-loop) | `0/18` (`0.0%`) | `11/18` (`61.1%` bare JSON) | `4320` (`240.0`) | `[1, 0, -4320]` | `11` `GOALS_NOT_MET`, `7` `MISSING_JSON_KEYS` |
| `S2` (`P2-B` stateful probe loop) | `1/18` (`5.6%`, `I-1`) | `18/18` (`100.0%` probed) | `4088` (`227.1`) | `[1, 1, -4088]` | `5` fatal steps rolled back safely, `8` stagnation warnings |
| `S3` (`P2-B` 4.0s Python cell, `k <= 4`) | `0/18` (`0.0%`) | `1` forbidden import blocked | `4320` (`240.0`) | `[1, 0, -4320]` | `2` `PREMATURE_WIN_EXTRA_KEYS` (`I-1`), `2` `4.0s` timeouts, `1` `DUAL_ORACLE_MISMATCH` (`II-4`) |

- **Live differential catch (`II-4` `"RRR"`)**: `S3` Turn 1 flagged `DUAL_ORACLE_MISMATCH` on fatal Goblin collision. Both `PuzzleScriptOracle` and `FlatBitmaskOracle` agree `alive == False`, `exact_win == False`, and `traj_fnv64`, while `PuzzleScriptOracle` renders `'X'` (`#....XO.#...#`) and `FlatBitmaskOracle` renders `'F'` (`#....FO.#...#`). `verify_route_dual_strict` rejected the route fail-closed.

## Scope Limits

`FixedRadixCertificate` certifies adapter norm, `K0` null-space leakage, and safety-direction orthogonality. Route validity always rests on dual-oracle replay (`PuzzleScriptOracle` + `FlatBitmaskOracle`). External Frontier room bounds stored in `soko_mcp/data/catalog.json` remain distinct from floors reproduced inside this repository's C++ prover.
