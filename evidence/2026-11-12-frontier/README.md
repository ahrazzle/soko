# Frontier test on November 12

The existing III-20 84-key route and III-21 316-key route reproduced locally. No new shorter route was found in the baseline searches. The public final replays were inspected in Firefox on the Mac. No new record was submitted.

A later every-start window scan also found no improvement. It expanded 39,495,921 states in 177.119 seconds, with 118 node-cap truncations. `window-search/summary.json` records the completed and interrupted windows. These are search bounds, not proof bounds.

## Evidence

| Artifact | What it records |
| --- | --- |
| `browser-observations.json` | Current queue, source editor, public replay endpoints and limits |
| `iii20-live-instance.json`, `iii21-live-instance.json` | Captured instance, route and attribution |
| `iii20-certificate.json`, `iii21-certificate.json` | Complete instance and route hashes, current Python checker hashes, replay outcomes and explicit proof limits |
| `iii20-search.json`, `iii21-search.json` | Results from the recovered C++ optimizer: 84 to 84 and 316 to 316 |
| `iii21-dual-python-replay.json` | Raw current-repository replay output |
| `recovered-package-tests.txt` | Six historical package tests run against the recovered source with GCC 16. This is not the current repository test suite |
| `repo-tests.txt` | Twelve tests run against the composed repository and new evidence adapter |
| `search-runner-smoke.json` | Portable clang build and direct candidate-generator runner on a two-move corridor |

The baseline searches used beam width 40,000 and a configured 60-second beam budget. III-20 used the default 14-key window. III-21 used an 18-key window and took 83.96 seconds. The recovered optimizer does not bound the whole search with that budget. The new runner adds a process timeout.

Raw older outputs use the package's `VERIFIED` label. Here that means successful empirical replay with the engines named in the record. It does not mean the Proven-Commons Verified Bar passed. The new certificates state `differential_replay` and `formal_proof_checked: false` to prevent that ambiguity.

Reproduction commands and source hashes are in `experiments/frontier_mac/README.md`. The general MCP contract and remaining proof obligations are in `docs/verified-systems-loop.md`.
