"""Verify completed live runs against the pre-change snapshot; write acceptance."""
import hashlib
import json
from pathlib import Path
import re
from anomaly_detector import compare_inspection
from history_store import HistoryStore
from fingerprint_store import FingerprintStore
from inspection_history import validate_history_record

ROOT = Path(__file__).resolve().parents[1]


def read_run(filename, phase, require_complete=True):
    text = (ROOT/'data'/filename).read_text(encoding='utf-8-sig', errors='replace')
    prefix = f'PHASE{phase}_RESULT: '
    result = json.loads(next(line[len(prefix):] for line in text.splitlines() if line.startswith(prefix)))
    assert f'PHASE{phase}_CLOSING: exit_code=0' in text, filename
    assert 'Traceback (most recent call last)' not in text, filename
    assert '[Error]' not in text, filename
    if require_complete:
        assert result['completed'] and result['detected_splices'] == ['S01','S02','S03','S04','S05'], filename
    return result, sorted({line for line in text.splitlines() if '[Warning]' in line})


def main():
    before = json.loads((ROOT/'data/phase6_before.json').read_text())
    runs = {}; warnings = {}
    runs['initial'], warnings['initial'] = read_run('phase6_initial_run.log', 6, False)
    runs['phase6'], warnings['phase6'] = read_run('phase6_run.log', 6)
    for phase in range(1,6):
        name = f'phase{phase}'
        runs[name], warnings[name] = read_run(f'phase6_phase{phase}_regression.log', phase)
        if phase >= 2: assert runs[name]['exactly_24_channels']
    final = runs['phase6']
    assert final['six_levels_complete'] and final['pending_inspections'] == 0
    assert final['baselines_read_only'] and final['baselines_created'] == 0
    assert final['prims'] == 260 and final['exactly_24_channels']
    assert runs['phase4']['history_ui_checks'] == ['history_latest', 'history_previous', 'history_baseline']
    assert (ROOT/'project/phase6_conveyor.usda').read_bytes() == (ROOT/'project/phase5_conveyor.usda').read_bytes()
    fingerprints = FingerprintStore(ROOT/'data/baseline', read_only=True)
    baseline_after = {p.name: {'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                              'mtime_ns':p.stat().st_mtime_ns}
                      for p in (ROOT/'data/baseline').glob('*.json')}
    assert baseline_after == before['baseline']
    old_count = sum(len(doc['inspections']) for doc in before['history'].values())
    appended = sum(run.get('history_appended',0) for run in runs.values())
    with HistoryStore(ROOT/'data/history') as history:
        assert history.loaded_count == old_count + appended
        for splice, document in before['history'].items():
            assert history.records(splice)[:len(document['inspections'])] == document['inspections']
        records = {r['inspection_id']:r for splice in before['history'] for r in history.records(splice)}
        for record in records.values(): validate_history_record(record)
        counts = history.counts()
    for run in runs.values():
        for result in run.get('anomaly_results', []):
            assert compare_inspection(records[result['inspection_id']], fingerprints.get(result['splice_id'])) == result
    trend = final['degradation_trend']
    assert [p['degradation_level'] for p in trend] == list(range(6))
    assert [p['severity'] for p in trend] == ['NORMAL','NORMAL','WATCH','WARNING','WARNING','CRITICAL']
    for key in ('anomaly_score','mfl_deviation','camera_deviation','profile_deviation','tension_deviation'):
        assert all(a[key] < b[key] for a,b in zip(trend,trend[1:])), key
    assert trend[-1]['affected_channels'] == [f'MFL{i:02d}' for i in range(9,14)]
    others = {}
    for splice in ('S01','S02','S04','S05'):
        results = [r for r in final['anomaly_results'] if r['splice_id'] == splice]
        assert len(results) == 6 and all(r['severity']=='NORMAL' for r in results)
        others[splice] = {'inspections':len(results), 'severity':'NORMAL',
                          'min_score':min(r['anomaly_score'] for r in results),
                          'max_score':max(r['anomaly_score'] for r in results)}
    trend_path = ROOT/'data/degradation'/f'run_{final["history_run"]:04d}.json'
    assert json.loads(trend_path.read_text())['points'] == trend
    test_log = (ROOT/'data/phase6_tests.log').read_text(encoding='utf-8-sig',errors='replace')
    assert re.search(r'Ran 53 tests',test_log) and test_log.rstrip().endswith('OK')
    screenshots = [f'screenshots/phase6_hud_{name}.png' for name in ('progression','trend','s03_degradation')]
    for path in screenshots:
        assert (ROOT/path).read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    report = dict(phase=6, accepted=True, tests={'passed':53,'existing_unchanged':37,'new':16},
        launch_command='Set-Location C:\\BeltTwin; & .\\scripts\\run_isaac.ps1 phase6_scene.py --seconds 187 *> data/phase6_run.log',
        trend=trend, trend_source=str(trend_path), other_splices=others,
        strict_monotonicity=True, recomputed_results_identical=True,
        baseline_before=before['baseline'], baseline_after=baseline_after,
        baseline_sha256_unchanged=True, baseline_mtime_unchanged=True,
        old_history_records_preserved=old_count, intentional_history_appends=appended,
        history_counts_after=counts, history_count_after=sum(counts.values()),
        all_persisted_observations_valid=True, all_24_channels_preserved=True,
        s03_observations={p['inspection_id']: {
            'camera':records[p['inspection_id']]['camera']['score'],
            'profile_mm':records[p['inspection_id']]['profile']['deviation'],
            'tension':records[p['inspection_id']]['tension']['score']}
            for p in trend},
        performance_reference_fps=21, measured_fps=final['approximate_fps'],
        scene_identical_to_phase5=True, primitive_count=260,
        runs=runs, warnings=warnings, screenshots=screenshots,
        earlier_attempt={'log':'data/phase6_phase3_first_attempt.log',
                         'note':'First Phase 3 regression completed inspections but reported RTX shader-cache startup failure; rejected for acceptance and rerun.',
                         'diagnostics':[line for line in (ROOT/'data/phase6_phase3_first_attempt.log').read_text(errors='replace').splitlines()
                                        if '[Error]' in line or '[Warning]' in line]},
        installed_packages=[], isaac_installation_edits=[], phase7_started=False)
    (ROOT/'data/phase6_acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('accepted','tests','intentional_history_appends',
                                          'history_counts_after','measured_fps')},indent=2))


if __name__ == '__main__':
    main()
