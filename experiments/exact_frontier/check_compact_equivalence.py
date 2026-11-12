"""Check compact/legacy III-14 transitions over arbitrary symbolic states.

This proves an encoding refactor relative to the legacy model, not equivalence
of either model to PuzzleScript. Each selected-action difference is compiled
to CNF, solved, and optionally checked by an independent DRAT checker.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import z3

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.exact_frontier import iii14_smt as legacy
from experiments.exact_frontier import iii14_compact as compact
from experiments.exact_frontier import cnf_search, certified_sat
from experiments.exact_frontier.certified_sat import sha256, solve_cnf
from experiments.exact_frontier.cnf_search import compile_cnf


def symbolic_state(prefix='equivalence'):
    return (z3.BitVec(prefix + '_wall', legacy.N),
            z3.BitVec(prefix + '_crate', legacy.N),
            z3.BitVec(prefix + '_bard', legacy.N),
            z3.BitVec(prefix + '_druid', legacy.N),
            z3.Bool(prefix + '_active'),
            z3.BitVec(prefix + '_notes', legacy.N),
            z3.Bool(prefix + '_opened'))


def difference(key: str, candidate=compact.trans):
    """A SAT witness is any input state where the implementations disagree.

    No reachable-state, occupancy, hero-count, or note invariant is assumed.
    Checking all five fixed selections covers all exactly-one action inputs.
    Legality and all next-state components are compared even on losing inputs.
    """
    if key not in 'UDLRA' or len(key) != 1:
        raise ValueError('expected one action from UDLRA')
    state = symbolic_state()
    actions = [z3.BoolVal(key == k) for k in 'UDLRA']
    old_next, old_legal = legacy.trans(state, key)
    new_next, new_legal = candidate(state, actions)
    if len(new_next) != len(old_next):
        raise ValueError('candidate state shape differs')
    return z3.Or(old_legal != new_legal,
                 *[old != new for old, new in zip(old_next, new_next)])


def check(output: Path, timeout_seconds=60, proof_checker: Path | None = None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError('use an empty output directory')
    report = {
        'scope': 'arbitrary-state one-step equivalence to the legacy III-14 model',
        'original_game_equivalence_proved': False,
        'certificate_scope': 'the five transformed difference CNFs are unsatisfiable',
        'trusted_transformations': 'Z3 symbolic expression construction, simplification and bit-blasting; DRAT checks only the resulting CNF',
        'state_assumptions': [],
        'action_assumption': 'exactly one of UDLRA; all five cases checked',
        'z3_version': z3.get_version_string(),
        'source_sha256': {str(Path(m.__file__).name): sha256(Path(m.__file__))
                          for m in (legacy, compact, cnf_search, certified_sat)},
        'checker_source_sha256': sha256(Path(__file__)),
        'cases': {},
        'status': 'running',
    }
    def save():
        temporary = output / 'summary.tmp'
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(output / 'summary.json')
    save()
    for key in 'UDLRA':
        case = output / key
        case.mkdir()
        began = time.monotonic()
        solver = z3.Solver()
        solver.add(difference(key))
        dimacs, _ = compile_cnf(solver)
        cnf = case / 'difference.cnf'
        cnf.write_text(dimacs)
        compile_seconds = time.monotonic() - began
        result = solve_cnf(cnf, case, timeout_seconds, proof_checker)
        result['compile_seconds'] = compile_seconds
        report['cases'][key] = result
        save()
        if result['status'] == 'sat':
            report['status'] = 'counterexample'
            save()
            return report
        if result['status'] != 'unsat':
            report['status'] = 'inconclusive'
            save()
            return report
    checked = all(r['checker_status'] == 'verified' for r in report['cases'].values())
    report['status'] = 'encoding_equivalence_checked' if checked else 'unchecked_encoding_equivalence'
    save()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout-seconds', type=float, default=60,
                        help='per-case solve-and-certificate budget; compilation is additional')
    parser.add_argument('--proof-checker', type=Path)
    args = parser.parse_args()
    result = check(args.output, args.timeout_seconds, args.proof_checker)
    print(json.dumps(result, indent=2))
    if result['status'] not in ('encoding_equivalence_checked', 'unchecked_encoding_equivalence'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
