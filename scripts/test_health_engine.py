"""Phase 7 fusion contracts using the unchanged scenario and detector."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from anomaly_detector import compare_inspection
from degradation_scenario import apply_degradation
from fingerprint_store import FingerprintStore
from history_store import HistoryStore
from inspection_event import build_inspection_record
from health_engine import evaluate_health, health_state, trend_direction, health_from_history
from splice_tracker import SpliceTracker, LOOP_LENGTH

ROOT=Path(__file__).resolve().parents[1]


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.store=FingerprintStore(ROOT/'data/baseline',read_only=True)
        self.records=[]; self.anomalies=[]; self.health=[]
        self.by_splice={s:[] for s in ('S01','S02','S03','S04','S05')}
        counts={s:0 for s in self.by_splice}
        for i,event in enumerate(SpliceTracker().advance(6*LOOP_LENGTH),91):
            splice=event['splice']; level=counts[splice]; counts[splice]+=1
            record=apply_degradation(build_inspection_record(event,i),self.store.get(splice),level)
            record.update(inspection_sequence=counts[splice],run_sequence=1,timestamp_s=record['simulation_time_s'])
            anomaly=compare_inspection(record,self.store.get(splice))
            result=evaluate_health(anomaly,self.by_splice[splice])
            self.by_splice[splice].append(anomaly)
            self.records.append(record); self.anomalies.append(anomaly); self.health.append(result)
        self.target=[r for r in self.health if r['splice_id']=='S03']

    def test_healthy_state_high_health(self):
        self.assertEqual(self.target[0]['health_score'],100)
        self.assertEqual(self.target[0]['health_state'],'HEALTHY')

    def test_severe_state_low_health(self):
        self.assertLess(self.target[-1]['health_score'],25)
        self.assertEqual(self.target[-1]['health_state'],'CRITICAL')

    def test_progression_health_strictly_decreases(self):
        values=[r['health_score'] for r in self.target]
        self.assertTrue(all(a>b for a,b in zip(values,values[1:])))
        self.assertEqual([r['health_state'] for r in self.target],['HEALTHY','STABLE','DEGRADING','DEGRADING','AT RISK','CRITICAL'])

    def test_historical_deterioration_lowers_equivalent_current_health(self):
        current=deepcopy(self.by_splice['S03'][3]); current['anomaly_score']=.5
        rising=deepcopy(self.by_splice['S03'][1:3])
        rising[0]['anomaly_score']=.2; rising[1]['anomaly_score']=.35
        stable=deepcopy(rising)
        for r in stable: r['anomaly_score']=.5
        self.assertLess(evaluate_health(current,rising)['health_score'],evaluate_health(current,stable)['health_score'])

    def test_stable_low_history_stays_stable(self):
        results=[r for r in self.health if r['splice_id']=='S01']
        self.assertTrue(all(r['trend_direction']=='STABLE' and r['trend_score']<.1 for r in results))

    def test_progressive_s03_trend_is_degrading(self):
        self.assertTrue(all(r['trend_direction']=='DEGRADING' for r in self.target[2:]))
        values=[r['trend_score'] for r in self.target]
        self.assertTrue(all(a<b for a,b in zip(values,values[1:])))

    def test_other_splices_high_health_stable_trend(self):
        for r in self.health:
            if r['splice_id']!='S03':
                self.assertEqual(r['trend_direction'],'STABLE')
                self.assertIn(r['health_state'],('HEALTHY','STABLE'))
                self.assertGreaterEqual(r['health_score'],90)

    def test_bounds_and_current_only_monotonicity(self):
        current=deepcopy(self.by_splice['S03'][0]); values=[]
        for score in (0,.1,.2,.4,.6,.8,1):
            current['anomaly_score']=score
            value=evaluate_health(current)['health_score']
            self.assertGreaterEqual(value,0); self.assertLessEqual(value,100); values.append(value)
        self.assertTrue(all(a>b for a,b in zip(values,values[1:])))

    def test_health_thresholds_exact(self):
        for value,state in ((0,'CRITICAL'),(24.999,'CRITICAL'),(25,'AT RISK'),(49.999,'AT RISK'),
                            (50,'DEGRADING'),(74.999,'DEGRADING'),(75,'STABLE'),(89.999,'STABLE'),(90,'HEALTHY'),(100,'HEALTHY')):
            self.assertEqual(health_state(value),state)
        for value in (-1,101,float('nan')):
            with self.assertRaises(ValueError): health_state(value)

    def test_direction_thresholds_exact(self):
        for deltas,direction in (([.04,.04],'DEGRADING'),([.03999,.03999],'STABLE'),
                                 ([-.04,-.04],'IMPROVING'),([-.03999,-.03999],'STABLE'),([], 'STABLE'),([.2],'STABLE')):
            self.assertEqual(trend_direction(deltas),direction)

    def test_single_jump_not_confirmed_deterioration(self):
        self.assertEqual(trend_direction([0,0,.8]),'STABLE')
        self.assertEqual(trend_direction([.8,-.8,0]),'STABLE')

    def test_no_history_safe_and_confidence_lower(self):
        result=evaluate_health(self.by_splice['S03'][0])
        self.assertEqual(result['trend_observation_count'],1)
        self.assertAlmostEqual(result['data_confidence'],.7)
        self.assertIn('insufficient history',result['explanation'])

    def test_single_prior_observation(self):
        result=evaluate_health(self.by_splice['S03'][1],self.by_splice['S03'][:1])
        self.assertEqual(result['trend_observation_count'],2)
        self.assertEqual(result['trend_direction'],'STABLE')
        self.assertAlmostEqual(result['data_confidence'],.775)

    def test_complete_history_confidence_and_window_limit(self):
        self.assertEqual(self.target[-1]['trend_observation_count'],5)
        self.assertEqual(self.target[-1]['data_confidence'],1)
        self.assertNotIn(self.target[0]['inspection_id'],self.target[-1]['trend_source_inspections'])

    def test_incomplete_health_evidence_rejected(self):
        current=deepcopy(self.by_splice['S03'][0]); current['mfl_channel_deviations'].pop()
        with self.assertRaises(ValueError): evaluate_health(current)

    def test_existing_detector_requires_24_channels(self):
        current=deepcopy(next(r for r in self.records if r['splice_id']=='S03'))
        current['mfl']['channels'].pop()
        with self.assertRaises(ValueError): compare_inspection(current,self.store.get('S03'))

    def test_determinism_and_inputs_unchanged(self):
        source=deepcopy(self.by_splice['S03']); before=deepcopy(source)
        self.assertEqual(evaluate_health(source[-1],source[:-1]),evaluate_health(source[-1],source[:-1]))
        self.assertEqual(source,before)

    def test_explanation_uses_actual_evidence(self):
        result=self.target[-1]
        self.assertIn('MFL has the largest',result['explanation'])
        self.assertIn('Repeated anomaly increases',result['explanation'])
        self.assertIn(f'{result["health_score"]:.2f}/100',result['explanation'])
        self.assertIn('not statistical probability',result['confidence_basis'])

    def test_formula_and_pass_through_sensor_evidence(self):
        for result,current in zip(self.health,self.anomalies):
            self.assertAlmostEqual(result['health_score'],100*(.7*(1-current['anomaly_score'])+.3*(1-result['trend_score'])))
            self.assertAlmostEqual(sum(result['health_point_contributions'].values()),result['health_score'])
            for name in ('mfl','camera','profile','tension'):
                self.assertEqual(result[name+'_evidence']['deviation'],current[name+'_deviation'])
                self.assertEqual(result[name+'_evidence']['anomaly_contribution'],current['weighted_contributions'][name])

    def test_invalid_history_mixing_order_duplicates(self):
        current=self.by_splice['S03'][-1]
        for prior in ([current], [self.by_splice['S01'][0]], list(reversed(self.by_splice['S03'][:3]))):
            with self.assertRaises(ValueError): evaluate_health(current,prior)
        prior=deepcopy(self.by_splice['S03'][:1]); prior[0]['run_sequence']=99
        with self.assertRaises(ValueError): evaluate_health(current,prior)

    def test_persisted_adapter_and_restart_scope(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'data',prefix='health-test-') as directory:
            with HistoryStore(Path(directory)/'history') as history:
                for record in self.records:
                    saved=history.append(record)
                    anomaly=compare_inspection(saved,self.store.get(saved['splice_id']))
                    actual=health_from_history(anomaly,history,self.store)
                    expected=next(r for r in self.health if r['inspection_id']==saved['inspection_id'])
                    self.assertEqual(actual['health_score'],expected['health_score'])
            with HistoryStore(Path(directory)/'history') as history:
                record=build_inspection_record(SpliceTracker().advance(LOOP_LENGTH)[0],121)
                saved=history.append(record)
                result=health_from_history(compare_inspection(saved,self.store.get(saved['splice_id'])),history,self.store)
                self.assertEqual(result['trend_observation_count'],1)

    def test_baselines_history_and_reused_modules_unchanged(self):
        before=json.loads((ROOT/'data/phase7_before.json').read_text())
        for name,expected in before['baseline'].items():
            p=ROOT/'data/baseline'/name
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),expected['sha256'])
            self.assertEqual(p.stat().st_mtime_ns,expected['mtime_ns'])
        for splice,doc in before['history'].items():
            now=json.loads((ROOT/'data/history'/f'{splice}.json').read_text())['inspections']
            self.assertEqual(now[:len(doc['inspections'])],doc['inspections'])
        for name,expected in before['preserved_code'].items():
            self.assertEqual(hashlib.sha256((ROOT/'scripts'/name).read_bytes()).hexdigest(),expected)

    def test_accepted_phase6_persisted_data_compatibility(self):
        accepted=json.loads((ROOT/'data/phase6_acceptance.json').read_text())
        phase6_run=accepted['runs']['phase6']['history_run']
        snapshot=json.loads((ROOT/'data/phase7_before.json').read_text())
        rows=[r for r in snapshot['history']['S03']['inspections'] if r['run_sequence']==phase6_run]
        previous=[]; measured=[]
        for row in rows:
            anomaly=compare_inspection(row,self.store.get('S03'))
            measured.append(evaluate_health(anomaly,previous))
            previous.append(anomaly)
        self.assertEqual(len(measured),6)
        self.assertEqual([r['health_score'] for r in measured],[r['health_score'] for r in self.target])
        self.assertEqual(measured[-1]['trend_direction'],'DEGRADING')


if __name__=='__main__':
    unittest.main(verbosity=2)
