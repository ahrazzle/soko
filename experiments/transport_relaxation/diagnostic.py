"""Two fixed-schedule allocation diagnostics, never a record-search loop.

The shorter schedule is one constructed modification of the reference route.
A polynomial dynamic program fills only the Druid path, with the Bard path
fixed. Token feasibility is then delegated to the fixed-hero allocation oracle.
"""
from __future__ import annotations

from dataclasses import dataclass

from experiments.transport_relaxation.project import H, W, ROWS, project, oracle_state, _point
from soko_mcp.oracle import DIRS, PuzzleScriptOracle

SHORT_PREFIX = 'LLULULULURURURURU'
REFERENCE_PREFIX_LENGTH = 18


@dataclass(frozen=True)
class HeroFrame:
    bard: tuple[int, int]
    druid: tuple[int, int]
    active: bool


def baseline_heroes():
    p = project()
    return p.route, tuple(HeroFrame((f.bard_x, f.bard_y),
                                    (f.druid_x, f.druid_y), f.active) for f in p.frames)


def shortened_heroes():
    """Build the one 47-input schedule and its fixed-Bard Druid trajectory.

    The 17-input prefix is replayed concretely. For the remaining fixed keys,
    DP keeps one minimum-deviation path per Druid cell and requires the second
    goal at the end. This optimizes only the path in this single fixed schedule;
    it does not enumerate action schedules or claim completeness across paths.
    """
    baseline = project()
    route = SHORT_PREFIX + baseline.route[REFERENCE_PREFIX_LENGTH:]
    oracle = PuzzleScriptOracle(3, ROWS)
    prefix = []

    def current():
        _, _, bard, druid, active, _, _ = oracle_state(oracle)
        return HeroFrame(_point(bard), _point(druid), bool(active))

    prefix.append(current())
    for key in SHORT_PREFIX:
        alive, won = oracle.step(key)
        if not alive or won:
            raise ValueError('unexpected prefix outcome')
        prefix.append(current())
    if prefix[-1] != HeroFrame((2, 2), (5, 1), False):
        raise ValueError('short prefix does not reach the constructed state')
    offset = REFERENCE_PREFIX_LENGTH - len(SHORT_PREFIX)
    suffix_heros = baseline.frames[REFERENCE_PREFIX_LENGTH:]
    frontier = {prefix[-1].druid: (0, None)}
    layers = [frontier]
    for t, key in enumerate(route[len(SHORT_PREFIX):], start=len(SHORT_PREFIX)):
        a, b = baseline.frames[t + offset:t + offset + 2]
        old_bard, new_bard = (a.bard_x, a.bard_y), (b.bard_x, b.bard_y)
        dx, dy = DIRS.get(key, (0, 0))
        nxt = {}
        for (x, y), (cost, _) in sorted(frontier.items()):
            choices = [(x, y)]
            if key != 'A' and (not a.active or (
                    old_bard != new_bard and max(abs(x - old_bard[0]), abs(y - old_bard[1])) <= 2)):
                choices.append((x + dx, y + dy))
            for nx, ny in choices:
                if not (0 <= nx < W and 0 <= ny < H):
                    continue
                score = cost + abs(nx - b.druid_x) + abs(ny - b.druid_y)
                if (nx, ny) not in nxt or score < nxt[nx, ny][0]:
                    nxt[nx, ny] = (score, (x, y))
        if not nxt:
            raise ValueError(f'no Druid path through frame {t + 1}')
        frontier = nxt
        layers.append(nxt)
    final_bard = (baseline.frames[-1].bard_x, baseline.frames[-1].bard_y)
    goals = {(9, 3), (11, 3)}
    if final_bard not in goals:
        raise ValueError('reference Bard did not finish on a goal')
    final_druid = next(iter(goals - {final_bard}))
    if final_druid not in frontier:
        raise ValueError('no Druid trajectory to the other goal for this schedule')
    path = [final_druid]
    for layer in reversed(layers[1:]):
        path.append(layer[path[-1]][1])
    path.reverse()
    frames = list(prefix)
    for i, pos in enumerate(path[1:], start=1):
        old = suffix_heros[i]
        frames.append(HeroFrame((old.bard_x, old.bard_y), pos, old.active))
    if len(route) != 47 or len(frames) != len(route) + 1:
        raise AssertionError('constructed schedule length mismatch')
    return route, tuple(frames)


def hero_mappings(frames):
    return tuple({'bard_x': frame.bard[0], 'bard_y': frame.bard[1],
                  'druid_x': frame.druid[0], 'druid_y': frame.druid[1],
                  'active': frame.active} for frame in frames)


def possible_landmarks(route, frames):
    """Return all frames with at least nine distinct earlier harvest opportunities.

    This cheap necessary check excludes earlier frames; it does not claim the
    resulting opportunities can all be used or that tokens can reach switches.
    """
    from experiments.transport_relaxation.model import BORDER
    border = set(BORDER)
    origins = set()
    result = []
    for t, key in enumerate(route):
        old, new = frames[t:t + 2]
        if key != 'A' and not old.active and old.druid == new.druid:
            dx, dy = DIRS[key]
            q = old.druid[0] + dx, old.druid[1] + dy
            if q in border:
                origins.add(q)
        if len(origins) >= 9:
            result.append(t + 1)
    return tuple(result)


