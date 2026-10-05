"""Progression contracts, unchanged detector, and persistent-data integrity."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from anomaly_detector import compare_inspection
from degradation_scenario import apply_degradation, ProgressiveScenario, trend_point, validate_scenario
from fingerprint_store import FingerprintStore
from history_store import HistoryStore
from inspection_event import build_inspection_record, validate_record
from inspection_history import validate_observation
from splice_tracker import SpliceTracker, SPLICES, LOOP_LENGTH

ROOT = Path(__file__).resolve().parents[1]


class ProgressionTests(unittest.TestCase):
    def setUp(self):
        self.store = FingerprintStore(ROOT/'data/baseline', read_only=True)
        self.events = SpliceTracker().advance(LOOP_LENGTH)
        self.records = {e['splice']: build_inspection_record(e, i) for i, e in enumerate(self.events, 100)}
        self.baseline = self.store.get('S03')
        self.states = [apply_degradation(self.records['S03'], self.baseline, level) for level in range(6)]
        self.results = [compare_inspection(r, self.baseline) for r in self.states]

    def test_level_zero_matches_original_healthy_values(self):
        state = self.states[0]
        self.assertEqual(state['mfl']['channels'], self.baseline['mfl']['channels'])
        self.assertEqual(state['profile']['samples'], self.baseline['profile']['samples'])
        self.assertEqual(self.results[0]['anomaly_score'], 0)

    def test_deterministic_and_inputs_unmodified(self):
        before = deepcopy(self.records); baseline = deepcopy(self.baseline)
        for level in range(6):
            self.assertEqual(apply_degradation(before['S03'], baseline, level), self.states[level])
        self.assertEqual(before, self.records)
        self.assertEqual(baseline, self.baseline)

    def test_non_target_splices_remain_exactly_healthy(self):
        for splice in ('S01','S02','S04','S05'):
            for level in range(6):
                r = apply_degradation(self.records[splice], self.store.get(splice), level)
                self.assertEqual(r, self.records[splice]); validate_record(r)
                self.assertEqual(compare_inspection(r, self.store.get(splice))['severity'], 'NORMAL')

    def test_24_channels_at_every_level(self):
        for record in self.states:
            self.assertEqual(len(record['mfl']['channels']), 24)
            validate_observation(record)

    def test_only_localized_mfl_region_changes_strictly(self):
        for channel in range(24):
            values = [r['mfl']['channels'][channel] for r in self.states]
            if 8 <= channel <= 12:
                self.assertTrue(all(a < b for a,b in zip(values,values[1:])))
            else:
                self.assertEqual(len(set(values)), 1)
        self.assertEqual(self.results[-1]['affected_channels'], [f'MFL{i:02d}' for i in range(9,14)])
        self.assertEqual(self.results[-1]['mfl_max_channel_index'], 11)

    def test_camera_strictly_decreases(self):
        values = [r['camera']['score'] for r in self.states]
        self.assertTrue(all(a > b for a,b in zip(values,values[1:])))

    def test_profile_strictly_increases(self):
        values = [r['profile']['deviation'] for r in self.states]
        self.assertTrue(all(a < b for a,b in zip(values,values[1:])))

    def test_tension_strictly_decreases(self):
        values = [r['tension']['score'] for r in self.states]
        self.assertTrue(all(a > b for a,b in zip(values,values[1:])))

    def test_all_detector_deviations_and_score_strictly_increase(self):
        for key in ('anomaly_score','mfl_deviation','camera_deviation','profile_deviation','tension_deviation'):
            values = [r[key] for r in self.results]
            self.assertTrue(all(a < b for a,b in zip(values,values[1:])), key)

    def test_existing_detector_severity_progression(self):
        self.assertEqual([r['severity'] for r in self.results],
                         ['NORMAL','NORMAL','WATCH','WARNING','WARNING','CRITICAL'])
        self.assertLess(self.results[-1]['anomaly_score'], 1)

    def test_context_encoder_and_ids_are_preserved(self):
        for r in self.states:
            for key in ('inspection_id','splice_id','simulation_time_s','encoder','encoder_ticks','position_m'):
                self.assertEqual(r[key], self.records['S03'][key])
            validate_observation(r)

    def test_invalid_level_metadata_and_cross_splice_rejected(self):
        for level in (-1,6,True,1.5,float('nan')):
            with self.assertRaises(ValueError): apply_degradation(self.records['S03'], self.baseline,level)
        with self.assertRaises(ValueError): apply_degradation(self.records['S03'],self.store.get('S02'),0)
        metadata = deepcopy(self.states[2]['synthetic_scenario']); metadata['stage']='HEALTHY'
        with self.assertRaises(ValueError): validate_scenario(metadata)

    def test_progress_only_on_target_and_saturates(self):
        scenario = ProgressiveScenario(self.store)
        levels = []
        for _ in range(8):
            scenario(self.records['S01'])
            levels.append(scenario(self.records['S03'])['synthetic_scenario']['level'])
        self.assertEqual(levels, [0,1,2,3,4,5,5,5])
        self.assertEqual(ProgressiveScenario(self.store)(self.records['S03'])['synthetic_scenario']['level'],0)

    def test_progression_independent_of_global_inspection_counter(self):
        event = next(e for e in self.events if e['splice']=='S03')
        for index in (1,100,10000):
            for level in range(6):
                r=apply_degradation(build_inspection_record(event,index),self.baseline,level)
                self.assertEqual(compare_inspection(r,self.baseline)['anomaly_score'],self.results[level]['anomaly_score'])

    def test_history_reload_append_only_and_trend_references(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'data',prefix='progression-test-') as directory:
            scenario=ProgressiveScenario(self.store)
            events=SpliceTracker().advance(7*LOOP_LENGTH)
            with HistoryStore(Path(directory)/'history') as history:
                for i,e in enumerate(events[:5],1): history.append(build_inspection_record(e,i))
                old={s:history.records(s) for s in SPLICES}
                for i,e in enumerate(events[5:],6):
                    saved=history.append(scenario(build_inspection_record(e,i)))
                    if saved['splice_id']=='S03':
                        result=compare_inspection(saved,self.baseline)
                        point=trend_point(result)
                        self.assertEqual(point['inspection_id'],saved['inspection_id'])
                        self.assertEqual(point['anomaly_score'],result['anomaly_score'])
                        self.assertNotIn('mfl',point)
                for splice in SPLICES: self.assertEqual(history.records(splice)[:1],old[splice])
            with HistoryStore(Path(directory)/'history') as history:
                self.assertEqual(history.loaded_count,35)
                self.assertEqual([r['synthetic_scenario']['level'] for r in history.records('S03')[1:]],list(range(6)))

    def test_real_baseline_hash_mtime_and_preexisting_history_unchanged(self):
        before=json.loads((ROOT/'data/phase6_before.json').read_text())
        for name,expected in before['baseline'].items():
            p=ROOT/'data/baseline'/name
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),expected['sha256'])
            self.assertEqual(p.stat().st_mtime_ns,expected['mtime_ns'])
        for splice,doc in before['history'].items():
            now=json.loads((ROOT/'data/history'/f'{splice}.json').read_text())['inspections']
            self.assertEqual(now[:len(doc['inspections'])],doc['inspections'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
