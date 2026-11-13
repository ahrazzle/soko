import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import z3

from experiments.causal_solver import search


class CausalSearchTests(unittest.TestCase):
    def test_local_replay_stops_at_first_win(self):
        route = search.causal.reference_assignment(50)['route']
        result = search.local_replay(route)
        self.assertEqual(result['status'], 'won')
        self.assertEqual(result['step'], 48)
        self.assertEqual(result['route'], route[:48])

    def test_unknown_exact_never_adds_cut(self):
        assignment = search.causal.reference_assignment(48)
        assignment['route'] = 'U' + assignment['route'][1:]
        solver = z3.Solver()
        dummy = SimpleNamespace(solver=solver)
        refiner = SimpleNamespace(check=lambda *a, **kw: {'status': 'unknown'})
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'result.json'
            with (patch.object(search, 'source_hashes', return_value={'source': 'hash'}),
                  patch.object(search.causal, 'build_master', return_value=dummy),
                  patch.object(search.causal, 'validate_assignment'),
                  patch.object(search.universal_flow, 'build_universe', return_value=object()),
                  patch.object(search.cut_certificate, 'check_universe_spec', return_value='universe'),
                  patch.object(search.global_master, 'decode', return_value=assignment),
                  patch.object(search, 'local_replay', return_value={'status': 'not_won'}),
                  patch.object(search.refinement, 'ExactRefiner', return_value=refiner),
                  patch.object(search.refinement, 'add_core_cut') as add_cut,
                  patch.object(search.causal, 'evaluate_flow', return_value={'flow_value': 9}) as flow):
                result = search.run(48, 5, output=target, phase_order='flow-first',
                                    cut_selection='sink_minimal')
            self.assertEqual(result['status'], 'unknown')
            self.assertEqual(result['cuts'], [])
            self.assertEqual(len(result['candidates']), 1)
            add_cut.assert_not_called()
            self.assertEqual(flow.call_args.kwargs['cut_selection'], 'sink_minimal')
            self.assertEqual(result['cut_selection'], 'sink_minimal')
            self.assertFalse(result['learn_prefix_frames'])
            self.assertEqual(json.loads(target.read_text())['status'], 'unknown')

    def test_hard_budget_ends_build_and_writes_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'out.json'
            result = search.run_bounded({'horizon': 48, 'budget_seconds': 0.01,
                                        'cut_selection': 'sink_minimal'}, output)
            self.assertEqual(result['status'], 'unknown')
            self.assertEqual(result['reason'], 'hard wall budget exhausted')
            self.assertTrue(output.exists())
            self.assertFalse(result['record_claim'])
            self.assertEqual(result['cut_selection'], 'sink_minimal')

    def test_worker_uses_absolute_html_and_executable_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'out.json'

            def launch(command, **kwargs):
                options = json.loads(command[command.index('--options') + 1])
                self.assertEqual(options['html'], str(Path('relative.html').resolve()))
                self.assertEqual(options['chromium'], str(Path('bin/chromium').resolve()))
                self.assertTrue(options['learn_prefix_frames'])
                output.write_text(json.dumps({'status': 'unknown', 'source_hashes_before': {'s': 'h'}}))
                return SimpleNamespace(wait=lambda timeout: 0, returncode=0)

            with patch.object(search, 'source_hashes', return_value={'s': 'h'}), \
                 patch.object(search.subprocess, 'Popen', side_effect=launch):
                result = search.run_bounded({'horizon': 1, 'budget_seconds': 1,
                    'html': 'relative.html', 'chromium': 'bin/chromium',
                    'learn_prefix_frames': True}, output)
            self.assertEqual(result['status'], 'unknown')


if __name__ == '__main__':
    unittest.main()
