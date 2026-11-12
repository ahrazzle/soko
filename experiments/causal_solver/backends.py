"""Solver adapters. A completed SAT result must pass an independent model check."""
from __future__ import annotations

import time


def check_clauses(clauses, assignment, nv=None):
    if nv is None:
        nv = max((abs(lit) for clause in clauses for lit in clause), default=0)
    if (any(type(lit) is not int or lit == 0 or abs(lit) > nv for lit in assignment)
            or len(assignment) != nv or {abs(lit) for lit in assignment} != set(range(1, nv + 1))):
        return False
    values = set(assignment)
    return all(any(lit in values for lit in clause) for clause in clauses)


def check_witness(route, mode, room):
    """Replay only the represented prefix: exact goal states absorb inputs."""
    oracle = room.PuzzleScriptOracle(3, room.ROWS)
    checked = route
    won = False
    for i, key in enumerate(route):
        alive, won = oracle.step(key)
        if not alive: raise ValueError('witness lost a hero in concrete replay')
        if won and mode == 'goal':
            checked = route[:i + 1]
            break
    if mode == 'goal' and not won: raise ValueError('goal witness did not win')
    if not room.validate(checked): raise ValueError('witness failed independent concrete replay')
    return checked


def run(solver, actions, backend, pins, checkpoint, mode='goal'):
    import z3
    from experiments.exact_frontier import iii14_smt as room
    timings = {'compilation_seconds': 0.0, 'solve_seconds': 0.0,
               'witness_seconds': 0.0, 'certificate_seconds': 0.0}
    extra = {'certificate_status': 'not_requested'}
    if backend == 'z3':
        checkpoint('solving', timings)
        start = time.monotonic(); result = solver.check(); timings['solve_seconds'] = time.monotonic() - start
        status = str(result)
        route = None
        if status == 'sat':
            start = time.monotonic(); model = solver.model()
            if not all(z3.is_true(model.eval(a, model_completion=True)) for a in solver.assertions()):
                raise ValueError('SMT assignment failed assertion check')
            route = ''.join('UDLRA'[next(i for i, a in enumerate(frame)
                                         if z3.is_true(model.eval(a, model_completion=True)))] for frame in actions)
            timings['witness_seconds'] = time.monotonic() - start
        if status == 'unknown': extra['reason'] = solver.reason_unknown()
    else:
        from pysat.formula import CNF
        from experiments.exact_frontier.cnf_search import compile_cnf
        checkpoint('compiling', timings)
        start = time.monotonic(); dimacs, aliases = compile_cnf(solver); cnf = CNF(from_string=dimacs)
        timings['compilation_seconds'] = time.monotonic() - start
        extra.update(variables=cnf.nv, clauses=len(cnf.clauses))
        checkpoint('solving', timings)
        start = time.monotonic()
        if backend == 'pysat':
            from pysat.solvers import Solver
            with Solver(name='cadical195', bootstrap_with=cnf.clauses) as engine:
                result = engine.solve(); assignment = engine.get_model() if result else None
            status = 'sat' if result else 'unsat'
        elif backend == 'cpsat':
            from ortools.sat.python import cp_model
            model = cp_model.CpModel(); variables = [None] + [model.NewBoolVar('v%d' % i) for i in range(1, cnf.nv + 1)]
            for clause in cnf.clauses:
                model.AddBoolOr([variables[lit] if lit > 0 else variables[-lit].Not() for lit in clause])
            engine = cp_model.CpSolver(); engine.parameters.num_search_workers = 1
            timings['compilation_seconds'] += time.monotonic() - start
            checkpoint('solving', timings); start = time.monotonic()
            result = engine.Solve(model)
            status = ('sat' if result in (cp_model.OPTIMAL, cp_model.FEASIBLE) else
                      'unsat' if result == cp_model.INFEASIBLE else 'unknown')
            assignment = ([i if engine.Value(variables[i]) else -i for i in range(1, cnf.nv + 1)]
                          if status == 'sat' else None)
            extra['cp_status'] = engine.StatusName(result)
        else:
            raise ValueError('unknown backend')
        timings['solve_seconds'] = time.monotonic() - start
        route = None
        if status == 'sat':
            start = time.monotonic()
            if not check_clauses(cnf.clauses, assignment, cnf.nv):
                raise ValueError('CNF assignment failed independent clause check')
            positive = set(assignment)
            route_chars = []
            for i, frame in enumerate(actions):
                selected = [key for key in 'UDLRA' if aliases.get(f'action_{i}_{key}') in positive]
                if not selected and i < len(pins): selected = [pins[i]]
                if len(selected) != 1: raise ValueError('Missing or non-one-hot action aliases')
                route_chars.extend(selected)
            route = ''.join(route_chars)
            timings['witness_seconds'] = time.monotonic() - start
    if route is not None:
        start = time.monotonic()
        checked_route = check_witness(route, mode, room)
        timings['witness_seconds'] += time.monotonic() - start
        extra.update(route=checked_route, model_actions=route, witness_check='cnf_and_local_replay' if backend != 'z3' else 'assertions_and_local_replay', original_replay='required_for_win_claim')
    return status, timings, extra
