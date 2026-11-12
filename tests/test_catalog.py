"""Pinned corpus integrity, message indexing, and offline loader boundaries."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from soko_mcp.catalog import get_room, list_rooms, load_catalog
from tools.import_catalog import SOURCE_FILES, cached_response, extract_source, parse_levels


class CatalogTests(unittest.TestCase):
    def test_all_original_grids_and_canonical_ids_are_preserved(self):
        catalog = load_catalog()
        expected = [f'{part}-{room}' for part in ('I', 'II', 'III') for room in range(1, 23)]
        self.assertEqual(list(catalog), expected)
        grids = {key: room['grid'] for key, room in catalog.items()}
        digest = hashlib.sha256(json.dumps(grids, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(digest, '1f957d169ee2800004c336d2b4fc36c80b9d463438a66cd41a0432ab758df8bd')
        for room in catalog.values():
            self.assertEqual(room['height'], len(room['grid']))
            self.assertTrue(all(len(row) == room['width'] for row in room['grid']))
            self.assertEqual(room['coordinates']['transform'], 'identity')
            self.assertEqual(room['source']['html_sha256'], SOURCE_FILES[room['part'] - 1][1])

    def test_compiled_indices_include_original_message_entries(self):
        expected = {
            1: [1, 3, 5, 7, 9, 10, 11, 13, 14, 15, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29],
            2: [3, 5, 6, 8, 10, 12, 13, 15, 17, 19, 20, 21, 23, 24, 26, 27, 28, 29, 30, 31, 32, 34],
            3: [3, 5, 6, 8, 10, 11, 12, 13, 14, 16, 17, 18, 21, 22, 23, 24, 25, 26, 27, 28, 30, 31],
        }
        for part, indices in expected.items():
            self.assertEqual([r['compiled_level_index'] for r in list_rooms() if r['part'] == part], indices)
        self.assertEqual(get_room('I-1')['tutorial_messages'], ['Walk to the exit.'])
        self.assertEqual(len(get_room('II-1')['tutorial_messages']), 3)
        self.assertEqual(len(get_room('III-1')['tutorial_messages']), 3)
        self.assertEqual(get_room('I-22')['grid'][1].count('F'), 1)
        self.assertEqual(sum(row.count(hero) for row in get_room('I-22')['grid'] for hero in 'FTW'), 3)

    def test_every_baseline_has_attribution_snapshot_and_valid_route(self):
        self.assertEqual(sum(len(r['reference_route']) for r in list_rooms()), 3063)
        for room in list_rooms():
            route, baseline, record = room['reference_route'], room['baseline'], room['frontier_observation']
            self.assertEqual(route, baseline['route'])
            self.assertEqual(len(route), baseline['length'])
            self.assertEqual(len(route), record['length'])
            self.assertEqual(room['frontier_record'], record['length'])
            self.assertTrue(set(route) <= set('UDLRA'))
            self.assertEqual(baseline['holder'], record['handle'])
            self.assertEqual(baseline['record_id'], record['id'])
            self.assertIn(f'/api/replay/{record["id"]}', baseline['url'])
            self.assertIn(f'record={record["id"]}', baseline['replay_url'])
            self.assertTrue(baseline['observed_at'].startswith('2026-11-12T'))
            self.assertEqual(len(baseline['response_sha256']), 64)
            self.assertEqual(room['shortest_known'], record['known'])
            self.assertEqual(room['proven_floor'], record['lower'])
            self.assertLessEqual(room['proven_floor'], room['shortest_known'])
            self.assertEqual(room['source']['author'], 'Jonah Ostroff')
            self.assertIn('Public accepted route', baseline['attribution'])

    def test_returned_metadata_is_independent(self):
        catalog = load_catalog()
        catalog['I-1']['grid'][0] = 'changed'
        catalog['I-1']['baseline']['holder'] = 'changed'
        listed = list_rooms()
        listed[0]['tutorial_messages'].append('changed')
        self.assertTrue(get_room('I-1')['grid'][0].startswith('#'))
        self.assertNotEqual(get_room('I-1')['baseline']['holder'], 'changed')
        self.assertNotIn('changed', get_room('I-1')['tutorial_messages'])
        with self.assertRaises(KeyError):
            get_room('III-23')

    def test_loader_and_offline_cache_never_download(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('network used')):
            self.assertEqual(len(load_catalog()), 66)
            with tempfile.TemporaryDirectory() as tmp:
                destination = Path(tmp) / 'source.html'
                with self.assertRaises(FileNotFoundError):
                    cached_response('https://invalid.test', destination, offline=True)
                destination.write_bytes(b'cached')
                self.assertEqual(cached_response('https://invalid.test', destination, offline=True), (b'cached', 'unknown'))

    def test_parser_associates_messages_without_counting_them_as_rooms(self):
        source = 'title Test\nLEVELS\n=======\nMessage first\n\nMessage second\n\n'
        source += '\n\n'.join('###\n#F#\n###' for _ in range(22))
        source += '\nMessage thanks\n'
        rooms, entries = parse_levels(source)
        self.assertEqual(rooms[0]['compiled_level_index'], 2)
        self.assertEqual(rooms[0]['tutorial_messages'], ['first', 'second'])
        self.assertEqual(rooms[1]['tutorial_messages'], [])
        self.assertEqual(entries[-1], {'message': 'thanks'})
        self.assertEqual(extract_source(('var sourceCode=' + json.dumps(source) + ';').encode()), source)
        with self.assertRaises(ValueError):
            parse_levels('LEVELS\n###\n###')
        with self.assertRaises(ValueError):
            extract_source(b'no source')
