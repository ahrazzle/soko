# Nine-token transport relaxation

This experiment asks whether III-14's shortest-key problem becomes tractable
when represented by the necessary work of acquiring and transporting material.
It is a global relaxation of the original initial-state problem. It neither
fixes a route prefix nor restricts the number or order of control changes.
An abstract winning trace is not a playable solution.

## Optimization from first principles

The concrete problem is a shortest path in the directed graph of legal game
states, with one unit of cost per input. A replayed winning path gives an upper
bound on the optimum. A lower bound needs an argument covering every possible
winning path, including ones unlike the incumbent.

The shortest-path dual assigns a potential `h(s)` to states such that

```text
h(goal) <= 0
h(s) - h(s_next) <= 1    for every legal input transition
```

Summing the inequalities along a winning path proves `h(initial) <= path length`.
This explains why a plausible progress score is not automatically a lower
bound: its one-step inequality must hold globally. It also explains why adding
independent object distances can be wrong here. One Bard input can transport
many objects simultaneously; that input cannot be charged separately to each.

An abstraction that admits every concrete winning execution supplies another
way to obtain lower bounds. Its exact distance to its goal is a dual-feasible
potential on the corresponding augmented state space. This pilot does not
construct a potential table or solve a linear program. Instead, it asks whether
an abstract win exists within a horizon. If the relaxed formula is UNSAT at
`H`, then every concrete winning route has length at least `H + 1`, subject to
the projection theorem and encoding correctness described below.

The existing generic `formal_certify_lower_bound` implementation enumerates
concrete transitions to establish its certificate's domain closure. Passing it
a short potential function does not by itself avoid concrete state explosion.
This experiment therefore uses a separately defined finite relaxation and the
existing CNF/proof-checking infrastructure.

## State and allowed behavior

Keep the two hero positions, their active identity, and nine labeled material
tokens. Each token has a position and a Boolean recording whether its first
wall-to-crate conversion has happened. Each label corresponds to one of the
nine switch cells; its original position is an existentially selected initial
boundary wall. All nine original positions must be distinct.

Before its first conversion, a token stays at its original position. Conversion
requires a Druid directional input targeting that position from the adjacent
cell and leaves Druid stationary. After conversion the abstraction forgets
whether the token is currently a wall or a crate.

On a Bard directional input, Bard may stay or step one cell in that direction.
If Bard steps, any already converted token within Chebyshev distance two of
Bard's previous position may independently stay or take the same step. The
inactive Druid has the corresponding optional carriage behavior. If Bard does
not step, the whole Bard movement phase stays put. On a Druid directional input,
Druid may stay or take one step; Bard and the tokens stay. A harvesting input
requires Druid to stay. The action input changes active identity without moving
anything. Positions remain inside the original board.

The abstraction drops occupancy, collision, door, and frozen-material
restrictions. Independent token stuttering admits both blocked and frozen
objects. It permits additional behavior; it does not model the original
movement phase exactly. In particular, removing an untracked object from the
concrete game and executing the remaining board would not establish the
required relaxation: blockers can change which other objects move.

The abstract goal requires a historical frame with all nine labeled tokens on
their corresponding switch cells, followed by both heroes on distinct goals.
The material condition is historical, not a requirement on the final frame.
Extra concrete materials and any number of later transformations are allowed.

## Why every concrete win has an abstract witness

The topology and material argument is documented in
[`structure_system.md`](../exact_frontier/structure_system.md) and
[`iii14_strengthening.md`](../exact_frontier/iii14_strengthening.md). Its scope is
the exact original 15-by-7 III-14 board and pinned Part III mechanics source,
SHA-256 `f66ceb8f8a2c23a3cb270bad62cdf194e47479772cab94f154ed26f0ff7c20e0`.

Take the first settled frame in which both surviving heroes are inside the
three-cell goal enclosure. Immediately before that frame, neither hero is on a
switch and at least one occupies a purple door. The door must be open, so all
nine switches hold material. Call this earlier frame the landmark.

