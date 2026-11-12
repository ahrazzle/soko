"""Interface contracts are checked with a deterministic original-engine stand-in."""
import json
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from soko_mcp.__main__ import main
from soko_mcp.play import play
from soko_mcp.server import dispatch_tool_call, handle_jsonrpc_message
from tests.test_mcp_server import McpStdioClient


def fake_replay(part, room, route, **kwargs):
    win = route.index('A') + 1 if 'A' in route else None
    death = route.index('D') + 1 if 'D' in route else None
    return {'part': part, 'room': room, 'route': route, 'source_pins': {'html_sha256': 'pinned'},
            'first_win': win, 'first_death': death, 'steps_executed': len(route),
            'valid_winning_route': win == len(route) and death is None,
            'final_ascii': [route], 'final_objects': [len(route)]}


class PlayCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.original = patch('soko_mcp.original.replay', side_effect=fake_replay)
        self.replay = self.original.start()
        self.addCleanup(self.original.stop)

    def test_checkpoint_roundtrip_undo_reset_and_exact_reconstruction(self):
        initial = play(room_id='I-1', keys='RR')
        saved = json.loads(json.dumps(initial['checkpoint']))
        result = play(checkpoint=saved, keys='U')
        self.assertEqual(result['route'], 'RRU')
        self.assertEqual(result['replay']['final_objects'], [3])
        self.assertEqual(self.replay.call_args_list[-1].args, (1, 1, 'RRU'))
        undo = play(checkpoint=result['checkpoint'], action='undo')
        self.assertEqual(undo['route'], 'RR')
        reset = play(checkpoint=undo['checkpoint'], action='reset')
        self.assertEqual(reset['route'], '')
        self.assertEqual(reset['current_key_count'], 0)

    def test_terminal_is_observable_but_cannot_be_extended(self):
        for key in ('A', 'D'):
            end = play(room_id='I-1', keys=key)
            self.assertTrue(end['terminal'])
            self.assertEqual(play(checkpoint=end['checkpoint'], action='observe')['route'], key)
            with self.assertRaisesRegex(ValueError, 'terminal'):
                play(checkpoint=end['checkpoint'], keys='R')
            self.assertEqual(play(checkpoint=end['checkpoint'], action='undo')['route'], '')
        with self.assertRaisesRegex(ValueError, 'terminal'):
            play(room_id='I-1', keys='ARR')

    def test_rejects_tampering_room_mismatch_and_source_change(self):
        checkpoint = play(room_id='I-1', keys='R')['checkpoint']
        with self.assertRaisesRegex(ValueError, 'room_id'):
            play(room_id='I-2', checkpoint=checkpoint)
        tampered = dict(checkpoint, route='RR')
        with self.assertRaisesRegex(ValueError, 'integrity'):
            play(checkpoint=tampered)
        self.replay.side_effect = lambda *a, **k: dict(fake_replay(*a, **k), source_pins={'html_sha256': 'different'})
        with self.assertRaisesRegex(ValueError, 'source pins'):
            play(checkpoint=checkpoint)

    def test_unsettled_or_partially_executed_replay_cannot_create_a_checkpoint(self):
        for changes in ({'again_limit_hit': True}, {'steps_executed': 0}):
            with self.subTest(changes=changes):
                self.replay.side_effect = lambda *a, **k: dict(fake_replay(*a, **k), **changes)
                with self.assertRaisesRegex(ValueError, 'again limit|complete route'):
                    play(room_id='I-1', keys='RR')

    def test_cli_checkpoint_files_resume(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(StringIO()):
            checkpoint = str(Path(tmp) / 'checkpoint.json')
            self.assertEqual(main(['play', '--room', 'II-2', '--keys', 'RR', '--checkpoint-out', checkpoint]), 0)
            self.assertEqual(main(['play', '--checkpoint-in', checkpoint, '--keys', 'U', '--checkpoint-out', checkpoint]), 0)
            self.assertEqual(json.loads(Path(checkpoint).read_text())['route'], 'RRU')

    def test_original_tool_prefix_baseline_and_error_transport(self):
        result = dispatch_tool_call('soko_replay_original', {'room_id': 'III-20', 'route': ''})
        self.assertFalse(result['valid_winning_route'])
        self.assertEqual(result['room'], 20)
        message = handle_jsonrpc_message({'id': 1, 'method': 'tools/call', 'params': {
            'name': 'soko_replay_original', 'arguments': {'room_id': 'I-1', 'route': '', 'baseline': True}}})
        self.assertTrue(message['result']['isError'])

    def test_local_cli_custom_instance_and_original_runtime_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            instance = Path(tmp) / 'instance.json'
            instance.write_text(json.dumps({'part': 1, 'grid': ['#####', '#F.G#', '#####']}))
            with patch('soko_mcp.__main__.dispatch_tool_call', return_value={'scope': 'local'}) as dispatch, redirect_stdout(StringIO()):
                self.assertEqual(main(['verify', '--instance', str(instance), '--route', 'RR']), 0)
            self.assertEqual(dispatch.call_args.args, ('soko_verify_route', {'part': 1, 'grid': ['#####', '#F.G#', '#####'], 'route': 'RR'}))
        with patch('soko_mcp.__main__.dispatch_tool_call', side_effect=RuntimeError('Install playwright and Chromium')), redirect_stderr(StringIO()) as errors:
            self.assertEqual(main(['replay-original', '--room', 'I-1', '--route', '']), 2)
            self.assertIn('playwright', errors.getvalue())


class CatalogStdioTests(unittest.TestCase):
    def test_offline_catalog_and_new_tool_discovery(self):
        client = McpStdioClient()
        try:
            names = {tool['name'] for tool in client.request('tools/list')['result']['tools']}
            self.assertTrue({'soko_get_room', 'soko_replay_original', 'soko_play'}.issubset(names))
            result = client.request('tools/call', {'name': 'soko_list_rooms', 'arguments': {}})['result']['structuredContent']
            self.assertEqual(result['room_count'], 66)
            self.assertNotIn('fixtures', result)
            self.assertEqual(result['rooms'][0]['room_id'], 'I-1')
            self.assertNotIn('reference_route', result['rooms'][0])
            room = client.request('tools/call', {'name': 'soko_get_room', 'arguments': {'room_id': 'III-14'}})['result']['structuredContent']
            self.assertEqual((room['part'], room['room']), (3, 14))
            self.assertEqual(len(room['grid'][0]), 15)
        finally:
            client.close()
