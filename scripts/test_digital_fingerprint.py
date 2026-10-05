"""Baseline completeness, persistence and create-once tests; no scan comparison."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from fingerprint_store import FingerprintStore
from inspection_event import build_inspection_record
from digital_fingerprint import validate_fingerprint
from splice_tracker import SpliceTracker, LOOP_LENGTH, SPLICES

ROOT = Path(__file__).resolve().parents[1]


class FingerprintTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'data', prefix='fingerprint-test-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        events = SpliceTracker().advance(LOOP_LENGTH)
        self.records = {e['splice']: build_inspection_record(e, i) for i, e in enumerate(events, 1)}

    def test_five_complete_snapshots_and_restart(self):
        store = FingerprintStore(self.path)
        for splice, record in self.records.items():
            fp, created = store.remember(record)
            self.assertTrue(created)
            validate_fingerprint(fp)
            self.assertEqual(fp['splice_id'], splice)
            self.assertEqual(fp['created_from_inspection'], record['inspection_id'])
            self.assertEqual(fp['mfl']['channel_count'], 24)
            self.assertEqual(len(fp['mfl']['channels']), 24)
            for sensor in ('camera','profile','tension'):
                self.assertEqual(fp[sensor], record[sensor])
            self.assertEqual(fp['mfl']['channels'], record['mfl']['channels'])
            self.assertEqual(json.loads((self.path / f'{splice}.json').read_text()), fp)
        restarted = FingerprintStore(self.path)
        self.assertEqual(restarted.loaded_count, 5)
        for splice in SPLICES:
            self.assertEqual(restarted.get(splice), store.get(splice))

    def test_later_different_inspection_cannot_overwrite_s03(self):
        store = FingerprintStore(self.path)
        fp, _ = store.remember(self.records['S03'])
        path = self.path / 'S03.json'
        before, mtime = path.read_bytes(), path.stat().st_mtime_ns
        later = copy.deepcopy(self.records['S03'])
        later['inspection_id'] = 'INS-9000'
        later['camera']['score'] = .1
        later['mfl']['channels'] = [.9] * 24
        later['profile']['deviation'] = 9
        later['tension']['score'] = .2
        for instance in (store, FingerprintStore(self.path)):
            actual, created = instance.remember(later)
            self.assertFalse(created)
            self.assertEqual(actual, fp)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(path.stat().st_mtime_ns, mtime)

    def test_copies_do_not_alias_source_or_returned_values(self):
        store = FingerprintStore(self.path)
        record = self.records['S03']
        fp, _ = store.remember(record)
        original = copy.deepcopy(fp)
        record['mfl']['channels'][0] = 99
        fp['camera']['score'] = 99
        exposed = store.get('S03')
        exposed['profile']['samples'][0] = 99
        self.assertEqual(store.get('S03'), original)

    def test_invalid_first_record_does_not_create_baseline(self):
        for bad in ('incomplete', 'unhealthy', 'missing_channel', 'mismatched_id'):
            record = copy.deepcopy(self.records['S03'])
            if bad == 'incomplete': record['status'] = 'SCANNING'
            elif bad == 'unhealthy': record['camera']['score'] = .1
            elif bad == 'missing_channel': record['mfl']['channels'].pop()
            else: record['tension']['inspection_id'] = 'INS-9000'
            with self.assertRaises(ValueError):
                FingerprintStore(self.path).remember(record)
            self.assertFalse((self.path / 'S03.json').exists())

    def test_concurrent_store_preserves_existing_file(self):
        first, second = FingerprintStore(self.path), FingerprintStore(self.path)
        original, _ = first.remember(self.records['S03'])
        events = SpliceTracker().advance(LOOP_LENGTH * 2)
        event = [e for e in events if e['splice'] == 'S03'][-1]
        later = build_inspection_record(event, 10)
        fp, created = second.remember(later)
        self.assertFalse(created)
        self.assertEqual(fp, original)
        self.assertEqual(list(self.path.glob('*.tmp')), [])

    def test_corrupt_existing_file_is_preserved(self):
        path = self.path / 'S03.json'
        path.write_text('{broken')
        with self.assertRaises(ValueError):
            FingerprintStore(self.path)
        self.assertEqual(path.read_text(), '{broken')


if __name__ == '__main__':
    unittest.main(verbosity=2)
