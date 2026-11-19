# Controlled search-policy experiment

Shared before execution, 2026-11-12 America/Chicago. User authorizes autonomous
system and record work, with III-20 excluded and immediate reporting of a
new record after original-game verification.

Question: does checking the cheap material flow before exact completion reject
unproductive global hero schedules more efficiently, and does the new sink-side
cut help or hurt that process?

The exact initial 15x7 III-14 instance, horizon 47, terminal absorption, source
code and wall budget remain fixed. Run these configurations sequentially in
separate bounded workers with 30 seconds each:

1. Exact first, source-minimal cuts (current default).
2. Flow first, source-minimal cuts.
3. Flow first, sink-minimal cuts.

Keep events and symmetry disabled as in the measured default. Retain every
candidate, checked cut, phase timing, termination status and source hash. The
result is a diagnostic, not an optimality proof or a general speed claim. Exact
UNSAT still needs the existing recheck; flow feasibility still needs concrete
completion and original-game replay. No prefix or incumbent route is pinned.

Decision rule: inspect which phase consumes the budget and whether cheaper
flow checks eliminate candidates or merely replace useful exact cuts with
weaker cuts. If a policy shows useful progress, repeat it and the baseline
under equal budgets before any default change. If all stall, use the profile to
choose one targeted representation or scheduling improvement; do not widen
the search blindly. Publish the tested result and any subsequent implementation
back to issue #22.
