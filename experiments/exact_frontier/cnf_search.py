#!/usr/bin/env python3
"""Convert the experimental III-14 model to CNF and search with PySAT.

Run under an external wall-clock timeout. UNSAT concerns this model and the
specified restrictions only; this tool does not certify original-game bounds.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import z3
from pysat.formula import CNF
from pysat.solvers import Solver

try:
    from . import iii14_smt as room
except ImportError:  # Direct script execution.
    import iii14_smt as room


def compile_cnf(solver):
    goal = z3.Goal()
    goal.add(*solver.assertions())
    # Keep frame variables. solve-eqs inlines large transition expressions and
    # can make preprocessing much slower. These tactics retain action aliases.
    transformed = z3.Then('simplify', 'propagate-values', 'card2bv',
                          'propagate-values', 'bit-blast', 'tseitin-cnf')(goal)
    if len(transformed) != 1:
        raise ValueError('Expected exactly one conjunctive SAT subgoal')
    goal = transformed[0]
    # Reject residual arithmetic or other theory atoms: treating them as free
    # propositional variables would silently change the problem.
    if not z3.Probe('is-propositional')(goal):
        raise ValueError('CNF conversion left non-propositional atoms')
    dimacs = goal.dimacs()
    aliases = {name: int(number) for number, name in
               re.findall(r'^c (\d+) (action_\d+_[UDLRA])$', dimacs, re.M)}
    return dimacs, aliases


def solve(args):
    began = time.monotonic()
    out = Path(args.output)
    report = {'room': 'III-14', 'horizon': args.n, 'prefix': args.prefix,
              'guide': args.guide, 'distance': args.distance,
              'milestone': args.milestone, 'backend': args.backend,
              'proof_claim': None, 'status': 'building',
              'z3_version': z3.get_version_string(),
              'model_sha256': hashlib.sha256(Path(room.__file__).read_bytes()).hexdigest(),
              'backend_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}

    def save(**updates):
        report.update(updates, elapsed_seconds=round(time.monotonic()-began, 3))
        temporary = out.with_suffix(out.suffix+'.tmp')
        temporary.write_text(json.dumps(report, indent=2)+'\n')
        temporary.replace(out)
        print(json.dumps(updates), flush=True)

    save()
    source, actions, _ = room.build(args.n, args.prefix, args.guide,
                                   args.distance, construct_only=True,
                                   milestone=args.milestone)
    save(status='compiling', assertions=len(source.assertions()))
    dimacs, aliases = compile_cnf(source)
    cnf = CNF(from_string=dimacs)
    for i in range(args.n):
        for k in 'UDLRA':
            if f'action_{i}_{k}' not in aliases:
                raise ValueError(f'Missing action alias {i}/{k}')
    save(status='solving', variables=cnf.nv, clauses=len(cnf.clauses),
         cnf_sha256=hashlib.sha256(dimacs.encode()).hexdigest())
    if args.export_cnf:
        Path(args.export_cnf).write_text(dimacs)
    with Solver(name=args.backend, bootstrap_with=cnf.clauses) as backend:
        result = backend.solve()
        save(status='sat' if result else 'unsat', statistics=backend.accum_stats())
        if result:
            positive = {v for v in backend.get_model() if v > 0}
            route = ''
            for i in range(args.n):
                selected = [k for k in 'UDLRA' if aliases[f'action_{i}_{k}'] in positive]
                if len(selected) != 1:
                    raise ValueError(f'Non one-hot action at frame {i}')
                route += selected[0]
            oracle = room.PuzzleScriptOracle(3, room.ROWS)
            if args.milestone:
                route += 'RRRUU'
            for i, k in enumerate(route):
                alive, won = oracle.step(k)
                if not alive:
                    raise ValueError('SAT witness lost a hero in local replay')
                if won:
                    route = route[:i+1]
                    break
            if not won or not room.validate(route):
                raise ValueError('SAT witness failed local transition validation')
            save(route=route, length=len(route), local_replay='passed',
                 original_replay='required')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--n', type=int, default=47)
    p.add_argument('--prefix', default='')
    p.add_argument('--guide', default='')
    p.add_argument('--distance', type=int)
    p.add_argument('--milestone', action='store_true')
    p.add_argument('--backend', default='cadical195')
    p.add_argument('--export-cnf')
    p.add_argument('--output', required=True)
    p.add_argument('--wall-timeout-seconds', type=float, default=150)
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = p.parse_args()
    if args.worker:
        solve(args)
    else:
        began = time.monotonic()
        try:
            run = subprocess.run([sys.executable, __file__, *sys.argv[1:], '--worker'],
                                 timeout=args.wall_timeout_seconds)
            if run.returncode:
                raise RuntimeError(f'Worker exited with status {run.returncode}')
        except (subprocess.TimeoutExpired, RuntimeError) as exc:
            output = Path(args.output)
            report = json.loads(output.read_text()) if output.exists() else {}
            report.update(last_stage=report.get('status'),
                          status='unknown' if isinstance(exc, subprocess.TimeoutExpired) else 'error',
                          reason='wall_timeout' if isinstance(exc, subprocess.TimeoutExpired) else str(exc),
                          wall_budget_seconds=args.wall_timeout_seconds,
                          elapsed_seconds=round(time.monotonic()-began, 3), proof_claim=None)
            output.write_text(json.dumps(report, indent=2)+'\n')
            print(json.dumps(report), flush=True)
            if not isinstance(exc, subprocess.TimeoutExpired):
                raise SystemExit(1)
