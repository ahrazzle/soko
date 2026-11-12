#!/usr/bin/env python3
"""Compare III-14 construction/CNF costs in isolated, bounded processes.

Example: python experiments/exact_frontier/compare_encodings.py --output /tmp/cnf-comparison
This performs no SAT search. Outputs are measurements, not solvability claims.
Each output directory must be new or empty; interrupted runs are not resumed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import resource
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ENCODINGS = ('compact', 'legacy')


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def provenance():
    # Include all local experiment modules so new encoder dependencies are covered.
    sources = sorted((ROOT / 'experiments/exact_frontier').glob('*.py'))
    sources += [ROOT / 'soko_mcp/oracle.py', ROOT / 'soko_mcp/data/catalog.json']
    versions = {'python': sys.version, 'platform': platform.platform(),
                'executable': sys.executable}
    for distribution in ('z3-solver', 'python-sat'):
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = None
    return {'source_sha256': {str(p.relative_to(ROOT)): digest(p) for p in sources},
            'versions': versions}


def peak_rss_bytes():
    # Linux reports KiB; macOS reports bytes.
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == 'darwin' else value * 1024)


def worker(args):
    out = args.output
    began = time.monotonic()
    report = dict(provenance(), encoding=args.encoding, horizon=args.horizons[0],
                  status='importing', proof_claim=None, sat_search_performed=False,
                  timing_clock='time.perf_counter', keep_cnf=args.keep_cnf)

    def save(**updates):
        report.update(updates, elapsed_seconds=time.monotonic() - began,
                      peak_rss_bytes=peak_rss_bytes())
        atomic_json(out / 'progress.json', report)

    save()
    try:
        from experiments.exact_frontier.iii14_problem import build_problem
        from experiments.exact_frontier.cnf_search import compile_cnf
        import z3
        report['versions']['z3_runtime'] = z3.get_version_string()
        save(status='building')
        started = time.perf_counter()
        solver, actions, states = build_problem(args.horizons[0], encoding=args.encoding)
        build_seconds = time.perf_counter() - started
        save(status='compiling', build_seconds=build_seconds,
             assertions=len(solver.assertions()), action_steps=len(actions),
             state_frames=len(states))
        started = time.perf_counter()
        dimacs, aliases = compile_cnf(solver)
        compile_seconds = time.perf_counter() - started
        save(status='measuring', compile_seconds=compile_seconds)
        match = re.search(r'^p cnf (\d+) (\d+)\s*$', dimacs, re.M)
        if match is None:
            raise ValueError('Compiler output has no DIMACS header')
        cnf_bytes = dimacs.encode('utf-8')
        report.update(cnf_variables=int(match[1]), cnf_clauses=int(match[2]),
                      cnf_bytes=len(cnf_bytes), cnf_sha256=hashlib.sha256(cnf_bytes).hexdigest(),
                      action_aliases=len(aliases))
        # Simplification can remove actions, especially at inconsistent short horizons.
        report['expected_action_aliases'] = args.horizons[0] * 5
        if args.keep_cnf:
            temporary = out / 'problem.cnf.tmp'
            temporary.write_bytes(cnf_bytes)
            temporary.replace(out / 'problem.cnf')
            atomic_json(out / 'action_aliases.json', aliases)
        save(status='complete')
        return 0
    except Exception as exc:
        save(status='error', error_type=type(exc).__name__, error=str(exc))
        traceback.print_exc()
        return 1


def process_peak_rss_bytes(pid):
    """Best-effort Linux high-water sample, including for a killed worker."""
    try:
        match = re.search(r'^VmHWM:\s+(\d+) kB$',
                          Path(f'/proc/{pid}/status').read_text(), re.M)
        return int(match[1]) * 1024 if match else None
    except (OSError, ProcessLookupError):
        return None


def run_one(args, encoding, horizon):
    out = args.output / f'horizon_{horizon}' / encoding
    out.mkdir(parents=True)
    command = [sys.executable, str(Path(__file__).resolve()), '--worker',
               '--encoding', encoding, '--horizons', str(horizon), '--output', str(out)]
    if args.keep_cnf:
        command.append('--keep-cnf')
    began = time.monotonic()
    sampled_peak = None
    timed_out = False
    with (out / 'stdout.log').open('wb') as stdout, (out / 'stderr.log').open('wb') as stderr:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr)
        while process.poll() is None:
            sample = process_peak_rss_bytes(process.pid)
            if sample is not None:
                sampled_peak = max(sampled_peak or 0, sample)
            if time.monotonic() - began >= args.wall_timeout_seconds:
                timed_out = True
                process.kill()
                break
            time.sleep(0.05)
        returncode = process.wait()
    progress_path = out / 'progress.json'
    report = json.loads(progress_path.read_text()) if progress_path.exists() else {
        'encoding': encoding, 'horizon': horizon, 'status': 'starting',
        'proof_claim': None, 'sat_search_performed': False}
    report.update(worker_returncode=returncode, subprocess_wall_seconds=time.monotonic() - began,
                  wall_budget_seconds=args.wall_timeout_seconds,
                  sampled_peak_rss_bytes=sampled_peak,
                  command=command, result_path=str((out / 'result.json').relative_to(args.output)))
    if timed_out:
        report.update(last_stage=report['status'], status='timeout', reason='wall_timeout')
    elif returncode or report.get('status') != 'complete':
        report.update(last_stage=report['status'], status='error',
                      reason=report.get('error', f'Worker exited with status {returncode}'))
    # A killed worker's exact peak may exceed the last /proc sample. Label it honestly.
    report['peak_rss_measurement'] = ('worker_ru_maxrss' if report['status'] == 'complete'
                                      else 'last_worker_checkpoint_and_parent_proc_samples')
    atomic_json(out / 'result.json', report)
    return report


def compare(args):
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f'Refusing nonempty output directory: {args.output}')
    args.output.mkdir(parents=True, exist_ok=True)
    initial_provenance = provenance()
    summary = dict(initial_provenance, schema_version=1, status='running',
                   horizons=args.horizons, encodings=list(ENCODINGS), results=[], ratios={},
                   wall_budget_seconds_per_worker=args.wall_timeout_seconds,
                   proof_claim=None, sat_search_performed=False,
                   ratio_definition='compact / legacy; values below 1 mean smaller compact cost')
    atomic_json(args.output / 'progress.json', summary)
    for horizon in args.horizons:
        pair = {}
        for encoding in ENCODINGS:
            summary['current'] = {'horizon': horizon, 'encoding': encoding}
            atomic_json(args.output / 'progress.json', summary)
            result = run_one(args, encoding, horizon)
            summary['results'].append(result)
            pair[encoding] = result
            atomic_json(args.output / 'progress.json', summary)
            print(f'horizon={horizon} encoding={encoding} status={result["status"]}', flush=True)
        if all(pair[e]['status'] == 'complete' for e in ENCODINGS):
            if pair['compact']['source_sha256'] == pair['legacy']['source_sha256']:
                summary['ratios'][str(horizon)] = {
                    metric: pair['compact'][metric] / pair['legacy'][metric]
                    for metric in ('build_seconds', 'compile_seconds', 'cnf_variables',
                                   'cnf_clauses', 'cnf_bytes', 'peak_rss_bytes')
                    if pair['legacy'][metric] > 0}
            else:
                summary.setdefault('comparison_errors', []).append(
                    f'Source files changed between workers for horizon {horizon}; ratios omitted')
    summary.pop('current', None)
    summary['status'] = ('complete' if all(r['status'] == 'complete' for r in summary['results'])
                         and not summary.get('comparison_errors') else 'incomplete')
    atomic_json(args.output / 'summary.json', summary)
    atomic_json(args.output / 'progress.json', summary)
    return 0 if summary['status'] == 'complete' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--horizons', type=int, nargs='+', default=[8, 47])
    parser.add_argument('--wall-timeout-seconds', type=float, default=180)
    parser.add_argument('--keep-cnf', action='store_true')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--encoding', choices=ENCODINGS, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if any(h < 0 for h in args.horizons) or len(set(args.horizons)) != len(args.horizons):
        parser.error('horizons must be distinct nonnegative integers')
    if not math.isfinite(args.wall_timeout_seconds) or args.wall_timeout_seconds <= 0:
        parser.error('wall timeout must be positive and finite')
    args.output = args.output.resolve()
    if args.worker and (args.encoding is None or len(args.horizons) != 1):
        parser.error('worker requires one horizon and an encoding')
    return worker(args) if args.worker else compare(args)


if __name__ == '__main__':
    raise SystemExit(main())
