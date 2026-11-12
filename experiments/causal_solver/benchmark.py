"""Sequential, wall-budgeted III-14 encoding/backend comparison; JSON output."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import resource
import signal
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]


def write(path, data):
    path = Path(path); temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n'); temp.replace(path)


def sources():
    paths = [ROOT / 'experiments/causal_solver' / n for n in ('benchmark.py', 'backends.py', 'encoding.py', 'events.py')]
    paths += [ROOT / 'experiments/exact_frontier' / n for n in ('iii14_compact.py', 'iii14_smt.py', 'cnf_search.py', 'iii14_problem.py')]
    paths += [ROOT / 'soko_mcp/oracle.py', ROOT / 'soko_mcp/catalog.py', ROOT / 'soko_mcp/data/catalog.json']
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.exists()}


def versions():
    result = {'python': platform.python_version()}
    for package in ('z3-solver', 'python-sat', 'ortools'):
        try: result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError: result[package] = None
    return result


def worker(spec, output):
    report = {'case': spec, 'status': 'running', 'phase': 'building', 'peak_rss_kib': 0,
              'timings': {'build_seconds': 0.0, 'compilation_seconds': 0.0,
                          'solve_seconds': 0.0, 'witness_seconds': 0.0, 'certificate_seconds': 0.0}}
    def save(phase, timings=None):
        report['phase'] = phase
        if timings: report['timings'].update(timings)
        report['peak_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        write(output, report)
    save('building')
    try:
        from experiments.causal_solver import backends
        from experiments.exact_frontier.iii14_problem import _guard_current_source
        _guard_current_source()
        if spec['encoding'] == 'compact':
            from experiments.exact_frontier import iii14_compact as encoding
        else:
            from experiments.causal_solver import encoding
        start = time.monotonic(); solver, actions, states = encoding.build(spec['horizon'])
        if spec['mode'] == 'transition':
            # Remove just the terminal goal; pinned inputs form a positive transition control.
            assertions = list(solver.assertions()); solver.reset(); solver.add(*assertions[:-1])
        for i, key in enumerate(spec['pins']): solver.add(actions[i]['UDLRA'.index(key)])
        if spec['events']:
            if spec['mode'] != 'goal': raise ValueError('event constraints require the terminal goal')
            from experiments.causal_solver.events import add_exact_constraints
            add_exact_constraints(solver, actions, states, symmetry=False)
        report['timings']['build_seconds'] = time.monotonic() - start
        report['assertions'] = len(solver.assertions())
        status, timings, extra = backends.run(solver, actions, spec['backend'], spec['pins'], save, spec['mode'])
        report.update(extra, status=status); save('finished', timings)
    except ImportError as exc:
        report.update(status='unavailable', reason=str(exc)); save('finished')
    except Exception as exc:
        report.update(status='error', reason=f'{type(exc).__name__}: {exc}'); save('finished')


def bounded(spec, budget):
    with tempfile.TemporaryDirectory(prefix='causal-bench-') as td:
        inp = Path(td) / 'input.json'; out = Path(td) / 'out.json'; log = Path(td) / 'log'
        write(inp, spec)
        cmd = [sys.executable, '-m', 'experiments.causal_solver.benchmark', '--worker', str(inp), str(out)]
        started = time.monotonic()
        with log.open('w') as stream:
            proc = subprocess.Popen(cmd, cwd=ROOT, stdout=stream, stderr=stream, start_new_session=True)
            peak = 0
            while proc.poll() is None and time.monotonic() - started < budget:
                try:
                    status = Path(f'/proc/{proc.pid}/status').read_text()
                    peak = max(peak, int(next(line for line in status.splitlines() if line.startswith('VmHWM:')).split()[1]))
                except (OSError, StopIteration): pass
                time.sleep(min(0.05, max(0, budget - (time.monotonic()-started))))
            if proc.poll() is None:
                try: os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                proc.wait()
                report = json.loads(out.read_text()) if out.exists() else {'case': spec, 'phase': 'startup'}
                report.update(status='unknown', reason='wall_timeout')
            else:
                report = json.loads(out.read_text()) if out.exists() else {'case': spec, 'status': 'error', 'reason': 'worker exited without report'}
                if proc.returncode: report.update(status='error', reason=f'worker exit {proc.returncode}', worker_log=log.read_text()[-2000:])
            report['peak_rss_kib'] = max(peak, report.get('peak_rss_kib', 0))
        report.update(wall_seconds=time.monotonic()-started, budget_seconds=budget, command=cmd[:3] + ['--worker', '<spec.json>', '<result.json>'])
        return report


def allocation(results):
    """Select only a decisive >=20% wall-time lead on the same completed case."""
    groups = {}
    for r in results:
        c = r['case']; key = (c['horizon'], c['pins'], c['mode'])
        groups.setdefault(key, []).append(r)
    choices = []
    for key, rows in sorted(groups.items()):
        choice = {'workload': {'horizon': key[0], 'pins': key[1], 'mode': key[2]}, 'decision': 'inconclusive'}
        configurations = {}
        for r in rows:
            c = r['case']; config = (c['encoding'], c['backend'], c['events'])
            configurations.setdefault(config, []).append(r)
        # Require three repetitions, matching statuses and budgets, and a clear
        # margin between the medians. Unknown/error/unavailable cannot win.
        eligible = []
        for config, repeats in configurations.items():
            if (len(repeats) >= 3 and all(r['status'] in ('sat', 'unsat') for r in repeats)
                    and len({r['status'] for r in repeats}) == 1
                    and len({r['budget_seconds'] for r in repeats}) == 1):
                eligible.append((statistics.median(r['wall_seconds'] for r in repeats), config, repeats[0]['status']))
        if (len(eligible) >= 2 and len({r['status'] for r in rows if r['status'] in ('sat', 'unsat')}) == 1
                and len({r['budget_seconds'] for r in rows}) == 1):
            ordered = sorted(eligible)
            if ordered[0][0] <= 0.8 * ordered[1][0]:
                c = ordered[0][1]; choice.update(decision='measured_winner', encoding=c[0], backend=c[1], events=c[2], median_wall_seconds=ordered[0][0])
        choices.append(choice)
    return choices


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output'); p.add_argument('--budget', type=float, default=10)
    p.add_argument('--horizons', default='0,1,2'); p.add_argument('--pins', default=None); p.add_argument('--mode', choices=('goal', 'transition'), default='goal'); p.add_argument('--backends', default='z3,pysat,cpsat')
    p.add_argument('--repetitions', type=int, default=3); p.add_argument('--encodings', default='compact,causal'); p.add_argument('--events', action='store_true')
    p.add_argument('--worker', nargs=2, metavar=('SPEC', 'OUTPUT'), help=argparse.SUPPRESS)
    args = p.parse_args()
    if args.worker:
        worker(json.loads(Path(args.worker[0]).read_text()), args.worker[1]); return
    if not args.output or not math.isfinite(args.budget) or args.budget <= 0 or args.repetitions < 1: p.error('--output and a positive --budget are required')
    horizons = [int(h) for h in args.horizons.split(',')]
    backends = args.backends.split(','); encodings = args.encodings.split(',')
    if any(h < 0 for h in horizons) or not set(backends) <= {'z3','pysat','cpsat'} or not set(encodings) <= {'compact','causal'}: p.error('invalid controls')
    if args.pins is not None:
        if any(k not in 'UDLRA' for k in args.pins) or any(len(args.pins) > h for h in horizons): p.error('invalid pins')
        controls = [{'horizon': h, 'pins': args.pins, 'mode': args.mode} for h in horizons]
    else:
        controls = [{'horizon': h, 'pins': '', 'mode': 'goal'} for h in horizons]
        controls += [{'horizon': 1, 'pins': 'A', 'mode': 'transition'}]
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True)
    report = {'schema': 'causal-benchmark-v1', 'instance': 'III-14', 'git_head': revision.stdout.strip() if revision.returncode == 0 else None,
              'command': [sys.executable, '-m', 'experiments.causal_solver.benchmark', *sys.argv[1:]], 'sources_sha256': sources(),
              'versions': versions(), 'platform': platform.platform(), 'results': []}
    write(args.output, report)
    for control in controls:
        for encoding in encodings:
            for backend in backends:
                for event in ([False, True] if args.events and control['mode'] == 'goal' else [False]):
                    spec = dict(control, encoding=encoding, backend=backend, events=event)
                    for repetition in range(args.repetitions):
                        if sources() != report['sources_sha256']:
                            report['status'] = 'source_changed'; write(args.output, report)
                            raise RuntimeError('Source changed during benchmark; comparison aborted')
                        result = bounded(spec, args.budget); result['repetition'] = repetition
                        if sources() != report['sources_sha256']:
                            result.update(status='error', reason='source_changed_during_run')
                            report['results'].append(result); report['status'] = 'source_changed'; write(args.output, report)
                            raise RuntimeError('Source changed during benchmark; comparison aborted')
                        report['results'].append(result); report['allocation'] = allocation(report['results']); write(args.output, report)
    print(json.dumps({'output': args.output, 'runs': len(report['results'])}))


if __name__ == '__main__': main()
