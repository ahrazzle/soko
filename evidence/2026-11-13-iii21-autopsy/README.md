# III-21 route autopsy + live-frontier re-baseline, 2026-11-13

Cayde's first session playing the Frontier game. No new record. What this
bundle does is re-baseline the live board (it moved overnight), autopsy the
316-key III-21 record key by key, test the room's mirror symmetry, and run
one fresh optimisation attempt. Everything is reproducible from this
directory; nothing here is a proof, and the negative results are recorded
with the same care as the positive ones.

## Live frontier, 2026-11-13 08:55 UTC (raw: `frontier-2026-11-13T0855Z.json`)

Only three rooms still have a gap. The other 63 are closed
(`lower == known`).

| Room | Floor | Record | Gap | Holder |
|------|------:|-------:|----:|--------|
| III-14 | 44 | 48 | 4 | SJanuskas |
| III-20 | 75 | 84 | 9 | a1kindus |
| III-21 | 269 | 316 | 47 | futarchist |

Trilogy sums: known **3,063**, floors **3,003**, total gap **60**.

The floors moved overnight, after the repo's 2026-11-12 snapshot: banteg
accepted proofs raising III-14 43 → **44** and III-20 74 → **75** at
00:33 UTC, and III-21 268 → **269** at 02:58 UTC. The repo's stored
`proven_floor` values (43 / 74 / 268) and the numbers in
`docs/original-eval-and-frontier.md` are therefore one day stale. The
team's own reproduced floors trail the live accepted ones: III-14 ≥38 on
the 15×7 catalog board (vs 44 live), III-20 ≥48 generic MCP (vs 75 live).
Local proving is currently a reproduction tool, not the floor leader.

futarchist ground III-21 from 341 to 316 across 2026-11-12 (last step
317 → 316 at 10:28 UTC) and has not moved it since. The III-21 race is
quiet right now; the 47-key gap is 78% of the trilogy's remaining gap.

## Route autopsy: the 316, key by key (`autopsy.py`, `autopsy.json`, `autopsy.md`)

Stepped the official route through the repo's `PuzzleScriptOracle` and
logged the active hero, its position and board band after every key.
(`soko_verify_route` independently re-verified the route first:
dual + triple oracle, differential match.)

- **75 of 316 keys (23.7%) are `A` hero-switch presses.** 241 are moves.
- **76 hero-visit segments, in strict cycle order throughout:**
  F → T → W → P → B → D, repeated 13 times (12–13 visits per hero).
  No segment ever breaks the cycle order.
- **37 working segments, 39 transit-only segments.** 39 of the 75 `A`s
  are pure transit: the route switches to a hero, does nothing with them,
  and switches on. Those are not waste in the naive sense — to reach a
  hero two steps ahead in the fixed cycle you must pass through the hero
  between — but they price the interleaving: every pass through all six
  heroes costs at least 5 `A`s, and the route makes 13 passes.
- **Keys by hero:** Fighter 112, Bard 51, Druid 49, Priest 42,
  Thief 40, Wizard 22. The Fighter does over a third of the route.
- **Keys by band:** top 56, middle 179, bottom 81; **61 band
  transitions.** The chambers are not solved one at a time; work is
  interleaved across bands all the way through. Any per-chamber
  decomposition of III-21 has to price 61 crossings, which is why this
  bundle does not attempt an additive chamber floor.
- **Switch density peaks mid-route:** keys 51–150 carry 34 `A`s in 100
  keys (vs 7 in keys 201–250). That is the goblin-clearing /
  crate-shuffling phase, where each hero does 1–3 moves per visit.
- **Endgame is a final scramble:** the first hero reaches a goal at key
  57, but the second does not arrive until key 287; then 289, 309, 312,
  and the sixth on the winning key 316. The first 286 keys are setup
  with at most one hero parked; the last 30 keys park all six.
- **Longest single-hero stretches:** Fighter 29 (opening, keys 1–29),
  Bard 22 (232–253), Druid 21 (202–222), Fighter 20 (47–66).

