# Evidence-aware room triage

This read-only screening report adapts [issue #22](https://github.com/ahrazzle/soko/issues/22).
It covers all 66 canonical rooms and keeps public record lengths, public floors,
and their differences explicitly **reported**, not independently certified.
A zero reported gap never becomes an optimality certificate.

```sh
# Fetch public data, save the raw evidence, and honor the current III-20 exclusion:
python -m experiments.portfolio.triage --exclude III-20 --save-snapshot /tmp/frontier.json > /tmp/triage.json

# Reproduce a saved observation; use its actual recorded observation timestamp:
python -m experiments.portfolio.triage --snapshot /tmp/frontier.json --observed-at 2026-11-12T23:15:02.067601+00:00 --exclude III-20

python -m unittest tests.test_room_triage -v
```

The ranked queue sorts positive reported gaps descending. This estimates the
room available under the supplied public interval; it is not a probability of
finding a record or an estimate of search difficulty. Exclusions remain visible
in both the complete room list and a separate excluded list. All malformed,
duplicate, incomplete or inverted room data fail closed. Duplicate JSON keys
and nonfinite numbers are rejected.

Incumbent-entry age comes only from public history matching the current record
ID, room and length, with an unambiguous timestamp no later than observation.
Missing or conflicting matching entries give null. This is the age of that
entry, not necessarily the first time its length was achieved. Observation time
is never substituted for record age. Public proof fields are not proof-checked
and cannot upgrade a reported floor.

The existing `formal_triage_portfolio` accepts caller-supplied numeric bounds.
This adapter deliberately does not route imported page floors through that
tool's optimality classification. It adds no lower-bound formula: independent
hero walk/push sums require sound cost partitioning, and movement/portal rules
must be represented before a distance can be an admissible bound.

The [recorded execution](../../evidence/2026-11-12-issue22/README.md) finds only
three positive reported gaps: III-21 48, III-20 10, and III-14 5. The selected
queue is III-21, then III-14 after the user's III-20 exclusion. No solver search,
new record or new lower bound is claimed.
