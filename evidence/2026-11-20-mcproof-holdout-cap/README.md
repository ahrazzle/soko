# mcproof's 0/96 holdout result is not yet a measurement of the model (2026-11-20)

**Status:** committed while a second reviewer, asked to disprove it, is still working. Do not cite it until that review is recorded below.

This is a known-answer test on someone else's instrument. It applies the method of the [2026-11-13 stall test](../2026-11-13-seeded-search-stall/README.md) to `Proven-Commons/mcproof`, the Formal Verification MDE blueprinted in [siliconcordat/mde issue 4](https://github.com/siliconcordat/mde/issues/4). This repository's auditors (`lean4_auditor.py`, `checker_auditor.py`) are among its oracles. Write access to mcproof was not available from this session, so the finding is recorded here.

**Result.** mcproof's sealed 96-item holdout scored 0/96 in all 8 arms. That includes the bare model and the ceiling arm `B1`, which carries the full 32,216-token specification in its prompt. The verification report reads this as "single-pass 4B fails deep Lean 4 proof search" and enforces the "Honest Kill Boundary". Three facts in mcproof's own published files show the 0/96 is at least partly made by the scoring setup:

1. **The holdout answers were cut at half the length the validation answers got.** The public validation run recorded `max_tokens: 1024` (`compile/artifacts/evaluation/validation_scorecard.json`). The holdout run hard-codes `max_tokens=512` (`verification/score_arms_against_vault.py`, line 381). The holdout receipts record no cap at all. The scorer also keeps only the answer text, so the server's report of whether generation stopped at the limit is lost.
2. **Known-good answers fail at 512 tokens.** All 72 public gold answers in Families B and C pass mcproof's public grader. Cut at 512 tokens, 14 of them fail: all 8 over-length Family B answers (`PYTHON_SYNTAX_ERROR` or rejected fixtures) and 6 of the 7 over-length Family C answers (`MISSING_WHAT_YOU_MUST_TRUST`). These are the holdout's own leading error categories, reproduced from answers known to be correct. The gold answers are terse. Also, the holdout grader requires the "What is not proved" and "What you must trust" sections in Families A and B. The public grader does not, and none of the 72 public A and B gold answers include them. So validation and holdout do not measure the same thing in those two families even before the cap.
3. **The adapter arm ran into the cap on every Lean and Python item.** P2-B's holdout answers in Family A took 28.9 to 29.7 s, and in Family B 29.4 to 30.6 s. Its retention answers, capped at 384 tokens, top out at 22.8 s. That is about 59 ms per token, so 512 tokens comes to about 30 s. The tight clusters are what fixed-length, truncated generation looks like. Families C and D, whose answers can end early, spread from 13 s to 32 s.

There is also a pattern the cap does not fully explain. All 24 Family B holdout items fail with exactly the same three errors in all 8 arms: two missing sections and a Python syntax error. That is 192 of 192 B outcomes, including the bare model, which passes 32 of 35 coding retention items. If holdout B were as hard as validation B, where the bare model passed 4 of 12, the chance of 0 of 24 is about 6 in 100,000. The bare model's B answers do not cluster at the cap, so for that arm something besides truncation may also be at work.

For contrast, this repository's own MDE pack (`mde_soko/results/soko_eval_live_receipt.json`) records `completion_tokens` for every answer, so the same question takes one look there. In the open-loop arms S0 and S1, 7 of 18 answers stopped at exactly the 256-token cap. Those are exactly the 7 `MISSING_JSON_KEYS` failures, in both arms, for the same rooms. Every best-known route for those 18 rooms fits in at most 30 tokens as `{"keys": ...}`, so there the cap does not decide the outcome: the model ran on without writing the answer. Recording the token count is what makes the difference between "failed" and "cut off" checkable.

## Experiment record

- **Question.** Can mcproof's holdout scoring tell a correct answer from a wrong one under the conditions the arms were run in?
- **Hypothesis.** Not reliably. A 0/96 shared by every arm, ceiling included, is the reading an instrument gives when it cannot pass anything. That is the pattern of soko issue 49, where a broken lock made the verifier reject every route, proven-optimal ones included.
- **Positive control.** Grade public gold answers whole. All 72 pass.
- **Intervention.** Grade the same answers cut at 512 tokens.
- **Prediction.** Answers longer than the cap fail, with the holdout's leading error categories.
- **Decision rule.** If known-good answers fail under the holdout's own cap, the 0/96 cannot support a verdict on the model until the cap is lifted or shown not to bind.

## Method and limits

- Token counts use `cl100k_base` scaled by 32,216 / 30,873, mcproof's own measured ratio for Qwen3.5 tokens. The real Qwen tokenizer would move individual counts a little.
- Public gold is a stand-in for the sealed holdout gold, which this session cannot see. The two use disjoint mathematics, so lengths may differ.
- Model answers usually run longer than gold answers (preambles, explanations), so the real cap pressure is likely higher than this control shows.
- Family A and D gold were not graded here, because this machine has no Lean toolchain.
- Timing is indirect evidence of truncation. The direct evidence is the server's per-answer stop reason, which the scorer did not keep.

## Checks for whoever holds `mcproof-vault`

Each takes minutes and settles the question:

1. Run `verification/graders/grade_holdout.py --verify-gold` and publish the receipt. The mode exists, but no receipt in the repository shows it was run.
2. Cut each holdout gold answer at 512 Qwen tokens and grade it. Any gold that fails cannot be passed by any arm under the current cap.
3. Rerun the holdout arms with `n_predict` 1024, matching validation. Record the server's `stop_type`, `truncated` and `tokens_predicted` for every answer, and put the cap in the receipt.

Until then, the Phase 5 rows that depend on the holdout (primary gain, ceiling ratio, mixed integrity) are unmeasured, not failed. That is not a claim that P2-B works; on the public validation split it scored 2/48 against the bare model's 4/48.

## Reproduce

```sh
git clone https://github.com/Proven-Commons/mcproof && cd mcproof && git checkout adea9b65efcafa5911aaaafce2e5e3e7954408c5
python3 bin/bootstrap-deps --with-siliconcordat           # pinned dependencies; then build siliconcordat/mde with cargo
python3 /path/to/receipts_analysis.py .                    # facts 1 and 3 and the Family B pattern, from published receipts
cd datasets && MCPROOF_MDE_ROOT=/path/to/siliconcordat/mde python3 /path/to/cap_control.py . /tmp/cap_control.json 512
```

`receipts_analysis.out` and `cap_control.json` are this run's outputs. mcproof commit `adea9b6` (branch `feat/formal-verification-mde-v0.1`). SHA-256 prefixes of the inputs: `vault_arm_b0.json` `4ab88c12689b8fbb`, `vault_arm_b1.json` `ff743f965f7b5076`, `vault_arms_adapters.json` `c94eccf20733d9b6`, `validation_scorecard.json` `21b810c95dd67dbb`, `score_arms_against_vault.py` `c6ef0add62163330`, `grade_holdout.py` `36290a49bf92f90f`.
