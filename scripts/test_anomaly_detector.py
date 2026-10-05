"""Deterministic comparison, exact severity boundaries and data integrity tests."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from anomaly_detector import compare_inspection, severity
from digital_fingerprint import from_inspection
from fingerprint_store import FingerprintStore
from history_store import HistoryStore
from inspection_event import build_inspection_record
from sensor_scenario import apply_scenario
from phase5_config import WEIGHTS, MFL_BUMP, CAMERA_DROP_SPAN, PROFILE_INCREASE_SPAN_MM, TENSION_DROP_SPAN
from splice_tracker import SpliceTracker, LOOP_LENGTH, SPLICES

ROOT = Path(__file__).resolve().parents[1]


class AnomalyTests(unittest.TestCase):
    def setUp(self):
        self.events = SpliceTracker().advance(LOOP_LENGTH)
        self.records = {e['splice']: build_inspection_record(e, i) for i, e in enumerate(self.events, 1)}
        self.baselines = {s: from_inspection(r) for s, r in self.records.items()}

    def result(self, splice='S03', name='degradation', level=1):
        return compare_inspection(apply_scenario(self.records[splice], name, level), self.baselines[splice])

    def test_exact_healthy_scan_is_zero(self):
        self.assertEqual(self.result(name='healthy')['anomaly_score'], 0)
        self.assertEqual(self.result(name='healthy')['severity'], 'NORMAL')

    def test_s03_change_is_significantly_higher(self):
        result = self.result()
        self.assertGreater(result['anomaly_score'], self.result(name='healthy')['anomaly_score'] + .3)
        self.assertEqual(result['severity'], 'WARNING')
        self.assertLess(result['anomaly_score'], .7)

    def test_other_splices_and_healthy_variation_stay_normal(self):
        for i in (30, 50, 100, 1000):
            for event in self.events:
                record = build_inspection_record(event, i)
                splice = record['splice_id']
                if splice != 'S03':
                    self.assertEqual(apply_scenario(record)['mfl']['channels'], record['mfl']['channels'])
                    self.assertEqual(compare_inspection(apply_scenario(record), self.baselines[splice])['severity'], 'NORMAL')
                else:
                    self.assertEqual(compare_inspection(apply_scenario(record), self.baselines[splice])['severity'], 'WARNING')
                self.assertEqual(compare_inspection(apply_scenario(record, 'healthy'), self.baselines[splice])['severity'], 'NORMAL')

    def test_baseline_requires_24_channels(self):
        for size in (23, 25):
            baseline = deepcopy(self.baselines['S03'])
            baseline['mfl']['channels'] = [0.025] * size
            with self.assertRaises(ValueError): compare_inspection(self.records['S03'], baseline)

    def test_current_requires_24_channels(self):
        for size in (23, 25):
            record = deepcopy(self.records['S03'])
            record['mfl']['channels'] = [0.025] * size
            with self.assertRaises(ValueError): compare_inspection(record, self.baselines['S03'])

    def test_affected_channels_are_measured(self):
        result = self.result()
        self.assertEqual(result['affected_channels'], [f'MFL{i:02d}' for i in MFL_BUMP])
        self.assertEqual(result['mfl_max_channel_index'], 11)
        self.assertAlmostEqual(result['mfl_max_channel_deviation'], .080)
        unrelated = deepcopy(self.records['S01'])
        unrelated['mfl']['channels'][2] += .1
        measured = compare_inspection(unrelated, self.baselines['S01'])
        self.assertEqual(measured['mfl_max_channel_index'], 3)
        self.assertIn('MFL03', measured['affected_channels'])

    def test_camera_drop_contributes(self):
        record = deepcopy(self.records['S03']); record['camera']['score'] -= .1
        result = compare_inspection(record, self.baselines['S03'])
        self.assertAlmostEqual(result['camera_deviation'], .1 / CAMERA_DROP_SPAN)
        self.assertAlmostEqual(result['anomaly_score'], WEIGHTS['camera'] * .5)

    def test_profile_increase_contributes(self):
        record = deepcopy(self.records['S03'])
        record['profile']['samples'] = [v + .05 for v in record['profile']['samples']]
        record['profile']['deviation'] = max(record['profile']['samples'])
        result = compare_inspection(record, self.baselines['S03'])
        self.assertAlmostEqual(result['profile_deviation'], .05 / PROFILE_INCREASE_SPAN_MM)
        self.assertAlmostEqual(result['anomaly_score'], WEIGHTS['profile'] * .5)

    def test_tension_drop_contributes(self):
        record = deepcopy(self.records['S03']); record['tension']['score'] -= .1
        result = compare_inspection(record, self.baselines['S03'])
        self.assertAlmostEqual(result['tension_deviation'], .1 / TENSION_DROP_SPAN)
        self.assertAlmostEqual(result['anomaly_score'], WEIGHTS['tension'] * .5)

    def test_documented_weighted_formula(self):
        result = self.result()
        self.assertEqual(result['weights'], {'mfl': .5, 'camera': .2, 'profile': .2, 'tension': .1})
        expected = sum(WEIGHTS[name] * result[name + '_deviation'] for name in WEIGHTS)
        self.assertAlmostEqual(result['anomaly_score'], expected)
        self.assertAlmostEqual(sum(result['weighted_contributions'].values()), expected)

    def test_exact_severity_boundaries(self):
        for score, label in ((0,'NORMAL'),(.199999,'NORMAL'),(.2,'WATCH'),(.399999,'WATCH'),
                             (.4,'WARNING'),(.699999,'WARNING'),(.7,'CRITICAL'),(1,'CRITICAL')):
            self.assertEqual(severity(score), label)
        for value in (-.01, 1.01, float('nan')):
            with self.assertRaises(ValueError): severity(value)

    def test_determinism_and_no_input_mutation(self):
        before = deepcopy(self.records)
        fingerprints = deepcopy(self.baselines)
        self.assertEqual(self.result(), self.result())
        self.assertEqual(self.records, before)
        self.assertEqual(self.baselines, fingerprints)
        self.assertEqual(self.result(level=0)['anomaly_score'], 0)

    def test_same_splice_required(self):
        with self.assertRaises(ValueError): compare_inspection(self.records['S03'], self.baselines['S04'])

    def test_mfl_scale_invariance_and_zero_floor(self):
        record = apply_scenario(self.records['S03'])
        baseline = deepcopy(self.baselines['S03'])
        expected = compare_inspection(record, baseline)['mfl_deviation']
        record['mfl']['channels'] = [v*10 for v in record['mfl']['channels']]
        baseline['mfl']['channels'] = [v*10 for v in baseline['mfl']['channels']]
        self.assertAlmostEqual(compare_inspection(record, baseline)['mfl_deviation'], expected)
        baseline['mfl']['channels'] = [0]*24
        record['mfl']['channels'] = [0]*24
        self.assertEqual(compare_inspection(record, baseline)['mfl_deviation'], 0)

    def test_nonfinite_data_rejected(self):
        record = deepcopy(self.records['S03']); record['mfl']['channels'][0] = float('nan')
        with self.assertRaises(ValueError): compare_inspection(record, self.baselines['S03'])
        with self.assertRaises(ValueError): apply_scenario(self.records['S03'], level=float('inf'))

    def test_baseline_and_old_history_integrity(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'data', prefix='anomaly-test-') as directory:
            root = Path(directory)
            store = FingerprintStore(root/'baseline')
            for record in self.records.values(): store.remember(record)
            before = {p.name:(hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns) for p in (root/'baseline').glob('*.json')}
            readonly = FingerprintStore(root/'baseline', read_only=True)
            with self.assertRaises(PermissionError): readonly.remember(self.records['S03'])
            with HistoryStore(root/'history') as history:
                for record in self.records.values(): history.append(record)
                old = {s:history.records(s) for s in SPLICES}
            with HistoryStore(root/'history') as history:
                for i,event in enumerate(self.events,6):
                    changed = apply_scenario(build_inspection_record(event,i))
                    saved = history.append(changed)
                    compare_inspection(saved, readonly.get(saved['splice_id']))
                for splice in SPLICES: self.assertEqual(history.records(splice)[:-1], old[splice])
            with HistoryStore(root/'history') as reloaded:
                self.assertEqual(reloaded.loaded_count, 10)
                self.assertTrue(all(len(r['mfl']['channels'])==24 for r in reloaded.records('S03')))
            after = {p.name:(hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns) for p in (root/'baseline').glob('*.json')}
            self.assertEqual(after,before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
