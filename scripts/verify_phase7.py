"""Audit the Phase 7 acceptance run and live regressions against the saved start."""
import hashlib
import json
from pathlib import Path
import re
from anomaly_detector import compare_inspection
from fingerprint_store import FingerprintStore
from history_store import HistoryStore
from inspection_history import validate_history_record
from health_engine import health_from_history

ROOT=Path(__file__).resolve().parents[1]


def read_run(path, phase):
    text=path.read_text(encoding='utf-8-sig',errors='replace')
    prefix=f'PHASE{phase}_RESULT: '
    result=json.loads(next(line[len(prefix):] for line in text.splitlines() if line.startswith(prefix)))
    assert f'PHASE{phase}_CLOSING: exit_code=0' in text, path
    assert '[Error]' not in text and 'Traceback (most recent call last)' not in text, path
    assert result['completed'] and result['detected_splices']==['S01','S02','S03','S04','S05'], path
    return result,[line for line in text.splitlines() if '[Warning]' in line]


def main():
    before=json.loads((ROOT/'data/phase7_before.json').read_text())
    runs={}; warnings={}
    runs['initial'],warnings['initial']=read_run(ROOT/'data/phase7_initial_run.log',7)
    runs['phase7'],warnings['phase7']=read_run(ROOT/'data/phase7_run.log',7)
    for phase in range(1,7):
        name=f'phase{phase}'
        runs[name],warnings[name]=read_run(ROOT/'data'/f'phase7_phase{phase}_regression.log',phase)
        if phase>=2: assert runs[name]['exactly_24_channels']
    final=runs['phase7']
    assert final['six_levels_complete'] and final['health_snapshots']==30
    assert runs['phase6']['six_levels_complete']
    assert runs['phase4']['history_ui_checks']==['history_latest','history_previous','history_baseline']
    assert final['baselines_read_only'] and final['baselines_created']==0 and final['prims']==260
    assert (ROOT/'project/phase7_conveyor.usda').read_bytes()==(ROOT/'project/phase6_conveyor.usda').read_bytes()
    after={p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'mtime_ns':p.stat().st_mtime_ns}
           for p in (ROOT/'data/baseline').glob('*.json')}
    assert after==before['baseline']
    for name,expected in before['preserved_code'].items():
        assert hashlib.sha256((ROOT/'scripts'/name).read_bytes()).hexdigest()==expected
    appended=sum(r.get('history_appended',0) for r in runs.values())
    old_count=sum(len(doc['inspections']) for doc in before['history'].values())
    fingerprints=FingerprintStore(ROOT/'data/baseline',read_only=True)
    with HistoryStore(ROOT/'data/history') as history:
        assert history.loaded_count==old_count+appended
        for splice,doc in before['history'].items():
            assert history.records(splice)[:len(doc['inspections'])]==doc['inspections']
        records={r['inspection_id']:r for s in before['history'] for r in history.records(s)}
        for record in records.values(): validate_history_record(record)
        for run in (runs['initial'], final):
            for result in run['health_results']:
                raw=records[result['inspection_id']]
                anomaly=compare_inspection(raw,fingerprints.get(raw['splice_id']))
                assert health_from_history(anomaly,history,fingerprints)==result
                assert json.loads((ROOT/'data/health'/f'{result["inspection_id"]}.json').read_text())==result
        counts=history.counts()
    trend=[r for r in final['health_results'] if r['splice_id']=='S03']
    assert [r['synthetic_scenario']['level'] for r in trend]==list(range(6))
    assert all(a['health_score']>b['health_score'] for a,b in zip(trend,trend[1:]))
    assert all(a['trend_score']<b['trend_score'] for a,b in zip(trend,trend[1:]))
    assert all(r['trend_direction']=='DEGRADING' for r in trend[2:])
    assert trend[-1]['health_state']=='CRITICAL' and trend[-1]['data_confidence']==1
    latest={s:next(r for r in reversed(final['health_results']) if r['splice_id']==s) for s in before['history']}
    for result in final['health_results']:
        if result['splice_id']!='S03':
            assert result['trend_direction']=='STABLE' and result['health_state'] in ('HEALTHY','STABLE')
            assert result['health_score']>=90 and result['current_anomaly_score']<.2
    assert [r['current_anomaly_score'] for r in trend]==[r['anomaly_score'] for r in runs['phase6']['degradation_trend']]
    tests=(ROOT/'data/phase7_tests.log').read_text(encoding='utf-8-sig',errors='replace')
    assert re.search(r'Ran 76 tests',tests) and tests.rstrip().endswith('OK')
    screenshots=[f'screenshots/phase7_hud_{name}.png' for name in ('health','health_trend','sensor_fusion')]
    for path in screenshots: assert (ROOT/path).read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    report=dict(phase=7,accepted=True,tests={'passed':76,'existing_unchanged':53,'new':23},
        launch_command='Set-Location C:\\BeltTwin; & .\\scripts\\run_isaac.ps1 phase7_scene.py --seconds 187 *> data/phase7_run.log',
        health_formula='100 * (0.70 * (1 - current_anomaly) + 0.30 * (1 - trend_score))',
        trend_formula='clip(mean(window) + 0.5 * clip(median_adjacent_delta / 0.20)) if direction is DEGRADING; otherwise mean(window)',
        direction_rule='Latest 5 same-splice/same-run points; median delta >= 0.04 and at least two deltas >= 0.04: DEGRADING; symmetric <= -0.04: IMPROVING; otherwise STABLE',
        thresholds={'HEALTHY':'90-100','STABLE':'75-<90','DEGRADING':'50-<75','AT RISK':'25-<50','CRITICAL':'0-<25'},
        data_confidence_formula='0.70 for complete sensor evidence + 0.30 * min(prior_count,4)/4; completeness, not probability',
        latest_by_splice=latest,s03_progression=trend,monotonic_health=True,identical_phase6_anomaly_sequence=True,
        baseline_before=before['baseline'],baseline_after=after,baseline_sha256_unchanged=True,baseline_mtime_unchanged=True,
        phase5_detector_and_phase6_scenario_unchanged=True,old_history_records_preserved=old_count,
        intentional_history_appends=appended,health_snapshots_created=len(final['health_results'])+len(runs['initial']['health_results']),
        initial_run_note='Completed with window minimized for much of the run; retained for data integrity, excluded from rendering performance acceptance.',
        history_counts_after=counts,history_count_after=sum(counts.values()),
        persisted_health_recomputed_identically=True,encoder_and_24_channels_valid=True,
        measured_fps=final['approximate_fps'],performance_reference_fps=21,scene_identical_to_phase6=True,
        runs=runs,warnings=warnings,screenshots=screenshots,installed_packages=[],isaac_installation_edits=[],phase8_started=False)
    (ROOT/'data/phase7_acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('accepted','tests','intentional_history_appends','history_counts_after','measured_fps')},indent=2))


if __name__=='__main__':
    main()
