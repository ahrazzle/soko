"""Recheck archived causal-search cuts and optional original replay, without search."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from experiments.causal_solver import master, refinement
from experiments.transport_relaxation import cut_certificate, universal_flow


def require(test, message):
    if not test:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--html', type=Path, help='Optionally repeat pinned original-engine replay')
    parser.add_argument('--chromium')
    args = parser.parse_args()
    summary = []
    paths = sorted(HERE.glob('*-search.json.gz'))
    archives = json.loads((HERE / 'archives.json').read_text())
    require(bool(paths), 'missing search artifacts')
    for path in paths:
        result = json.loads(gzip.decompress(path.read_bytes()))
        before = result['source_hashes_before']
        require(before == result['source_hashes_after'], 'source changed during archived run')
        for name, expected in before.items():
            snapshot = subprocess.check_output(['git', 'show', f'{archives[path.name]}:{name}'], cwd=ROOT)
            require(hashlib.sha256(snapshot).hexdigest() == expected,
                    f'archived source differs: {name}')
        assignments = [item['assignment'] for item in result['candidates']]
        for assignment in assignments:
            master.validate_assignment(assignment, result['horizon'])
        graph = universal_flow.build_universe(result['horizon'])
        identity = cut_certificate.check_universe_spec(graph)
        require(identity == result['universe_sha256'], 'universe identity differs')
        exact_count = flow_count = 0
        for cut in result['cuts']:
            certificate = cut['certificate']
            if cut['kind'] == 'exact':
                metadata = certificate['metadata']
                refiner = refinement.ExactRefiner(metadata['horizon'], metadata['encoding'])
                checked = refiner.check_certificate(certificate, timeout_seconds=30)
                require(checked.get('verified') is True, 'exact contradiction did not recheck')
                exact_count += 1
            elif cut['kind'] == 'flow':
                matches = [a for a in assignments
                           if cut_certificate._assignment(graph, a)[1] == certificate['assignment_sha256']]
                require(bool(matches), 'missing generating flow assignment')
                cut_certificate.check_cut_certificate(graph, matches[0], certificate)
                flow_count += 1
            else:
                raise ValueError('unknown archived cut kind')
        replayed = 0
        for item in result['candidates']:
            if item.get('flow_value') == 9:
                checked = master.evaluate_flow(graph, item['assignment'])
                require(checked['flow_value'] == 9, 'reference flow rejected')
            certificate = item.get('original_replay')
            if args.html and certificate and certificate.get('valid_winning_route'):
                from soko_mcp.original import replay
                checked = replay(3, 14, item['local_replay']['route'], html=args.html,
                                 chromium=args.chromium)
                require(checked['valid_winning_route'], 'original engine rejected route')
                replayed += 1
        summary.append({'artifact': path.name, 'archived_status': result['status'],
                        'candidates_validated': len(assignments), 'exact_cuts_rechecked': exact_count,
                        'flow_cuts_rechecked': flow_count, 'original_replays_repeated': replayed,
                        'new_record_claim': False})
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