Choose the nine material identities occupying those switches at the landmark,
labeling them by their landmark switch. They began as nine distinct boundary
walls. Transformation preserves material identity; movement changes its
position; door closure can delete identity but cannot create it. Because each
chosen token survives to the landmark, it was first converted at its own
original boundary position before moving. Follow those identities from the
initial frame to the landmark.

Every conversion and movement in this selected history is admitted by the
abstract transition rules. In particular:

* Druid's first conversion targets an adjacent original wall and does not move
  Druid. No other input can make that wall leave its original position first.
* A selected token's displacement is a Bard displacement, in the same direction
  as Bard. Concrete blocking and frozen material are represented by choosing
  to stay; the abstraction does not force all nearby tokens to move.
* At a settled frame with Bard active, every concrete movement note is on an
  eligible crate or inactive Druid in the radius-two square around Bard. The
  source recomputes notes after ordinary transitions and activation. A canceled
  Bard turn preserves both the board and the notes, so the same containment
  remains valid. Using the previous settled positions for the abstract aura
  therefore admits every actual carried displacement. Allowing every harvested
  token in that square is permissive even when it is currently frozen.
* Bard's blocked input cancels the whole movement; choosing all positions to
  stay admits it. The abstraction also admits the concrete hero movements and
  each control change.

After the landmark, the selected abstract tokens may simply remain fixed
forever while the abstract heroes follow their concrete positions and control
changes. These are ghost positions: no occupancy constraint ties them to the
heroes or to later material. Consequently, crushing a selected concrete token
after the landmark does not invalidate the witness. Requiring continued token
existence in the concrete board, or requiring the switches to stay filled,
would be an unsound strengthening of this proof.

A concrete win before the horizon can be padded by abstract stuttering inputs
with no further harvesting. Its historical landmark and final goal positions
persist. Thus a winning execution of length at most `H` supplies a satisfying
assignment to the horizon-`H` relaxation.

The selection of token identities depends on the future landmark. This is an
**existential path projection**, not a claimed deterministic quotient map from
the current unlabeled concrete state. The proof needs only the implication
`concrete win => abstract witness`; taking its contrapositive justifies an
abstract UNSAT lower bound. It makes no completeness claim in the reverse
direction.

## Conditional decomposition: reachability plus matching

Once the input sequence and both hero trajectories are fixed, the nine tokens
do not interact through movement. Their only remaining coupling is that their
initial wall identities must be distinct and that they must occupy all nine
switches at a common landmark. This conditional allocation problem has a
polynomial algorithm; it does not need general SAT search over token origins.
The supplied hero schedule must itself satisfy the initial positions, control
changes, movement, and carriage rules; matching cannot establish that part.

For each of the 40 initial boundary cells `o`, propagate a reachable set
`R[o, t]` of pairs `(position, harvested)` through the fixed hero schedule. Start
with `(o, false)`. A token can always stay. A Druid input can change its flag
from false to true only if Druid stays and targets `o`. A Bard input can move an
already harvested token only if Bard steps in that direction and the token is
within the previous radius-two aura. Positions outside the board are excluded.
These are exactly the token transition rules of the relaxation under the fixed
hero schedule, with no interactions omitted beyond those already relaxed.

At a proposed landmark `t`, construct a bipartite graph with the 40 origins on
one side and the nine switches on the other. Put an edge from `o` to switch `q`
when `R[o, t]` contains a state at `q`. A matching covering all nine switches
exists if and only if nine distinct original tokens can occupy their assigned
switches at that time:

1. Any abstract token witness supplies those nine matching edges.
2. For any such matching, choose a reachable path for each matched edge. Their
   combination is allowed because token transitions are independent. Harvest
   conflicts cannot arise: an unharvested token remains at its distinct origin,
   and a directional Druid input targets just one cell.

Backpointers reconstruct the nine paths and their first-conversion events.
After the landmark, keep all nine token positions fixed. If a pair of hero goal
positions occurs at or after that landmark, this gives an abstract win. A
successful allocation certificate consists of the distinct origins, matching,
and reconstructed paths; it can be checked without trusting the matching
algorithm, and the entire witness can also be pinned into the SAT model.

