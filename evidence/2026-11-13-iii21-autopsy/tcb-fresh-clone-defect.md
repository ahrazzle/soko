# Defect: a fresh clone silently rebuilds the pinned engine and breaks its own TCB lock

Found 2026-11-13 while running the III-21 optimiser in a fresh clone of
`ahrazzle/soko` at `9fcb6cf`. This is a defect in the verification
machinery, not in any room result. All three oracles agreed throughout;
the failure is in the lock around them.

## What happened

1. Fresh `git clone`, new branch. First Sokoban tool call auto-compiled
   the C++ engine (the MCP compiles on first use).
2. `python3 -m soko_mcp optimize --room III-21 --window-len 24 ...`
   failed immediately with:
   `seed_route (len=316) is not a valid winning route for this room:
   alive=True, exact_win=True, premature_win=False`
   Every reported field says the route wins. The message hides the cause.
3. `python3 -m soko_mcp verify` on the same route reported
   `epistemic_status: REJECTED_TCB_UNLOCKED`, `differential_match: true`,
   `triple_oracle_checked: true`, `checker_pins_ok: true`.
4. `python3 -m soko_mcp tcb-lock` reported `TAMPERED_OR_UNLOCKED` with
   exactly one mismatch:
   `cpp/build/soko_engine`: expected
   `d72b3629e60709366b86f57b4f8eed0966ab0a06a26b46f65223ea94f34a4102`,
   actual `e2673ee7a9fc1964e57fe8294a3420614c1ff9e7a50840dc48f9c7ea1989f54c`.

## Mechanism (verified, not inferred)

- `SHA256SUMS` pins the hash of the *compiled binary*
  `cpp/build/soko_engine`. The binary is tracked in git (force-added;
  `.gitignore` lists `cpp/build/`) and was committed in `4f274f3`.
- `soko_mcp/engine_bridge.py::ensure_cpp_engine` reuses the binary only
  if its mtime is >= the source mtime; otherwise it rebuilds with
  `[g++] -O3 -pthread -std=c++20` and replaces the binary. A fresh
  `git clone` sets mtimes by checkout order, so whether the pinned
  binary survives is decided by checkout order, not by any check.
  In this clone the binary was older than the source, so it was rebuilt.
- The rebuild is toolchain-dependent: this VM's g++ 13.3 produces a
  different binary than the pinned one (built on the author's toolchain),
  so the manifest mismatches and the lock fails.
- `verify_route_dual` then sets `valid_winning_route: False` because the
  lock is a conjunct (`dual/triple checked AND differential match AND
  exact win AND pins OK AND tcb locked`), and `optimize_route_verified`
  raises on that flag. The optimiser never runs — fail-closed — on a
  seed every oracle agrees wins.

## Why it matters

- Every fresh checkout is one mtime ordering away from a broken
  optimiser, with an error message that points at the *route* instead
  of the lock. A new player following the quickstart hits this before
  they solve anything.
- The failure is silent about its own cause in the one place a player
  looks (`optimize`'s error). The diagnosable signal
  (`REJECTED_TCB_UNLOCKED`) only appears in `verify` output.
- It makes the pinned binary's trust depend on the builder's toolchain
  rather than on the pinned source plus the oracles' agreement.

## Workaround used in this session (no policy change)

Restored the pinned bytes and made the binary newer than the source so
the cache check keeps it:

```sh
git checkout -- cpp/build/soko_engine
touch cpp/build/soko_engine
python3 -m soko_mcp tcb-lock   # tcb_locked: True
```

This restores the repo to its pinned state; it does not weaken the lock.
The branch in this PR contains no binary change (`git status` shows only
the new evidence bundle and docs).

## Fix directions (for team review; not applied here)

The TCB policy is security-critical machinery, so this bundle reports the
defect and proposes, but does not apply, a fix:

- **A (recommended): pin the source, not the binary.** Drop
  `cpp_soko_engine_bin_sha256` from the manifest. Trust in the binary
  should come from (i) the pinned source hash, (ii) a rebuild from that
  source, and (iii) the behavioural agreement the triple-oracle check
  already computes. A binary hash adds no security once the source is
  pinned and the oracles cross-check behaviour — it only adds
  toolchain fragility.
- **B: make the build reproducible and the cache check content-based.**
  Record the exact compiler and flags, and rebuild only when the binary
  is missing or the *source hash* changed — never on mtime. The pinned
  binary then survives clones on any machine with the recorded toolchain.
- **C (minimal, no policy change):** include the epistemic status and
  the TCB reason in the optimiser's error, so the next person sees
  `REJECTED_TCB_UNLOCKED` instead of a misleading "not a valid winning
  route".

## Reproduction

```sh
git clone https://github.com/ahrazzle/soko.git soko-fresh
cd soko-fresh
# If cpp/build/soko_engine is older than cpp/soko_engine.cpp, the first
# Sokoban call rebuilds it; check with:
python3 -m soko_mcp tcb-lock
python3 -m soko_mcp optimize --room III-21 --window-len 24 --beam-width 40000 --budget-sec 240
```
