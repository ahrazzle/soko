"""Bounded, checkpointed CEGAR search. See search.md for trust and controls."""
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request

import z3

from experiments.causal_solver import master as causal, refinement
from experiments.transport_relaxation import cut_certificate, global_master, universal_flow
from experiments.exact_frontier import iii14_smt as mechanics, iii14_problem
from soko_mcp.oracle import PuzzleScriptOracle

ROOT = Path(__file__).resolve().parents[2]
# Include every local source in the dependency packages; provenance is deliberately
# broader than a hand-maintained import list.
SOURCE_DIRS = ('experiments/causal_solver', 'experiments/transport_relaxation',
               'experiments/exact_frontier', 'soko_mcp')


def source_hashes():
    iii14_problem._guard_current_source()
    paths = sorted([p for directory in SOURCE_DIRS for p in (ROOT / directory).rglob('*.py')]
                   + list((ROOT / 'soko_mcp/data').rglob('*.json')))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def local_replay(route):
    oracle = PuzzleScriptOracle(3, mechanics.ROWS)
    for index, key in enumerate(route, 1):
        alive, won = oracle.step(key)
        if not alive:
            return {'status': 'loss', 'step': index}
        if won:
            return {'status': 'won', 'step': index, 'route': route[:index]}
    return {'status': 'not_won', 'step': len(route)}



def compare_frontier(route, timeout):
    url = 'https://soko.banteg.xyz/api/frontier'
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'soko-causal-search/1'})
        with urllib.request.urlopen(request, timeout=max(.001, timeout)) as response:
            raw = response.read()
        data = json.loads(raw)
        matches = [room for room in data['rooms'] if room.get('part') == 3 and room.get('room') == 14]
        if len(matches) != 1 or type(matches[0].get('length')) is not int:
            raise ValueError('unexpected Frontier response')
        room = matches[0]
        return {'status': 'observed', 'url': url, 'observed_at': datetime.now(timezone.utc).isoformat(),
                'response_sha256': hashlib.sha256(raw).hexdigest(), 'room': room,
                'route_length': len(route), 'strictly_shorter': len(route) < room['length']}
    except Exception as exc:
        return {'status': 'unavailable', 'url': url, 'reason': str(exc)}

def control_assignment(control, horizon):
    if control == 'reference':
        return causal.reference_assignment(horizon)
    if control == 'spurious':
        if horizon != 47:
            raise ValueError('spurious control requires horizon 47')
        from experiments.transport_relaxation.diagnostic import shortened_heroes, hero_mappings
        route, heroes = shortened_heroes()
        return {'route': route, 'heroes': list(hero_mappings(heroes)), 'landmark': 42}
    if control is not None:
        raise ValueError('unknown control')
    return None


def _save(path, result):
    if path is None:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    os.replace(tmp, path)