The prize for batching hero visits is bounded by the floor: at most 47
keys of slack exist in total, and the suffix from key 246 is already
calibrated tight by the isolated planner (PR #12). The autopsy therefore
points the next search at keys 51–150 (the switch-dense middle), not at
the endgame.

## Mirror analysis (`mirror.py`, `mirror.json`)

The static board (walls, goals, crates, monsters; heroes stripped) is
**exactly left-right mirror-symmetric on rows 0–6, 8 and 12**, and breaks
on **16 cells in rows 7, 9, 10, 11** — the Wizard/Druid chamber and its
ceiling. The single off-centre crate `*` at (9,7) is the middle band's
only breaker. The mirror induces the hero permutation
Fighter↔Priest, Thief↔Bard, Wizard↔Druid, which **commutes with the
`A`-cycle** (checked computationally) but **swaps every hero role**, so
the mirror is a geometry-only symmetry: it does not transport routes.
(Contrast III-20, where the vertical mirror plus the directional cycle
gave the 84-key route its shape.) What the III-21 mirror licenses is
narrower: geometry-equivalent single-hero sub-tasks in the symmetric
bands, and a symmetry-breaking constraint for search (fix the first
asymmetric choice in the symmetric bands to one side). A literal
mirrored 316 was not attempted because the initial state is not
mirror-invariant — the heroes' roles differ — and replaying one would
test nothing.

The repo's `soko_inspect_room` reports `exact_mirror_x: false` with 16
mismatches; it counts raw characters including hero digits, so it cannot
see a relabelling symmetry. The mismatch count agrees with this bundle
(16), but the tool's verdict hides the structure: 9 of 13 rows are
exactly symmetric. A relabelling-aware symmetry check is a small,
concrete follow-up for the inspector.

## Optimisation attempt (this session)

`optimize-w24.log`: sliding-window optimisation of the 316 seed with
window 24 (wider than the 18-key window run on 2026-11-12), beam 40,000,
budget 240 s, C++20 engine, run time 215 s. Result: 316 → **316**,
0 keys saved, `improved: false`, `epistemic_status: VERIFIED`,
dual-oracle verified, triple-oracle checked, differential match. The
returned route is byte-identical to the seed (sha `39362103ceed`, the
same prefix recorded by the isolated planner in PR #12). No window of 24
anywhere in the route admits a shorter path between its endpoint states.
This is a negative result at a wider window than the previous best
attempt, and it is consistent with the planner's calibration that the
suffix from key 246 is tight. It does not prove 316 optimal.

## Methods, techniques, innovations (the process, for the record)

- **Route autopsy as a lens.** The isolated planner (PR #12) searches
  alternative subgoal orders; the autopsy instead segments the *official*
  route itself — hero visits, `A`-press accounting, band transitions,
  goal-arrival times. It found the structure (13 strict-cycle passes,
  39 transit `A`s, 61 band crossings, final-scramble endgame) that the
  plan search does not surface. Segmenting a record before searching it
  is cheap and directs where the expensive search goes.
- **Transit-`A` accounting.** Splitting `A`-presses into working switches
  vs pure transit, and passes into working vs transit visits, turns "the
  route is 316 keys" into a priced interleaving: 39 keys are cycle
  transit. The bound that matters is the floor gap (47), which caps the
  total prize — stated before any search, so a negative result stays
  informative.
- **Relabelling-aware symmetry test.** Strip hero labels before testing
  board symmetry, then test the induced permutation against the control
  cycle separately from the board. Board symmetry, cycle commutation and
  role preservation are three different claims; III-21 passes the first
  two and fails the third. Conflating them is how a mirrored route gets
  "tried" and its failure misread.
- **Live re-baseline before playing.** The frontier moved overnight
  (three floors in three hours). Any number quoted from the repo's
  Nov-12 snapshot would have been stale. The raw API response is kept
  in this bundle with its fetch time.

## Cross-disciplinary angles used

- **Proven Commons (verified bar):** dual/triple-oracle replay as the
  ground truth for every claim; negative results logged as evidence, not
  dropped; the planted-bug style of reasoning applied to the mirror
  (state the transform's failure mode *before* trusting it). The
  autopsy scripts are small, single-purpose, and re-runnable — the same
  one-command re-check discipline as a Lean slice.
- **Foundation-0 (formal systems):** the mirror test is a quotient /
  homomorphism check in miniature — a board map plus a control-cycle
  commutation test — the same shape as the `PairAtomQuotientPDB` and
  cost-partitioned quotient certificates already in the repo, applied
  here to the *room* instead of the *search*. The additive-floor idea
  (cost partitioning across chambers, `formal_certify_lower_bound`) was
  considered for III-21 and set aside on a measured number: 61 band
  crossings price the coupling above any naive per-chamber sum.
- **Exo / harness practice:** the autopsy replays the record in the
  repo's own oracle rather than trusting the Frontier's display, the way
  a harness pilot's report is checked against the live run, not the
  summary. The fresh-clone discipline (this work lives in its own
  checkout and branch, away from the review lane's checkout) mirrors
  keeping pilot feedback on its own account.
- **Rift-manager / game-design lens:** the `A`-cycle is a fixed draft
  order. The route's strict cycle order is the same phenomenon as a
  rotation that never breaks: the cost of a pick is the distance forward
  in the order, and batching is the only way to pay less. That framing
  is what motivated the transit-`A` accounting.

## What this does not claim

- No shorter route, no raised floor, no optimality claim for 316.
- The mirror result is not a route. The transit-`A` count is not slack
  — it is a price, and the dependencies that force 13 passes are not
  yet mapped.
- The III-14 / III-20 / III-21 floors quoted here are Frontier-reported,
  not reproved in this bundle.

## Next search (concrete plan, not yet run)

**Pass-batching in keys 51–150.** Take the official route's states at
the pass boundaries in that region (the autopsy gives the segment spans),
and run exact BFS between consecutive *working* states with the
intermediate hero visits merged — i.e. ask, for each pair of same-hero
visits one pass apart, whether the second visit's work can be pulled
forward into the first. The Rust planner's plan book has no
pass-batching template; this is the missing template. A single merged
visit saves the transit `A`s of one pass (up to 5 keys) plus any
duplicated walks. If two merges succeed, the route drops below 310;
if none succeed across the region, the 13-pass structure is itself
evidence that the interleaving is forced, and that belongs in the
ledger too.

## Reproduction

```sh
python3 evidence/2026-11-13-iii21-autopsy/autopsy.py   # writes autopsy.json/.md
python3 evidence/2026-11-13-iii21-autopsy/mirror.py    # writes mirror.json
python3 -m soko_mcp verify --room III-21 --route <316-key route in autopsy.py>
python3 -m soko_mcp optimize --room III-21 --window-len 24 --beam-width 40000 --budget-sec 240
```

Live snapshot: `curl -s https://soko.banteg.xyz/api/frontier`.
Room data: `python3 -m soko_mcp get-room --room III-21`.
