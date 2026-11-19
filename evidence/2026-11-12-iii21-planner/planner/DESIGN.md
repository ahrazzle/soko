# III-21 one-shot planner

A route shorter than 316, if one exists in the plan space below, is found in a single
run and checked with PR 8's `verify_route_dual` and, when a candidate exists, PR 10's
original-game replay. This is a finder, not a proof that 316 is optimal. The published
floor 268 is KNOWN from the live Frontier, not reproved here.

## Why not more local windows

VERIFIED: every official single-hero stretch, and the 70-key suffix from key 246 under
the restrictions already searched, is shortest to its official end state. Matching those
intermediate states cannot beat 316. The research-loop experiment for III-21 is a
different subgoal order or assignment, realized by exact local search.

## What the system searches

A **plan** is a committed prefix of the official route (0, 85, 185, 232, or 246), a goal
assignment, and an ordered list of jobs. Jobs are predicates on the concrete board:

- `GateHeld` — complete when Druid is west of the goblin gate, or Wizard is already free,
  or the left goblins are gone. Priest on the walkway is only a partial (the escort).
- `Shaft(x)` — the two walls at (x,8) and (x,9), x in {1,2,3}, are no longer walls.
  Realized in two exact phases: first wall, then fully open.
- `WFree` — Wizard is out of the starting alcove (no goal is inside it, so this is required)
- `Open(x,y)` — the wall at (x,y) is gone. Finish plans use `Open(10,10)`; early-escape
  plans also open (12,10).
- `MidGobsClear` / `RightGobsClear` — goblins in those regions are gone
- `Deliver` + `Win` — one finishing beam: all six heroes on the six goals (the plan's
  assignment is a guide; the win condition is any assignment), on the last key

The official assignment is P(10,1), B(12,1), D(10,6), T(12,6), W(10,11), F(12,11).
Alternate assignments are first-class: they change whether (10,10) must open, and how
far Wizard travels after escaping.

Plan templates (the generator, not a list of ad-hoc tries):

- Official order from 246 and 232, as a calibration control
- Early escape: shaft and Wizard-free first, from key 85, from key 185, or from 0
- Early Bard: Bard moves earlier to transport Druid or a mid-clear group
- Shaft at x=1, 2, or 3; several Wizard-goal swaps

## How a plan is realized

A **chain** of exact packed multi-source BFS for short jobs (`GateHeld`, `Shaft`,
`WFree`, `Open`), then a guided beam through `Deliver`+`Win`. Guided beam is also the
fallback when exact search misses, and the primary runner for long jobs (`MidGobsClear`).

Poses are kept as a beam of concrete states and ranked by estimated **total**
(`path.len() + remaining guide`), not by shortest first-job path. A cheap first job
that leaves a messy pose (the 16-key crate-at-(1,9) path, a 28-key Wizard-free that
still costs ~40 to finish) is kept only if the estimated total still beats 316.
Estimates are a **guide** (CONJECTURE as bounds) and are never used to prune a branch
as impossible. The only cutoff is depth `316 - prefix`. A state with a missing hero is
dropped (petrify is a dead end).

On calibration plans, the official suffix is seeded into the beam after each job, so a
shorter exact hit cannot hide the known finishing pose. If a pose is an official prefix,
the official remaining suffix is played as a control; a 70-key recovery is CALIBRATION
OK. The finish beam still searches for a shorter continuation.

## Calibration

The official job order from key 246 must recover a winning route of length at most 70
(total 316). VERIFIED in `cal_246j.log`: the chain opens the shaft in 24 keys and frees
the Wizard in 28 (both shorter than the official 28 and 34), opens (10,10) at 52 (guided)
and at official 56, and the official 14-key remaining suffix wins at 70; rust-verify
alive, exact win, 316 steps. After calibration, the same `shot` run continues through
the rest of the plan book.

Official suffix timings from key 246, VERIFIED with PR 8's flat oracle on the official
23×13 board and the 316-key reference route:

- GateHeld (Druid west of the gate): +4
- Shaft(1) first wall (1,8): +10; fully open (1,9): +28
- WFree: +34
- Open(10,10): +56
- Win: +70, path `LLLLLLLADDRDALDDAUAAALDURADDUUAAAUAARRRRRRRRUUURUUADRDDDAAAUUURDDDAUUL`

## How to rerun

```
# from this evidence directory, rustc 1.85+
rustc -O -C target-cpu=native iii21.rs -o iii21-seek
./iii21-seek shot 60 40000 8000000
# optional: ./iii21-seek shot 90 40000 10000000 only=cal_246_official
python3 planner/verify_shot.py planner/runs/candidates.txt
```

Seconds, beam width, and seen-state cap are the three numeric arguments. Every candidate
is also written under `planner/runs/`. Claim a shorter record only after PR 8
`verify_route_dual` returns a valid exact win, and after PR 10's original-game replay
when that path is available. Do not submit to the live site from this tool.
