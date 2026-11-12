"""Prevent restricted controls or unchecked solver reports becoming global bounds."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments.transport_relaxation import run


class TransportCertificateTests(unittest.TestCase):
    def report(self, kind, solver_result):
        with tempfile.TemporaryDirectory() as name:
            output = Path(name)
            (output / 'bundle.json').write_text('{}')
            bundle = {'kind': kind, 'horizon': 47}
            with patch.object(run, 'checked_bundle', return_value=bundle), \
                 patch.object(run, 'solve_cnf', return_value=solver_result):
                return run.solve(output)

    def test_checked_unsat_transfers_only_with_projection_obligations(self):
        result = self.report('global_transport_relaxation',
                             {'status': 'unsat', 'checker_status': 'verified'})
        self.assertEqual(result['status'], 'certified_abstract_cnf_unsat')
        self.assertEqual(result['abstract_lower_bound'], 48)
        self.assertIn('projection', result['conclusion'])
        self.assertFalse(result['original_game_equivalence_proved'])
        self.assertFalse(result['record_claim'])

    def test_unsat_reference_control_never_establishes_a_bound(self):
        result = self.report('reference_projection_control',
                             {'status': 'unsat', 'checker_status': 'verified'})
        self.assertEqual(result['status'], 'reference_control_rejected')
        self.assertNotIn('abstract_lower_bound', result)

    def test_unchecked_unsat_and_unknown_have_no_bound(self):
        for solver_result, status in [({'status': 'unsat', 'checker_status': 'unchecked'},
                                       'unverified_unsat_claim'),
                                      ({'status': 'unknown'}, 'unknown')]:
            with self.subTest(status=status):
                result = self.report('global_transport_relaxation', solver_result)
                self.assertEqual(result['status'], status)
                self.assertNotIn('abstract_lower_bound', result)

    def test_unchecked_sat_rejected_before_decoding(self):
        with self.assertRaisesRegex(ValueError, 'independently checked'):
            self.report('global_transport_relaxation',
                        {'status': 'sat', 'checker_status': 'unchecked'})

    def test_mutated_bundle_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            output = Path(name)
            cnf = output / 'problem.cnf'
            cnf.write_text('p cnf 0 1\n0\n')
            bundle = {'source_sha256': run.source_identity(),
                      'artifacts': {'problem.cnf': run.sha(cnf)}}
            (output / 'bundle.json').write_text(json.dumps(bundle))
            cnf.write_text('p cnf 0 0\n')
            with self.assertRaisesRegex(ValueError, 'artifact changed'):
                run.checked_bundle(output)


if __name__ == '__main__':
    unittest.main()
