# Recorded calibration of the research loop

The planned III-20 control completed in 2.588 seconds under a 45-second wall
budget. The pinned original Part III engine accepted the existing 84-key route,
with its first win at key 84 and no death or restart. This reproduces the dated
baseline; **new keys saved: 0**.

Files retain the full chain:

- `plan.json`: the question, hypothesis, control, prediction and decision rule,
  captured before execution.
- `result.json`: exact command, executable/runner/source hashes, source stability,
  exit status, budget, logs and the replay artifact hash.
- `stdout.log`, `stderr.log`: raw command output.
- `replay.json`: original-engine route acceptance and bound source, instance,
  trajectory and checker identities.

The runner's `acceptance: not_evaluated` and `verified_gain: null` are deliberate:
successful process completion does not evaluate a route or infer an improvement.
The separate replay report supports the baseline acceptance above. Neither
report claims public submission or optimality.

The command's absolute HTML and interpreter paths describe this execution
environment. To repeat it elsewhere, follow the [research loop example](../../docs/research-loop.md)
with a new output directory and either a locally cached pinned HTML file or the
checker's automatic download. Browser dependencies are optional and documented
in the [original-engine checker](../../experiments/original_engine/README.md).

Validation on this revision: 79 tests passed, no skips, with original-browser
integration enabled. Those browser tests include the 48/84/316-key baselines,
an incomplete 83-key route, an extra key after the 84-key win, and a route that
dies. The runtime source manifest also passed without modification.
