"""Factored III-14 bounded model with the legacy transition as its reference.

Action selection happens before shared blocker propagation and the late phase.
This changes only the Boolean circuit representation, not the game constraints.
"""
from __future__ import annotations

import z3

from experiments.exact_frontier import iii14_smt as reference


def _select_direction(actions, values):
    """Select U/D/L/R; the unused A case takes the last directional value."""
    result = values[-1]
    for selected, value in reversed(list(zip(actions[:3], values[:3]))):
        result = z3.If(selected, value, result)
    return result


def trans(state, actions):
    """Return (next_state, legal) under exactly one of the UDLRA actions.

    Equivalence to the reference holds on arbitrary seven-component bitvector
    states; it does not require reachable-state or board-topology assumptions.
    The caller supplies the exactly-one action constraint.
    """
    if len(actions) != 5:
        raise ValueError('Expected five UDLRA action booleans')
    m = reference
    wall, crates, bard, druid, active, note, opened = state
    action = actions[4]
    directions = 'UDLR'

    def shifted(value):
        return _select_direction(actions, [m.shift(value, key) for key in directions])

    occupied = wall | crates | bard | druid | z3.If(opened, m.Z, m.BV(m.DOOR))
    target = shifted(druid)
    survives = (target & bard) == m.Z
    free = (target & occupied) == m.Z
    druid_wall = z3.If((target & wall) != m.Z, wall & ~target,
                         z3.If((target & crates) != m.Z, wall | target, wall))
    druid_crates = z3.If((target & wall) != m.Z, crates | target,
                           z3.If((target & crates) != m.Z, crates & ~target, crates))
    druid_position = z3.If(z3.And(free, target != m.Z), target, druid)

    pending = bard | note
    empty = ~occupied & m.FULL
    def reverse_jump(value, distance):
        # Compose edge-masked shifts with a single constant-distance shift.
        # Source masks prevent row wraparound, including for arbitrary states.
        variants = []
        for direction in directions:
            reverse = m.INV[direction]
            dx, dy = {'L': (-1, 0), 'R': (1, 0),
                      'U': (0, -1), 'D': (0, 1)}[reverse]
            source = sum(1 << (y * m.W + x)
                         for y in range(m.H) for x in range(m.W)
                         if 0 <= x + dx * distance < m.W
                         and 0 <= y + dy * distance < m.H)
            amount = distance * (m.W if dy else 1)
            masked = value & m.BV(source)
            variants.append(z3.LShR(masked, amount) if dx < 0 or dy < 0
                            else masked << amount)
        return _select_direction(actions, variants)

    movable = pending & reverse_jump(empty, 1)
    span = pending
    for jump in (1, 2, 4, 8):
        movable = movable | (span & reverse_jump(movable, jump))
        span = span & reverse_jump(span, jump)
    bard_moves = (movable & bard) != m.Z
    bard_position = z3.If(bard_moves, shifted(bard), bard)
    bard_crates = z3.If(bard_moves,
                        (crates & ~movable) | shifted(crates & movable), crates)
    bard_druid = z3.If(bard_moves,
                       (druid & ~movable) | shifted(druid & movable), druid)

    # The direction-dependent work is selected before this shared late phase.
    nw = z3.If(action, wall, z3.If(active, wall, druid_wall))
    nc = z3.If(action, crates, z3.If(active, bard_crates, druid_crates))
    nb = z3.If(action, bard, z3.If(active, bard_position, bard))
    nd = z3.If(action, druid, z3.If(active, bard_druid, druid_position))
    na = z3.If(action, z3.Not(active), active)
    legal = z3.Or(action, active, survives)
    cancelled = z3.And(z3.Not(action), active, nb == bard)
    notes = z3.If(na, m.area(nb) & (nc | nd), m.Z)
    newopen = ((nw | nc | nb | nd) & m.BV(m.SW)) == m.BV(m.SW)
    closing = z3.And(opened, z3.Not(newopen))
    legal = z3.And(legal, z3.Or(z3.Not(closing), ((nb | nd) & m.BV(m.DOOR)) == m.Z))
    nw = z3.If(closing, nw & ~m.BV(m.DOOR), nw)
    nc = z3.If(closing, nc & ~m.BV(m.DOOR), nc)
    notes = z3.If(closing, notes & ~m.BV(m.DOOR), notes)
    updated = (nw, nc, nb, nd, na, notes, newopen)
    return (tuple(z3.If(cancelled, old, new) for old, new in zip(state, updated)),
            z3.Or(cancelled, legal))


def build(horizon):
    """Build the complete <= horizon problem, with no search restrictions."""
    if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 0:
        raise ValueError('horizon must be a nonnegative integer')
    m = reference
    solver = z3.Solver()

    def frame(i):
        return (z3.BitVec(f'w{i}', m.N), z3.BitVec(f'c{i}', m.N),
                z3.BitVec(f'b{i}', m.N), z3.BitVec(f'd{i}', m.N),
                z3.Bool(f'a{i}'), z3.BitVec(f'n{i}', m.N), z3.Bool(f'o{i}'))

    states = [frame(i) for i in range(horizon + 1)]
    actions = [[z3.Bool(f'action_{i}_{key}') for key in 'UDLRA']
               for i in range(horizon)]
    solver.add(*[a == b for a, b in zip(states[0], m.initial())])
    for state in states:
        for hero in state[2:4]:
            solver.add(z3.PbEq([(z3.Extract(i, i, hero) == 1, 1)
                                for i in range(m.N)], 1))
    for i, selected in enumerate(actions):
        solver.add(z3.PbEq([(action, 1) for action in selected], 1))
        next_state, legal = trans(states[i], selected)
        goal = (states[i][2] | states[i][3]) == m.BV(m.GOAL)
        solver.add(z3.Implies(z3.Not(goal), z3.And(legal, *[
            a == b for a, b in zip(states[i + 1], next_state)])))
        solver.add(z3.Implies(goal, z3.And(*[
            a == b for a, b in zip(states[i + 1], states[i])])))
    solver.add((states[-1][2] | states[-1][3]) == m.BV(m.GOAL))
    return solver, actions, states
