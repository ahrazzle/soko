# Issue #22: checked portfolio observation

Observed at **2026-11-12 17:15:02 America/Chicago**; the raw UTC timestamp is in
`report.json`. `frontier.json` is the public response, with its hash and the
canonical catalog hash recorded by the report.

| Room | Reported record | Reported floor | Reported gap | Selected queue |
|---|---:|---:|---:|---|
| III-21 | 316 | 268 | 48 | 1 |
| III-20 | 84 | 74 | 10 | Excluded per prior user instruction |
| III-14 | 48 | 43 | 5 | 2 |

The other 63 rooms have zero reported gap. This report does not re-prove the
page's floors or certify optimality. Age is incumbent-entry age from matching
public history; the current III-21 and III-14 entries were approximately 12.8
and 28.2 hours old at observation. These are not estimates of search difficulty.

Reproduce exactly from the checkout:

```sh
python -m experiments.portfolio.triage --snapshot evidence/2026-11-12-issue22/frontier.json --observed-at 2026-11-12T23:15:02.067601+00:00 --exclude III-20
python -m unittest tests.test_room_triage -v
```

`tests.txt` records six passing unittest cases with adversarial subtests for
coverage, duplicated/invalid inputs, ignored public proof assertions, exclusions,
and age provenance. The live CLI was also executed successfully.

`iii21-baseline-replay.json` retains a fresh exact-win agreement at 316 inputs
from the two Python oracles and C++ engine. It matches the baseline route hash
in PR #12's calibration outputs. This intake did not rerun those capped searches
or original Chromium replay; the [existing original-game replay](../../experiments/macro_scheduler/evidence/baseline-original-replay.json)
records acceptance for the same route. Calibration recovery is not evidence of a new strategy.

`shared-action-example.json` records input 24 of the known III-14 route: one D
input moves both Bard and Druid one cell. This demonstrates shared action cost;
it does not supply a new global bound. Independent walk/push costs require a
valid composition argument before they can be summed into a lower bound.

Source: [issue #22](https://github.com/ahrazzle/soko/issues/22), by Zero
(`zero-aska`), with disclosed `grk-axiom` assistance. This implementation adapts
the portfolio-screening idea and does not copy planner code or issue prose.
No new record, certified bound, or optimality claim results from this intake.
