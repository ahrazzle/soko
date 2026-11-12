"""Parity rejection tests use synthetic reports; no browser or network needed."""
from copy import deepcopy
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from soko_mcp import original
from soko_mcp.catalog import get_room
from soko_mcp.oracle import PuzzleScriptOracle
from tools.check_corpus import (GLYPHS, compare_room, digest, project_local,
                                project_original, validate_original_report)


def resign(report):
    report['trajectory_sha256'] = digest(report['frames'])
    report['certificate_sha256'] = digest({k: v for k, v in report.items() if k != 'certificate_sha256'})
    return report


def fixture():
    """A small self-consistent report for identity/rejection tests, not evidence."""
    room = get_room('I-1')
    names = ['background'] + sorted(set(GLYPHS.values()) | {'note'})
    ids = {name: index for index, name in enumerate(names)}
    stride = (len(names) + 31) // 32
    sim = PuzzleScriptOracle(room['part'], room['grid'])

    def words():
        layers = project_local(sim)
        data = []
        for x in range(sim.w):
            for y in range(sim.h):
                cell = [0] * stride
                for name in ['background'] + layers[y][x]:
                    cell[ids[name] >> 5] |= 1 << (ids[name] & 31)
                data.extend(cell)
        return data

    url, html_hash, source_hash = original.SOURCES[1]
    checker_hash = hashlib.sha256(Path(original.__file__).read_bytes()).hexdigest()
    report = {'part': 1, 'room': 1, 'width': room['width'], 'height': room['height'],
        'compiled_level_index': room['compiled_level_index'], 'stride': stride, 'object_ids': ids,
        'source_url': url, 'html_sha256': html_hash, 'puzzlescript_source_sha256': source_hash,
        'checker_sha256': checker_hash, 'route': room['reference_route'],
        'route_len': len(room['reference_route']),
        'route_sha256': hashlib.sha256(room['reference_route'].encode()).hexdigest(),
        'initial_objects': words(), 'frames': [], 'first_win': len(room['reference_route']),
        'first_death': None, 'restarts': 0, 'again_limit_hit': False, 'valid_winning_route': True}
    for step, key in enumerate(room['reference_route'], 1):
        alive, won = sim.step(key)
        report['frames'].append({'step': step, 'key': key, 'winning': won, 'dead': not alive,
                                 'restarts': 0, 'objects': words()})
    report['final_objects'] = words()
    report['steps_executed'] = len(report['frames'])
    report['instance_sha256'] = digest({key: report[key] for key in
        ('html_sha256', 'part', 'room', 'width', 'height', 'stride', 'initial_objects')})
    report['source_pins'] = {key: report[key] for key in
        ('html_sha256', 'puzzlescript_source_sha256', 'checker_sha256', 'source_url')}
    return room, resign(report)


class CorpusParityTests(unittest.TestCase):
    def test_same_final_state_does_not_hide_seeded_intermediate_divergence(self):
        room, report = fixture()
        dual = {'differential_match': True, 'trajectory_digest_match': True,
                'triple_oracle_checked': True, 'valid_winning_route': True}
        with patch('tools.check_corpus.verify_route_dual', return_value=dual):
            self.assertTrue(compare_room(room, report)['passed'])
            changed = deepcopy(report)
            # Shift only frame one's fighter; later frames and final state agree.
            ids, height = changed['object_ids'], changed['height']
            old = (3 * height + 2) * changed['stride'] + (ids['fighter'] >> 5)
            new = (4 * height + 2) * changed['stride'] + (ids['fighter'] >> 5)
            changed['frames'][0]['objects'][old] &= ~(1 << (ids['fighter'] & 31))
            changed['frames'][0]['objects'][new] |= 1 << (ids['fighter'] & 31)
            resign(changed)
            result = compare_room(room, changed)
        self.assertFalse(result['passed'])
        self.assertEqual(result['first_divergence']['step'], 1)
        self.assertEqual(result['mismatched_frames'], 1)
        self.assertEqual(result['original_projected_frame_sha256'][-1], result['local_projected_frame_sha256'][-1])
        self.assertEqual(result['first_divergence']['coordinate_differences'][0]['x'], 3)

    def test_stale_wrong_room_route_source_and_checker_caches_are_rejected(self):
        room, report = fixture()
        validate_original_report(report, room)
        for key, changed in [('room', 2), ('part', 2), ('route', 'L' * 8),
                             ('route_sha256', '0' * 64), ('checker_sha256', '0' * 64),
                             ('html_sha256', '0' * 64), ('compiled_level_index', 0)]:
            with self.subTest(key=key):
                stale = deepcopy(report)
                stale[key] = changed
                resign(stale)
                with self.assertRaisesRegex(ValueError, 'mismatch'):
                    validate_original_report(stale, room)
        altered = deepcopy(report)
        altered['checked_at'] = 'altered without updating certificate'
        with self.assertRaisesRegex(ValueError, 'certificate hash mismatch'):
            validate_original_report(altered, room)

    def test_unknown_persistent_objects_and_bits_are_never_silently_ignored(self):
        _, report = fixture()
        unknown = deepcopy(report)
        unknown['object_ids']['mystery_actor'] = 31
        with self.assertRaisesRegex(ValueError, 'Unknown original persistent objects'):
            project_original(unknown, unknown['initial_objects'])
        unknown = deepcopy(report)
        unknown['initial_objects'][0] |= 1 << 31
        with self.assertRaisesRegex(ValueError, 'Unknown original object bits'):
            project_original(unknown, unknown['initial_objects'])

    def test_incomplete_or_reordered_frames_are_rejected(self):
        room, report = fixture()
        for mutate in (lambda r: r['frames'].pop(), lambda r: r['frames'][0].update(key='L')):
            with self.subTest(mutate=mutate):
                changed = deepcopy(report)
                mutate(changed)
                resign(changed)
                with self.assertRaises(ValueError):
                    validate_original_report(changed, room)

    def test_open_doors_and_note_overlaps_are_compared_at_their_coordinates(self):
        _, report = fixture()
        ids = report['object_ids']
        words = [0] * (report['width'] * report['height'] * report['stride'])
        index = (2 * report['height'] + 1) * report['stride']
        for name in ('note', 'yellowopen', 'fighter'):
            words[index + (ids[name] >> 5)] |= 1 << (ids[name] & 31)
        projected = project_original(report, words)
        self.assertEqual(projected[1][2], ['fighter', 'note', 'yellowopen'])
        self.assertEqual(projected[2][1], [])
