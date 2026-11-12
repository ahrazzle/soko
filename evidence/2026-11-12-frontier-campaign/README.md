# Frontier campaign: preserved results and limits

**New keys saved: 0. New stronger lower bounds: 0. Public submissions: 0.**
This records the later November 12 campaign against III-14, III-20 and III-21,
after the earlier [baseline/window experiments](../2026-11-12-frontier/README.md).
It is a record of tested hypotheses and bounded negative results, not a claim
that the current routes are optimal. [summary.json](summary.json) is the compact
machine-readable record.

| Room | Displayed lower bound | Existing route | New complete route |
| --- | ---: | ---: | --- |
| III-14 | 43 | 48 | None |
| III-20 | 74 | 84 | None |
| III-21 | 268 | 316 | None |

These are the November 12 snapshot, not a refreshed leaderboard. Existing routes
were attributed to SJanuskas, a1kindus and futarchist respectively by the public
service. The user's earlier 84-key III-20 result is background to this campaign;
reproducing an existing 84-key route is not a new improvement.

## What became reusable

The original PuzzleScript engine replayed the 48-, 84- and 316-key baseline
routes, with first win on the last key and no death. Its source identity and
negative controls are retained in
[historical/original-engine.json](historical/original-engine.json). An 83-key
III-20 prefix did not win; the 84-key solution plus one key was rejected because
the win occurred before its final key. Initial raw bitfields matched the public
evaluator for III-14 and III-20. That initial-state agreement does not establish
universal transition equivalence or public-service acceptance.

The [reusable original-engine checker](../../experiments/original_engine/README.md)
now pins the upstream HTML and embedded PuzzleScript source. Its wrapper is a
maintained successor to the scratch checker identified in the historical
report, not the exact same file. The upstream HTML and compiled search binaries
are deliberately not bundled here.

Instance identity mattered. The original III-14 room is **15×7**; a legacy local
variant was 14×7. This is separate from the earlier I-1 discrepancy, where the
repository fixture was 12×5 and original I-1 was 13×5, documented in
[the original-eval assessment](../../docs/original-eval-and-frontier.md).
A room label alone is insufficient to identify a result.

## Search coverage and caps

| Room | Preserved coverage | Result and limits |
| --- | --- | --- |
| III-14 | 20 logged beam calls; 593,963,500 attempted transitions; full-route beams of 20,000/120,000 and suffix beams up to 1,000,000 | No route below 48. Beam pruning is incomplete. The `expanded` field counts attempted transitions, **not unique states**. |
| III-20 | 22 guided calls; 83 local windows of depth at most 28; 42,381,256 window expansions | No route below 84. Windows had 3,000,000-state/4-second caps; offsets 25–67 were limited. Guided beams used 80,000–400,000 slots and configured 60–180-second budgets. |
| III-21 | 131 logged windows across four runs; 28,584,245 expansions; suffix starts 232/253/282; 184,390 route contractions | No route below 316. Three window scans were stopped after cap-heavy intervals. Guided windows had 500,000-node/4-second caps; other window caps were 700,000/1,000,000. |

III-20 also recorded two hash-cap stops near 13 million seen hashes at depth 78
and a suffix timeout at depth 66. Its `RESULT 0` lines mean **no candidate**, not
a zero-key solution. III-21's completed guided tail scan covered offsets
184–314 in steps of two; completing those calls does not mean their search
spaces were exhausted. The machine summary records the covered offsets, widths,
elapsed times and caps.

These counters have different meanings and must not be combined into one
"states searched" total. Hash-only deduplication, heuristic pruning and capped
searches do not yield proof bounds. The historical generator sources changed
between III-14 batches; the exact binary-to-source mapping is not pinned for
every run. Repeated identical counts across variants are not evidence that
independent neighborhoods were covered. This campaign is not a controlled
ablation and does not establish which heuristic is better.

## A small hypothesis that can be reproduced

III-14's baseline creates nine crates with the 18-key prefix
`LLULULULRURURURURU`. The 17-key prefix `LLULULULURURURURU` also creates nine
crates, but leaves a different state. Appending the unchanged baseline suffix
produces a 47-key route that **does not win**. Larger suffix beams also found no
completion that preserved the apparent saving.

Run this read-only local-oracle probe from the repository root:

```sh
python3 evidence/2026-11-12-frontier-campaign/probe_iii14_prefix.py
```

It replays both prefixes, the known 48-key route, and the failed 47-key splice;
it prints states, routes and code/input hashes and exits nonzero if the observed
conditions change. [prefix-probe.json](prefix-probe.json) records the captured
output. This probe uses the repository's Python oracle. It is an intermediate
hypothesis check, not an original-engine certificate or optimality proof.

The useful next question is whether the altered crate/hero placement admits a
cheaper continuation. Merely maximizing crate count or making the opening
shorter did not deliver an end-to-end gain. Any follow-up should name a concrete
continuation hypothesis, compare it against a pinned baseline under the same
budget, and validate a completed candidate in the original engine. The
[research loop](../../docs/research-loop.md) defines that experiment process;
the [verified systems loop](../../docs/verified-systems-loop.md) defines the
general claim boundaries.

## Artifact and attribution boundaries

| Artifact | Purpose |
| --- | --- |
| `historical/*.json` | Raw captured scoreboard, room summaries and original-engine provenance; their absolute workspace paths are historical. |
| `logs/*` | Selected original terminal logs, including caps and unsuccessful suffix searches. |
| `artifact-manifest.json` | SHA-256 and byte sizes for the available historical source/log snapshots; distinguishes included files from hash-only references. |
| `probe_iii14_prefix.py`, `prefix-probe.json` | Small reusable reproduction of the intermediate observation. |

Source hashes identify snapshots; they cannot recover omitted source or prove
which binary ran. The record therefore does not promise full reproduction of
the historical campaign. Search drivers incorporated the recovered experimental
C++ candidate-generator family; the user's supplied solver was attributed to
Gemini Carbon 4. Those generators are not proof checkers. This record keeps
their identities without blindly republishing source trees or compiled files.

Game and puzzle credit belongs to [Jonah Ostroff](https://sites.math.washington.edu/~ostroff/puzzles/Heroes_of_Sokoban_III_The_Bard_and_The_Druid.html);
the [Frontier](https://soko.banteg.xyz/frontier/) and
[write-up](https://banteg.xyz/posts/sokoban/) are by banteg. Existing record routes
retain the public holder attribution above. No Proven-Commons Verified Bar or
kernel-checked proof claim is made by this campaign record.
