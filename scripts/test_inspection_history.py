"""History identity, append/reload, atomic-write and baseline isolation tests."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fingerprint_store import FingerprintStore
from history_store import HistoryStore
from inspection_event import build_inspection_record, InspectionSession
from splice_tracker import SpliceTracker, LOOP_LENGTH, SPLICES

ROOT = Path(__file__).resolve().parents[1]


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'data', prefix='history-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'history'
        self.events = SpliceTracker().advance(LOOP_LENGTH * 4)
        self.records = [build_inspection_record(event, i) for i, event in enumerate(self.events, 1)]

    def test_mixed_order_isolation_and_unequal_counts(self):
        with HistoryStore(self.path) as store:
            for record in self.records[:7]:
                saved = store.append(record)
                for sensor in ('camera', 'profile', 'tension'):
                    self.assertEqual(saved[sensor], record[sensor])
                self.assertEqual(saved['mfl']['channels'], record['mfl']['channels'])
            self.assertEqual(store.counts(), {'S01': 2, 'S02': 2, 'S03': 1, 'S04': 1, 'S05': 1})
            for splice in SPLICES:
                rows = store.records(splice)
                self.assertTrue(all(r['splice_id'] == splice for r in rows))
                self.assertEqual([r['inspection_sequence'] for r in rows], list(range(1, len(rows) + 1)))
                document = json.loads((self.path / f'{splice}.json').read_text())
                self.assertEqual(document['inspections'], rows)
                self.assertEqual(document['inspection_count'], len(rows))
                self.assertNotIn('fingerprint', document)

    def test_restart_retains_every_value_and_appends(self):
        with HistoryStore(self.path) as store:
            for record in self.records[:15]:
                store.append(record)
            before = {s: store.records(s) for s in SPLICES}
            self.assertEqual(len(before['S03']), 3)
        with HistoryStore(self.path) as loaded:
            self.assertEqual(loaded.loaded_count, 15)
            for splice in SPLICES:
                self.assertEqual(loaded.records(splice), before[splice])
                self.assertTrue(all(len(r['mfl']['channels']) == 24 for r in loaded.records(splice)))
            session = InspectionSession(loaded.last_inspection_number)
            event = self.events[4]  # S03, in the restarted simulation's first lap.
            current = session.start(event, event['time_s'])
            self.assertEqual(current['inspection_id'], 'INS-0016')
            session.advance(event['time_s'] + 1)
            saved = loaded.append(current)
            self.assertEqual(saved['inspection_sequence'], 4)
            self.assertEqual(saved['run_sequence'], 2)
            self.assertEqual(saved['timestamp_s'], loaded.time_offset + event['time_s'])
            self.assertGreater(saved['timestamp_s'], before['S03'][-1]['timestamp_s'])
            self.assertEqual(loaded.records('S03')[:-1], before['S03'])
            for sensor in ('camera', 'mfl', 'profile', 'tension'):
                self.assertEqual(saved[sensor]['inspection_id'], 'INS-0016')
        with HistoryStore(self.path) as again:
            self.assertEqual(again.records('S03')[-1], saved)

    def test_reject_duplicate_and_out_of_order_without_changes(self):
        with HistoryStore(self.path) as store:
            store.append(self.records[4])
            path = self.path / 'S03.json'
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                store.append(self.records[4])
            earlier = build_inspection_record(self.events[0], 99)
            with self.assertRaises(ValueError):
                store.append(earlier)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(sum(store.counts().values()), 1)

    def test_reject_invalid_identity_or_missing_channels(self):
        with HistoryStore(self.path) as store:
            for mutation in ('identity', 'channels', 'incomplete'):
                record = deepcopy(self.records[0])
                if mutation == 'identity': record['splice_id'] = 'S04'
                elif mutation == 'channels': record['mfl']['channels'].pop()
                else: record['status'] = 'SCANNING'
                with self.assertRaises(ValueError):
                    store.append(record)
            self.assertEqual(list(self.path.glob('*.json')), [])

    def test_copy_isolation(self):
        with HistoryStore(self.path) as store:
            source = deepcopy(self.records[0])
            result = store.append(source)
            before = store.records('S02')
            source['mfl']['channels'][0] = 999
            result['camera']['score'] = 999
            exposed = store.records('S02')
            exposed[0]['profile']['samples'][0] = 999
            self.assertEqual(store.records('S02'), before)

    def test_failed_publication_preserves_old_file_and_memory(self):
        with HistoryStore(self.path) as store:
            store.append(self.records[0])
            path = self.path / 'S02.json'
            before = path.read_bytes()
            with patch('history_store.os.replace', side_effect=OSError('simulated write failure')):
                with self.assertRaises(OSError):
                    store.append(self.records[5])
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(store.counts()['S02'], 1)
            self.assertEqual(list(self.path.glob('*.tmp')), [])

    def test_one_writer_and_restart_lock_release(self):
        with HistoryStore(self.path) as first:
            with self.assertRaises(RuntimeError):
                HistoryStore(self.path)
            first.append(self.records[0])
        with HistoryStore(self.path) as second:
            self.assertEqual(second.loaded_count, 1)

    def test_corrupt_existing_history_is_not_replaced(self):
        with HistoryStore(self.path) as store:
            store.append(self.records[0])
        path = self.path / 'S02.json'
        document = json.loads(path.read_text())
        document['inspections'][0]['splice_id'] = 'S03'
        path.write_text(json.dumps(document))
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            HistoryStore(self.path)
        self.assertEqual(path.read_bytes(), before)

    def test_history_never_modifies_baselines(self):
        baseline_path = self.root / 'baseline'
        baseline = FingerprintStore(baseline_path)
        for record in self.records[:5]:
            baseline.remember(record)
        before = {p.name: (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
                  for p in baseline_path.glob('*.json')}
        with HistoryStore(self.path, minimum_inspection_number=5) as store:
            for record in self.records[5:]:
                store.append(record)
        with HistoryStore(self.path) as restarted:
            self.assertEqual(restarted.loaded_count, 15)
        after = {p.name: (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
                 for p in baseline_path.glob('*.json')}
        self.assertEqual(after, before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
