"""Compare two frozen checkouts sequentially; retain all worker artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pretty-checkout', type=Path, required=True)
    p.add_argument('--compact-checkout', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    roots = {'pretty': args.pretty_checkout.resolve(), 'compact': args.compact_checkout.resolve()}
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        p.error('use a new or empty output directory')
    output.mkdir(parents=True, exist_ok=True)
    report = {'command': [sys.executable, *sys.argv], 'budget_seconds': 15,
              'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'git_heads': {k: subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=v, text=True).strip()
                            for k, v in roots.items()}, 'runs': []}
    for repeat in range(3):
        for mode in (('pretty', 'compact') if repeat % 2 == 0 else ('compact', 'pretty')):
            target = output / f'{mode}-{repeat + 1}.json'
            command = [sys.executable, '-m', 'experiments.causal_solver.search', '--horizon', '47',
                       '--budget-seconds', '15', '--output', str(target)]
            with target.with_suffix('.log').open('w') as log:
                proc = subprocess.run(command, cwd=roots[mode], stdout=log, stderr=log)
            if proc.returncode:
                raise RuntimeError(f'{mode} worker failed: {proc.returncode}')
            result = json.loads(target.read_text())
            if result['source_hashes_before'] != result['source_hashes_after']:
                raise RuntimeError('source changed during run')
            depths = [c['exact']['frame'] for c in result['candidates']
                      if c.get('exact', {}).get('status') == 'unsat']
            report['runs'].append({'artifact': target.name, 'mode': mode, 'command': command,
                'status': result['status'], 'record_claim': result['record_claim'],
                'candidates': len(result['candidates']), 'checked_cuts': len(result['cuts']),
                'median_rejected_depth': statistics.median(depths) if depths else None,
                'maximum_rejected_depth': max(depths) if depths else None,
                'elapsed_seconds': result['elapsed_seconds'], 'bytes': target.stat().st_size})
            (output / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps(report['runs'][-1]), flush=True)
            if result['status'] != 'unknown':
                return
    common = []
    for repeat in range(1, 4):
        pretty = json.loads((output / f'pretty-{repeat}.json').read_text())
        compact = json.loads((output / f'compact-{repeat}.json').read_text())
        count = min(len(pretty['candidates']), len(compact['candidates']))
        same = all(a['assignment'] == b['assignment'] for a, b in
                   zip(pretty['candidates'][:count], compact['candidates'][:count]))
        changed = sorted(k for k in set(pretty['source_hashes_before']) | set(compact['source_hashes_before'])
                         if pretty['source_hashes_before'].get(k) != compact['source_hashes_before'].get(k))
        common.append({'pair': repeat, 'candidate_prefix_length': count, 'identical': same,
                       'differing_sources': changed})
    report['common_prefixes'] = common
    (output / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
