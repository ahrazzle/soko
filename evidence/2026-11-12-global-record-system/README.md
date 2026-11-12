# Global-system validation, 2026-11-12

No new record or original-game lower bound is claimed. After the change in
direction toward a reusable global system, runs here are controls and formula
preparation, not further record attempts.

Both positive controls passed the full pipeline: unrestricted model construction,
known actions and independent intermediate-state constraints, CNF conversion,
CaDiCaL, independent checking of every assignment clause, route decoding, and
replay in the pinned original PuzzleScript game. III-14 first wins at 48 inputs;
III-20 first wins at 84. The reference holders remain credited in each instance.

The two `*-reference-control` directories preserve the formula, assignment,
source identities, benchmark snapshot, calibration and original certificate.
Compressed artifacts retain their exact original bytes when decompressed:

```sh
gunzip -c iii14-reference-control/problem.cnf.gz > /tmp/control.cnf
gunzip -c iii14-reference-control/assignment.json.gz > /tmp/assignment.json
```

Historical JSON paths identify the execution workspace. The corresponding
portable files are the copies in these directories. Results are labeled
`reference_control_passed`; they cannot be record claims. Their preparation used
five initial random samples and one near-baseline sample, in addition to the
complete baseline and mechanic controls. Separate full-size calibration reports
are in `experiments/exact_frontier/iii14_calibration.json` and
`iii20_problem_calibration.json`.

The zero-horizon III-14 control produced an UNSAT CNF with an empty clause.
CaDiCaL's proof was accepted by the pinned drat-trim checker. The backend also
independently checked the input empty clause to handle drat-trim's unusual
nonzero exit for this case. This is a pipeline control, not a new useful bound.

`prepared-iii14-global.json` describes an actual unrestricted 47-input formula
prepared against a live 48-input record observation. The 180 MB uncompressed
formula remains at `/tmp/soko-system-ready-iii14/problem.cnf` in the originating
workspace and is reproducible with `record_system prepare`; it is not committed.
No SAT search was launched against this prepared global query.

Validation:

- 19 focused tests passed, including corrupted certificates, changed bundle
  artifacts/source, checked versus unchecked claims, timeouts, landmark guards,
  and model controls.
- The branch-wide suite ran 140 tests: 26 failures, 10 errors, 4 skipped.
- A clean checkout of main `2399514e39848d39f97481e022060df05802eb10` ran 127
  tests with the **identical multiset of failures and errors**. The 13 newly
  discovered tests introduced no additional failures. Six model tests live
  separately under the experimental package and passed in the focused run.

Both runs began with the same checked-in native binary. Recompiling that binary
can invalidate main's existing binary-inclusive integrity manifest and change
additional test outcomes. The existing main failures, including native trilogy
parity and search/evidence behavior, are preserved in the logs; this change does
not modify those implementations. `validation-summary.json` records the comparison.