def run(horizon, budget_seconds, *, control=None, phase_order='exact-first',
        use_events=True, symmetry=False, encoding='compact', html=None,
        chromium=None, output=None):
    if type(horizon) is not int or horizon < 0:
        raise ValueError('invalid horizon')
    if isinstance(budget_seconds, bool) or not isinstance(budget_seconds, (int, float)) or not math.isfinite(budget_seconds) or budget_seconds <= 0:
        raise ValueError('budget must be positive and finite')
    if phase_order not in ('exact-first', 'flow-first'):
        raise ValueError('invalid phase order')
    started = time.monotonic()
    deadline = started + budget_seconds
    result = {'status': 'running', 'horizon': horizon, 'control': control,
              'phase_order': phase_order, 'events': use_events, 'symmetry': symmetry,
              'encoding': encoding, 'candidates': [], 'cuts': [], 'phases': [],
              'source_hashes_before': source_hashes(), 'record_comparison': {'status': 'not_available'}, 'record_claim': False}

    def remaining():
        return max(0.0, deadline - time.monotonic())

    def checkpoint():
        result['elapsed_seconds'] = time.monotonic() - started
        result['source_hashes_after'] = source_hashes()
        if result['source_hashes_after'] != result['source_hashes_before']:
            result['status'] = 'source_mutation_error'
            _save(output, result)
            raise RuntimeError('source changed during search')
        _save(output, result)

    def phase(name, fn):
        begin = time.monotonic()
        try:
            return fn()
        finally:
            result['phases'].append({'name': name, 'seconds': time.monotonic() - begin})
            checkpoint()

    checkpoint()
    m = phase('master_build', lambda: causal.build_master(horizon, use_events=use_events, symmetry=symmetry))
    assignment = control_assignment(control, horizon)
    if assignment is not None:
        causal.validate_assignment(assignment, horizon)
        global_master.pin_assignment(m, assignment)
    universe = phase('flow_build', lambda: universal_flow.build_universe(horizon))
    result['universe_sha256'] = phase('flow_spec_check', lambda: cut_certificate.check_universe_spec(universe))
    refiner = None
    exact_rejection = False
    checkpoint()
    while remaining() > 0:
        m.solver.set(timeout=max(1, math.ceil(remaining() * 1000)))
        status = phase('master_solve', m.solver.check)
        if status == z3.unknown:
            result.update(status='unknown', reason=m.solver.reason_unknown())
            break
        if status == z3.unsat:
            result['status'] = ('control_passed' if control == 'spurious' and exact_rejection
                                else 'control_failed' if control else 'solver_global_unsat')
            result['proof'] = 'solver result; checked cores are replay recipes, not independent UNSAT proofs'
            break
        candidate = global_master.decode(m, m.solver.model())
        causal.validate_assignment(candidate, horizon)
        item = {'assignment': candidate}
        result['candidates'].append(item)
        checkpoint()
        local = phase('local_replay', lambda: local_replay(candidate['route']))
        item['local_replay'] = local
        if local['status'] == 'won':
            if control == 'spurious':
                result.update(status='control_failed', reason='spurious route won locally')
                break
            if control == 'reference':
                flow = phase('flow_evaluate', lambda: causal.evaluate_flow(universe, candidate))
                item['flow_value'] = flow['flow_value']
                if flow['flow_value'] != 9:
                    result.update(status='control_failed', reason='reference flow below nine')
                    break
                refiner = phase('exact_build', lambda: refinement.ExactRefiner(horizon, encoding=encoding))
                checked = phase('exact_check', lambda: refiner.check(candidate, timeout_seconds=remaining()))
                item['exact'] = checked
                if checked['status'] != 'sat':
                    result.update(status='unknown' if checked['status'] == 'unknown' else 'control_failed',
                                  reason='reference exact completion did not return SAT')
                    break
            if remaining() <= 0:
                result.update(status='unknown', reason='wall budget exhausted before original replay')
                break
            from soko_mcp.original import replay
            try:
                evidence = phase('original_replay', lambda: replay(3, 14, local['route'], html=html,
                                  chromium=chromium, timeout_sec=max(.001, remaining())))
            except (TimeoutError, subprocess.TimeoutExpired):
                result.update(status='unknown', reason='original replay timed out')
                break
            item['original_replay'] = evidence
            if remaining() <= 0:
                result.update(status='unknown', reason='wall budget exhausted during original replay')
                break
            if evidence.get('valid_winning_route'):
                result['status'] = 'control_passed' if control == 'reference' else 'original_verified_win'
                if control is None:
                    comparison = phase('frontier_comparison', lambda: compare_frontier(local['route'], remaining()))
                    result['record_comparison'] = comparison
                    result['record_claim'] = comparison.get('status') == 'observed' and comparison.get('strictly_shorter', False)
                break
            result.update(status='error', reason='local win rejected by original engine')
            break
        cut_added = False
        for which in (('exact', 'flow') if phase_order == 'exact-first' or control == 'spurious' else ('flow', 'exact')):
            if remaining() <= 0:
                break
            if which == 'flow':
                flow = phase('flow_evaluate', lambda: causal.evaluate_flow(universe, candidate))
                item['flow_value'] = flow['flow_value']
                if flow['flow_value'] < 9:
                    cert = phase('flow_certificate', lambda: cut_certificate.make_cut_certificate(universe, candidate, flow))
                    ids = cut_certificate.check_cut_certificate(universe, candidate, cert)
                    global_master.add_cut(m, universe, ids)
                    result['cuts'].append({'kind': 'flow', 'certificate': cert, 'verified': True})
                    cut_added = True
                    checkpoint()
                    break
            else:
                if refiner is None:
                    refiner = phase('exact_build', lambda: refinement.ExactRefiner(horizon, encoding=encoding))
                checked = phase('exact_check', lambda: refiner.check(candidate, timeout_seconds=remaining()))
                item['exact'] = checked
                if checked['status'] == 'unknown':
                    result.update(status='unknown', reason='exact completion unknown')
                    break
                if checked['status'] == 'sat':
                    # A symbolic completion is not an original-engine win.
                    result.update(status='unknown', reason='exact SAT without local original-game win')
                    break
                if checked['status'] != 'unsat':
                    raise ValueError('unexpected exact status')
                verification = phase('exact_certificate_recheck', lambda: refinement.add_core_cut(m, checked['certificate'], timeout_seconds=remaining()))
                verification.pop('expression', None)
                item['exact_verification'] = verification
                if not verification.get('verified') or not verification.get('added'):
                    result.update(status='unknown', reason='exact core not independently rechecked')
                    break
                result['cuts'].append({'kind': 'exact', 'certificate': verification['certificate'], 'verified': True})
                exact_rejection = True
                cut_added = True
                checkpoint()
                break
        if not cut_added:
            break
    if result['status'] == 'running':
        result.update(status='unknown', reason='wall budget exhausted')
    checkpoint()
    return result