def compare_baseline(timeout_ms=10000):
    """Compare two checks for the same fixed route and hero trajectory."""
    import time
    import z3
    from experiments.transport_relaxation import allocation, model

    route, heroes = baseline_heroes()
    started = time.perf_counter()
    assigned = allocation.allocate(route, hero_mappings(heroes), 43)
    allocation_seconds = time.perf_counter() - started
    if assigned['status'] != 'feasible':
        raise ValueError(f'baseline allocation failed: {assigned}')
    started = time.perf_counter()
    solver, actions, frames = model.build_problem(len(route))
    build_seconds = time.perf_counter() - started
    started = time.perf_counter()
    for row, key in zip(actions, route):
        solver.add(row['UDLRA'.index(key)])
    for frame, values in zip(frames, hero_mappings(heroes)):
        solver.add(*model.frame_constraints(frame, values))
    solver.add(model.at_landmark(frames[43]))
    setup_seconds = time.perf_counter() - started
    solver.set(timeout=timeout_ms)
    started = time.perf_counter()
    status = solver.check()
    solve_seconds = time.perf_counter() - started
    reason = solver.reason_unknown() if status == z3.unknown else None
    # A fully pinned assignment is a separate correctness control.
    for frame, values in zip(frames, assigned['frames']):
        solver.add(*model.frame_constraints(frame, values))
    started = time.perf_counter()
    witness_status = solver.check()
    witness_seconds = time.perf_counter() - started
    return {
        'scope': 'reference route and every hero frame fixed, landmark at frame 43; tokens otherwise unconstrained',
        'allocation_status': assigned['status'], 'allocation_seconds': allocation_seconds,
        'z3_build_seconds': build_seconds, 'z3_setup_seconds': setup_seconds,
        'z3_solve_seconds': solve_seconds,
        'z3_status': str(status), 'z3_reason': reason, 'z3_timeout_ms': timeout_ms,
        'pinned_allocation_status': str(witness_status),
        'pinned_allocation_seconds': witness_seconds,
        'landmark_frame': assigned['landmark_frame'],
    }


def compare_original_heroes(route, heroes):
    """Locate the first mismatch against the local original-game interpreter."""
    oracle = PuzzleScriptOracle(3, ROWS)
    mismatch = None
    for i, key in enumerate(route):
        alive, won = oracle.step(key)
        if not alive:
            return {'winning': False, 'reason': 'hero_lost', 'input': i + 1,
                    'first_hero_mismatch': mismatch}
        state = oracle_state(oracle)
        actual = HeroFrame(_point(state[2]), _point(state[3]), bool(state[4]))
        if mismatch is None and actual != heroes[i + 1]:
            mismatch = {'frame': i + 1, 'key': key,
                        'expected_abstract': heroes[i + 1].__dict__, 'original': actual.__dict__}
        if won:
            return {'winning': True, 'first_win': i + 1, 'first_hero_mismatch': mismatch}
    return {'winning': False, 'reason': 'not_won', 'first_hero_mismatch': mismatch,
            'final_board': oracle.render_ascii()}


def check_witness(route, result):
    """Pin a complete allocation witness to the symbolic relaxation."""
    from dataclasses import fields
    import z3
    from experiments.transport_relaxation import model
    from experiments.transport_relaxation.project import Projection, ProjectionFrame, pin_projection
    rows = []
    for values in result['frames']:
        normal = {field.name: values[field.name] for field in fields(ProjectionFrame)}
        for key in ('token_x', 'token_y', 'harvested'):
            normal[key] = tuple(normal[key])
        rows.append(ProjectionFrame(**normal))
    projection = Projection(route, tuple(tuple(p) for p in result['origins']),
                            result['first_landmark_frame'], tuple(rows))
    solver, actions, frames = model.build_problem(len(route))
    pin_projection(solver, actions, frames, projection)
    solver.set(timeout=10000)
    status = solver.check()
    return {'status': str(status), 'reason': solver.reason_unknown() if status == z3.unknown else None}


def diagnose_short():
    """Evaluate every possible common landmark for the one constructed schedule."""
    from experiments.transport_relaxation import allocation
    route, heroes = shortened_heroes()
    possible = possible_landmarks(route, heroes)
    order = ([42] if 42 in possible else []) + [t for t in possible if t != 42]
    checks, witness = [], None
    for t in order:
        result = allocation.allocate(route, hero_mappings(heroes), t)
        if result['status'] not in ('feasible', 'infeasible'):
            raise ValueError(f'allocator could not check landmark {t}: {result}')
        checks.append({k: result[k] for k in ('landmark_frame', 'status', 'matching_size', 'hall_obstruction')
                       if k in result})
        if result['status'] == 'feasible' and witness is None:
            witness = result
    report = {'route': route, 'horizon': len(route),
              'scope': 'one constructed action schedule and one fixed hero trajectory',
              'record_claim': False, 'possible_landmarks': list(possible),
              'landmark_checks': checks, 'original_replay': compare_original_heroes(route, heroes)}
    if witness is not None:
        report['abstract_witness'] = witness
        report['pinned_model_check'] = check_witness(route, witness)
    return report


if __name__ == '__main__':
    import json
    print(json.dumps({'baseline_comparison': compare_baseline(),
                      'constructed_47': diagnose_short()}, indent=2))
