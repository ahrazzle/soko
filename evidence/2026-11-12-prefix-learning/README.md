# Controlled causal-search experiments

2026-11-12 America/Chicago. No new winning route or stronger bound was obtained.
The plans were shared before implementation/execution in issue #22 and in
[`SEARCH_POLICY_PLAN.md`](../../experiments/causal_solver/SEARCH_POLICY_PLAN.md)
and [`PREFIX_LEARNING_PLAN.md`](../../experiments/causal_solver/PREFIX_LEARNING_PLAN.md).

## Useful retained change: compact checkpoints

The search repeatedly rewrites its growing, complete evidence checkpoint. A
10-second cProfile diagnostic spent 4.95 of 10.32 total seconds in checkpointing,
including 2.86 seconds in `_save`. These figures include profiling overhead.
Replacing indented JSON with compact JSON preserves the data, strict nonfinite
rejection, source-check cadence, and atomic write behavior.

Three sequential, alternating-order pairs compare frozen pretty-writer
`2d0bd9a` with compact-writer `7dc3994`, each with 15 seconds on unrestricted
15x7 III-14 at H47, exact-first/source-minimal, without prefix learning:

| Pair | Pretty: checked exact cuts | Compact: checked exact cuts |
|---|---:|---:|
| 1 | 34 | 43 |
| 2 | 44 | 46 |
| 3 | 38 | 49 |
| Median | **38** | **46** |

This is **21.05% more checked cuts at the median** on this workload and host.
Each pair's common candidate prefix and certificate payload hashes are identical;
the source inventories differ only in `experiments/causal_solver/search.py`,
whose only code change is JSON formatting. This supports a local throughput
improvement, not a general solver speedup, larger proof coverage, or a record.
All six runs ended `unknown`. The compact writer is retained.

## Prefix learning: implemented, checked, not selected by default

The opt-in `--learn-prefix-frames` learns complete hero/active facts under a
checked action prefix after agreement between the retained exact transition and
the separate Python oracle with all material present. Facts remain private to
the independent recheck; supplied serialized facts are not trusted. The existing
nogood and extra implications install together only after successful validation.
Other prefixes remain free, terminal absorption is preserved, and SMT cores
do not acquire these extra facts.

Three 30-second pairs at frozen source `2d0bd9a` produced baseline exact-cut
counts **61, 63, 64** versus prefix-learning counts **65, 59, 64**. Maximum
contradicted prefix depth was 16 versus 17, while median contradicted depth was
7 versus 6. These are different-strength constraints, so counts and depths are
diagnostics, not comparable proof-coverage units. There is no convincing gain;
prefix learning stays **off by default**. All runs ended `unknown`.

The original first pair was conservatively replaced because overlap with a
reviewer's short test run could not be ruled out. All eight original/replacement
runs are retained, including the excluded pair. The replacement was recorded
explicitly rather than silently overwriting observations.

## Earlier phase-order diagnostic

At source `91accff`, three sequential 30-second runs yielded:

| Policy | Checked cuts | Outcome |
|---|---:|---|
| Exact first, source-minimal | 64 exact | Unknown |
| Flow first, source-minimal | 1 flow | Unknown; master then stalled |
| Flow first, sink-minimal | 15 flow | Unknown |

Cut families differ, so these counts are not equivalent progress measures.
There was no reason to switch the default phase order. III-21 staging
reconnaissance did not establish a new beneficial milestone, so no undirected
III-21 beam campaign followed.

## Validation and reproduction

`tests.txt` records 78 passing focused tests, including the 11 new prefix-learning
tests: complete Bard/Druid/active implications, unrelated-prefix freedom,
reference preservation, spurious rejection, absorption, metadata/tampering,
timeouts, and oracle disagreement. Independent review found no blocker.
The compact writer also passed direct decoded-data equality, strict JSON and
preservation of the prior checkpoint after a rejected nonfinite value.

Artifacts are deterministic gzip bundles with their original result/log files:
`policy-runs.json.gz`, `prefix-runs.json.gz`, `prefix-replacement-runs.json.gz`,
and `checkpoint-runs.json.gz`. Each run retains source hashes, candidates and
accepted checked certificates. `summary.json` provides counts, source revisions,
commands and comparison checks. `checkpoint-profile.txt` records the profiling
command and table. Each bundle names its source revision; later source edits
are not silently treated as the original experiment.

```sh
# At source 2d0bd9a, reproduce the prefix-learning comparison:
python -m experiments.causal_solver.compare_prefix_learning --output /tmp/new-prefix-runs

# Isolated frozen checkouts for the formatting-only comparison:
git worktree add --detach /tmp/soko-pretty 2d0bd9a
git worktree add --detach /tmp/soko-compact 7dc3994
python evidence/2026-11-12-prefix-learning/compare_checkpoints.py --pretty-checkout /tmp/soko-pretty --compact-checkout /tmp/soko-compact --output /tmp/new-checkpoint-runs
```

Use the same Python environment with Z3 for both checkouts. The comparison
driver is outside the source-hash inventory, identifies its own hash, and runs
workers sequentially. Use fresh output directories.

The live Frontier observation at **2026-11-12 21:32 America/Chicago** still lists
records III-14 = 48 and III-21 = 316. It now reports floors 44 and 269 respectively;
those are external claims, not bounds established by this experiment. The raw
response, exact timestamp and hash are retained. III-20 remains excluded.
