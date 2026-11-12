"""Fixed-hero token-capacity flow controls, not a record attempt.

The two schedules are the existing reference route and the single constructed
47-input abstraction example. The latter is assessed under one fixed hero path;
its infeasibility cannot rule out other trajectories or schedules.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import time

from experiments.transport_relaxation.diagnostic import (
    baseline_heroes, check_witness, compare_original_heroes, hero_mappings,
    possible_landmarks, shortened_heroes,
)

ROOT = Path(__file__).resolve().parents[2]


def provenance():
    sources = ('experiments/transport_relaxation/model.py',
               'experiments/transport_relaxation/project.py',
               'experiments/transport_relaxation/diagnostic.py',
               'experiments/transport_relaxation/allocation.py',
               'experiments/transport_relaxation/flow_allocation.py',
               'experiments/transport_relaxation/flow_diagnostic.py',
               'experiments/exact_frontier/iii14_smt.py',
               'experiments/exact_frontier/iii14_problem.py', 'soko_mcp/oracle.py',
               'soko_mcp/data/catalog.json')
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in sources}


def check_capacity(result):
    """Independently check harvested token and hero vertex occupancy through landmark."""
    for t, frame in enumerate(result['frames'][:result['landmark_frame'] + 1]):
        harvested = [(x, y) for x, y, flag in zip(frame['token_x'], frame['token_y'],
                                                   frame['harvested']) if flag]
        if len(harvested) != len(set(harvested)):
            raise ValueError(f'two harvested tokens share a cell at frame {t}')
        heroes = {(frame['bard_x'], frame['bard_y']), (frame['druid_x'], frame['druid_y'])}
        if heroes.intersection(harvested):
            raise ValueError(f'hero and harvested token share a cell at frame {t}')
    return True


def timed_flow(route, heroes, landmark):
    from experiments.transport_relaxation import flow_allocation
    started = time.perf_counter()
    result = flow_allocation.allocate_flow(route, hero_mappings(heroes), landmark)
    elapsed = time.perf_counter() - started
    if result['status'] not in ('feasible', 'infeasible'):
        raise ValueError(f'flow could not assess landmark {landmark}: {result}')
    summary = {'landmark_frame': landmark, 'status': result['status'],
               'flow_value': result['flow_value'], 'flow_seconds': elapsed}
    if result['status'] == 'feasible':
        started = time.perf_counter()
        summary['capacity_check'] = check_capacity(result)
        summary['pinned_model_check'] = check_witness(route, result)
        summary['witness_check_seconds'] = time.perf_counter() - started
        summary['witness'] = result
    else:
        summary['min_cut'] = result['min_cut']
    return summary


def run():
    original, original_heroes = baseline_heroes()
    baseline = timed_flow(original, original_heroes, 43)
    if baseline['status'] != 'feasible':
        raise ValueError('reference projection unexpectedly rejected by flow')
    short, short_heroes = shortened_heroes()
    alternate = timed_flow(short, short_heroes, 42)
    others = []
    if alternate['status'] == 'infeasible':
        for t in possible_landmarks(short, short_heroes):
            if t != 42:
                others.append(timed_flow(short, short_heroes, t))
    return {
        'scope': ('Two fixed action schedules and fixed hero trajectories. Flow failure '
                  'is conditional on those choices and the landmark frame.'),
        'soundness_boundary': ('Necessary vertex capacities through landmark, with material '
                               'before harvest and after landmark relaxed; source mechanics '
                               'and model mapping are not formally proved.'),
        'record_claim': False,
        'source_sha256': provenance(),
        'baseline_48_frame_43': baseline,
        'constructed_47_frame_42': alternate,
        'constructed_47_other_landmarks': others,
        'constructed_47_original_replay': compare_original_heroes(short, short_heroes),
    }


if __name__ == '__main__':
    import json
    print(json.dumps(run(), indent=2))
