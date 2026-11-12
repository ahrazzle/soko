"""Run a bounded SAT solve and independently validate its certificate.

Optional DRAT checker (pinned source):
  git clone https://github.com/marijnheule/drat-trim.git /tmp/soko-drat-trim
  git -C /tmp/soko-drat-trim checkout 2e3b2dc0ecf938addbd779d42877b6ed69d9a985
  gcc -D_DEFAULT_SOURCE -std=c99 -O2 /tmp/soko-drat-trim/drat-trim.c -o /tmp/soko-drat-trim/drat-trim
Pass that executable's path as proof_checker. Its SHA-256 is recorded in results.
Requires python-sat with CaDiCaL 1.9.5. The timeout is a single wall-clock
budget shared by solving and proof checking; certificate parsing and hashing
also consume the budget, although individual file I/O cannot be interrupted.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def verify_assignment(cnf_path: Path, assignment_path: Path) -> bool:
    """Strictly parse DIMACS and check every clause against a complete model."""
    try:
        model = json.loads(assignment_path.read_text())
        if not isinstance(model, list) or any(type(x) is not int or x == 0 for x in model):
            return False
        values = {}
        for lit in model:
            v = abs(lit)
            if v in values:
                return False
            values[v] = lit > 0
        header = None
        clause = []
        count = 0
        with cnf_path.open() as f:
            for line in f:
                fields = line.split()
                if not fields or fields[0] == 'c':
                    continue
                if fields[0] == 'p':
                    if header is not None or clause or count or len(fields) != 4 or fields[1] != 'cnf':
                        return False
                    header = (int(fields[2]), int(fields[3]))
                    if min(header) < 0:
                        return False
                    continue
                if header is None:
                    return False
                for field in fields:
                    lit = int(field)
                    if lit == 0:
                        count += 1
                        if not any(values.get(abs(x)) == (x > 0) for x in clause):
                            return False
                        clause.clear()
                    else:
                        if abs(lit) > header[0] or abs(lit) not in values:
                            return False
                        clause.append(lit)
        return header is not None and not clause and count == header[1] and all(1 <= x <= header[0] for x in values)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def _dimacs_clauses(cnf: Path):
    """Stream strictly validated clauses, retaining only the current clause."""
    header = None
    clause = []
    count = 0
    with cnf.open() as source:
        for line in source:
            fields = line.split()
            if not fields or fields[0] == 'c':
                continue
            if fields[0] == 'p':
                if header is not None or clause or count or len(fields) != 4 or fields[1] != 'cnf':
                    raise ValueError('invalid DIMACS header')
                header = (int(fields[2]), int(fields[3]))
                if min(header) < 0:
                    raise ValueError('negative DIMACS header count')
                continue
            if header is None:
                raise ValueError('missing DIMACS header')
            for field in fields:
                lit = int(field)
                if lit == 0:
                    count += 1
                    if count > header[1]:
                        raise ValueError('too many DIMACS clauses')
                    yield clause
                    clause = []
                elif abs(lit) > header[0]:
                    raise ValueError('DIMACS literal exceeds declared variables')
                else:
                    clause.append(lit)
    if header is None or clause or count != header[1]:
        raise ValueError('incomplete DIMACS formula')


def _worker(cnf: Path, assignment: Path, proof: Path) -> None:
    from pysat.solvers import Solver
    with Solver(name='cadical195', with_proof=True) as solver:
        for clause in _dimacs_clauses(cnf):
            solver.add_clause(clause)
        result = solver.solve()
        stats = solver.accum_stats()
        if result:
            assignment.write_text(json.dumps(solver.get_model()) + '\n')
        else:
            proof.write_text('\n'.join(solver.get_proof()) + '\n')
        print(json.dumps({'sat': result, 'stats': stats}))


def solve_cnf(cnf_path: Path, output_dir: Path, timeout_seconds: float,
              proof_checker: Path | None = None) -> dict:
    """Solve using a killable worker and return a JSON-serializable result.

    A status of ``unsat`` with checker_status ``unchecked`` is a solver claim,
    not a certified result. A checker rejection returns ``error``. A timeout
    during either solving or checking returns ``unknown`` and names the phase.
    Output directories should be dedicated to one call, not shared concurrently.
    """
    start = time.monotonic()
    result = {'status': 'error', 'cnf_sha256': None, 'assignment_path': None,
              'proof_path': None, 'proof_sha256': None, 'checker_status': 'not_run',
              'checker_sha256': None, 'stats': {}, 'phase': 'setup'}
    try:
        cnf_path = Path(cnf_path).resolve(strict=True)
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        assignment, proof = output_dir / 'assignment.json', output_dir / 'proof.drat'
        for path in (assignment, proof):
            path.unlink(missing_ok=True)
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError('timeout_seconds must be finite and positive')
        result['cnf_sha256'] = sha256(cnf_path)
        if proof_checker is not None:
            proof_checker = Path(proof_checker).resolve(strict=True)
            result['checker_sha256'] = sha256(proof_checker)
        def remaining():
            left = timeout_seconds - (time.monotonic() - start)
            if left <= 0:
                raise subprocess.TimeoutExpired('wall-clock budget', timeout_seconds)
            return left
        result['phase'] = 'solve'
        run = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker',
                              str(cnf_path), str(assignment), str(proof)],
                             capture_output=True, text=True, timeout=remaining())
        if run.returncode:
            raise RuntimeError('SAT worker failed: ' + run.stderr[-4000:])
        response = json.loads(run.stdout)
        result['stats'] = response['stats']
        if sha256(cnf_path) != result['cnf_sha256']:
            raise RuntimeError('CNF changed during solve')
        if response['sat'] is True:
            result['phase'] = 'verify_assignment'
            if not verify_assignment(cnf_path, assignment):
                raise RuntimeError('assignment rejected by independent clause checker')
            remaining()
            result.update(status='sat', assignment_path=str(assignment), checker_status='assignment_verified')
        elif response['sat'] is False:
            result.update(proof_path=str(proof), proof_sha256=sha256(proof), checker_status='unchecked')
            if proof_checker is not None:
                result['phase'] = 'check_proof'
                check = subprocess.run([str(proof_checker), str(cnf_path), str(proof)],
                                       capture_output=True, text=True, timeout=remaining())
                result['checker_output'] = (check.stdout + check.stderr)[-4000:]
                lines = set(check.stdout.splitlines())
                # Pinned drat-trim returns 1 after reporting a trivial input
                # empty clause: parse() returns UNSAT, but main leaves sts at
                # ERROR. Confirm the input independently before accepting that
                # one specific path; other nonzero exits remain failures.
                trivial = False
                if check.returncode == 1 and 'c trivial UNSAT' in lines and 's VERIFIED' in lines:
                    trivial = False
                    for clause in _dimacs_clauses(cnf_path):
                        if not clause:
                            trivial = True
                if not ((check.returncode == 0 and 's VERIFIED' in lines) or trivial):
                    result['checker_status'] = 'rejected'
                    raise RuntimeError('DRAT proof rejected by checker')
                result['checker_status'] = 'verified'
            remaining()
            result['status'] = 'unsat'
        else:
            raise RuntimeError('SAT worker returned an invalid result')
        result['phase'] = 'complete'
    except subprocess.TimeoutExpired:
        result['status'] = 'unknown'
        result['reason'] = 'wall-clock timeout'
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, json.JSONDecodeError) as exc:
        result['reason'] = str(exc)
    result['elapsed_seconds'] = time.monotonic() - start
    return result


if __name__ == '__main__':
    if len(sys.argv) == 5 and sys.argv[1] == '--worker':
        _worker(*(Path(arg) for arg in sys.argv[2:]))
    else:
        raise SystemExit('This module provides solve_cnf; --worker is internal.')
