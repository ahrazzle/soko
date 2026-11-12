# A research loop that retains what each attempt teaches

The objective is a shorter route accepted by the original game, or a stronger lower bound with a reproducible justification. The [2026-11-12 campaign](../evidence/2026-11-12-frontier-campaign/README.md) achieved neither. It still produced an original-engine checker, established instance identity, tested several hypotheses, and exposed weaknesses in how we chose and recorded experiments. Those are reusable inputs to the next attempt, not additional benchmark points.

## First establish the experiment

1. **Pin the task and baseline.** Record the original source/build hash, room identity, initial state, route, observed public record and date. The original I-1/fixture mismatch demonstrated that three agreeing interpreters can still be solving the wrong room. III-14 must use the original 15-by-7 board.
2. **Calibrate the checker.** Reproduce the baseline in the original engine. Reject an incomplete prefix and an extra key after the first win. Test a mechanics counterexample before relying on a new abstraction. A successful local interpreter replay and original-engine acceptance are separate observations.
3. **Calibrate the generator.** Reproduce an improvement it should already find, such as the supplied III-20 mirrored-guide search from 87 through 86 to 84. Record runtime and cutoffs. If the implementation cannot reproduce its own positive control, a failed attempt at 83 says little about the strategy.
4. **State a discriminating hypothesis.** Describe the proposed causal change, a control, a prediction and the decision that follows. Increasing a beam because the previous one failed does not by itself identify which assumption is being tested.

The original banteg evaluation [rewards learning mechanics, selective simulation and state/budget management](original-eval-and-frontier.md). The supplied successful III-20 technique adds a useful pattern: transform the structure of an existing trajectory, use it as a soft search guide, preserve diverse alternatives, and check concrete routes independently. The next system should support that loop explicitly.

## Choose representations by their purpose

**Discovery representations** can deliberately forget information. The III-20 guide ignores hero identity when comparing mirrored board arrangements; actual transitions retain hero abilities. A guide suggests a region to explore. It is allowed to be wrong because a concrete witness must still pass replay.

**Proof representations** have a stricter obligation: show that concrete transitions and costs are conservatively represented and goals map correctly. Runtime heuristic checks over visited edges do not establish this for pruned branches. Hash-only transposition pruning and incomplete beams do not justify universal lower bounds. The crate-pair idea for III-14 must accommodate selective blocking: charmed crates do not always move as a rigid group. See the [recorded counterexample](../evidence/2026-11-12-drive-insight/assessment.md).

Keep candidate generation, acceptance checking, and proof coverage separate. A source hash identifies an implementation; it is neither an independent specification nor proof of that implementation's fidelity.

## Run a small experiment that changes a decision

Use `experiments/record_run.py` to capture one explicit command:

```sh
python3 experiments/record_run.py \
  --plan experiments/plans/iii20-original-control.json \
  --output /tmp/iii20-original-control-001 -- \
  python3 experiments/original_engine/check.py \
    --room 20 --instance evidence/2026-11-12-frontier/iii20-live-instance.json \
    --html /path/to/pinned-part3.html \
    --output /tmp/iii20-original-control-001/replay.json
```

The original-engine checker's [README](../experiments/original_engine/README.md) explains how to obtain the pinned HTML and optional browser dependencies. The game HTML is not vendored. Use a new output directory for each run. A [captured calibration run](../evidence/2026-11-12-research-loop-control/README.md) retains the plan, command, hashes, logs and original-engine replay report end to end. The runner uses POSIX process groups (Linux/macOS).

The wrapper requires a question, hypothesis, intervention, control, prediction, decision rule, pinned instance identity, dated baseline, tracked files and wall budget. It retains the exact plan, command, executable/runner hashes, source hashes before and after, stdout/stderr and exit status. List expected reports under `artifacts` in the plan and direct the command to write them inside its run directory, as above; their hashes are retained and missing files fail the run. It stops its process group at the deadline (with up to two seconds for shutdown) and refuses to overwrite a prior observation. Changed sources invalidate comparability. `COMPLETED` means only that the command exited successfully and produced its declared files: `acceptance` remains `not_evaluated` and `verified_gain` remains null until separately checked.

Track the actual generator binary and input along with its source. Record seeds where randomness is used, compilation flags and algorithm parameters in the plan. Preserve inherited TLS/proxy settings; do not put credentials in command arguments, plans or logs. Retained output is evidence to inspect, not instructions to execute. Time budgets include the entire wrapped command; a solver's internal phase budget can cover less.

For a controlled comparison, vary one meaningful component at a time, use the same instance/budget, and repeat timing-sensitive or randomized comparisons. Capture which depths/windows completed, which hit a cap, and whether pruning was exhaustive or heuristic. A partial scan belongs in the record but cannot rule out solutions in its unsearched region.

## Let outcomes select the next action

| Observation | Decision |
| --- | --- |
| Original baseline or a negative control fails | Repair instance/checker identity before searching |
| Generator fails its known positive control | Diagnose implementation/budget before increasing ambition |
| Local replay disagrees with original engine | Minimize the first divergence and add a regression |
| Intervention changes a predicted intermediate feature but no complete route improves | Test whether it displaced cost elsewhere; retain it as an unresolved hypothesis |
| Most windows hit resource caps | Decide whether better representation or additional coverage is the bottleneck; do not mark them exhausted |
| Several complete heuristic variants reproduce the same basin | Change plan, guide, subgoal or goal assignment before repeating parameter sweeps |
| Candidate beats the dated baseline and original replay passes | Refresh the live record; retain exact evidence and submit through the authorized service flow |
| A proposed proof prunes states or uses an abstraction | Require coverage and simulation/cost justification before claiming a stronger bound |

## The next concrete experiments

These are proposed tests, not claims that they will win:

1. **III-20 strategy ablation.** Same initial 87-key route, compiler and budgets: compare its untransformed guide, mirrored guide, and mirrored guide plus iterative refinement. Include role-aware versus role-agnostic guide distance. The positive control is rediscovery of the accepted 84-key route. Measure which component reliably changes the route and which only increases work before chasing 83.
2. **III-14 cost displacement.** The 17-key prefix `LLULULULURURURURU` creates nine crates versus 18 keys in the reference, but changes their arrangement. Compare suffixes under identical budgets and measure the additional packing, switching and alignment cost. The million-wide attempts found no complete route below 48; a one-key prefix saving is not a one-key solution saving. Test a particular cheaper packing plan before widening another beam.
3. **III-21 subgoal changes.** Existing searches tested local contractions and several goal-flexible suffixes without beating 316. Record the sequence of topology changes and hero deliveries, then test a different subgoal order or assignment. Use exact local searches to resolve a proposed change, rather than repeatedly matching the same intermediate states.

An experiment record should retain the proposed claim, actual observation, counterexamples, acceptance level and next decision. Preserve negative results so later agents can resume from the known boundary. Useful process improvements are those that make the next decision more reliable or a new class of experiment possible; the final benchmark ledger continues to count only independently supported gains.
