# Sound structural landmarks for complete bounded solving

This document supplies necessary conditions, not a route, a new record, or a
machine-checked optimality proof. No heuristic macro order or fixed material
count is imposed. Coordinates are zero-based, with y increasing downward.

## Certified scope and trust boundary

Enable the concrete III-14 clauses below only for the exact original 15x7 grid
returned by `soko_mcp.catalog.get_room('III-14')`, with its pinned Part III source
SHA256 `f66ceb8f8a2c23a3cb270bad62cdf194e47479772cab94f154ed26f0ff7c20e0`.
Compare the complete initial grid and mechanics identity, not merely the room
name or dimensions. Disable these clauses for any different instance. The
current proofs are mathematical arguments checked against source mechanics;
they are not proof-assistant certificates of the transition implementation.

Relevant source assumptions:

* There are exactly two initial heroes: inactive Bard (2,2), active Druid (2,4).
* No rule creates heroes. A winning execution therefore loses neither hero:
  original win conditions are both `All Hero on Goal` and `All Goal on Hero`.
* Each surviving hero moves at most one orthogonal cell per input, including
  an inactive Druid carried by Bard. There is no Wizard in this room.
* Closed purple doors block movement, cannot be transmuted, and cannot coexist
  with a surviving hero. Closing a door on a hero is fatal.
* At every live settled frame, purple doors are open exactly when all nine
  switches are weighted. A cancelled Bard input preserves the previous settled
  frame, so it does not violate this invariant.
* In this room switch weights are heroes, crates, or walls. There are no
  monsters. Bard moves crates and the inactive hero, not walls.

Original grid:

```text
###############
#.............#
#.5.}}}.]]]]].#
#...}}}.]G.G].#
#.D.}}}.]]]]].#
#.............#
###############
```

## III-14: all switches must simultaneously contain material

Let `C = {(9,3), (10,3), (11,3)}`. These are the three cells inside the
closed-door enclosure; the two goals are (9,3) and (11,3). Direct inspection
shows that its external orthogonal neighborhood is exactly

```text
N(C) = {(8,3), (12,3), (9,2), (10,2), (11,2), (9,4), (10,4), (11,4)}.
```

Every cell of `N(C)` is initially a purple door. None of `C union N(C)` is a
switch. Both heroes initially lie outside C.

Take the first settled frame t in which both heroes are in C. Such a frame
exists in every win. At t-1, each hero is in `C union N(C)`, because each moved
at most one cell. At least one is in N(C), by minimality of t. Consequently:

1. Neither hero is on a switch at t-1.
2. A surviving hero occupies a door cell at t-1, so the doors are open.
3. All nine switches are therefore weighted at t-1, entirely by walls/crates.

The proof covers simultaneous Bard/Druid entrance. It does not assume who
enters first, which side they use, or that doors remain open after t. Moving
around a converted exterior border cannot bypass N(C). An interior origin
would invalidate the argument, but the checked initial state has none.

For bitboards `W[t]` (walls), `K[t]` (crates), and fixed switch mask `SW`, add:

```text
OR over t=0..H: (((W[t] | K[t]) & SW) == SW).
```

This is an existential historical landmark, not a final-state requirement.

## III-14: at least nine wall-to-crate events

Initially all material tokens are walls on the outer boundary; there are no
crates, interior walls, or monsters. For the argument, give each initial wall
a conceptual identity. Transmutation preserves that token's identity; Bard
movement relocates it; door crushing can only delete it. Hero destruction
cannot occur in a winning execution. Doors cannot be turned into material.

At the landmark above, nine distinct non-boundary switch cells contain nine
distinct material tokens. Each token started as a stationary boundary wall.
Before reaching a switch, each must have undergone at least one Druid
wall-to-crate event, because only the crate form can move. Thus every winning
execution has at least nine such events before the landmark and in total.

A simple necessary clause is:

```text
sum over transitions t=0..H-1 of wall_to_crate_event[t] >= 9.
```

Count the actual Druid directional transition into a wall, not net crate-count
increases: movement and door crushing can occur in other transitions. Repeated
conversions of the same material count as repeated events; this weakens but
does not invalidate the bound. A stronger optional implication is that each
landmark frame has at least nine preceding events.

Do not replace this with exactly nine events, exactly nine crates, exactly nine
remaining materials, or a prohibition on crushing. The baseline ends with six
crates plus three frozen walls on switches. Additional material or different
freeze patterns remain in the complete search space.

For suffix-only models, replay the prefix and carry the prior event count and
a landmark-already-seen flag. Never require the historical landmark to recur
inside the suffix. Models retaining every frame with a fixed prefix can apply
the formulas directly over that complete timeline.

## Reusable topology relaxation

For mechanics where no hero can cross an intact wall, the union of initially
walled cells ever transmuted must provide connectivity from each initial hero
to its eventual goal. Wizard teleportation respects this condition only when
its ray is stopped by intact walls, as in this source. Bard carriage and pushes
also respect it. The union relaxation deliberately permits walls removed at
different times to be simultaneously absent.

Build a permissive cell graph with all nonwall cells traversable, including
potential door cells. Select initially walled vertices to remove so that the
initial heroes can be matched to distinct goals within resulting connected
components. The minimum number of selected walls lower-bounds distinct initial
walls transformed and therefore wall-to-crate events. Shared openings must be
charged once; summing individual hero shortest-path wall costs is generally
unsound. Simpler constraints require one removal from each separating wall
cut; their counts may be summed only when the relevant event sets are disjoint.

A mechanically generated certificate should list the exact initial-grid hash,
cut vertex sets, their disjointness where claimed, connectivity checks before
removal, and the mechanics assumptions forbidding wall crossing. Mutable doors
must be treated permissively or justified by a separate door-specific proof.
This relaxation is a lower bound, not an equivalence to the concrete puzzle.

## Solver architecture and certification limits

Use these clauses as redundant consequences of the exact transition system.
Keep all legal hero assignments, material counts, control orders, and paths.
An incumbent can seed solver hints but must not restrict the global formula.
Any abstraction must admit every concrete transition; deleting an object and
making its cell empty does not satisfy this requirement in general, because
objects can serve as Wizard anchors and Bard movement blockers.

For a SAT result, replay the extracted keys in independent local interpreters
and then the pinned original build. For UNSAT, retain the complete instance,
source/model hashes, enabled landmark IDs and assumptions, solver result and
proof artifact when available. A timeout is unknown. A solver UNSAT result is
conditional on model correctness until its encoding and proof are independently
checked; simulation calibration alone is not a universal equivalence proof.

No macroaction or commutation transformation is authorized by this document.
