"""Recheck archived global cuts/witnesses without rerunning optimization.

Run from any directory in a Git clone containing the pinned source commit.
Optional --proof-checker independently rechecks the archived H=1 CNF proof.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from experiments.transport_relaxation import cut_certificate as checker, universal_flow


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proof-checker', type=Path)
    args = parser.parse_args()
    reports = []
    for path in sorted(HERE.glob('*-bundle.json.gz')):
        bundle = json.loads(gzip.decompress(path.read_bytes()))
        files = bundle['files']
        result = json.loads(files['result.json'])
        commit = bundle['source_commit']
        for name, expected in result['source_sha256'].items():
            archived = subprocess.check_output(['git', 'show', f'{commit}:{name}'], cwd=ROOT)
            require(digest(archived) == expected, f'pinned source changed: {name}')
            # Driver-only CLI fixes after the archived run do not affect replay.
            if not name.endswith('/global_search.py'):
                require(digest((ROOT / name).read_bytes()) == expected,
                        f'current verification dependency changed: {name}')
        graph = universal_flow.build_universe(result['horizon'])
        identity = checker.check_universe_spec(graph)
        require(identity == result['universe_sha256'], 'universe hash mismatch')
        accepted = json.loads(files.get('accepted-cuts.json', '[]'))
        require(len(accepted) == result['cuts_checked'], 'accepted-cut count mismatch')
        for item in accepted:
            prefix = f"iterations/{item['iteration']:04d}/"
            raw = files[prefix + 'cut.json']
            require(digest(raw.encode()) == item['sha256'], 'cut hash mismatch')
            assignment = json.loads(files[prefix + 'assignment.json'])
            checker.check_cut_certificate(graph, assignment, json.loads(raw))
        checked_witness = False
        if result.get('flow_witness_checked'):
            raw = files['witness.json']
            require(digest(raw.encode()) == result['witness_sha256'], 'witness hash mismatch')
            witness = json.loads(raw)
            # The flow checker checks capacities; this separately validates heroes.
            evaluation = universal_flow.evaluate_flow(graph, witness['assignment'])
            require(evaluation['flow_value'] == 9, 'hero/flow validation failed')
            checker.check_flow_witness(graph, witness['assignment'], witness['flow_edge_paths'])
            checked_witness = True
        proof_checked = False
        if result.get('unsat_certificate'):
            certificate = result['unsat_certificate']
            cnf = files['final-master.cnf'].encode()
            proof = files['unsat-certificate/proof.drat'].encode()
            require(digest(cnf) == certificate['cnf_sha256'], 'CNF hash mismatch')
            require(digest(proof) == certificate['proof_sha256'], 'proof hash mismatch')
            if args.proof_checker:
                executable = args.proof_checker.resolve()
                require(digest(executable.read_bytes()) == certificate['checker_sha256'],
                        'proof checker differs from archived executable')
                with tempfile.TemporaryDirectory() as directory:
                    directory = Path(directory)
                    (directory / 'input.cnf').write_bytes(cnf)
                    (directory / 'proof.drat').write_bytes(proof)
                    replay = subprocess.run([str(executable), str(directory / 'input.cnf'),
                                             str(directory / 'proof.drat')],
                                            capture_output=True, text=True, timeout=30)
                    require(replay.returncode == 0 and 's VERIFIED' in replay.stdout,
                            'archived proof rejected')
                    proof_checked = True
        reports.append({'bundle': path.name, 'cuts_checked': len(accepted),
                        'flow_witness_checked': checked_witness,
                        'cnf_proof_rechecked': proof_checked,
                        'record_claim': False})
    print(json.dumps(reports, indent=2))


if __name__ == '__main__':
    main()
