# Source-guarded events and remaining-input bounds

`events.py` adds necessary conditions for the original III-14 grid and pinned
source. Both adapters invoke the existing exact source/grid guard. The hero
master must supply legal relaxed hero transitions and absorbing goal frames;
the exact adapter requires the complete seven-component transition and one-hot
surviving heroes. These are adapter preconditions, not claims established by
the event clauses themselves.

## Events and chronology

For every initial border wall cell c and input t, a master release opportunity
means: the frame is preterminal, Druid is active, the directional input targets
c, and Druid holds position. The master movement rules then also hold Bard.
An exact release additionally requires a wall currently at c. Define
seen[0,c]=false and seen[t+1,c]=seen[t,c] OR release[t,c]. Thus arbitrary Boolean
event claims cannot invent a past release. At the common material-flow landmark
the master requires at least nine distinct seen origins. The exact adapter
imposes this at every all-material-switch frame.

The original room starts with no crates and only boundary-wall material. The
nine switch occupants at the necessary material landmark have nine distinct
initial wall origins. Transformations preserve an origin; transport changes
position; door crushing only deletes material. Each selected token first moves
from its origin only after Druid transforms its wall into a crate there. That
input leaves both heroes fixed. Consequently nine distinct exact releases,
and hence nine master release opportunities, precede the landmark. Counting
opportunities that do not release useful material merely weakens the master.
No event is earned during absorbing terminal padding.

## A bound that respects simultaneous movement

For hero-position pairs p and q, let

    J(p,q) = max(0, dx_B, dx_D) + max(0, -dx_B, -dx_D)
           + max(0, dy_B, dy_D) + max(0, -dy_B, -dy_D),

where each displacement is destination minus source. During one directional
input, each hero either holds or moves one cell in that input's direction.
Thus any one input reduces J to a fixed destination by at most one. This
permits simultaneous Bard and Druid movement and does not add their Manhattan
distances. All symbolic differences and sums use integer arithmetic, including
unsigned BV2Int conversion of master coordinates; coordinate overflow cannot
weaken or strengthen these inequalities.

Let k[t] count distinct seen origins and a[t] count preterminal A inputs before
frame t. Release inputs and A inputs are disjoint, and both leave both heroes
fixed. Every true projected trace therefore satisfies

    J(starts, current[t]) + k[t] + a[t] <= t.

For at least one assignment g of the two heroes to the two distinct goals,

    J(current[t], g) + max(0, 9-k[t]) + activation[t,g] <= horizon-t.

The activation term is one exactly when Bard is inactive and Bard has not
already reached its assigned goal. Only active Bard can move Bard, so a future
A input is then necessary. That input is disjoint from both directional travel
and future releases. If k[t]>=9 the resource deficit is zero, including after
the material landmark and terminal frame; nothing is charged twice. At the
initial frame these conditions imply the conservative global bound 21 inputs
(11 joint travel, nine releases, one activation). They do not establish the
optimal puzzle length or a measured search speedup.

## Equivalent choices and normalization

The exact wall and crate bitmasks already quotient all permutations of
artificial material identities. `canonical_full_state_key` retains walls,
crates, both hero masks, activity, notes and door state. It removes no actual
game state and applies no spatial symmetry: the source, goals and hero roles
do not justify a board-symmetry restriction.

Optional normalization forbids consecutive preterminal A inputs. In a settled
reachable state, switching twice restores hero roles and notes; occupancy does
not change, so the occupancy-determined settled doors and material also stay
fixed. More explicitly, reachable settled states satisfy

    notes = if active then area(Bard) AND (crates OR Druid) else 0
    opened = ((walls OR crates OR Bard OR Druid) AND switches) == switches.

The initial state satisfies these equalities. Every successful late phase
recomputes them; closing doors removes material and corresponding notes only
from door cells, which are disjoint from switch cells. Hero survival excludes
door deletion of either hero. A cancelled Bard turn preserves the prior state
and hence the invariant. Under this invariant, A changes only activity and
notes, so AA restores all seven fields. Arbitrary stale seven-field states
need not obey AA identity; their exclusion is not justified by this argument.
The tests prove AA identity symbolically under the settled invariant and check
the invariant at every concrete reference frame.

The exact adapter may additionally forbid a directional input only when
all seven state components remain equal. Deleting such an input preserves the
complete state and reduces cost. The hero master cannot observe material,
notes or doors, so it never removes a direction merely because heroes hold.
In particular, an essential Druid conversion holds both heroes.

Deleting any finite sequence of these redundant inputs yields the same winning
state at no larger cost. Absorbing terminal semantics pad the shorter win to
the requested horizon. Normalization is therefore an existence-preserving
bounded optimization, not a constraint satisfied by every original route.
`normalize_route` independently verifies complete endpoint equality after
deletions, repeating when deletion exposes another AA pair, and truncates at
first win. The default adapters leave normalization disabled.

## Controls and limits

The tests independently extract events by reading the concrete Python engine,
accept the known 48-input route, compare every event and cumulative origin
count, reject planted premature seen/release claims, and exercise the source
guard. A complete two-by-two-board enumeration checks the one-input J decrease
for every simultaneous hold/move pattern and every destination pair. Short
concrete traces exhaustively check normalization endpoint and cost preservation;
the known win checks postterminal padding. These finite controls support the
quantified argument above. They are not a formal proof that either retained
symbolic transition equals the original game for all traces; winning candidates
still require independent original-game replay.
