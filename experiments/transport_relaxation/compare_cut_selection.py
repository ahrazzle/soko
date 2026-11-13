"""Compare residual cut extrema on retained assignments, without search.

Run from the repository root:
    python -m experiments.transport_relaxation.compare_cut_selection --output /tmp/cut-comparison.json

Select the first 12 distinct, valid, flow-deficient assignments in archive
order from the causal search, then the older global-cut bundle if necessary.
The result contains complete assignments and independently checked deficient
cut certificates. The retained reference48 assignment is a positive control;
its independent path witness and full reconstructed boundary certify flow 9.
Counts group exact (kind, params) pairs, as global_master.add_cut does; 'one'
is the sole constant kind. These are structural predicate counts, not counts
of simplified Z3 expressions. There is no timing or record-search claim.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from experiments.causal_solver import master
from experiments.transport_relaxation import cut_certificate, universal_flow

ROOT = Path(__file__).resolve().parents[2]
CAUSAL = 'evidence/2026-11-12-causal-tractability/global47-selected-search.json.gz'
GLOBAL = 'evidence/2026-11-12-global-cuts/global47-bundle.json.gz'
REFERENCE = 'evidence/2026-11-12-global-cuts/reference48-bundle.json.gz'
MODES = ('source_minimal', 'sink_minimal')
SAMPLE_SIZE = 12


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes():
    paths = [Path(__file__), ROOT / 'soko_mcp/oracle.py', ROOT / 'soko_mcp/data/catalog.json']
    for directory in ('experiments/causal_solver', 'experiments/transport_relaxation',
                      'experiments/exact_frontier'):
        paths.extend((ROOT / directory).glob('*.py'))
    return {str(p.relative_to(ROOT)): file_hash(p) for p in sorted(set(paths))}


def archive(path):
    return json.loads(gzip.decompress((ROOT / path).read_bytes()))


def candidates():
    data = archive(CAUSAL)
    for i, item in enumerate(data['candidates']):
        yield {'archive': CAUSAL, 'location': f'candidates[{i}]'}, item['assignment']
    files = archive(GLOBAL)['files']
    for name in sorted(k for k in files if k.startswith('iterations/') and k.endswith('/assignment.json')):
        yield {'archive': GLOBAL, 'location': f'files[{name!r}]'}, json.loads(files[name])


def evaluate(universe, assignment, mode):
    result = master.evaluate_flow(universe, assignment, cut_selection=mode)
    # Reconstruct the entire boundary using the independent certificate code.
    normalized, assignment_hash = cut_certificate._assignment(universe, assignment)
    boundary = cut_certificate._boundary(universe, normalized, result['source_side'])
    ids = [row['edge_id'] for row in boundary]
    capacity = sum(row['capacity'] for row in boundary)
    if ids != result['crossing_ids'] or capacity != result['crossing_capacity'] or capacity != result['flow_value']:
        raise ValueError('independent boundary, reported boundary, capacity, and flow disagree')
    keys = {(row['kind'], tuple(row['params'])) for row in boundary}
    counts = {'crossing_edges': len(boundary),
              'unique_nonconstant_predicates': sum(kind != 'one' for kind, _ in keys),
              'grouped_all_predicates': len(keys), 'crossing_capacity': capacity}
    if result['flow_value'] < cut_certificate.REQUIRED_FLOW:
        certificate = cut_certificate.make_cut_certificate(universe, assignment, result)
        checked = cut_certificate.check_cut_certificate(universe, assignment, certificate)
        if list(checked) != ids:
            raise ValueError('independent certificate boundary mismatch')
        proof = {'type': 'deficient_cut', 'certificate': certificate,
                 'certificate_sha256': digest(certificate), 'independently_checked': True}
    else:
        cut_certificate.check_flow_witness(universe, assignment, result['flow_edge_paths'])
        certificate = {'assignment_sha256': assignment_hash,
                       'universe_sha256': cut_certificate._universe(universe)[0],
                       'source_side': result['source_side'], 'crossing_edges': boundary,
                       'crossing_capacity': capacity, 'flow_edge_paths': result['flow_edge_paths']}
        proof = {'type': 'flow_witness_and_boundary', 'certificate': certificate,
                 'certificate_sha256': digest(certificate), 'independently_checked': True}
    return {'mode': mode, 'flow_value': result['flow_value'], **counts, **proof}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    hashes_before = source_hashes()
    archive_hashes = {p: file_hash(ROOT / p) for p in (CAUSAL, GLOBAL, REFERENCE)}
    graph = universal_flow.build_universe(47)
    identities = {'47': cut_certificate.check_universe_spec(graph)}
    sample, seen = [], set()
    scanned = {'total': 0, 'invalid': 0, 'duplicate': 0, 'nondeficient': 0}
    for provenance, assignment in candidates():
        scanned['total'] += 1
        key = digest(assignment)
        if key in seen:
            scanned['duplicate'] += 1
            continue
        seen.add(key)
        try:
            master.validate_assignment(assignment, 47)
        except ValueError:
            scanned['invalid'] += 1
            continue
        first = evaluate(graph, assignment, MODES[0])
        if first['flow_value'] >= cut_certificate.REQUIRED_FLOW:
            scanned['nondeficient'] += 1
            continue
        second = evaluate(graph, assignment, MODES[1])
        if first['flow_value'] != second['flow_value']:
            raise ValueError('minimum cuts disagree on flow value')
        sample.append({'provenance': provenance, 'assignment': assignment,
                       'assignment_sha256': key, 'modes': {MODES[0]: first, MODES[1]: second}})
        if len(sample) == SAMPLE_SIZE:
            break
    if len(sample) != SAMPLE_SIZE:
        raise ValueError(f'only {len(sample)} unique valid deficient assignments found')

    ref_location = 'iterations/0002/assignment.json'
    ref = json.loads(archive(REFERENCE)['files'][ref_location])
    ref_graph = universal_flow.build_universe(48)
    identities['48'] = cut_certificate.check_universe_spec(ref_graph)
    master.validate_assignment(ref, 48)
    ref_modes = {mode: evaluate(ref_graph, ref, mode) for mode in MODES}
    if any(result['flow_value'] != 9 for result in ref_modes.values()):
        raise ValueError('known reference did not deliver nine units')
    comparison = {}
    for metric in ('unique_nonconstant_predicates', 'grouped_all_predicates', 'crossing_edges'):
        pairs = [(row['modes'][MODES[0]][metric], row['modes'][MODES[1]][metric]) for row in sample]
        baseline, alternate = map(sum, zip(*pairs))
        comparison[metric] = {'source_total': baseline, 'sink_total': alternate,
                              'sink_less_count': sum(b < a for a, b in pairs),
                              'equal_count': sum(b == a for a, b in pairs),
                              'sink_greater_count': sum(b > a for a, b in pairs),
                              'aggregate_percent_change': (100 * (alternate - baseline) / baseline
                                                           if baseline else None)}
    hashes_after = source_hashes()
    if hashes_before != hashes_after or archive_hashes != {p: file_hash(ROOT / p) for p in archive_hashes}:
        raise ValueError('source or input archive changed during comparison')
    output = {'method': __doc__, 'sample_size': SAMPLE_SIZE, 'scanned': scanned,
              'archive_sha256': archive_hashes, 'source_sha256': hashes_before,
              'universe_sha256': identities, 'sample': sample, 'comparison': comparison,
              'positive_control': {'provenance': {'archive': REFERENCE, 'location': f'files[{ref_location!r}]'},
                                   'assignment': ref, 'assignment_sha256': digest(ref), 'modes': ref_modes},
              'limitations': 'New fixed-input sample only; no timing, search-speed, record, or room-bound claim.'}
    raw = (json.dumps(output, indent=2, sort_keys=True) + '\n').encode()
    args.output.write_bytes(gzip.compress(raw, mtime=0) if args.output.suffix == '.gz' else raw)
    print(json.dumps({'output': str(args.output), 'sample_size': len(sample), 'scanned': scanned,
                      'comparison': comparison}, indent=2))


if __name__ == '__main__':
    main()
