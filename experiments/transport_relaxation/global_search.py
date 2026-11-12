"""Run the global hero-master / certified material-cut loop.

Flow SAT is abstract feasibility only. Search limits are unknown. Global UNSAT
requires checked cuts and a separate checked CNF certificate, with the written
game projection and encoding/compilation still in the trusted boundary.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import z3

from experiments.exact_frontier.certified_sat import solve_cnf
from experiments.exact_frontier.cnf_search import compile_cnf
from experiments.exact_frontier.record_system import sha, write_json
from experiments.transport_relaxation import cut_certificate as certificates
from experiments.transport_relaxation import global_master, model, universal_flow
from experiments.transport_relaxation.run import local_replay


def source_identity():
    paths = sorted((ROOT / 'experiments/transport_relaxation').glob('*.py'))
    paths += [ROOT / name for name in (
        'experiments/exact_frontier/iii14_problem.py',
        'experiments/exact_frontier/iii14_smt.py',
        'experiments/exact_frontier/cnf_search.py',
        'experiments/exact_frontier/certified_sat.py',
        'experiments/exact_frontier/record_system.py',
        'soko_mcp/oracle.py', 'soko_mcp/data/catalog.json')]
    return {str(path.relative_to(ROOT)): sha(path) for path in paths}


def reference_assignment(horizon):
    from experiments.transport_relaxation.project import project
    reference = project()
    padding = horizon - len(reference.route)
    if padding < 0:
        raise ValueError('reference control horizon cannot be shorter than the reference')
    names = ('bard_x', 'bard_y', 'druid_x', 'druid_y', 'active')
    heroes = [{name: getattr(frame, name) for name in names} for frame in reference.frames]
    return {'route': 'U' * padding + reference.route,
            'heroes': [dict(heroes[0]) for _ in range(padding)] + heroes,
            # Deliberately deficient landmark exercises actual cut generation.
            'landmark': 1}


def pin_heroes(master, assignment):
    for row, key in zip(master.actions, assignment['route']):
        master.solver.add(row[model.KEYS.index(key)])
    for frame, values in zip(master.frames, assignment['heroes']):
        for name, value in values.items():
            master.solver.add(getattr(frame, name) == value)


def search(output: Path, horizon: int, timeout_seconds=120, max_iterations=200,
           proof_checker=None, control=False):
    """Complete the loop or return explicit unknown with durable progress."""
    began = time.monotonic()
    deadline = began + timeout_seconds
    initial_sources = source_identity()
    report = {
        'schema_version': 1, 'room': 'III-14', 'horizon': horizon,
        'kind': 'reference_master_control' if control else 'global_flow_cut_search',
        'status': 'running', 'phase': 'build', 'iterations': 0, 'cuts_checked': 0,
        'timeout_seconds': timeout_seconds, 'max_iterations': max_iterations,
        'source_sha256': initial_sources, 'z3_version': z3.get_version_string(),
        'record_claim': False, 'original_game_equivalence_proved': False,
        'search_restrictions': ['reference_actions_and_hero_positions'] if control else [],
        'termination_normalization': 'first hero-goal pair at horizon; earlier concrete wins embed by prepended abstract initial U-stays',
        'trusted_boundary': 'written game-to-flow projection, master/capacity encodings, Z3 transformations; cut boundaries and capacities independently reconstructed',
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / 'iterations').mkdir(exist_ok=True)

    def save(**updates):
        report.update(updates, elapsed_seconds=time.monotonic() - began)
        write_json(output / 'progress.json', report)

    def remaining():
        left = deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError('wall-clock budget exhausted')
        return left

    def finish(status, **updates):
        if source_identity() != initial_sources:
            status, updates = 'error', {'reason': 'source files changed during execution'}
        save(status=status, **updates)
        write_json(output / 'result.json', report)
        return report

    save()
    master = global_master.build_master(horizon)
    universe = universal_flow.build_universe(horizon)
    checked_identity = certificates.check_universe_spec(universe)
    save(universe_sha256=checked_identity, universe_spec_checked=True,
         universal_nodes=len(universe.node_labels), universal_edges=len(universe.edges))
    seed = reference_assignment(horizon) if control else None
    if seed is not None:
        pin_heroes(master, seed)
    accepted_cuts = []
    try:
        for iteration in range(1, max_iterations + 1):
            save(phase='master', iterations=iteration)
            master.solver.set(timeout=max(1, int(remaining() * 1000)))
            seed_round = iteration == 1 and seed is not None
            if seed_round:
                master.solver.push()
                master.solver.add(master.landmarks[0])
            solve_started = time.monotonic()
            outcome = master.solver.check()
            unknown_reason = master.solver.reason_unknown() if outcome == z3.unknown else None
            solve_seconds = time.monotonic() - solve_started
            assignment = global_master.decode(master, master.solver.model()) if outcome == z3.sat else None
            if seed_round:
                master.solver.pop()
            if outcome == z3.unknown:
                return finish('unknown', reason=unknown_reason, last_phase='master')
            if outcome == z3.unsat:
                if seed_round or control:
                    return finish('reference_control_rejected', reason='restricted reference master is unsatisfiable')
                save(phase='compile_unsat_certificate')
                remaining()
                cnf, _ = compile_cnf(master.solver)
                cnf_path = output / 'final-master.cnf'
                cnf_path.write_text(cnf)
                save(phase='check_unsat_certificate', final_cnf_sha256=sha(cnf_path))
                proof = solve_cnf(cnf_path, output / 'unsat-certificate', remaining(), proof_checker)
                report['unsat_certificate'] = proof
                if proof['status'] == 'unsat' and proof['checker_status'] == 'verified':
                    return finish('certified_relaxation_cnf_unsat', abstract_lower_bound=horizon + 1,
                                  conclusion='No relaxed master/flow plan by this horizon, conditional on checked cut construction and documented projection/encoding assumptions.')
                if proof['status'] == 'unknown':
                    return finish('unknown', reason='UNSAT certificate budget expired')
                if proof['status'] == 'unsat':
                    return finish('unverified_master_unsat', reason='no independently checked CNF proof')
                return finish('error', reason='master UNSAT certification disagreed or failed')

            save(phase='flow')
            remaining()
            step_dir = output / 'iterations' / f'{iteration:04d}'
            step_dir.mkdir()
            write_json(step_dir / 'assignment.json', assignment)
            flow_started = time.monotonic()
            evaluation = universal_flow.evaluate_flow(universe, assignment)
            flow_seconds = time.monotonic() - flow_started
            remaining()
            step = {'iteration': iteration, 'master_seconds': solve_seconds,
                    'flow_seconds': flow_seconds, 'flow_value': evaluation['flow_value'],
                    'landmark': assignment['landmark'],
                    'candidate_source': 'deliberate_deficient_reference_landmark' if seed_round else 'master_solver'}
            if evaluation['flow_value'] >= 9:
                save(phase='check_flow_witness')
                certificates.check_flow_witness(universe, assignment, evaluation['flow_edge_paths'])
                witness = {'assignment': assignment, 'flow_edge_paths': evaluation['flow_edge_paths'],
                           'witness': evaluation['witness'], 'universe_sha256': report['universe_sha256']}
                write_json(output / 'witness.json', witness)
                write_json(step_dir / 'result.json', step)
                replay = local_replay(assignment['route'])
                return finish('reference_control_passed' if control else 'relaxed_feasible',
                              route=assignment['route'], landmark=assignment['landmark'],
                              flow_witness_checked=True, witness_sha256=sha(output / 'witness.json'),
                              concrete_local_replay=replay)

            save(phase='check_cut')
            certificate = certificates.make_cut_certificate(universe, assignment, evaluation)
            crossing = certificates.check_cut_certificate(universe, assignment, certificate)
            write_json(step_dir / 'cut.json', certificate)
            # Candidate must satisfy the master before the cut, and falsify the
            # symbolic form of the independently checked capacity inequality.
            master.solver.push()
            global_master.pin_assignment(master, assignment)
            master.solver.set(timeout=max(1, int(remaining() * 1000)))
            pinned_status = master.solver.check()
            if pinned_status != z3.sat:
                master.solver.pop()
                if pinned_status == z3.unknown:
                    return finish('unknown', reason='candidate/cut consistency check timed out')
                return finish('error', reason='decoded candidate does not satisfy current master')
            pinned_model = master.solver.model()
            master.solver.pop()
            expression = global_master.add_cut(master, universe, crossing)
            if not z3.is_false(pinned_model.eval(expression, model_completion=True)):
                return finish('error', reason='checked cut does not reject its generating assignment')
            remaining()
            step.update(crossing_edges=len(crossing), cut_sha256=sha(step_dir / 'cut.json'))
            write_json(step_dir / 'result.json', step)
            accepted_cuts.append({'iteration': iteration, 'sha256': step['cut_sha256']})
            write_json(output / 'accepted-cuts.json', accepted_cuts)
            save(cuts_checked=len(accepted_cuts), last_flow_value=evaluation['flow_value'],
                 last_cut_edges=len(crossing))
        return finish('unknown', reason='iteration budget exhausted')
    except TimeoutError as error:
        return finish('unknown', reason=str(error))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('run', 'control'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--horizon', type=int)
    parser.add_argument('--timeout-seconds', type=float, default=120)
    parser.add_argument('--max-iterations', type=int, default=200)
    parser.add_argument('--proof-checker', type=Path)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.horizon = (48 if args.command == 'control' else 47) if args.horizon is None else args.horizon
    if args.horizon < 0 or args.max_iterations < 1 or not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0:
        parser.error('invalid horizon, iteration limit, or finite positive time budget')
    if args.command == 'control' and args.horizon < 48:
        parser.error('reference control requires horizon >= 48')
    args.output = args.output.resolve()
    if args.worker:
        try:
            result = search(args.output, args.horizon, args.timeout_seconds,
                            args.max_iterations, args.proof_checker, args.command == 'control')
        except Exception as error:
            result = {'status': 'error', 'reason': str(error), 'record_claim': False}
            write_json(args.output / 'result.json', result)
            raise
        print(json.dumps(result, indent=2))
        return
    if args.output.exists() and any(args.output.iterdir()):
        parser.error('use a new or empty output directory')
    args.output.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-m', 'experiments.transport_relaxation.global_search',
               *sys.argv[1:], '--worker']
    with (args.output / 'stdout.log').open('w') as stdout, (args.output / 'stderr.log').open('w') as stderr:
        worker = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr,
                                  start_new_session=True)
        try:
            worker.wait(timeout=args.timeout_seconds + 2)
        except subprocess.TimeoutExpired:
            # Include proof-solver descendants in the same wall-clock limit.
            try:
                os.killpg(worker.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            worker.wait()
            progress = args.output / 'progress.json'
            result = json.loads(progress.read_text()) if progress.exists() else {}
            result.update(status='unknown', reason='outer wall-clock budget exhausted', record_claim=False)
            write_json(args.output / 'result.json', result)
        else:
            if not (args.output / 'result.json').exists():
                write_json(args.output / 'result.json', {'status': 'error',
                    'reason': f'worker exited {worker.returncode} without a result', 'record_claim': False})
    print((args.output / 'result.json').read_text())


if __name__ == '__main__':
    main()