There are at most `40 * (H + 1) * 105 * 2` origin/time/token-state combinations,
each with a constant number of successors. The matching graph has only 40 by 9
possible edges. This factorization removes conditional token-allocation search;
it does not remove the global search over hero and input schedules.

### Absorption and the fixed-trajectory contract

The implemented `allocation.allocate` accepts a fixed complete hero schedule
and a specified landmark frame. It supports schedules whose **first distinct
hero-goal pair is at the final frame**. Earlier goal-pair schedules are explicitly
unsupported, not conditionally infeasible. Within this supported class the
oracle exactly decides token allocation at the specified landmark and preserves
every supplied hero frame.

Rebuilt token paths may fill all switches earlier than the proposed landmark.
The oracle computes the actual first landmark and its historical flag, rather
than requiring the proposed time to be first. No earlier absorption can occur
in the supported class because the heroes have not both reached goals. After
the specified landmark the tokens stay fixed, and the supplied hero schedule
finishes on the goals. Requiring the proposed landmark to be the first would be
unnecessary and would introduce new coupling between the token paths.

A broader winning-prefix oracle could accept schedules with earlier goal-pair
visits, reconstruct the actual first terminal frame, and truncate or normalize
the suffix there. That would preserve the supplied hero schedule only until
the first abstract win. It is not the present API contract. Terminal padding
must hold the complete state, including active identity; the terminal SAT
encoding ignores subsequent input choices and requires that full-state hold.

### What a failed allocation can prove

For a fixed hero schedule and landmark, Hall's theorem supplies a compact
matching obstruction: a set of switches has fewer reachable origin neighbors
than its cardinality. Certifying the obstruction also requires checking the
reachable sets used to construct its neighbor graph. A failed matching at one
landmark says nothing about other landmark times; rejecting the entire fixed
schedule requires considering every eligible landmark. The current allocator
checks the one supplied landmark and does not make that broader rejection.

The global loop below uses hero schedules as the master problem
and token allocation as the subproblem. A failed conditional allocation can
safely exclude the exact failed master assignment. A Hall-deficient switch set
is not automatically a globally valid cut on different hero schedules: those
schedules can change every reachability edge. Stronger Benders or CEGAR cuts
require an additional proof that their conditions preserve the reachability
obstruction. The conditional oracle alone establishes neither a new concrete
lower bound nor a complete global planning algorithm.

Constructing a short abstract schedule with this oracle diagnoses the strength
of the relaxation. If the schedule cannot execute in the concrete game, the
failure identifies omitted mechanics. It is not a concrete record attempt or
evidence of an improved game solution.

## Stronger conditional decomposition: time-expanded material flow

Independent reachability and matching allow several selected tokens to occupy
one cell at an intermediate frame. For fixed hero trajectories, this particular
omission can be repaired while retaining a polynomial algorithm. Replace the
independent token paths by an integral, single-commodity maximum flow in a
time-expanded graph.

The graph has a source, one node for each initial boundary-wall origin, split
cell nodes for every frame through the specified landmark, nine switch sinks,
and a common sink. Its edges are:

* Source to each origin, capacity one. This limits each original material
  identity to one selected path, regardless of how many release times it has.
* Origin to its cell at frame `i + 1`, capacity one, whenever input `i` is a
  Druid directional input targeting that origin while Druid stays in place.
  This represents the token's first conversion. No material occupancy is
  represented for that token before this release edge.
* Cell-in to cell-out at each frame, capacity one. Exclude cells occupied by
  either hero in the fixed schedule. These edges enforce occupancy only among
  selected, already harvested material tokens and the two heroes.
* Between consecutive frames, edges for staying in the same cell and for the
  permitted Bard displacement. Displacement requires Bard to step, the cell
  to lie in Bard's previous radius-two aura, and the destination to remain on
  the board. Druid inputs and control changes provide only stay edges.
* Each switch cell at the landmark to its switch sink, and each switch sink to
  the common sink, capacity one.