def _descendants(pid):
    """Find descendants even when a browser worker starts a new session."""
    parents = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / 'stat').read_text()
            fields = stat[stat.rfind(')') + 2:].split()
            parents[int(entry.name)] = int(fields[1])
        except (OSError, ValueError, IndexError):
            continue
    found, pending = [], [pid]
    while pending:
        parent = pending.pop()
        children = [child for child, ppid in parents.items() if ppid == parent]
        found.extend(children)
        pending.extend(children)
    return found


def run_bounded(options, output):
    """Put the entire build/check loop in a worker and enforce a hard deadline."""
    budget = options.get('budget_seconds')
    if isinstance(budget, bool) or not isinstance(budget, (int, float)) or not math.isfinite(budget) or budget <= 0:
        raise ValueError('budget must be positive and finite')
    options = dict(options)
    if options.get('html') is not None:
        options['html'] = str(Path(options['html']).resolve())
    if options.get('chromium') and '/' in str(options['chromium']):
        options['chromium'] = str(Path(options['chromium']).resolve())
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Never mistake an old checkpoint for this run.
    output.unlink(missing_ok=True)
    command = [sys.executable, '-m', 'experiments.causal_solver.search', '--worker',
               '--options', json.dumps(options), '--output', str(output)]
    before = source_hashes()
    started = time.monotonic()
    proc = subprocess.Popen(command, cwd=ROOT, start_new_session=True)
    try:
        proc.wait(timeout=options['budget_seconds'])
    except subprocess.TimeoutExpired:
        for pid in reversed(_descendants(proc.pid)):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
        result = json.loads(output.read_text()) if output.exists() else {
            'horizon': options['horizon'], 'control': options.get('control'),
            'candidates': [], 'cuts': [], 'phases': [], 'source_hashes_before': before}
        result.update(status='unknown', reason='hard wall budget exhausted',
                      elapsed_seconds=time.monotonic() - started, record_claim=False)
        try:
            after = source_hashes()
            result['source_hashes_after'] = after
            if after != before or result.get('source_hashes_before') != before:
                result.update(status='source_mutation_error', reason='source changed during search')
        except Exception as exc:
            result.update(status='source_mutation_error', reason=str(exc))
        _save(output, result)
        return result
    if not output.exists():
        raise RuntimeError(f'search worker failed ({proc.returncode}) before its first checkpoint')
    result = json.loads(output.read_text())
    try:
        after = source_hashes()
        if after != before or result.get('source_hashes_before') != before:
            result.update(status='source_mutation_error', reason='source changed during search')
            _save(output, result)
    except Exception as exc:
        result.update(status='source_mutation_error', reason=str(exc))
        _save(output, result)
    if proc.returncode and result['status'] != 'source_mutation_error':
        result.update(status='error', reason=f'worker exited {proc.returncode}')
        _save(output, result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--horizon', type=int)
    p.add_argument('--budget-seconds', type=float)
    p.add_argument('--control', choices=('reference', 'spurious'))
    p.add_argument('--phase-order', choices=('exact-first', 'flow-first'), default='exact-first')
    p.add_argument('--no-events', action='store_true')
    p.add_argument('--symmetry', action='store_true')
    p.add_argument('--encoding', choices=('compact', 'causal', 'legacy'), default='compact')
    p.add_argument('--html')
    p.add_argument('--chromium')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    p.add_argument('--options', help=argparse.SUPPRESS)
    args = p.parse_args()
    if args.worker:
        run(**json.loads(args.options), output=args.output)
        return
    if args.horizon is None or args.budget_seconds is None:
        p.error('--horizon and --budget-seconds are required')
    options = {'horizon': args.horizon, 'budget_seconds': args.budget_seconds,
               'control': args.control, 'phase_order': args.phase_order,
               'use_events': not args.no_events, 'symmetry': args.symmetry,
               'encoding': args.encoding, 'html': args.html, 'chromium': args.chromium}
    result = run_bounded(options, args.output)
    print(json.dumps({'status': result['status'], 'output': str(args.output)}))


if __name__ == '__main__':
    main()
