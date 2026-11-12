# Isolated III-21 planner search

This snapshot is the method and recorded runs of an isolated III-21 planner
search. It credits the isolated III-21 / III-14 search work. The files are
offered as methods and evidence. The route below is recorded run output, not a
newly proved optimum or a new lower bound.

## Method

`iii21.rs` is the Rust engine and search driver. It includes `shot.rs`, the
planner that runs a book of subgoal jobs (GateHeld, Shaft(1), WFree,
Open(10, 10), win) from a calibration cut. `planner/DESIGN.md` is the search
author's design note. It describes the planner as "a finder, not a proof that
316 is optimal" and says the floor 268 is "KNOWN from the live Frontier, not
reproved here." `iii21_eng.py`, `iii21_delivery.py` and `iii21_try.py` are the
Python engine and exploration scripts used alongside it.
`planner/verify_shot.py` replays candidates through the package's
`verify_route_dual`.

DESIGN.md also labels some calibration timings VERIFIED: the calibration chain
in `planner/runs/cal_246j.log`, and the official suffix timings checked with a
flat oracle on the official board. Those labels are claims in that document.
The checked-in logs are the recorded runs behind them.

## Recorded runs

- `planner/runs/cal_246.log` and `cal_246b.log` through `cal_246j.log` are the
  calibration runs.
- `planner/runs/book_v1.log` is the plan-book run. It is 211366 bytes, sha256
  `78c9cbf609fbf634fa6390aa4ebc4a0e1304b6b4ad2c5f68b8e29776698b498f`. It
  includes `FAIL GateHeld not realized` and ends
  `SHOT DONE cal_ok=true best=316`.
- `planner/runs/candidates.txt` lists three calibration names, with
  `cal_246_official` twice, all `len=316 rust_win=true`.
- The three `candidate-*.txt` files carry the same 316-key route string. Their
  headers differ by calibration name. The route sha256 is
  `39362103ceedf8d5f2ff4f7513839c58617f9a7ad0aa6fad070dd0d69269a17c`.
- `intermediates-*.txt` hold the beam each job realized, per calibration.

## Changes from the collected snapshot

Paths that pointed at the original search workspace were made relative so the
tree runs from this directory:

- `planner/runs/candidates.txt`: the four absolute candidate paths are now
  bare filenames. The records are otherwise unchanged.
- `shot.rs`: intermediates and candidates are written under `planner/runs`.
- `planner/verify_shot.py`: the default argument is
  `planner/runs/candidates.txt`, and candidate names in that index resolve
  next to it.
- `planner/DESIGN.md`: the rerun comment says to run from this directory.

The logs are byte-identical to the collected run. Some log lines still show
the original `/workspace/soko-search` write paths from that run.
`SHA256SUMS` lists every file in this directory as checked in.

## Reproduction

From this directory, with rustc 1.85 or later:

```sh
rustc -O -C target-cpu=native iii21.rs -o iii21-seek
./iii21-seek shot 60 40000 8000000
PYTHONPATH=/path/to/soko python3 planner/verify_shot.py planner/runs/candidates.txt
```

The three numbers are seconds, beam width and the seen-state cap. A new run
appends to `planner/runs/candidates.txt`, so copy the tree first to keep the
recorded index intact. The Python scripts also insert `/workspace/soko` or
`/workspace/soko-pr8` on `sys.path`. Those were checkouts of this repository
in the original workspace. Where they do not exist, `PYTHONPATH` set to this
repository's root supplies the oracles.
