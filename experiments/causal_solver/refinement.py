"""Full-material completion and independently replayed assumption-core cuts.

No abstract landmark is assumed: a selected nine-token landmark need not be a
frame where *all* exact material occupies those cells. Certificates are replay
recipes, not standalone UNSAT proofs or original-engine verification.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import time

import z3

from experiments.exact_frontier import iii14_problem as exact
from experiments.exact_frontier import iii14_smt as mechanics

KEYS = 'UDLRA'
ROOT = Path(__file__).resolve().parents[2]
CERTIFICATE_VERSION = 1


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def _certificate(metadata, core, descriptors, kind):
    payload = {'kind': kind, 'metadata': deepcopy(metadata), 'core': [list(d) for d in core],
               'origin_assumptions_sha256': _digest(descriptors)}
    return {**payload, 'payload_sha256': _digest(payload),
            'validation': {'status': 'not_run', 'verified': False}}


def _timeout_ms(seconds):
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
        raise ValueError('timeout_seconds must be finite and nonnegative')
    return max(1, math.ceil(seconds * 1000))


def _build(horizon, encoding):
    if encoding == 'causal':
        from .encoding import build
        return build(horizon)
    # Use game rules alone. The optional global landmarks are unnecessary for
    # completion, and would obscure whether a core is locally contradictory.
    return exact.build_problem(horizon, encoding=encoding, use_landmarks=False)


def _metadata(horizon, encoding):
    exact._guard_current_source()
    paths = ['experiments/exact_frontier/iii14_problem.py',
             'experiments/exact_frontier/iii14_smt.py', 'soko_mcp/oracle.py',
             'soko_mcp/data/catalog.json', 'soko_mcp/data/frontier_snapshot.json',
             'experiments/causal_solver/refinement.py']
    if encoding == 'compact':
        paths.append('experiments/exact_frontier/iii14_compact.py')
    elif encoding == 'causal':
        paths.append('experiments/causal_solver/encoding.py')
    return {'version': CERTIFICATE_VERSION, 'room': 'III-14', 'horizon': horizon,
            'encoding': encoding, 'goal_absorbing': True, 'landmarks': False,
            'source_sha256': exact.EXPECTED_SOURCE_SHA256,
            'board_sha256': _digest(list(mechanics.ROWS)),
            'mechanics_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                                 for p in paths}}


def _descriptor(raw, horizon):
    if not isinstance(raw, (list, tuple)) or not raw:
        raise ValueError('invalid assumption descriptor')
    kind = raw[0]
    if kind not in ('action', 'hero', 'active'):
        raise ValueError('unknown assumption kind')
    if len(raw) < 2 or type(raw[1]) is not int or not 0 <= raw[1] <= horizon:
        raise ValueError('invalid assumption time')
    if kind == 'action':
        if len(raw) != 3 or raw[1] == horizon or not isinstance(raw[2], str) or raw[2] not in tuple(KEYS):
            raise ValueError('invalid action assumption')
    elif kind == 'hero':
        if (len(raw) != 5 or raw[2] not in ('bard', 'druid')
                or type(raw[3]) is not int or not 0 <= raw[3] < mechanics.W
                or type(raw[4]) is not int or not 0 <= raw[4] < mechanics.H):
            raise ValueError('invalid hero assumption')
    elif len(raw) != 3 or type(raw[2]) is not bool:
        raise ValueError('invalid active assumption')
    return tuple(raw)


def _exact_predicate(descriptor, actions, states):
    kind, t, *values = descriptor
    if kind == 'action':
        return actions[t][KEYS.index(values[0])]
    if kind == 'active':
        return states[t][4] == values[0]
    hero, x, y = values
    return states[t][2 if hero == 'bard' else 3] == mechanics.BV(1 << (y * mechanics.W + x))


def _prefix_lemmas(solver, actions, states, descriptors, encoding):
    """Expose exact constant propagation hidden behind action assumptions.

    Given a contiguous fixed action prefix, deterministic transition evaluation
    proves ``prefix => frame == value``. These implications are redundant in
    E_H, including for assignments that choose entirely different actions.
    No oracle state, selected material or proposed hero coordinate is used.
    Fresh core replay derives these implications from *only* its core actions.
    """
    fixed = {d[1]: d[2] for d in descriptors if d[0] == 'action'}
    if encoding == 'legacy':
        def transition(state, key):
            return mechanics.trans(state, key)
    else:
        if encoding == 'compact':
            from experiments.exact_frontier.iii14_compact import trans
        else:
            from .encoding import trans
        def transition(state, key):
            return trans(state, [z3.BoolVal(k == key) for k in KEYS])
    state = tuple(z3.simplify(v) for v in mechanics.initial())
    prefix = []
    for t in range(len(actions)):
        if t not in fixed:
            break
        key = fixed[t]
        prefix.append(actions[t][KEYS.index(key)])
        guard = z3.And(*prefix)
        won = z3.is_true(z3.simplify((state[2] | state[3]) == mechanics.BV(mechanics.GOAL)))
        if not won:
            next_state, legal = transition(state, key)
            if z3.is_false(z3.simplify(legal)):
                solver.add(z3.Not(guard))
                break
            state = tuple(z3.simplify(v) for v in next_state)
        solver.add(z3.Implies(guard, z3.And(*[v == c for v, c in zip(states[t + 1], state)])))


def _deterministic_check(descriptors, horizon, encoding, deadline, independent=False,
                         checked_frames=None):
    """Decide a fixed exact prefix by determinism, with full material present.

    On independent replay use the retained transition and separately compare
    every surviving frame with the Python oracle. A contradictory fixed prefix
    is an UNSAT check of E_H AND core even when the suffix remains arbitrary.
    """
    actions = {}
    constraints = {}
    for d in descriptors:
        if d[0] == 'action':
            if d[1] in actions and actions[d[1]] != d[2]:
                return {'status': 'rejected', 'reason': 'conflicting prefix action descriptors'}
            actions[d[1]] = d[2]
        else:
            constraints.setdefault(d[1], []).append(d)
    oracle = None
    if independent:
        from soko_mcp.oracle import PuzzleScriptOracle
        oracle = PuzzleScriptOracle(3, mechanics.ROWS)
    def heroes_survive():
        # Oracle.alive alone can remain true after Druid petrifies Bard.
        # Counting hero masks also works when find_active would return None.
        cells = [cell for row in oracle.obj for cell in row]
        return sum(c in ('B', '5') for c in cells) == 1 and sum(c in ('D', '6') for c in cells) == 1
    if encoding == 'legacy' or independent:
        transition = mechanics.trans
    else:
        if encoding == 'compact':
            from experiments.exact_frontier.iii14_compact import trans
        else:
            from .encoding import trans
        def transition(state, key):
            return trans(state, [z3.BoolVal(k == key) for k in KEYS])
    state = tuple(z3.simplify(v) for v in mechanics.initial())
    prefix = []
    won = False
    for t in range(horizon + 1):
        if time.perf_counter() >= deadline:
            return {'status': 'unknown', 'reason_unknown': 'deterministic replay budget exhausted'}
        concrete = mechanics.eval_state(state)
        if oracle is not None and concrete != mechanics.oracle_state(oracle):
            return {'status': 'rejected', 'reason': f'independent oracle mismatch at frame {t}'}
        if independent and checked_frames is not None:
            # These facts come from the full-material transition and agreeing
            # oracle, never from the certificate's asserted hero equalities.
            # Retain them privately: a rejected/unknown replay must install none.
            points = tuple(((mask.bit_length() - 1) % mechanics.W,
                            (mask.bit_length() - 1) // mechanics.W)
                           for mask in concrete[2:4])
            checked_frames.append((t, points[0], points[1], concrete[4]))
        for descriptor in constraints.get(t, ()):
            kind, _, *values = descriptor
            if kind == 'active':
                matches = concrete[4] == values[0]
            else:
                hero, x, y = values
                matches = concrete[2 if hero == 'bard' else 3] == 1 << (y * mechanics.W + x)
            if not matches:
                return {'status': 'unsat', 'core': prefix + [descriptor],
                        'contradiction': 'hero_or_active_mismatch', 'frame': t}
        won = concrete[2] | concrete[3] == mechanics.GOAL
        if t == horizon:
            if won:
                return {'status': 'sat', 'route': ''.join(actions[i] for i in range(horizon))}
            return {'status': 'unsat', 'core': prefix, 'contradiction': 'terminal_goal_false', 'frame': t}
        if t not in actions:
            return {'status': 'open', 'frame': t}
        key = actions[t]
        prefix.append(('action', t, key))
        if won:
            continue  # The goal absorbs every component, including active.
        next_state, legal = transition(state, key)
        if not z3.is_true(z3.simplify(legal)):
            if oracle is not None:
                oracle.step(key)
                if heroes_survive():
                    return {'status': 'rejected', 'reason': 'independent oracle disagrees on hero loss'}
            return {'status': 'unsat', 'core': prefix, 'contradiction': 'illegal_hero_loss', 'frame': t + 1}
        state = tuple(z3.simplify(v) for v in next_state)
        if oracle is not None:
            alive, _ = oracle.step(key)
            if not alive or not heroes_survive():
                return {'status': 'rejected', 'reason': 'independent oracle unexpectedly loses a hero'}
    raise AssertionError('unreachable')


def assignment_descriptors(assignment, horizon):
    """Project only exact action, hero-position and active-hero equalities."""
    if not isinstance(assignment, Mapping):
        raise ValueError('assignment must be a mapping')
    route, heroes = assignment.get('route'), assignment.get('heroes')
    if not isinstance(route, str) or len(route) != horizon or any(k not in KEYS for k in route):
        raise ValueError('invalid route')
    if not isinstance(heroes, (list, tuple)) or len(heroes) != horizon + 1:
        raise ValueError('heroes must contain horizon + 1 frames')
    result = [('action', t, key) for t, key in enumerate(route)]
    for t, frame in enumerate(heroes):
        if not isinstance(frame, Mapping):
            raise ValueError('hero frame must be a mapping')
        try:
            result.extend([('hero', t, hero, frame[hero + '_x'], frame[hero + '_y'])
                           for hero in ('bard', 'druid')])
            result.append(('active', t, frame['active']))
        except KeyError as exc:
            raise ValueError('incomplete hero frame') from exc
    return [_descriptor(d, horizon) for d in result]


class ExactRefiner:
    """A reusable exact bounded problem; no material is selected or omitted."""

    def __init__(self, horizon, encoding='compact'):
        if type(horizon) is not int or horizon < 0:
            raise ValueError('horizon must be a nonnegative integer')
        if encoding not in ('compact', 'legacy', 'causal'):
            raise ValueError('unknown encoding')
        self.horizon, self.encoding = horizon, encoding
        started = time.perf_counter()
        self.metadata = _metadata(horizon, encoding)
        self.solver = self.actions = self.states = None
        self.build_seconds = time.perf_counter() - started

    def check(self, assignment, timeout_seconds=10):
        _timeout_ms(timeout_seconds)
        descriptors = assignment_descriptors(assignment, self.horizon)
        if self.metadata != _metadata(self.horizon, self.encoding):
            raise ValueError('mechanics changed since refiner construction')
        started = time.perf_counter()
        replay = _deterministic_check(descriptors, self.horizon, self.encoding,
                                      started + timeout_seconds)
        result = {**replay, 'horizon': self.horizon, 'encoding': self.encoding,
                  'build_seconds': self.build_seconds, 'solve_seconds': time.perf_counter() - started,
                  'assumption_count': len(descriptors), 'verified': False,
                  'method': 'deterministic_full_material_completion'}
        if replay['status'] == 'unsat':
            result['core'] = [list(d) for d in replay['core']]
            result['certificate'] = _certificate(self.metadata, replay['core'], descriptors,
                                                  'deterministic_prefix')
        return result

    def check_assumptions(self, descriptors, timeout_seconds=10):
        """Check a complete or partial assignment; UNSAT cores remain unchecked.

        Each assumption guards one equality. The core can therefore exclude
        many master assignments, including ones with different unrelated keys.
        A separate check_certificate call is mandatory before installing a cut.
        """
        timeout_ms = _timeout_ms(timeout_seconds)
        descriptors = [_descriptor(d, self.horizon) for d in descriptors]
        if len(set(descriptors)) != len(descriptors):
            raise ValueError('duplicate assumption descriptor')
        if self.metadata != _metadata(self.horizon, self.encoding):
            raise ValueError('mechanics changed since refiner construction')
        if self.solver is None:
            build_started = time.perf_counter()
            self.solver, self.actions, self.states = _build(self.horizon, self.encoding)
            self.build_seconds += time.perf_counter() - build_started
        started = time.perf_counter()
        self.solver.push()
        try:
            _prefix_lemmas(self.solver, self.actions, self.states, descriptors, self.encoding)
            assumptions = [z3.FreshBool('completion_assumption') for _ in descriptors]
            self.solver.add(*[z3.Implies(a, _exact_predicate(d, self.actions, self.states))
                              for a, d in zip(assumptions, descriptors)])
            self.solver.set(timeout=timeout_ms)
            status = self.solver.check(*assumptions) if timeout_seconds else z3.unknown
            result = {'status': str(status), 'horizon': self.horizon, 'encoding': self.encoding,
                      'build_seconds': self.build_seconds, 'solve_seconds': time.perf_counter() - started,
                      'assumption_count': len(descriptors), 'verified': False}
            if status == z3.unsat:
                selected = {a.get_id() for a in self.solver.unsat_core()}
                core = [list(d) for a, d in zip(assumptions, descriptors) if a.get_id() in selected]
                certificate = _certificate(self.metadata, core, descriptors, 'smt_core')
                result.update(core=core, certificate=certificate)
            elif status == z3.unknown:
                result['reason_unknown'] = self.solver.reason_unknown() if timeout_seconds else 'zero budget'
            else:
                # These are exact symbolic states, not an original-engine win claim.
                model = self.solver.model()
                result['route'] = ''.join(next(k for k, a in zip(KEYS, row)
                                               if z3.is_true(model.eval(a, model_completion=True)))
                                          for row in self.actions)
            return result
        finally:
            self.solver.pop()

    def check_certificate(self, certificate, timeout_seconds=10):
        """Independently rebuild E_H and require E_H AND core to be UNSAT."""
        return _check_certificate(certificate, timeout_seconds,
                                  expected_metadata=_metadata(self.horizon, self.encoding))


def _check_certificate(certificate, timeout_seconds, expected_metadata=None,
                       checked_frames=None):
    timeout_ms = _timeout_ms(timeout_seconds)
    started = time.perf_counter()
    rejected = {'status': 'rejected', 'verified': False}
    try:
        if not isinstance(certificate, dict) or set(certificate) != {
                'kind', 'metadata', 'core', 'origin_assumptions_sha256', 'payload_sha256', 'validation'}:
            raise ValueError('invalid certificate fields')
        if certificate['kind'] not in ('smt_core', 'deterministic_prefix'):
            raise ValueError('invalid certificate kind')
        metadata = certificate['metadata']
        if not isinstance(metadata, dict):
            raise ValueError('invalid certificate metadata')
        horizon, encoding = metadata['horizon'], metadata['encoding']
        if type(horizon) is not int or horizon < 0 or encoding not in ('compact', 'legacy', 'causal'):
            raise ValueError('invalid certificate problem')
        current = _metadata(horizon, encoding)
        if metadata != current or (expected_metadata is not None and current != expected_metadata):
            raise ValueError('certificate problem/source/mechanics mismatch')
        if not isinstance(certificate['core'], list):
            raise ValueError('invalid core')
        core = [_descriptor(d, horizon) for d in certificate['core']]
        if len(set(core)) != len(core):
            raise ValueError('duplicate core descriptor')
        origin_hash = certificate['origin_assumptions_sha256']
        if not isinstance(origin_hash, str) or len(origin_hash) != 64 or any(c not in '0123456789abcdef' for c in origin_hash):
            raise ValueError('invalid origin hash')
        payload = {k: certificate[k] for k in ('kind', 'metadata', 'core', 'origin_assumptions_sha256')}
        if certificate['payload_sha256'] != _digest(payload):
            raise ValueError('certificate payload digest mismatch')
    except (ValueError, TypeError, KeyError) as exc:
        return {**rejected, 'reason': str(exc)}
    if not timeout_seconds:
        return {'status': 'unknown', 'verified': False, 'reason_unknown': 'zero budget'}
    if certificate['kind'] == 'deterministic_prefix':
        replay = _deterministic_check(core, horizon, encoding, started + timeout_seconds,
                                      independent=True, checked_frames=checked_frames)
        status = replay['status']
        validation = {**{k: v for k, v in replay.items() if k != 'core'},
                      'status': 'verified' if status == 'unsat' else 'unknown' if status == 'unknown' else 'rejected',
                      'verified': status == 'unsat', 'recheck_status': status,
                      'seconds': time.perf_counter() - started,
                      'checker': 'retained_exact_transition_and_python_oracle'}
        checked = deepcopy(certificate)
        checked['validation'] = deepcopy(validation)
        return {**validation, 'certificate': checked}
    # A fresh solver has no candidate pins, learned clauses or trusted status.
    solver, actions, states = _build(horizon, encoding)
    solver.add(*[_exact_predicate(d, actions, states) for d in core])
    _prefix_lemmas(solver, actions, states, core, encoding)
    solver.set(timeout=timeout_ms)
    status = solver.check()
    validation = {'status': 'verified' if status == z3.unsat else 'unknown' if status == z3.unknown else 'rejected',
                  'verified': status == z3.unsat, 'recheck_status': str(status),
                  'seconds': time.perf_counter() - started, 'solver': 'z3-' + z3.get_version_string()}
    if status == z3.unknown:
        validation['reason_unknown'] = solver.reason_unknown()
    checked = deepcopy(certificate)
    checked['validation'] = deepcopy(validation)
    return {**validation, 'certificate': checked}


def add_core_cut(master, certificate, timeout_seconds=10, *, learn_prefix_frames=False):
    """Recheck, then install OR(not core equalities) on a hero/action master.

    The supplied ``validation`` field is never trusted. Unknown, mismatched or
    tampered certificates leave the master's solver completely unchanged.
    Optional prefix implications use only complete hero/activity facts obtained
    during this independent deterministic replay. SMT cores learn no frames.
    """
    if type(learn_prefix_frames) is not bool:
        raise ValueError('learn_prefix_frames must be Boolean')
    started = time.perf_counter()
    metrics = {'prefix_frames_learned': 0, 'prefix_max_depth': None}
    try:
        metadata = certificate['metadata']
        if type(master.horizon) is not int or master.horizon != metadata['horizon']:
            raise ValueError('master/certificate horizon mismatch')
    except (TypeError, KeyError, ValueError, AttributeError) as exc:
        return {'status': 'rejected', 'verified': False, 'added': False,
                'reason': str(exc), **metrics}
    checked_frames = [] if learn_prefix_frames else None
    validation = _check_certificate(certificate, timeout_seconds,
                                    checked_frames=checked_frames)
    if not validation['verified']:
        return {**validation, 'added': False, **metrics}
    predicates = []
    for kind, t, *values in certificate['core']:
        if kind == 'action':
            predicate = master.actions[t][KEYS.index(values[0])]
        elif kind == 'active':
            predicate = master.frames[t].active == values[0]
        else:
            hero, x, y = values
            frame = master.frames[t]
            predicate = z3.And(getattr(frame, hero + '_x') == x,
                               getattr(frame, hero + '_y') == y)
        predicates.append(predicate)
    expression = z3.Or(*[z3.Not(p) for p in predicates])
    implications = []
    if checked_frames:
        fixed = {d[1]: d[2] for d in certificate['core'] if d[0] == 'action'}
        prefix = []
        for t, bard, druid, active in checked_frames:
            if t:
                # Replay stops at the first absent action, so every surviving
                # frame has exactly this contiguous guard, including absorption.
                prefix.append(master.actions[t - 1][KEYS.index(fixed[t - 1])])
            frame = master.frames[t]
            implications.append(z3.Implies(z3.And(*prefix), z3.And(
                frame.bard_x == bard[0], frame.bard_y == bard[1],
                frame.druid_x == druid[0], frame.druid_y == druid[1],
                frame.active == active)))
        # Keep all mutation after validation and construction. In particular,
        # partial replay facts cannot escape when the opt-in budget expires.
        if time.perf_counter() - started >= timeout_seconds:
            return {**validation, 'status': 'unknown', 'verified': False,
                    'added': False, 'reason_unknown': 'prefix learning budget exhausted',
                    **metrics}
        metrics = {'prefix_frames_learned': len(implications),
                   'prefix_max_depth': checked_frames[-1][0]}
    master.solver.add(expression, *implications)
    return {**validation, 'added': True, 'expression': expression, **metrics}
