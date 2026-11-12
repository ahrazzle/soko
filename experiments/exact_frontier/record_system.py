#!/usr/bin/env python3
"""Prepare and solve one unrestricted, evidence-producing record query.

The objective is win by incumbent_length - 1. There are no route prefixes,
repair windows, fixed switch schedules, or guide neighborhoods in a record query.
Model UNSAT is deliberately distinguished from an original-game optimality proof.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.metadata
import json
import math
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from soko_mcp.catalog import get_room
from soko_mcp.oracle import PuzzleScriptOracle
from soko_mcp.original import replay

SUPPORTED = {'III-14': 'iii14_problem', 'III-20': 'iii20_problem'}
FRONTIER = 'https://soko.banteg.xyz/api/frontier'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def observe_frontier(destination: Path, snapshot: Path | None = None) -> dict:
    if snapshot:
        raw = snapshot.read_bytes()
    else:
        fetched = subprocess.run(['curl', '--fail', '--silent', '--show-error',
                                  '--location', '--max-time', '30', FRONTIER],
                                 capture_output=True, check=True, timeout=35)
        raw = fetched.stdout
    value = json.loads(raw)
    if not isinstance(value.get('rooms'), list):
        raise ValueError('Frontier response has no room list')
    destination.write_bytes(raw)
    return {'url': FRONTIER, 'sha256': sha(destination),
            'observed_at': datetime.now(timezone.utc).isoformat(),
            'mode': 'provided_snapshot' if snapshot else 'live_fetch'}


def incumbent(snapshot: dict, room: dict) -> dict:
    entries = [r for r in snapshot['rooms']
               if r.get('part') == room['part'] and r.get('room') == room['room']]
    if len(entries) != 1:
        raise ValueError('Frontier must identify exactly one matching room')
    result = entries[0]
    if type(result.get('length')) is not int or result['length'] < 1:
        raise ValueError('Frontier record length must be a positive integer')
    return result


def source_identity() -> dict:
    # All modeling, compilation and local checking code is bound to the bundle.
    paths = [Path(__file__).parent/name for name in
             ('record_system.py', 'cnf_search.py', 'iii14_smt.py', 'iii14_problem.py', 'iii14_compact.py',
              'iii20_bitvector.py', 'iii20_problem.py')]
    paths += [ROOT/'soko_mcp'/p for p in
              ('oracle.py', 'flat_oracle.py', 'original.py', 'catalog.py')]
    paths += [ROOT/'soko_mcp/data/catalog.json']
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)}


def prepare(args) -> dict:
    from experiments.exact_frontier.cnf_search import compile_cnf
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out/'bundle.json').exists():
        raise ValueError('Output already has a bundle; use a new directory')
    began = time.monotonic()
    initial_sources = source_identity()
    room = get_room(args.room)
    observed = observe_frontier(out/'frontier.json', args.frontier_snapshot)
    best = incumbent(json.loads((out/'frontier.json').read_text()), room)
    module = importlib.import_module('experiments.exact_frontier.' + SUPPORTED[args.room])
    control = args.command == 'check-reference'
    horizon = len(room['reference_route']) if control else best['length'] - 1
    report = {'schema_version': 1, 'room': args.room,
              'mode': 'reference_control' if control else 'global_record_query',
              'objective': {'first_win_at_or_before': horizon,
                            'observed_record_length': best['length']},
              'incumbent': best, 'frontier_observation': observed,
              'model_contract': module.MODEL_CONTRACT,
              'semantic_equivalence_proved': False,
              'search_restrictions': ['pinned_reference_actions_and_oracle_frames'] if control else [],
              'status': 'calibrating'}
    write_json(out/'progress.json', report)
    calibration = module.calibrate(initial_samples=args.calibration_samples,
                                   near_samples=args.calibration_samples // 5)
    if calibration.get('status') != 'passed':
        raise ValueError('Model calibration failed')
    write_json(out/'calibration.json', calibration)
    write_json(out/'instance.json', room)
    report.update(status='compiling')
    write_json(out/'progress.json', report)
    solver, actions, states = module.build_problem(horizon)
    if control:
        oracle = PuzzleScriptOracle(room['part'], room['grid'])
        for i, key in enumerate(room['reference_route']):
            solver.add(actions[i]['UDLRA'.index(key)])
            alive, won = oracle.step(key)
            if not alive or won != (i == horizon-1):
                raise ValueError('Reference control does not first win on its last input')
            values = module.oracle_state(oracle)
            solver.add(*[var == value for var, value in zip(states[i+1], values)])
    dimacs, aliases = compile_cnf(solver)
    for i in range(horizon):
        for key in 'UDLRA':
            if f'action_{i}_{key}' not in aliases:
                raise ValueError(f'CNF lost action alias {i}/{key}')
    (out/'problem.cnf').write_text(dimacs)
    write_json(out/'actions.json', aliases)
    if source_identity() != initial_sources:
        raise ValueError('Source files changed during preparation; prepare a fresh bundle')
    report.update(status='prepared', source_sha256=initial_sources,
                  runtime_versions={name: importlib.metadata.version(name)
                                    for name in ('z3-solver', 'python-sat', 'playwright')},
                  preparation_seconds=round(time.monotonic()-began, 3),
                  artifacts={name: sha(out/name) for name in
                             ('frontier.json', 'calibration.json', 'instance.json',
                              'problem.cnf', 'actions.json')})
    write_json(out/'bundle.json', report)
    write_json(out/'progress.json', report)
    return report


def checked_bundle(out: Path) -> dict:
    bundle = json.loads((out/'bundle.json').read_text())
    for name, expected in bundle['artifacts'].items():
        path = out/name
        if path.resolve().parent != out.resolve() or sha(path) != expected:
            raise ValueError(f'Bundle artifact changed: {name}')
    for name, expected in bundle['source_sha256'].items():
        path = ROOT/name
        if not path.is_file() or sha(path) != expected:
            raise ValueError(f'Bundle source changed: {name}; prepare a fresh bundle')
    if bundle['mode'] == 'global_record_query' and bundle['search_restrictions']:
        raise ValueError('Global query contains a search restriction')
    return bundle


def decode_route(assignment: list[int], aliases: dict, horizon: int) -> str:
    positive = {n for n in assignment if n > 0}
    route = ''
    for i in range(horizon):
        selected = [k for k in 'UDLRA' if aliases[f'action_{i}_{k}'] in positive]
        if len(selected) != 1:
            raise ValueError(f'Invalid one-hot action at frame {i}')
        route += selected[0]
    return route


def first_win(room: dict, route: str) -> str:
    oracle = PuzzleScriptOracle(room['part'], room['grid'])
    for i, key in enumerate(route):
        alive, won = oracle.step(key)
        if not alive:
            raise ValueError(f'Model witness loses a hero at input {i+1}')
        if won:
            return route[:i+1]
    raise ValueError('Model witness does not win in the independent local interpreter')


def solve(args) -> dict:
    from experiments.exact_frontier.certified_sat import solve_cnf
    out = args.output.resolve()
    bundle = checked_bundle(out)
    result = solve_cnf(out/'problem.cnf', out/'sat', args.timeout_seconds,
                       proof_checker=args.proof_checker)
    report = {'room': bundle['room'], 'mode': bundle['mode'],
              'bundle_sha256': sha(out/'bundle.json'), 'solver': result,
              'solver_source_sha256': sha(Path(__file__).parent/'certified_sat.py'),
              'semantic_equivalence_proved': False, 'public_submission': False}
    if result['status'] == 'sat':
        if result.get('checker_status') != 'assignment_verified':
            raise ValueError('SAT result has no independently checked assignment')
        assignment = json.loads(Path(result['assignment_path']).read_text())
        aliases = json.loads((out/'actions.json').read_text())
        room = json.loads((out/'instance.json').read_text())
        route = first_win(room, decode_route(assignment, aliases,
                          bundle['objective']['first_win_at_or_before']))
        certificate = replay(room['part'], room['room'], route, html=args.html)
        write_json(out/'original-replay.json', certificate)
        if not certificate.get('valid_winning_route') or certificate.get('first_win') != len(route):
            raise ValueError('Original-game replay rejected the model witness')
        report.update(route=route, length=len(route), original_replay='passed',
                      original_certificate_sha256=sha(out/'original-replay.json'))
        if bundle['mode'] == 'reference_control':
            report['status'] = 'reference_control_passed'
        else:
            report['status'] = 'verified_route'
            if bundle['frontier_observation']['mode'] == 'live_fetch':
                latest = observe_frontier(out/'frontier-at-result.json')
                best = incumbent(json.loads((out/'frontier-at-result.json').read_text()), room)
                report.update(frontier_at_result=latest, record_length_at_result=best['length'])
                if len(route) < best['length']:
                    report.update(status='verified_record_improvement', saved_inputs=best['length']-len(route))
            else:
                report['comparison_scope'] = 'provided historical snapshot only'
    elif result['status'] == 'unsat':
        if result.get('checker_status') == 'verified':
            report.update(status='certified_cnf_unsat',
                          conclusion='The encoded formula is UNSAT. Original-game completeness and the translation are not formally proved.')
        else:
            report.update(status='unverified_unsat_claim',
                          conclusion='Solver reported UNSAT, but no independently accepted proof is available.')
    else:
        report['status'] = result['status']
    write_json(out/'result.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'run', 'solve', 'check-reference'))
    parser.add_argument('--room', choices=tuple(SUPPORTED))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--frontier-snapshot', type=Path)
    parser.add_argument('--calibration-samples', type=int, default=500)
    parser.add_argument('--timeout-seconds', type=float, default=3600)
    parser.add_argument('--proof-checker', type=Path)
    parser.add_argument('--html', type=Path, help='Pinned original build; otherwise use the original replay cache')
    args = parser.parse_args()
    if args.command != 'solve' and not args.room:
        parser.error('--room is required to prepare a problem')
    if args.calibration_samples < 1 or not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0:
        parser.error('Calibration samples and timeout must be positive')
    try:
        result = prepare(args) if args.command != 'solve' else None
        if args.command != 'prepare':
            result = solve(args)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        args.output.mkdir(parents=True, exist_ok=True)
        result = {'status': 'error', 'reason': str(exc), 'public_submission': False}
        write_json(args.output/'error.json', result)
        print(json.dumps(result, indent=2))
        raise SystemExit(1)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
