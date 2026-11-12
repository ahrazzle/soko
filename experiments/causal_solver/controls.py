"""Bounded, executable diagnostic controls for the full-material transition.

The constructed positions are mechanics fixtures, not claims of reachability.
Run with --html to replay the known route in the pinned original engine.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import z3

from experiments.causal_solver import encoding
from experiments.exact_frontier import iii14_problem as problem, iii14_smt as m
from experiments.transport_relaxation.diagnostic import shortened_heroes, compare_original_heroes
from soko_mcp.oracle import PuzzleScriptOracle


def transition(state, key):
    values = tuple(z3.BoolVal(x) if isinstance(x, bool) else m.BV(x) for x in state)
    result, legal = encoding.trans(values, [z3.BoolVal(key == k) for k in 'UDLRA'])
    return m.eval_state(result), z3.is_true(z3.simplify(legal))


def both_heroes_survive(oracle, alive):
    # Druid petrification may remove the inactive hero without returning a
    # corpse flag. Either missing hero makes this two-hero goal impossible.
    objects = {cell for row in oracle.obj for cell in row}
    return alive and bool(objects & {'B', '5'}) and bool(objects & {'D', '6'})


def replay(route):
    oracle = PuzzleScriptOracle(3, m.ROWS)
    state = m.eval_state(m.initial())
    for step, key in enumerate(route, 1):
        state, legal = transition(state, key)
        alive, won = oracle.step(key)
        survives = both_heroes_survive(oracle, alive)
        if legal != survives:
            raise AssertionError(f'legality mismatch at {step}')
        if not survives:
            return {'outcome': 'loss_pruned', 'step': step}
        if state != m.oracle_state(oracle):
            raise AssertionError(f'full state mismatch at {step}')
        if won:
            return {'outcome': 'won', 'step': step, 'inputs': len(route)}
    return {'outcome': 'not_won', 'step': len(route)}


def exhaustive(depth=3):
    """All prefixes through depth, stop on win/loss as in game semantics."""
    if isinstance(depth, bool) or not isinstance(depth, int) or not 0 <= depth <= 4:
        raise ValueError('depth must be an integer in 0..4')
    root = PuzzleScriptOracle(3, m.ROWS)
    frontier = [(root, m.eval_state(m.initial()))]
    counts = {'depth': depth, 'transitions': 0, 'surviving': 0,
              'loss_pruned': 0, 'wins': 0}
    for _ in range(depth):
        following = []
        for oracle, state in frontier:
            for key in 'UDLRA':
                copy = oracle.clone()
                actual, legal = transition(state, key)
                alive, won = copy.step(key)
                survives = both_heroes_survive(copy, alive)
                counts['transitions'] += 1
                if legal != survives:
                    raise AssertionError('exhaustive loss-pruning mismatch')
                if not survives:
                    counts['loss_pruned'] += 1
                    continue
                if actual != m.oracle_state(copy):
                    raise AssertionError('exhaustive full-state mismatch')
                counts['surviving'] += 1
                if won:
                    counts['wins'] += 1
                else:
                    following.append((copy, actual))
        frontier = following
    return counts


def fixture(bard=(3, 3), druid=(10, 5), active='B', objects=(), opened=False):
    """Construct an adversarial original-sized board with original floor geometry."""
    oracle = PuzzleScriptOracle(3, m.ROWS)
    for y in range(m.H):
        for x in range(m.W):
            if oracle.obj[y][x] in ('B', '5', 'D', '6', '*'):
                oracle.obj[y][x] = None
            if oracle.obj[y][x] == ']' and opened:
                oracle.obj[y][x] = None
                oracle.floor[y][x] = 'PO'
    bx, by = bard
    dx, dy = druid
    oracle.obj[by][bx] = 'B' if active == 'B' else '5'
    oracle.obj[dy][dx] = 'D' if active == 'D' else '6'
    for x, y, obj in objects:
        if oracle.obj[y][x] is not None:
            raise ValueError('fixture overlaps an object')
        oracle.obj[y][x] = obj
    oracle._compute_notes()
    return oracle


def checked_step(oracle, key):
    before = m.oracle_state(oracle)
    actual, legal = transition(before, key)
    copy = oracle.clone()
    alive, _ = copy.step(key)
    survives = both_heroes_survive(copy, alive)
    if legal != survives or (survives and actual != m.oracle_state(copy)):
        raise AssertionError('fixture disagrees with oracle')
    return before, actual, legal


def planted_errors():
    """Check concrete mutants against independently evaluated transitions."""
    cases = {}

    def record(name, correct, mutant):
        if correct == mutant:
            raise AssertionError(f'mutant not detected: {name}')
        cases[name] = {'detected': True, 'correct': correct, 'mutant': mutant}

    # A charmed crate is blocked by material unrelated to any switch assignment.
    for kind, x in (('wall', 5), ('crate', 6)):
        objects = [(4, 3, '*')]
        if kind == 'crate':
            objects.append((5, 3, '*'))
        objects.append((x, 3, '#' if kind == 'wall' else '*'))
        oracle = fixture(objects=objects)
        before, after, legal = checked_step(oracle, 'R')
        omitted = list(before)
        component = 0 if kind == 'wall' else 1
        omitted[component] &= ~(1 << (3 * m.W + x))
        mutant, mutant_legal = transition(tuple(omitted), 'R')
        if not legal or not mutant_legal:
            raise AssertionError('unexpected illegal blocker fixture')
        record('omitted_unselected_' + kind + '_changes_bard_move', after[2], mutant[2])

    for kind in ('wall', 'crate'):
        oracle = fixture(active='D', bard=(2, 2), druid=(3, 3), objects=[(4, 3, '#' if kind == 'wall' else '*')])
        before, after, legal = checked_step(oracle, 'R')
        if not legal:
            raise AssertionError('unexpected illegal conversion')
        changed = 0 if kind == 'wall' else 1
        record('druid_' + kind + '_conversion_omitted', after[changed], before[changed])

    # A blocked Bard cancels even the closing door late phase.
    oracle = fixture(objects=[(4, 3, '#')], opened=True)
    before, after, legal = checked_step(oracle, 'R')
    if not legal or after != before:
        raise AssertionError('blocked Bard did not cancel')
    record('blocked_bard_fails_to_cancel_door_closing', after[6], False)

    # Open door containing material is crushed on closing; both types covered.
    for kind in ('wall', 'crate'):
        oracle = fixture(active='D', objects=[(8, 2, '#' if kind == 'wall' else '*')], opened=True)
        before, after, legal = checked_step(oracle, 'A')
        if not legal or after[6]:
            raise AssertionError('door did not close')
        component = 0 if kind == 'wall' else 1
        record('door_does_not_crush_' + kind, after[component], after[component] | (1 << (2*m.W+8)))

    # Activating the Bard computes the full 5x5 aura, including diagonals.
    oracle = fixture(active='D', objects=[(5, 5, '*')])
    before, after, legal = checked_step(oracle, 'A')
    if not legal:
        raise AssertionError('activation unexpectedly illegal')
    record('notes_exclude_diagonal_aura', after[5], after[5] & ~(1 << (5*m.W+5)))

    oracle = fixture(active='D', druid=(3, 3), bard=(4, 3))
    _, _, legal = checked_step(oracle, 'R')
    record('druid_petrifies_bard_not_pruned', legal, True)

    try:
        problem._verify_landmark_source(problem.EXPECTED_ROWS, problem.EXPECTED_ROWS, 'corrupt')
    except ValueError:
        cases['corrupt_source_pin'] = {'detected': True}
    else:
        raise AssertionError('corrupt source pin accepted')
    return cases


def run(depth=3, html=None):
    problem._guard_current_source()
    short, heroes = shortened_heroes()
    reference = replay(m.ROUTE)
    if len(m.ROUTE) != 48 or reference['outcome'] != 'won' or reference['step'] != 48:
        raise AssertionError('known route did not win at step 48')
    short_result = replay(short)
    abstract = compare_original_heroes(short, heroes)
    if short_result['outcome'] == 'won' or abstract['winning']:
        raise AssertionError('constructed short route unexpectedly won')
    result = {'scope': 'original III-14; constructed fixtures need not be reachable',
              'reference_48': {'route': m.ROUTE, **reference},
              'constructed_47': {'route': short, 'model_oracle_replay': short_result,
                                 'abstract_hero_comparison': abstract},
              'exhaustive': exhaustive(depth), 'planted_errors': planted_errors(),
              'original_engine': {'status': 'not_requested'}}
    if html is not None:
        from soko_mcp.original import replay as original_replay
        replayed = original_replay(3, 14, m.ROUTE, html=html, timeout_sec=25)
        result['original_engine'] = {'status': 'passed' if replayed['valid_winning_route'] else 'failed',
                                     'evidence': replayed}
        if not replayed['valid_winning_route']:
            raise AssertionError('pinned original engine rejected reference route')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--html', type=Path)
    parser.add_argument('--depth', type=int, default=3)
    args = parser.parse_args()
    result = run(args.depth, args.html)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'output': str(args.output), 'exhaustive': result['exhaustive'],
                      'planted_errors_detected': len(result['planted_errors']),
                      'original_engine': result['original_engine']['status']}))


if __name__ == '__main__':
    main()
