import os
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from experiments.exact_frontier.certified_sat import solve_cnf, verify_assignment

CHECKER = Path(os.environ.get('DRAT_TRIM', '/tmp/soko-drat-trim/drat-trim'))


@unittest.skipUnless(importlib.util.find_spec('pysat'), 'install the optional exact-frontier requirements')
class CertifiedSatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cnf = self.root / 'problem.cnf'

    def test_sat_and_corrupted_assignment(self):
        self.cnf.write_text('p cnf 2 2\n1 2 0\n-1 2 0\n')
        result = solve_cnf(self.cnf, self.root / 'out', 10)
        self.assertEqual(result['status'], 'sat', result)
        self.assertEqual(result['checker_status'], 'assignment_verified')
        assignment = Path(result['assignment_path'])
        self.assertTrue(verify_assignment(self.cnf, assignment))
        assignment.write_text('[1, -2]')
        self.assertFalse(verify_assignment(self.cnf, assignment))

    @unittest.skipUnless(CHECKER.is_file(), 'set DRAT_TRIM to a drat-trim executable')
    def test_checked_unsat_and_corrupt_proof(self):
        self.cnf.write_text('p cnf 2 4\n1 2 0\n1 -2 0\n-1 2 0\n-1 -2 0\n')
        result = solve_cnf(self.cnf, self.root / 'out', 10, CHECKER)
        self.assertEqual(result['status'], 'unsat', result)
        self.assertEqual(result['checker_status'], 'verified')
        proof = Path(result['proof_path'])
        proof.write_text('')
        checked = subprocess.run([str(CHECKER), str(self.cnf), str(proof)], capture_output=True, text=True)
        self.assertFalse(checked.returncode == 0 and 's VERIFIED' in checked.stdout)

    @unittest.skipUnless(CHECKER.is_file(), 'set DRAT_TRIM to a drat-trim executable')
    def test_zero_variable_empty_clause_checked(self):
        self.cnf.write_text('p cnf 0 1\n0\n')
        result = solve_cnf(self.cnf, self.root / 'out', 10, CHECKER)
        self.assertEqual(result['status'], 'unsat', result)
        self.assertEqual(result['checker_status'], 'verified')
        self.assertIn('c trivial UNSAT', result['checker_output'])

    def test_unchecked_unsat(self):
        self.cnf.write_text('p cnf 1 2\n1 0\n-1 0\n')
        result = solve_cnf(self.cnf, self.root / 'out', 10)
        self.assertEqual((result['status'], result['checker_status']), ('unsat', 'unchecked'))

    def test_timeout_kills_worker(self):
        self.cnf.write_text('p cnf 1 1\n1 0\n')
        created = []
        popen = subprocess.Popen
        def record(*args, **kwargs):
            child = popen([sys.executable, '-c', 'import time; time.sleep(10)'], **kwargs)
            created.append(child)
            return child
        with patch('subprocess.Popen', side_effect=record):
            result = solve_cnf(self.cnf, self.root / 'out', 0.2)
        self.assertEqual(result['status'], 'unknown', result)
        self.assertTrue(created)
        self.assertTrue(all(child.poll() is not None for child in created))


if __name__ == '__main__':
    unittest.main()