A flow of value nine gives nine paths from distinct origins to all nine
switches. Integer capacities guarantee an integral maximum flow. Path
decomposition recovers each release time and material trajectory; label paths
by their final switches. Before release, backfill the token at its unharvested
origin. After the landmark, keep it as a stationary ghost without occupancy
requirements. These reconstructed trajectories also satisfy the original
collision-free transport relaxation.

### Why the refinement remains globally sound

Take the same nine concrete survivors selected by the historical landmark
proof. For each, use its actual first wall-to-crate conversion as its release
edge. Its subsequent identity follows a cell path, including stationary periods
when it is blocked or frozen. A later transformation does not reset its release
time or require a second source edge. Selected survivors occupy distinct cells
and never share a cell with a live hero at a settled frame through the
landmark. Their paths therefore respect the graph's capacities and excluded
hero cells. Their original identities and landmark switches are distinct, so
the nine paths form a feasible flow.

Ignoring a token's occupancy before its first conversion only adds possibilities.
The graph does not enforce the original boundary walls, including unharvested
selected walls, as obstacles. It also ignores unselected material and the
wall-versus-crate type of released tokens. Those omissions must not be silently
reintroduced as extra constraints. In particular, Druid staying without a
selected token at its target is not by itself impossible: omitted material can
block movement or be transformed there.

The flow has no material deletion before the landmark because its selected
identities survive to that landmark by construction. Deletions afterward are
handled by the same ghost-token argument as before. All displacements share the
one selected key direction; no additional opposing-edge swap prohibition is
needed for this relaxation.

Consequently every concrete winning execution still induces a feasible
conditional flow under its own hero schedule and landmark. Conversely, an
integral flow exactly represents the strengthened conditional token rules,
with occupancy imposed only after release and through the landmark. This is
not an equivalence to the concrete game.

### Why this stays a single-commodity flow problem

After release, transition permissions depend on time, cell, and the fixed
heroes, not on the token's origin or its eventual switch label. Origin identity
is charged once by the source edge; all nine switches must be covered, but no
origin is assigned a particular switch in advance. The paths are therefore
interchangeable within the flow network. They can be assigned identities again
by following their decomposed source paths, and labels by their terminal
switches. Prescribed origin-to-switch pairings or token-specific movement rules
would be different problems and are not covered by this reduction.

The network has `O(H * board_cells + origins)` nodes and a comparable number of
edges for this fixed action alphabet. Integral maximum flow is polynomial even
with the intermediate occupancy constraints. A successful result supplies nine
paths; an unsuccessful result supplies a cut of capacity below nine. Either
certificate can be independently checked against the constructed network.
Transfer to the game additionally depends on the graph construction and the
projection proof above.

The implementation retains the matching oracle's supported hero-schedule
class: the first distinct hero-goal pair must occur at the final frame, and the
landmark is supplied explicitly. A deficient flow concerns that fixed schedule
and landmark only. It does not establish a global game lower bound, exclude
other landmark times, or justify a cut on different hero schedules without
further reasoning.

### Implemented global master and material-flow cuts

The implemented master/subproblem loop constructs one **fixed universal
network** containing every potentially usable time-cell node, release edge,
movement edge, and switch exit for the entire horizon. Give each edge a capacity
`c_e(m)` depending on the master assignment `m` of actions, hero trajectories,
and a common landmark selector. Include edges whose capacity is zero under the
current assignment; they may become usable under another assignment.

Origin source edges retain capacity one. Split-cell capacities encode hero-cell
exclusion. Release capacities encode Druid staying and targeting an origin;
movement capacities encode active Bard, the chosen direction, Bard stepping,
and the previous aura. A single exactly-one landmark selector gates the switch
exits at the same frame for all nine switch labels. Switch-to-sink capacities
remain one. Before release and after the selected sink frame, the same
occupancy omissions as above apply.

For any fixed set of nodes `S` containing the source but not the sink, every
feasible value-nine flow satisfies

```text
sum(c_e(m) for every universal edge e leaving S) >= 9.
```

