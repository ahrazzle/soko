# Issue #22: provenance-aware room triage

Shared before implementation under the team's document/share/implement/test/share
SOP. Canonical source: https://github.com/ahrazzle/soko/issues/22 (Zero / zero-aska,
with disclosed grk-axiom assistance), inspected 2026-11-12 America/Chicago.

Implement a small read-only report for all 66 rooms using the canonical catalog and a
saved or freshly fetched Frontier response. This adapts the issue's portfolio
recommendation; it does not import its proposed sum-of-hero-distances bound.

Required behavior:

- Validate canonical identities, unique complete coverage, integer nonnegative
  lengths/floors, and noninverted intervals. Fail closed on malformed inputs.
- Label every public floor and gap as reported, not locally certified. A zero
  reported gap never becomes an optimality certificate. Do not feed imported
  floors into the existing formal triage tool's CLOSED_OPTIMAL classification.
- Rank positive reported gaps for screening, not as a probability of success
  or difficulty estimate. Keep exclusions visible; the current user's III-20
  exclusion affects the search queue, not the underlying observations.
- Infer incumbent-entry age only from a matching public history entry by room,
  record ID and length with a valid timestamp. Missing matching history means
  unknown age; retrieval time is never substituted for record time.
- Pin raw snapshot and catalog hashes, observation time, source URL and report
  semantics. A saved snapshot requires its observation time explicitly.
- Tests cover all 66 rooms, duplicate/malformed/inverted data, zero-gap claim
  scope, exclusions, matching and missing/stale/future/conflicting timestamps.
- Execute against a current response, retain the report and tests, and post
  measured findings to issue #22. No new solver query or record claim is needed
  to establish this prioritization result.

The initial live observation has three positive reported gaps: III-21 48,
III-20 10, III-14 5. These are screening values. Summing independent walks/pushes
can double-count shared actions; Wizard mechanics can invalidate ordinary walk
bounds. A bound of 310 with incumbent 316 would allow up to six saved keys and would
not prove that a new record is impossible or unimportant.

## Completed

`triage.py` implements the report and strict input/history checks. Six unittest
cases with adversarial subtests pass, and a fresh live response was processed
and saved at 2026-11-12 17:15:02 America/Chicago. The resulting queue is III-21,
then III-14; III-20 remains visible as an exclusion. The other 63 entries have
zero reported gap without being relabeled as locally proved optimal.

The CLI, raw source, repeatable report, shared-action example and fresh III-21
baseline replay are in `evidence/2026-11-12-issue22/`. Results are posted back to
the source issue with the implementation PR. No new solver search was run.
