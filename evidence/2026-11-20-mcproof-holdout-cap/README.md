# mcproof's 0/96 holdout: the Family B and C results and the arm comparison are not yet measurements (2026-11-20)

This is a known-answer test on someone else's instrument. It applies the method of the [2026-11-13 stall test](../2026-11-13-seeded-search-stall/README.md) to `Proven-Commons/mcproof`, the Formal Verification MDE blueprinted in [siliconcordat/mde issue 4](https://github.com/siliconcordat/mde/issues/4). This repository's auditors (`lean4_auditor.py`, `checker_auditor.py`) are among its oracles. Write access to mcproof was not available from this session, so the finding is recorded here. A second reviewer was asked to disprove it before filing. Their corrections are folded in below.

**Result.** mcproof's sealed 96-item holdout scored 0/96 in all 8 arms, including the ceiling arm `B1` with the full 32,216-token specification in its prompt. The verification report reads this as "single-pass 4B fails deep Lean 4 proof search", and the Phase 5 gates comparing arms fail on 0 against 0. mcproof's own files show that for two of the four families the 0 comes from the scoring setup:

1. **Holdout answers were cut at half the length validation answers got.**
   - Validation recorded `max_tokens: 1024` (`compile/artifacts/evaluation/validation_scorecard.json`; `compile/src/mcproof_compile/evaluator.py:466`).
   - The holdout runs use `n_predict` 512: `verification/score_arms_against_vault.py` lines 381 and 486 for B0 and B1, and `verification/score_adapters_against_vault.py` lines 483 to 579 for the adapter arms, which ran on 8 parallel slots.
   - No receipt records the cap. Both scorers keep only the answer text and drop the server's report of whether generation stopped at the limit.
   - The holdout grader's positive control, `grade_holdout.py --verify-gold`, exists, but no receipt shows it was ever run.
2. **Answers known to be correct fail at 512 tokens.**
   - All 72 public gold answers in Families B and C pass mcproof's public grader.
   - Measured with the Qwen3.5 tokenizer, which gives the specification exactly mcproof's 32,216 tokens, 27 of those answers exceed 512 tokens. Cut at 512, 22 of them fail: 8 of 8 in Family B (`PYTHON_SYNTAX_ERROR`, rejected fixtures) and 14 of 19 in Family C (missing "What is not proved" or "What you must trust"). These are the holdout's own leading error categories.
   - The median Family C gold answer is 514 tokens, so a typical correct answer does not fit (`qwen_cut_512.out`).
3. **The adapter arms ran into the cap.**
   - P2-A and the naive-sum arm always run to the cap. Their retention answers (384 tokens) top out at 21.6 to 21.7 s, and their holdout answers (512 tokens) run 28.1 to 31.1 s. The 192, 384 and 512 caps scale linearly.
   - P2-B's Family A and B answers take 28.9 to 30.6 s, inside that capped range. They finish in lockstep groups (29.4 s and 30.1 s eight times each, 28.9 s and 29.0 s four times each), as fixed-length generation on parallel slots does.
   - Every 8-slot arm hit the cap on Family B (29.3 to 30.9 s). Prompts are under 700 tokens, so prompt processing takes under a second.
   - Clustering alone proves nothing: the bare model's uncapped Family A answers also cluster, at 8.9 to 9.6 s.
4. **Family B cannot pass the holdout as graded, whatever the cap.** The holdout grader requires the "What is not proved" and "What you must trust" sections in Families A and B. The public grader (`src/mcproof/oracles.py:831-862`) checks no sections for those families, and no public A or B prompt or gold answer mentions them. Every one of the 192 Family B holdout outcomes, 24 items in 8 arms, carries the missing-section error, with identical sanitized error categories. The two graders also extract code differently. The public grader takes the last Python block of an answer (`oracles.py`, `py_blocks[-1]`); the holdout grader joins every Python block (`grade_holdout.py`, `grade_family_b`). An answer that includes a usage example block can therefore pass one and be a syntax error in the other. The validation and holdout splits measure different things in Family B. The bare model passed 4 of 12 validation B items and 0 of 24 holdout B items (one-sided Fisher exact p = 0.008, about 1 in 120). That gap measures the change of grader, not difficulty.

## What still stands

The Lean conclusion does not rest on the holdout alone.

- Public Family A gold answers are at most 477 Qwen tokens, so a 512 cap would not cut them.
- On validation, at 1024 tokens and under the laxer grader, Family A scored 0 of 12 in every arm. Family D scored 0 of 12 in every arm except B1 (2 of 12).
- "Single-pass 4B fails deep Lean 4 proof search" is therefore supported by validation evidence.

