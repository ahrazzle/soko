# Exact FIFO macro scheduler

This reusable native scheduler rearranges a reference Heroes of Sokoban route's
maximal directional runs. Each hero's own runs retain their FIFO order; their
interleaving is free. Every macro executes the minimal forward Action chain to
select its hero, including intermediate Note and late-phase effects, then its
prescribed directions. There are no beams, repair windows, or reference-position
restrictions.

The canonical key contains the mixed-radix progress vector and complete native
state: objects (including active identity), Notes, and door flags. String equality
resolves hash collisions. With `--omit-noops`, the Action count is also in the key;
only the lowest emitted-input cost for one exact key is retained. A lower cost
reopens a previously expanded key.

An input is omitted only after executing its actual transition and confirming
that **every state component is unchanged**. The inventory still advances.
Blocked hero movement alone does not justify omission. The objective is emitted
input count, restricted here to at most 315 inputs and 75 Action inputs. Early
actual wins are permitted and every new witness requires original-build replay.

Default ordering with no-op omission is Dijkstra on emitted cost. The optional
`--goal-directed` queue score adds remaining literal directions. That number is
not a lower bound when no-ops can disappear: it orders the queue and **never
prunes**. Only actual emitted cost and the Action cap restrict costs. A score
above 315 remains eligible. There is no shortest-route claim for the first goal.
All nodes remain retained until exhaustion or the explicit resource guard.

## Build and controls

From the repository root, with `g++` and Python available:

```sh
g++ -std=c++20 -O3 experiments/macro_scheduler/macro_scheduler.cpp -o /tmp/macro_scheduler
python experiments/macro_scheduler/verify_controls.py
```

The control runner recompiles in a temporary directory, checks all 317 baseline
frames against both the portable transcript and `PuzzleScriptOracle`, checks
byte-identical 316-input normalization, and exercises the priority/reopening
unit control. It validates the stored pinned original certificate. It launches
**zero optimization queries**. To rerun the original baseline too, install the
optional Playwright/Chromium dependencies and supply the pinned original HTML:

```sh
python experiments/macro_scheduler/verify_controls.py --original-html /path/to/part3.html
```

Input is `part width height total_input_bound seconds memory_MiB`, followed by
grid rows and the reference route. The executable sets a native address-space
limit and checks elapsed wall time and peak memory. The portable inputs already
specify the two recorded scopes. These commands rerun them deliberately:

```sh
/tmp/macro_scheduler < experiments/macro_scheduler/evidence/fixed/input.txt
/tmp/macro_scheduler --omit-noops --action-cap 75 --goal-directed < experiments/macro_scheduler/evidence/goal-completed/input.txt
```

`--calibrate` emits canonical per-frame digests and exits before search.
`--control-only` normalizes the baseline and exits. `--priority-self-test` checks
that above-bound scores remain eligible, lower cost is queued, and stale higher
cost is discarded. It also exits before search.

## Recorded III-21 results and limits

The dated incumbent was 316. Its 37 runs contain 241 directional inputs:
F11, T6, W3, P8, B3, D6. There are 84,672 possible progress vectors, with multiple
physical states possible for one vector.

| Recorded scope | Result | Exact states | Time | Peak memory |
| --- | --- | ---: | ---: | ---: |
| Fixed directions, complete FIFO inventory, at most 74 Actions | Exhausted; no candidate | 270,592 | 15.3654 s | 388,352 KiB |
| Full-state no-op omission, at most 315 emitted inputs and 75 Actions; goal-directed ordering | Exhausted; no candidate | 1,784,930 | 208.731 s | 3,093,988 KiB |

The completed no-op query used an 8 GiB cap. It reran the identical binary and
finite problem after a 2 GiB resource truncation; only the input memory cap
changed. Earlier Dijkstra and goal-directed 2 GiB truncations are documented in
`evidence/earlier-truncations.json`; they established no impossibility result.

Portable evidence includes the 317-frame transcript, original-build baseline
certificate, calibration, unit control, input files, concise result/progress
logs, source/binary provenance hashes, and an integrity manifest. No binaries
are bundled. `evidence/summary.json` distinguishes both restricted scopes.

The rule-only native header was copied from the earlier III-21 engine; its
provenance hash is recorded in `evidence/calibration.json`. Baseline agreement is
empirical evidence, not a proof of equivalence on all off-baseline states.
Exhaustion concerns only the specified macro inventory, Action caps, and native
model. **Neither result proves an original-game global lower bound.** No new
record, accepted improvement, or public submission resulted.
