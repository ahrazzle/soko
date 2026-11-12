# Issue #22: provenance-aware room triage

Shared before implementation under the team's document/share/implement/test/share
SOP. Canonical source: https://github.com/ahrazzle/soko/issues/22 (Zero / zero-aska,
with disclosed grk-axiom assistance), inspected 2026-11-12 America/Chicago.

Implement a small read-only all66-room report using the canonical catalog and a
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
  record ID and length with a valid timestamp. Missing/truncated history means
  unknown age; retrieval time is never substituted for record time.
- Pin raw snapshot and catalog hashes, observation time, source URL and report
  semantics. A saved snapshot requires its observation time explicitly.
- Tests cover all66 coverage, duplicate/malformed/inverted data, zero-gap claim
  scope, exclusions, matching and missing/stale/future/conflicting timestamps.
- Execute against a current response, retain the report and tests, and post
  measured findings to issue #22. No new solver query or record claim is needed
  to establish this prioritization result.

The initial live observation has three positive reported gaps: III-21 48,
III-20 10, III-14 5. These are screening values. Summing independent walks/pushes
can double-count shared actions; Wizard mechanics can invalidate ordinary walk
bounds. A bound310 with incumbent316 would allow up to six saved keys and would
not prove that a new record is impossible or unimportant.