What the holdout cannot support yet:
- the Family B and C results (48 of the 96 items);
- the Phase 5 rows that compare arms on the holdout (primary gain and ceiling ratio, both 0 against 0);
- the mixed-integrity row.

None of this says P2-B works. On public validation it scored 2 of 48 against the bare model's 4 of 48.

For contrast, this repository's own MDE pack (`mde_soko/results/soko_eval_live_receipt.json`) records `completion_tokens` for every answer, so there the same question takes one look. In the open-loop arms S0 and S1, 7 of 18 answers stopped at exactly the 256-token cap. Those are exactly the 7 `MISSING_JSON_KEYS` failures, in both arms, in the same rooms. Every best-known route for those 18 rooms fits in at most 30 tokens as `{"keys": ...}`. So there the cap does not decide the outcome: the model kept going without writing the answer. Recording the token count is what makes "failed" and "cut off" tell apart.

## Experiment record

- **Question.** Can mcproof's holdout scoring tell a correct answer from a wrong one, under the conditions the arms were run in?
- **Hypothesis.** Not in every family. A 0/96 shared by every arm, ceiling included, is the reading an instrument gives when it cannot pass anything. That was the pattern of soko issue 49, where a broken lock made the verifier reject every route, proven-optimal ones included.
- **Positive control.** Grade the public gold answers whole. All 72 B and C answers pass.
- **Intervention.** Grade the same answers cut at 512 Qwen tokens.
- **Prediction.** Answers longer than the cap fail, with the holdout's leading error categories.
- **Decision rule.** Where answers known to be correct fail under the holdout's own conditions (cap or required sections), a 0 in that family cannot support a verdict on the model. That holds until the conditions are lifted or shown not to bind. Where validation shows the same failure under laxer conditions (Lean, Families A and D), the verdict stands on validation.

## Limits

- Public gold stands in for the sealed holdout gold, which this session cannot see. The two use disjoint mathematics, so lengths may differ.
- Model answers usually run longer than gold answers (preambles, explanations), so the real cap pressure is likely higher than this control shows.
- Families A and D were not graded here, because this machine has no Lean toolchain.
- Timing is indirect evidence of truncation. The direct evidence is the server's per-answer stop reason, which the scorers did not keep.
- `cap_control.py` and `cap_control.json` are the first pass. They estimate token counts with `cl100k_base` scaled by the specification's ratio, which undercounts Family C by about 12% and found 14 failures. `qwen_cut.py` and `qwen_cut_512.out`, using the real tokenizer, supersede them.

## Checks for whoever holds `mcproof-vault`

Each takes minutes:

1. Run `verification/graders/grade_holdout.py --verify-gold` and publish the receipt.
2. Cut each holdout gold answer at 512 Qwen tokens and grade it. Any gold that fails cannot be passed by any arm under the current cap.
3. Rerun the holdout arms with `n_predict` 1024, matching validation. Record the server's `stop_type`, `truncated` and `tokens_predicted` for every answer, and put the cap in the receipt.
4. Decide whether holdout Families A and B should require the two boundary sections. If they should, the public grader and public gold should require them too, so validation predicts the holdout.

## Reproduce

```sh
git clone https://github.com/Proven-Commons/mcproof && cd mcproof && git checkout adea9b65efcafa5911aaaafce2e5e3e7954408c5
python3 bin/bootstrap-deps --with-siliconcordat     # pinned dependencies; then build siliconcordat/mde with cargo
python3 /path/to/receipts_analysis.py .              # facts 1, 3 and 4 from the published receipts
MCPROOF_MDE_ROOT=/path/to/siliconcordat/mde python3 /path/to/qwen_cut.py 512 BC /path/to/Qwen3.5-4B/tokenizer.json .
```

The tokenizer used is the `Qwen3.5-4B` `tokenizer.json` (12,807,982 bytes, SHA-256 `5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42`). It is not committed here. This run's outputs are `receipts_analysis.out`, `qwen_cut_512.out` and `cap_control.json`. mcproof commit `adea9b6`, branch `feat/formal-verification-mde-v0.1`. SHA-256 prefixes of the inputs:

- `vault_arm_b0.json` `4ab88c12689b8fbb`
- `vault_arm_b1.json` `ff743f965f7b5076`
- `vault_arms_adapters.json` `c94eccf20733d9b6`
- `validation_scorecard.json` `21b810c95dd67dbb`
- `score_arms_against_vault.py` `c6ef0add62163330`
- `grade_holdout.py` `36290a49bf92f90f`