The proof is flow conservation: the net flow leaving `S` is nine, and the total
outgoing flow cannot exceed those outgoing capacities. If the current master
assignment has a minimum cut below nine, its source side therefore yields a
necessary inequality that excludes that assignment and can also exclude many
others. The same inequality remains valid when other master assignments enable
new edges, because their capacities were retained in the symbolic sum. This is
a global Benders feasibility cut derived from the network, rather than a Hall
deficiency informally generalized beyond its fixed schedule.

The global implementation is separate from the conditional oracle:
[`universal_flow.py`](universal_flow.py) retains the complete potential graph;
[`global_master.py`](global_master.py) chooses all actions, hero positions,
active identities and one common landmark; [`cut_certificate.py`](cut_certificate.py)
independently reconstructs the source-derived topology, every cut boundary and
its integer capacities. The master adds only these checked inequalities.
[`global_search.py`](global_search.py) repeats until a nine-unit witness, checked
encoded UNSAT, or an explicit inconclusive resource limit.

The master requires the first distinct hero-goal pair at the horizon. This
still covers every concrete win of length h <= H: prepend H-h abstract U
inputs holding the initial heroes and unharvested materials fixed, then shift
the original history and landmark. Initially Druid is active at (2,4), and its
U target (2,3) is not a boundary origin, so this padding needs no release. The
actual history has no earlier goal pair, because that would already be a win.
These prefix holds are legal in the abstraction; they are not asserted to be
legal original-game moves. Positive controls check the 48-key reference and
its padded 49-frame representation.

Each violated cut excludes its generating master assignment and preserves all
feasible flow assignments. With finite domains, unlimited iteration therefore
terminates at a relaxed witness or master UNSAT. This is a completeness
argument, not a practical polynomial-time bound for the global search.

An UNSAT master is recompiled to CNF and rerun through proof-producing SAT.
Only an independently checked certificate receives the status
`certified_relaxation_cnf_unsat`. That certificate proves the generated CNF;
the written game projection, symbolic encoding and CNF transformations remain
explicit assumptions. The result is not end-to-end proof-assistant verification.

## Running and interpreting the experiment

From the repository root, the command interface is:

```sh
python -m experiments.transport_relaxation.run prepare --output /tmp/transport-47 --horizon 47
python -m experiments.transport_relaxation.run solve --output /tmp/transport-47 --horizon 47 --timeout-seconds 60
python -m experiments.transport_relaxation.run control --output /tmp/transport-control
python -m experiments.transport_relaxation.global_search control --output /tmp/global-control
python -m experiments.transport_relaxation.global_search run --output /tmp/global-47 --horizon 47 --timeout-seconds 120 --proof-checker /path/to/drat-trim
```

The original driver accepts `--proof-checker PATH` and `--html PATH` where applicable.
The global driver stores every accepted cut with its generating assignment,
source hashes and progress, and bounds the worker process group by wall time.
Its local replay is diagnostic; original-engine replay is a separate check.
Use a separate output directory for each experiment and retain the generated
formula, manifest, model or proof artifacts, and results together.

The 48-input incumbent is a positive control: tracking its actual material
identities must yield an abstract witness. This checks implementation behavior
on that execution; it does not prove the universal projection theorem. Useful
negative controls mutate first-conversion timing, directional movement, aura
eligibility, and initial origin distinctness so the checker must reject them.

Interpret outcomes as follows:

| Outcome | Meaning |
| --- | --- |
| SAT | A relaxed schedule exists; inspect it for omitted constraints. It is neither a record nor a concrete upper bound. |
| UNSAT with a checked proof | No abstract win exists at this horizon. The concrete lower-bound consequence additionally depends on the projection argument, correct encoding, and pinned mechanics. |
| UNSAT without a checked proof | A solver report, not an independently checked computational certificate. |
| Timeout or unknown | No conclusion about feasibility or the optimum. |

Proof checking validates the generated CNF result. It does not automatically
prove the Python-to-CNF translation or the relationship to the original game.
The mathematical simulation argument, finite positive controls, and SAT proof
are separate pieces of evidence.

