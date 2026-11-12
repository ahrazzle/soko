"""Certificate boundary tests using deliberately small, synthetic bundles."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from experiments.exact_frontier import record_system as record


class RecordSystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        self.args = SimpleNamespace(output=self.out, timeout_seconds=3.25,
                                    proof_checker=None, html=None)
        self.write('problem.cnf', 'p cnf 5 1\n1 0\n')
        self.write_json('actions.json', {f'action_0_{k}': i + 1 for i, k in enumerate('UDLRA')})
        self.write_json('instance.json', {'part': 'III', 'room': 14, 'grid': []})
        self.write_json('frontier.json', {'rooms': []})
        self.write_json('calibration.json', {'status': 'passed'})
        self.bundle = {'room': 'III-14', 'mode': 'global_record_query',
                       'objective': {'first_win_at_or_before': 1, 'observed_record_length': 2},
                       'frontier_observation': {'mode': 'provided_snapshot'},
                       'search_restrictions': [], 'source_sha256': {},
                       'artifacts': {name: record.sha(self.out / name) for name in
                                     ('problem.cnf', 'actions.json', 'instance.json',
                                      'frontier.json', 'calibration.json')}}
        self.write_json('bundle.json', self.bundle)

    def write(self, name, value):
        (self.out / name).write_text(value)

    def write_json(self, name, value):
        self.write(name, json.dumps(value))

    def test_rejects_changed_cnf_and_aliases(self):
        for name in ('problem.cnf', 'actions.json'):
            with self.subTest(name=name):
                path = self.out / name
                original = path.read_text()
                path.write_text(original + ' ')
                with self.assertRaisesRegex(ValueError, 'Bundle artifact changed'):
                    record.checked_bundle(self.out)
                path.write_text(original)

    def test_rejects_incompatible_current_source(self):
        self.bundle['source_sha256'] = {'experiments/exact_frontier/record_system.py': '0' * 64}
        self.write_json('bundle.json', self.bundle)
        with self.assertRaisesRegex(ValueError, 'Bundle source changed'):
            record.checked_bundle(self.out)

    def test_rejects_invalid_one_hot_actions(self):
        aliases = json.loads((self.out / 'actions.json').read_text())
        for assignment in ([], [1, 2]):
            with self.subTest(assignment=assignment):
                with self.assertRaisesRegex(ValueError, 'one-hot'):
                    record.decode_route(assignment, aliases, 1)

    def solve_with(self, result):
        with patch('experiments.exact_frontier.certified_sat.solve_cnf', return_value=result) as solve:
            report = record.solve(self.args)
        solve.assert_called_once_with(self.out / 'problem.cnf', self.out / 'sat', 3.25,
                                      proof_checker=None)
        return report

    def test_unchecked_sat_never_reaches_route_decoding(self):
        with patch('experiments.exact_frontier.certified_sat.solve_cnf',
                   return_value={'status': 'sat', 'checker_status': 'unchecked'}):
            with self.assertRaisesRegex(ValueError, 'no independently checked assignment'):
                record.solve(self.args)

    def test_timeout_propagates_without_record_claim(self):
        report = self.solve_with({'status': 'unknown', 'reason': 'wall-clock timeout', 'phase': 'solve'})
        self.assertEqual(report['status'], 'unknown')
        self.assertEqual(report['solver']['reason'], 'wall-clock timeout')
        self.assertFalse(report['public_submission'])
        self.assertNotIn('route', report)

    def test_checked_unsat_is_conditioned_on_model(self):
        report = self.solve_with({'status': 'unsat', 'checker_status': 'verified'})
        self.assertEqual(report['status'], 'certified_cnf_unsat')
        self.assertFalse(report['semantic_equivalence_proved'])
        self.assertIn('encoded formula', report['conclusion'].lower())
        self.assertIn('not formally proved', report['conclusion'].lower())

    def test_unchecked_unsat_must_not_claim_proven_model_unsat(self):
        report = self.solve_with({'status': 'unsat', 'checker_status': 'unchecked'})
        self.assertEqual(report['status'], 'unverified_unsat_claim')
        self.assertNotIn('No route within this model', report.get('conclusion', ''))

    def test_historical_snapshot_route_is_not_advertised_as_current_record(self):
        assignment = self.out / 'assignment.json'
        assignment.write_text('[1, -2, -3, -4, -5]')
        result = {'status': 'sat', 'checker_status': 'assignment_verified', 'assignment_path': str(assignment)}
        with patch('experiments.exact_frontier.record_system.first_win', return_value='U'), \
             patch('experiments.exact_frontier.record_system.replay',
                   return_value={'valid_winning_route': True, 'first_win': 1}):
            report = self.solve_with(result)
        self.assertEqual(report['status'], 'verified_route')
        self.assertEqual(report['comparison_scope'], 'provided historical snapshot only')
        self.assertNotIn('saved_inputs', report)
        self.assertNotIn('record_length_at_result', report)


if __name__ == '__main__':
    unittest.main()
