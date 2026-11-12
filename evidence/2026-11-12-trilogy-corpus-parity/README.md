# Original trilogy baseline parity

All **66** captured baseline routes win in the corresponding source-pinned
original builds. Across **3,063 inputs** and **3,129 initial/settled frames**, the
original and readable Python interpreter agree on the compared persistent
layers and survival/win state. Both Python implementations and the native C++
engine also agree on baseline acceptance and rolling trajectory digests.

`summary.json` records the coverage, source/catalog/checker hashes and hashes of
the 66 per-room reports. Each room report retains baseline attribution, original
instance/trajectory identity, projected frame hashes, first-divergence fields
and the complete local differential certificate. There were zero mismatches.
The raw original HTML is externally cached, not redistributed. Original framed
reports can be regenerated with the command below.

## Reproduce

From the repository root with Playwright, Chromium and a C++20 compiler:

```sh
python3 tools/check_corpus.py --output-dir /tmp/trilogy-parity-new
```

Use a new output directory each time. `--room I-22` selects one room, and
`--cache-dir PATH` selects the original HTML cache. Each original replay has a
30-second whole-process deadline, adjustable with `--timeout-sec`. Runtime and
integrity failures are retained as failures rather than accepted results.

The recorded run consumed freshly executed original framed reports through
`--replay-cache-dir /tmp/soko-corpus-original-replays`; the harness checked each
report's complete hash, current checker hash, source pins, room/route identity,
compiled index, frame sequence and trajectory/instance hashes before comparing.
The cache is an execution optimization, not an independent signature or trust
authority. The default command above runs the originals again.

## Scope and repairs

Compared layers include all hero identities, crates, monsters, walls, goals,
switches, doors/open doors and Bard notes at their original coordinates. The
explicit exclusion list in every report covers background and original engine
bookkeeping/effect markers. Among these baseline frames, only `saved` occurred
besides background. Raw original observations remain available through
`soko_replay_original` with `include_frames=true`.

This exercise exposed and fixed two defects relevant to the original corpus:

- I-22 has three active heroes; movement must apply to all of them.
- In II-12, colored-door crushing must precede the monster-gate phase so a gate
  opens in the same turn when the last monster is crushed.

Additional minimized controls cover simultaneous followers, switching order,
Part II whole-turn cancellation, and Bard/Druid interactions in multi-active
custom boards. These tests supplement, rather than expand, the 66-route coverage
reported here. The full repository suite passed **118 tests with no skips**,
with browser integrations enabled.

This is route-specific differential evidence, not universal equivalence,
optimality, a new record, or a kernel-checked proof. Puzzle design and original
implementation are by Jonah Ostroff; each route retains its Frontier holder
attribution in the catalog and report.