The main failure mode is that collision-free independent movement makes the
relaxation too permissive. A short abstract schedule exposes which constraints
are missing and is still a useful diagnostic. Any refinement must be necessary
for every concrete execution. An observed schedule, the incumbent's control
order, or a preferred freeze pattern cannot justify excluding alternatives.
Smaller CNF size alone is not a demonstrated solving speedup. No stronger lower
bound is claimed merely from constructing or running this experiment.

## Recorded pilot and remaining gap

The unrestricted 47-input transport formula has 58,452 variables and 412,763
clauses, versus 343,781 variables and 2,865,101 clauses in the compact exact
model. The transport query reached its 60-second budget without a candidate
or proof. This alone is inconclusive.

The conditional decomposition subsequently constructs a 47-input **abstract**
witness. It satisfies the symbolic relaxation with every frame pinned. It does
not win in either the local interpreter or the pinned original PuzzleScript
build. The first hero-position discrepancy in the local replay is input 26:
the abstract Druid stays at `(6,3)`, while the real Druid moves to `(6,2)`.

With the reference actions, every hero frame, and landmark frame 43 fixed,
independent token reachability plus matching takes roughly 0.01 seconds;
the same conditional question in Z3 takes roughly one second to solve, plus
model construction. This is a single matched control, not a global-search
speedup measurement. Both methods accept a feasible allocation.

The stronger capacity-flow check also accepts the reference and the constructed
47-input schedule, in under 0.1 seconds each in the recorded runs. Its witnesses
pass separate harvested-token/hero occupancy checks and the base symbolic
model. Thus removing token overlaps does not eliminate this abstract plan.
The relaxation still permits blocking and freezing choices without accounting
for all of their concrete causes. Requiring a Druid stop to be justified by
one of the nine selected tokens would be unsound: additional, unselected
material may provide the obstacle. Further refinements must preserve that
possibility while charging its actual acquisition and manipulation costs.

The [portable evidence](../../evidence/2026-11-12-transport-system/README.md)
contains these controls, the abstract witnesses, original-engine replay, and
the completed global timeout. No stronger original-game lower bound or new
record resulted. The universal-network master/cut loop is now implemented and tested; its
[implementation plan](GLOBAL_CUT_IMPLEMENTATION.md) tracks the acceptance
checks and measured execution results. Additional Foundation-0 research and
its concrete implementation transfers are recorded in
[FOUNDATION_RESEARCH.md](FOUNDATION_RESEARCH.md).

## Research inspiration and attribution

The methodological inspiration is Ahraz Arifuddin / Aska Digital and the
contributors to [Foundation-0/incentre-lattices](https://github.com/Foundation-0/incentre-lattices),
read at commit `2d374fff2a59cc9331566733043a4bb25c1040bf`. No source code was copied
from that project. Its code is MIT licensed; its text and figures are CC BY 4.0.

* [CaB6 packing proof](https://github.com/Foundation-0/incentre-lattices/blob/2d374fff2a59cc9331566733043a4bb25c1040bf/results/cab6-packing/PROOF.md):
  a few necessary non-overlap inequalities supply an upper bound, with a
  separate all-pairs argument establishing attainment. The optimization is
  scoped to the stated CaB6 structure family, not all sphere packings.
* [Continuous fcc motion proof](https://github.com/Foundation-0/incentre-lattices/blob/2d374fff2a59cc9331566733043a4bb25c1040bf/results/fold-continuous-fcc/PROOF.md):
  a uniform bound excludes all distant periodic images, leaving finitely many
  exact polynomial inequalities covering the entire parameter interval. The
  written and computational proof has internal review; it is not presented as
  proof-assistant formalization or independent specialist review.
* [Rigidity proof](https://github.com/Foundation-0/incentre-lattices/blob/2d374fff2a59cc9331566733043a4bb25c1040bf/results/rigidity-nd/PROOF.md):
  its zero modes concern infinitesimal motion. They do not imply a finite
  reachable path, an optimal path, or a sound Sokoban search reduction.

The transferable idea is to isolate a small set of necessary constraints,
justify its coverage globally, and keep feasibility witnesses separate from
optimality certificates. The transport relaxation and its projection argument
here are specific to the planning mechanics; no geometric analogy supplies
their soundness.
