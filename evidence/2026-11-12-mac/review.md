# Checkout review, 2026-11-12

The reviewed source is commit `73fbf3363c6a8e3dfd8a3fc9a2e41bb16d160acf` in `ahrazzle/soko`. The source manifest records the original Git blob hash and SHA-256 hash for all 11 files. It describes the baseline, not a lock for these repairs.

## Shipped files and repairs

The baseline does not contain `cpp/soko_engine.cpp`, tests, CI workflows, `SHA256SUMS`, `formal_kernel.py`, Lean sources or the advertised `formal_*` tools. Its server registers eight tools, three resources and two prompts, rather than the README's advertised 14, five and four.

The repairs connect the existing manifest checker to MCP and the CLI. They add a capabilities command and distinguish an unavailable search engine from a completed search that found no solution. A backend returning no output reports failure rather than budget exhaustion. The README now describes the missing components before the earlier feature claims.

## Proof boundary

Matching results from the two Python interpreters provide evidence of agreement, not a formal proof. This checkout has no Lean theorem, no independently pinned external specification and no browser-engine comparison. The audit catches its ten planted mutations but does not establish that every rule matches the original game. Stored floor and optimality numbers remain metadata, not proofs checked in this run.

The manifest checker reports `TAMPERED_OR_UNLOCKED` because `SHA256SUMS` is absent. Route replay still permits a `VERIFIED` result without that manifest. That label describes agreement between available interpreters, not satisfaction of the full Proven-Commons verified bar.

## Validation

- Six regression tests pass with `python3 -m unittest discover -s tests -v`.
- `python3 -m compileall -q soko_mcp tests` passes.
- `git diff --check` passes.
- The existing audit passes ten baseline comparisons and catches all ten planted mutations.
- CLI checks for capabilities and the manifest complete successfully and report the absent C++ engine and manifest.
- No C++ compilation, CI run, browser replay or Lean proof was performed for this patch.

The saved test, audit and CLI outputs accompany this note. The hashes identify the source used for replay but do not prove interpreter correctness.

## Separate findings

The built-in I-1 grid needs nine right moves, while its stored route and metadata claim eight. Both Python interpreters accept nine moves and reject eight as a win. The metadata is unchanged because no original game source or public browser evidence was supplied to settle the intended room layout.

A separate local package, not copied into this checkout, was reported by the coordinating agent to fail with clang because it includes `bits/stdc++.h`, and to work with installed `g++-16`. This is a reported portability finding, not a compiler test performed against this commit. No compiler patch is included because the current remote commit lacks the C++ source.
