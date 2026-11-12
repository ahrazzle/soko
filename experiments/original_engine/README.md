# Replay in the original Part III engine

`check.py` runs Jonah Ostroff's original self-contained PuzzleScript build in
Chromium. It checks candidate routes independently of the repository's rewritten
Python and C++ interpreters. It does not submit anything to the Frontier.

The checker pins both the original HTML and its embedded PuzzleScript source to
the versions inspected on 2026-11-12. The HTML is downloaded from Ostroff's site
with normal TLS verification and stored in an external cache, not redistributed
in this repository. A changed or corrupt file fails closed. Updating these pins
requires a source review and revalidation, not an automatic hash refresh.

## Optional dependencies

The ordinary test suite and MCP do not require browser packages. For this checker,
install the Python `playwright` package in your development environment and use
an installed Chromium, or install Playwright's Chromium with `python3 -m
playwright install chromium`. No Playwright browser download is needed when
Chromium is already installed. `curl` is used for the pinned source download.

Browser selection, in order: `--chromium`, `SOKO_CHROMIUM`, a system `chromium`,
`chromium-browser` or `google-chrome`, then Playwright's installed browser.

## Run

From the repository root:

```sh
python3 experiments/original_engine/check.py \
  --room 20 \
  --instance evidence/2026-11-12-frontier/iii20-live-instance.json \
  --output /tmp/iii20-original-replay.json
```

Alternatively pass `--route UDLRA...`. Room numbers are 1–22 of **Part III**.
Only uppercase U/D/L/R/A is accepted, up to 10,000 keys. An instance JSON supplies
the route; **its grid does not replace the original room**. Conflicting room IDs
and non-Part-III inputs are rejected.

The default cache is `$XDG_CACHE_HOME/soko-original` (or `~/.cache/soko-original`).
Use `--cache-dir` to choose another external directory. `--html /path/part3.html`
uses an already downloaded file, still enforcing the same pin. Do not commit the
cached upstream HTML. After fetching, browser networking is restricted to the
single pinned page on an ephemeral loopback server; remote resources are blocked.

Exit 0 means the first win occurred on the final key without death, restart, or
an unfinished `again` cycle; exit 1 means the route did not meet that contract.
Invalid inputs, missing dependencies and integrity errors are failures, not wins.
Runtime/setup failures return exit 2 and replace the requested report with a
`CHECK_FAILED` attempt, so an earlier successful certificate cannot be mistaken
for the current run. Argument-parsing failures occur before an attempt is made.

Reports include the full route, source/checker/browser identity, initial raw
object state, instance hash, trajectory hash and complete certificate hash.
Default output is compact. `--frames` includes every executed raw frame for
debugging. These are **local original-build replay** results, not public-service
acceptance, optimality proofs or independent specification approval. Matching a
public initial bitfield establishes instance/encoding agreement; it does not
prove that every possible transition matches a server implementation.

For campaign runs, invoke this checker through `experiments/record_run.py` to
enforce a wall-clock budget. The key and `again` limits do not provide a timeout
for code executing inside the browser.

## Check the checker

```sh
python3 -m unittest tests.test_original_engine -v
SOKO_ORIGINAL_HTML=/path/to/pinned/part3.html \
  python3 -m unittest tests.test_original_engine -v
```

The first command runs seven checks of integrity, input, caching and acceptance
boundaries using only the standard library; two browser tests are explicitly skipped. The second
also runs original-engine baselines III-14 (48 keys), III-20 (84), III-21 (316),
and rejects an 83-key prefix, an 85-key route that wins prematurely at key 84,
and `AAU`, which kills the player on key 3.
The original III-14 room is 15×7.

Source and puzzle credit: [Jonah Ostroff](https://sites.math.washington.edu/~ostroff/puzzles/Heroes_of_Sokoban_III_The_Bard_and_The_Druid.html).
The pinned upstream build is executed unchanged; this wrapper observes its
transition, win, corpse and restart behavior. Original game assets and their
license/redistribution scope are not supplied by this wrapper.
