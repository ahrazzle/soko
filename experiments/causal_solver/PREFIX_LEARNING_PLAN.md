# Checked deterministic prefix-frame learning

Shared before implementation, 2026-11-12 America/Chicago. This follows the
[search-policy experiment](SEARCH_POLICY_PLAN.md) and issue #22.

The archived H47 exact-first run rejects 148 of 151 candidates for hero/active
mismatch and three for hero loss, all by frame 17. A new 30-second diagnostic
rejects 64 candidates without reaching flow. Flow-first instead adds one
source-minimal cut or fifteen sink-minimal cuts before timing out. These cuts
are different-strength constraints, so their counts are not comparable progress
units and none of these runs establishes a new bound.

Hypothesis: current exact cuts exclude one wrong equality under a fixed action
prefix, leaving other impossible hero positions under that same prefix. Learn
the complete actual Bard/Druid/active frame for each independently checked
prefix instead, so later candidates must respect all of those facts.

Implementation:

- Add opt-in `--learn-prefix-frames` to causal search. Keep the existing exact
  nogood and attach prefix implications only after its existing independent
  recheck succeeds. Default behavior stays unchanged during the experiment.
- Derive surviving frame facts during replay of the certificate's contiguous
  action prefix, using the retained transition and separate Python oracle with
  all material present. Never trust serialized asserted frame facts. Bind to
  the exact board/mechanics metadata and preserve terminal absorption.
- Install `actions[:t] == checked_prefix => complete_actual_hero_frame[t]` for
  each checked surviving frame. Do not constrain states under other prefixes.
  Illegal-loss prefixes retain the existing rejection. Failed, corrupt, timed
  out or disagreeing replay adds no implications.
- Test reference and spurious controls; wrong Bard, Druid and active values
  under the same prefix; unrelated-prefix freedom; metadata/tamper rejection;
  timeout no-add; and terminal absorption.

Measurement: same source, default exact-first policy, horizon 47, events and
symmetry off, sequential equal 30-second wall budgets. Compare ordinary cuts
and prefix learning, retaining candidate depth, cuts, phase times and sources.
Repeat before changing defaults. Profile checkpoint overhead separately because
existing phase timers are not pure solver timers. Deeper checked prefixes can
indicate a different frontier but do not prove better coverage or a record.

Publish code, tests, negative or positive result and limits. Stop this line if
larger master constraints erase its benefit; no unlimited compute campaign.
