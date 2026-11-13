"""Counterbalanced, equal-budget comparison of checked prefix learning.

Each run is a separate hard-bounded worker, executed sequentially. The driver
retains complete checkpoints and sources. Unknown results and deeper rejected
prefixes do not establish proof coverage, optimality, or a record.
"""
import argparse
import collections
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

from experiments.causal_solver import search


def summarize(result):
    exact = [row.get('exact', {}) for row in result.get('candidates', [])]
    depths = [row['frame'] for row in exact if row.get('status') == 'unsat' and 'frame' in row]
    facts = [row.get('exact_verification', {}) for row in result.get('candidates', [])]
    phases = collections.Counter()
    for row in result.get('phases', []):
        phases[row['name']] += row['seconds']
    return {'status': result['status'], 'reason': result.get('reason'),
            'record_claim': result.get('record_claim', False),
            'candidates': len(result.get('candidates', [])),
            'cuts_by_kind': dict(collections.Counter(row['kind'] for row in result.get('cuts', []))),
            'elapsed_seconds': result.get('elapsed_seconds'),
            'rejected_prefix_depth': {'count': len(depths),
                                      'median': statistics.median(depths) if depths else None,
                                      'maximum': max(depths) if depths else None},
            'prefix_frames_learned': sum(row.get('prefix_frames_learned', 0) for row in facts),
            'phase_seconds': dict(phases), 'interrupted_phase': result.get('active_phase'),
            'interrupted_phase_seconds': result.get('interrupted_phase_seconds')}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--budget-seconds', type=float, default=30)
    p.add_argument('--repetitions', type=int, default=3)
    args = p.parse_args()
    if args.repetitions < 1:
        p.error('repetitions must be positive')
    if not math.isfinite(args.budget_seconds) or args.budget_seconds <= 0:
        p.error('budget must be positive and finite')
    if args.output.exists() and any(args.output.iterdir()):
        p.error('use a new or empty output directory')
    args.output.mkdir(parents=True, exist_ok=True)
    sources = search.source_hashes()
    report = {'command': [sys.executable, '-m', 'experiments.causal_solver.compare_prefix_learning', *sys.argv[1:]],
              'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=search.ROOT, text=True).strip(),
              'source_hashes': sources, 'budget_seconds': args.budget_seconds,
              'repetitions': args.repetitions, 'runs': [],
              'limitations': 'Named phase timings include some checkpoint overhead. Counts and rejected depths are diagnostics, not proof coverage or a record.'}
    search._save(args.output / 'summary.json', report)
    for repetition in range(args.repetitions):
        for learn in ((False, True) if repetition % 2 == 0 else (True, False)):
            if search.source_hashes() != sources:
                raise RuntimeError('sources changed during comparison')
            name = f"{'prefix' if learn else 'baseline'}-{repetition + 1}.json"
            options = {'horizon': 47, 'budget_seconds': args.budget_seconds,
                       'phase_order': 'exact-first', 'use_events': False,
                       'symmetry': False, 'cut_selection': 'source_minimal',
                       'learn_prefix_frames': learn}
            result = search.run_bounded(options, args.output / name)
            if search.source_hashes() != sources:
                raise RuntimeError('sources changed during comparison')
            row = {'artifact': name, 'options': options, **summarize(result)}
            report['runs'].append(row)
            search._save(args.output / 'summary.json', report)
            print(json.dumps(row), flush=True)
            if result['status'] in ('original_verified_win', 'source_mutation_error', 'error'):
                return


if __name__ == '__main__':
    main()
