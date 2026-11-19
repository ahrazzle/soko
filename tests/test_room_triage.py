import copy
import json
import unittest
from datetime import datetime, timezone

from experiments.portfolio.triage import CATALOG, build_report

OBSERVED = '2026-11-12T12:00:00+00:00'


def report(snapshot, catalog, exclusions=()):
    return build_report(json.dumps(snapshot).encode(), json.dumps(catalog).encode(), OBSERVED, exclusions)


class RoomTriageTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(CATALOG.read_bytes())
        rooms = [dict(part=r['part'], room=r['room'], id=i + 1, length=10,
                      known=10, lower=10) for i, r in enumerate(self.catalog['rooms'])]
        rooms[-1].update(length=20, known=20, lower=5)
        rooms[-2].update(length=20, known=20, lower=10)
        self.snapshot = {'rooms': rooms, 'log': []}

    def test_complete_screening_and_exclusion(self):
        result = report(self.snapshot, self.catalog, ['III-21'])
        self.assertEqual(len(result['rows']), 66)
        self.assertEqual(len({r['room'] for r in result['rows']}), 66)
        self.assertEqual([r['room'] for r in result['ranked_queue']], ['III-22'])
        self.assertEqual(result['excluded_rows'][0]['exclusion_reason'], 'user exclusion')
        self.assertEqual(result['rows'][0]['reported_gap'], 0)
        self.assertIn('not an optimality certificate', result['semantics']['reported_gap'])
        self.assertIn('not locally certified', result['status'])

    def test_invalid_snapshot_fails_closed(self):
        for mutation in ('missing', 'duplicate', 'unknown', 'bool', 'float', 'negative', 'inverted', 'bad_id', 'duplicate_id'):
            with self.subTest(mutation=mutation):
                snapshot = copy.deepcopy(self.snapshot)
                row = snapshot['rooms'][0]
                if mutation == 'missing': snapshot['rooms'].pop()
                elif mutation == 'duplicate': snapshot['rooms'][-1] = copy.deepcopy(row)
                elif mutation == 'unknown': row['room'] = 23
                elif mutation == 'bool': row['lower'] = True
                elif mutation == 'float': row['length'] = 10.0
                elif mutation == 'negative': row['lower'] = -1
                elif mutation == 'inverted': row['lower'] = 11
                elif mutation == 'bad_id': row['id'] = False
                elif mutation == 'duplicate_id': row['id'] = snapshot['rooms'][1]['id']
                with self.assertRaises(ValueError): report(snapshot, self.catalog)

    def test_known_field_and_proofs_do_not_change_report(self):
        expected = report(self.snapshot, self.catalog)
        self.snapshot['rooms'][0]['known'] = 999
        del self.snapshot['rooms'][1]['known']
        self.snapshot['proofs'] = [{'part': 3, 'room': 22, 'lower': 999999, 'status': 'certified'}]
        actual = report(self.snapshot, self.catalog)
        self.assertEqual(actual['rows'], expected['rows'])
        self.assertEqual(actual['ranked_queue'], expected['ranked_queue'])

    def test_catalog_and_exclusions_validated(self):
        self.catalog['rooms'][0]['id'] = 'I-2'
        with self.assertRaises(ValueError): report(self.snapshot, self.catalog)
        with self.assertRaises(ValueError): report(self.snapshot, json.loads(CATALOG.read_bytes()), ['III-23'])

    def test_age_only_from_matching_unambiguous_current_entry(self):
        row = self.snapshot['rooms'][0]
        timestamp = int(datetime(2026, 11, 12, 11, tzinfo=timezone.utc).timestamp())
        entry = dict(id=row['id'], part=row['part'], room=row['room'], length=row['length'], at=timestamp, previous=row['length'])
        self.snapshot['log'] = [entry]
        self.assertEqual(report(self.snapshot, self.catalog)['rows'][0]['incumbent_entry_age_seconds'], 3600)
        for change in ({'id': 999}, {'room': 2}, {'length': 9}, {'at': timestamp + 7200}, {'at': 'invalid'}, {'at': True}):
            with self.subTest(change=change):
                self.snapshot['log'] = [dict(entry, **change)]
                self.assertIsNone(report(self.snapshot, self.catalog)['rows'][0]['incumbent_entry_age_seconds'])
        for conflict in (dict(entry, at=timestamp - 1), dict(entry, room=2)):
            self.snapshot['log'] = [entry, conflict]
            self.assertIsNone(report(self.snapshot, self.catalog)['rows'][0]['incumbent_entry_age_seconds'])

    def test_strict_json_rejects_duplicate_keys_and_nonfinite_numbers(self):
        good = json.dumps(self.snapshot).encode()
        catalog = CATALOG.read_bytes()
        for invalid in (b'{"rooms": [], "rooms": []}', b'{"proofs": [{"x": 1, "x": 2}]}',
                        b'{"x": NaN}', b'{"x": Infinity}', b'{"x": -Infinity}',
                        b'{"x": 1e400}', b'{"x": -1e400}'):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError): build_report(invalid, catalog, OBSERVED)
                with self.assertRaises(ValueError): build_report(good, invalid, OBSERVED)


if __name__ == '__main__':
    unittest.main()
