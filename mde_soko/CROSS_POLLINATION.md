# Cross-Pollination Ledger (`mde:soko-eval`)

`mde_soko` connects `ahrazzle/soko` with external verification, quantization, and benchmark repositories while keeping every Sokoban solver and oracle inside `soko`. Each transfer below maps to an executable module and unit test in this checkout.

## Architectural Boundary

`Proven-Commons/mcproof` holds domain-general Lean 4, Python property-checker, and epistemic-tier verification tools. `ahrazzle/soko` holds all Sokoban game physics, C++ search engines, and `mde_soko` evaluation adapters.

`mde_soko.domain_oracle.SokoDomainOracle` implements the four-method `DomainOracle` protocol (`domain_id`, `retrieve_plane1_context`, `grade_candidate`, `format_repair_feedback`). External repair loops can evaluate Sokoban tasks through that interface without importing Sokoban logic into `mcproof`.

## Transfers Implemented in `mde_soko`

| Source repository | Mechanism transferred | `mde_soko` target | Test coverage |
|---|---|---|---|
| `Proven-Commons/mcproof` | Label-free inference oracle (`grade_candidate`) separated from post-hoc benchmark scorer (`grade_item`) so ground-truth booleans never leak into repair prompts | `mde_soko/domain_oracle.py` | `test_domain_oracle_label_free_inference_and_dual_semantics` |
| `Proven-Commons/mcproof` | AST structural hash and `(failure_rule, steps_executed)` stagnation detection that switches repair strategy after repeated timeouts or deaths | `mde_soko/runner.py` | `run_full_soko_live_evaluation` (`S3`) |
| `ahrazzle/soko` (`formal_kernel.py`, `engine_bridge.py`) | Eight fail-closed certificate soundness detectors (`F01` single-engine differential claim through `F08` unbound or non-64-hex witness digest) | `mde_soko/domain_oracle.py::audit_soko_certificate` | `test_f01_through_f08_certificate_soundness_detectors` |
| `siliconcordat/weft` | Deterministic CPU `float64` `BetaEdit` null-space Cholesky + skinny-QR solver with `9/9`-file `0`-byte re-derivation from a `<1 MiB` activation sketch | `mde_soko/compiler.py` | `test_independent_9_of_9_zero_byte_rederivation_and_gate_separation` |
| `Moissanite-Labs/siliquant` (`PR #12`) | Asymmetric `int4` output / `f16` input factor quantization (`int4/f16` cuts `K0` leakage from `4.12e-3` in `int4/int8` down to `5.16e-5`, matching `f16` `5.29e-5`) | `mde_soko/compiler.py::write_wfsl_slab` | `test_independent_9_of_9_zero_byte_rederivation_and_gate_separation` |
| `rohanarun/AITrafficControlBench` | Lexicographic protocol qualification gate plus full-horizon (`240`-key) charging on unsolved rooms, keeping wall-clock time outside the deterministic score | `mde_soko/runner.py::compute_lexicographic_eval_score` | `test_vendored_prose_gate_and_zero_path_ip_leaks` |
| `CrocSwap/integer-mult-bounds` | Parse-time strict integer JSON loader rejecting floating-point literals, `NaN`/`Infinity`, duplicate keys, and Python `bool` as `int` | `mde_soko/compiler.py::load_strict_certificate_json` | `test_independent_9_of_9_zero_byte_rederivation_and_gate_separation` |
| `eumemic/stdhttp-verify` | Chunk-segmentation replay invariance (`replay(s, u + v) == replay(replay(s, u), v)`) between incremental `S2` turns and terminal dual-oracle verification | `mde_soko/domain_oracle.py::SokoPlaySession` | `test_stateful_play_session_and_zero_import_sandbox` |
| `eumemic/exoplanets` (`issue #20`) | Multi-witness baseline verification requiring all `18` benchmark rooms and `48` dataset rooms to pass dual-oracle parity under pre-registered gates | `mde_soko/datasets_builder.py` | `test_disjoint_66_room_partition_and_zero_spoiler_benchmark` |

## Outbound Sokoban Findings Fed Back to Domain-General Verification

1. **Quotient-homomorphism plus deficit step bounds (`Mcproof.Spec.quotientHeuristic_step_consistent`, `Mcproof.Spec.zeroSelfLoop_deficit_composition`)**: Combining a zero-self-loop quotient heuristic with a bounded deficit term preserves 1-step consistency (`H(s) - H(s') <= 1`), generalizing Sokoban border-wall harvest bounds to abstract transition graphs (`prefundedHeuristic_step_consistent`).
2. **Rational-ceiling step consistency (`Mcproof.Spec.ceilDiv_step_consistent_and_admissible`, `Mcproof.Spec.operatorCounting_dual_div_admissible`)**: Taking `ceil(h_Q(s))` over any 1-step-consistent rational LP dual preserves integer 1-step consistency for reopened-free layered A* search.
3. **Timeout vs transition-bug repair branching**: In `S3` 4-second zero-import Python synthesis, code-execution timeouts require state-tuple compression and `visited` deduplication on enqueue, whereas `HERO_DIED` or `SURVIVED_WITHOUT_GOAL` failures require transition-rule repair (all-switch door coverage and Wizard ray-first swap).
4. **Post-death `final_ascii` differential catch (`II-4`, `route = "RRR"`)**: Live `S3` dual-oracle checking exposed that on fatal Goblin collision (`"RRR"`), `PuzzleScriptOracle` renders corpse `'X'` (`#....XO.#...#`) while `FlatBitmaskOracle` renders `'F'` (`#....FO.#...#`), despite matching `alive == False` and `traj_fnv64`. Full-tuple `F01`/`F02` comparison catches drift on terminal error states.

## What Is Not Claimed

`mde_soko` updates a small set of locked TCB files (`soko_mcp/flat_oracle.py`, `cpp/soko_engine.cpp`, refreshed `SHA256SUMS`) so dual-oracle corpse rendering matches fatal-step replay used in `S2`/`S3`. Its `FixedRadixCertificate` bounds adapter Frobenius norm, spectral norm, `K0` covariance leakage, and safety-direction inner products rather than proving puzzle optimality.
