"""Shared standalone scene lifecycle for Phases 1 through 7."""
import argparse
import csv
import json
import math
import sys
import time
import traceback
from contextlib import nullcontext
from app_config import ROOT, launch
from splice_tracker import SpliceTracker, SPEED, LOOP_LENGTH, SPLICES, STATION_POSITION


def run(phase=1):
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=float, default=187 if phase >= 6 else (125 if phase == 4 else 65))
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--verify-history-ui', action='store_true', help='Capture history browser checks after the Phase 4 run')
    parser.add_argument('--scenario', choices=('healthy', 'degradation'), default='degradation')
    parser.add_argument('--degradation-level', type=float, default=1.0)
    args = parser.parse_args()
    if not math.isfinite(args.degradation_level) or not 0 <= args.degradation_level <= 1:
        parser.error('--degradation-level must be between 0 and 1')
    if not math.isfinite(args.seconds) or args.seconds <= 0:
        parser.error('--seconds must be positive and finite')
    sys.argv = [sys.argv[0]]
    app = launch(args.headless, phase=phase)
    exit_code = 0
    prefix = f'phase{phase}'
    history_store = None
    anomaly_results = []
    health_results = []
    try:
        import omni.usd
        from pxr import Gf, UsdGeom, UsdLux
        from omni.kit.viewport.utility import get_active_viewport, get_active_viewport_window, capture_viewport_to_file
        from conveyor import Conveyor, cube
        from inspection_station import create_station
        omni.usd.get_context().new_stage()
        stage = omni.usd.get_context().get_stage()
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        UsdGeom.SetStageMetersPerUnit(stage, 1)
        world = UsdGeom.Xform.Define(stage, '/World')
        stage.SetDefaultPrim(world.GetPrim())
        cube(stage, '/World/Ground', (0, 0, -.12), (27, 15, .2), (.16, .19, .22))
        for i, y in enumerate((-1.7, 1.7)):
            cube(stage, f'/World/Lane_{i}', (0, y, -.012), (20, .07, .015), (.85, .61, .16))
        light = UsdLux.DomeLight.Define(stage, '/World/Ambient')
        light.CreateIntensityAttr(600)
        key = UsdLux.DistantLight.Define(stage, '/World/Sun')
        key.CreateIntensityAttr(1800)
        key.AddRotateXYZOp().Set((-35, -25, 20))
        conveyor = Conveyor(stage)
        laser_beam, laser_flash, scan_line, scan_flash = create_station(stage, phase=phase)
        view = UsdGeom.Camera.Define(stage, '/World/Overview')
        view.CreateFocalLengthAttr(28)
        matrix = Gf.Matrix4d().SetLookAt(Gf.Vec3d(12, -19, 14), Gf.Vec3d(0, 0, .9), Gf.Vec3d(0, 0, 1))
        view.AddTransformOp().Set(matrix.GetInverse())
        viewport = get_active_viewport()
        viewport.camera_path = '/World/Overview'
        viewport.set_texture_resolution((1280, 720))
        tracker = SpliceTracker()

        window = get_active_viewport_window()
        session = None
        store = None
        pending_baselines = []
        if phase >= 2:
            from inspection_event import InspectionSession, validate_record
            from phase2_hud import Phase2HUD
            session = InspectionSession()
            if phase >= 3:
                from fingerprint_store import FingerprintStore
                from phase3_hud import Phase3HUD
                store = FingerprintStore(ROOT / 'data' / 'baseline', read_only=phase >= 5)
                print(f'FINGERPRINTS LOADED: {store.loaded_count}', flush=True)
                if phase >= 4:
                    from history_store import HistoryStore
                    from inspection_history import inspection_number
                    from phase4_hud import Phase4HUD
                    minimum_id = max([inspection_number(store.get(s)['created_from_inspection'])
                                      for s in SPLICES if store.get(s)], default=0)
                    history_store = HistoryStore(ROOT / 'data' / 'history', minimum_id)
                    session = InspectionSession(history_store.last_inspection_number)
                    print(f'HISTORY LOADED: {history_store.loaded_count}; counts={history_store.counts()}', flush=True)
                    if phase >= 5:
                        from sensor_scenario import apply_scenario
                        from anomaly_detector import compare_inspection, validate_current_record
                        from phase5_hud import Phase5HUD
                        if len(store) != len(SPLICES):
                            raise ValueError('Comparison requires all five existing healthy fingerprints; no baseline will be created')
                        if phase >= 6:
                            from degradation_scenario import ProgressiveScenario, trend_point
                            from phase6_hud import Phase6HUD
                            session = InspectionSession(history_store.last_inspection_number, ProgressiveScenario(store))
                            if phase == 7:
                                from phase7_hud import Phase7HUD
                                from health_engine import health_from_history
                                hud = Phase7HUD(window, store, history_store)
                                health_directory = ROOT / 'data' / 'health'
                                health_directory.mkdir(exist_ok=True)
                            else:
                                hud = Phase6HUD(window, store, history_store)
                        else:
                            session = InspectionSession(history_store.last_inspection_number,
                                lambda record: apply_scenario(record, args.scenario, args.degradation_level))
                            hud = Phase5HUD(window, store, history_store)
                    else:
                        hud = Phase4HUD(window, store, history_store)
                else:
                    hud = Phase3HUD(window, store)
            else:
                hud = Phase2HUD(window)
        else:
            from phase1_hud import Phase1HUD
            hud = Phase1HUD(window)
        scene_path = ROOT / 'project' / f'{prefix}_conveyor.usda'
        stage.GetRootLayer().Export(str(scene_path))
        prim_count = sum(1 for _ in stage.Traverse())
        print(f'SCENE_CREATED: {scene_path}; prims={prim_count}', flush=True)
        for _ in range(45):
            app.update()
        renderer_capture = None
        if not args.headless:
            import omni.kit.renderer_capture
            renderer_capture = omni.kit.renderer_capture.acquire_renderer_capture_interface()
        captures = []
        captured_states = set()
        captured_baselines = set()
        events = []
        recent_event_until = scan_until = -1.0
        scan_active = False
        shown_splice = None
        frames = math.ceil(args.seconds * 30)
        completed = 0
        previous_state = None
        state_counts = {'READY': 0, 'SCANNING': 0, 'COMPLETE': 0}
        wall_start = time.perf_counter()
        output = ((ROOT / 'data' / 'phase1_inspections.csv').open('w', newline='', encoding='utf-8')
                  if phase == 1 else nullcontext(None))
        with output as stream:
            writer = None
            if stream:
                writer = csv.DictWriter(stream, fieldnames=['splice', 'position_m', 'encoder_m', 'encoder_ticks', 'time_s', 'status'])
                writer.writeheader()
            for frame in range(frames):
                if not app.is_running():
                    break
                phase5_capture = None
                tick_start = time.perf_counter()
                simulation_time = min((frame + 1) / 30, args.seconds)
                distance = SPEED * simulation_time
                conveyor.update(distance)
                for event in tracker.advance(distance):
                    event['encoder_ticks'] = round(event['position_m'] * 100)
                    events.append(event)
                    if session:
                        record = session.start(event, simulation_time)
                        hud.on_inspection(record, session.total_inspections)
                        print(f'INSPECTION START: {record["inspection_id"]} / {record["splice_id"]}', flush=True)
                    else:
                        writer.writerow(event)
                        stream.flush()
                        hud.on_inspection(event, len(events))
                        print('INSPECTION EVENT: ' + json.dumps(event), flush=True)
                    recent_event_until = simulation_time + 2.5
                    scan_until = simulation_time + (.6 if session else .8)
                    shown_splice = event['splice']
                    conveyor.highlight(shown_splice)
                if session:
                    for record in session.advance(simulation_time):
                        (validate_current_record if phase >= 5 else validate_record)(record)
                        hud.on_complete(record)
                        print('INSPECTION COMPLETE: ' + json.dumps(record), flush=True)
                        if store is not None and phase < 5:
                            if store.get(record['splice_id']) is None:
                                hud.creating(record)
                                pending_baselines.append((simulation_time + .2, record))
                            else:
                                fp, created = store.remember(record)
                                hud.show_fingerprint(fp, 'EXISTS / BASELINE PRESERVED')
                                print(f'FINGERPRINT EXISTS: {fp["splice_id"]}; BASELINE PRESERVED', flush=True)
                        if history_store is not None:
                            historical = history_store.append(record)
                            hud.on_history_saved(historical)
                            print('HISTORY APPENDED: ' + json.dumps(historical), flush=True)
                            if phase >= 5:
                                baseline = store.get(historical['splice_id'])
                                result = compare_inspection(historical, baseline)
                                anomaly_results.append(result)
                                hud.on_comparison(historical, baseline, result)
                                print('ANOMALY RESULT: ' + json.dumps(result), flush=True)
                                if phase == 7:
                                    health_result = health_from_history(result, history_store, store)
                                    # One compact snapshot per globally unique inspection, never overwrite.
                                    with (health_directory / f'{result["inspection_id"]}.json').open('x', encoding='utf-8') as stream:
                                        json.dump(health_result, stream, indent=2)
                                    health_results.append(health_result)
                                    hud.on_health(health_result)
                                    print('HEALTH RESULT: ' + json.dumps(health_result), flush=True)
                                if historical['splice_id'] == 'S03':
                                    phase5_capture = ('health' if phase == 7 else ('progression' if phase >= 6 else 'anomaly'))
                    while pending_baselines and pending_baselines[0][0] <= simulation_time:
                        _, source = pending_baselines.pop(0)
                        fp, created = store.remember(source)
                        hud.show_fingerprint(fp, 'DIGITAL FINGERPRINT CREATED' if created else 'EXISTS / BASELINE PRESERVED')
                        print(('DIGITAL FINGERPRINT CREATED: ' if created else 'FINGERPRINT EXISTS: ') + json.dumps(fp), flush=True)
                    state = session.state(simulation_time)
                else:
                    state = 'COMPLETE' if simulation_time <= recent_event_until else 'READY'
                hud.update(distance, state)
                if state != previous_state:
                    state_counts[state] += 1
                    print(f'STATION STATE: {state} at {simulation_time:.3f}s', flush=True)
                    previous_state = state
                should_scan = simulation_time <= scan_until
                if should_scan != scan_active:
                    scan_active = should_scan
                    for prim in (laser_flash, scan_flash):
                        imageable = UsdGeom.Imageable(prim)
                        imageable.MakeVisible() if scan_active else imageable.MakeInvisible()
                if shown_splice and simulation_time > recent_event_until:
                    conveyor.highlight(None)
                    shown_splice = None
                app.update()
                # Capture the application swapchain, including the native HUD, not the desktop.
                capture_name = phase5_capture
                if capture_name:
                    pass
                elif frame == 0:
                    capture_name = 'start'
                elif store is not None and store.created_count in (1, 5) and store.created_count not in captured_baselines:
                    capture_name = f'baseline_created_{store.created_count}'
                    captured_baselines.add(store.created_count)
                elif store is not None and store.preserved_count == 1 and 'preserved' not in captured_baselines:
                    capture_name = 'baseline_preserved'
                    captured_baselines.add('preserved')
                elif state not in captured_states and events:
                    capture_name = state.lower()
                    captured_states.add(state)
                elif frame == frames - 1:
                    capture_name = 'end'
                if capture_name:
                    captures.append(capture_viewport_to_file(viewport, str(ROOT / 'screenshots' / f'{prefix}_{capture_name}.png')))
                    if renderer_capture:
                        renderer_capture.capture_next_frame_swapchain(str(ROOT / 'screenshots' / f'{prefix}_hud_{capture_name}.png'))
                completed += 1
                time.sleep(max(0, 1 / 30 - (time.perf_counter() - tick_start)))
        # A short run or window close must still save every completed first scan.
        for _, source in pending_baselines:
            fp, created = store.remember(source)
            print(f'FINGERPRINT SAVED AT CLOSE: {fp["splice_id"]}; created={created}', flush=True)
        pending_baselines.clear()
        wall_seconds = time.perf_counter() - wall_start
        ui_checks = []
        if phase == 4 and args.verify_history_ui and app.is_running():
            # Exercise the same methods used by the native navigation buttons.
            hud.select_splice('S03')
            hud.set_mode('history')
            for name, action in [('history_latest', lambda: None),
                                 ('history_previous', lambda: hud.browse(-1)),
                                 ('history_baseline', lambda: hud.set_mode('baseline'))]:
                action()
                selected = history_store.records('S03')
                if name == 'history_previous' and len(selected) > 1:
                    assert selected[-2]['inspection_id'] in hud.chart_record.text
                elif name == 'history_latest' and selected:
                    assert selected[-1]['inspection_id'] in hud.chart_record.text
                elif name == 'history_baseline':
                    assert 'HEALTHY MFL FINGERPRINT - S03' == hud.chart_title.text
                for _ in range(3):
                    app.update()
                if renderer_capture:
                    renderer_capture.capture_next_frame_swapchain(str(ROOT / 'screenshots' / f'{prefix}_hud_{name}.png'))
                app.update()
                ui_checks.append(name)
            hud.set_mode('history')
            hud.toggle_live()
        if phase == 5 and app.is_running() and anomaly_results:
            for name, splice in [('mfl_deviation', 'S03'), ('healthy_splices', 'S01')]:
                if splice not in hud.comparisons:
                    continue
                hud.select_splice(splice)
                hud.set_mode('compare')
                record, baseline, result = hud.comparisons[splice]
                # Restore the selected observation's raw values for the presentation capture.
                from phase2_hud import Phase2HUD
                Phase2HUD.on_inspection(hud, record, session.total_inspections)
                hud.on_complete(record)
                hud.refresh_view()
                hud.update(distance, 'COMPLETE')
                for _ in range(3):
                    app.update()
                if renderer_capture:
                    renderer_capture.capture_next_frame_swapchain(str(ROOT / 'screenshots' / f'phase5_hud_{name}.png'))
                app.update()
            (ROOT / 'data' / 'phase5_results.json').write_text(json.dumps(
                {'scenario': args.scenario, 'level': args.degradation_level, 'results': anomaly_results}, indent=2), encoding='utf-8')
        if phase >= 6:
            trend = [trend_point(r) for r in anomaly_results if r['splice_id'] == 'S03']
            trend_directory = ROOT / 'data' / 'degradation'
            trend_directory.mkdir(exist_ok=True)
            # One new artifact per history run; never replace an older trend.
            with (trend_directory / f'run_{history_store.run_sequence:04d}.json').open('x', encoding='utf-8') as stream:
                json.dump({'version': 'phase6_trend_v1', 'raw_source': 'data/history/S03.json',
                           'points': trend}, stream, indent=2)
            if app.is_running() and 'S03' in hud.comparisons:
                hud.show_trend()
                record, baseline, result = hud.comparisons['S03']
                Phase2HUD.on_inspection(hud, record, session.total_inspections)
                hud.on_complete(record)
                hud.refresh_view()
                hud.update(distance, 'COMPLETE')
                for name in (('health_trend', 'sensor_fusion') if phase == 7 else ('trend', 's03_degradation')):
                    for _ in range(3):
                        app.update()
                    if renderer_capture:
                        renderer_capture.capture_next_frame_swapchain(str(ROOT / 'screenshots' / f'{prefix}_hud_{name}.png'))
                    app.update()
        for _ in range(30):
            if app.is_running():
                app.update()
        summary = {'completed_frames': completed, 'requested_frames': frames,
                   'simulation_seconds': completed / 30, 'wall_seconds': wall_seconds,
                   'approximate_fps': completed / wall_seconds,
                   'events': len(events), 'detected_splices': sorted({e['splice'] for e in events}),
                   'loop_length_m': LOOP_LENGTH, 'prims': prim_count,
                   'motion': 'kinematic encoder-driven animation', 'completed': completed == frames}
        if session:
            history = session.inspection_history
            for record in history:
                (validate_current_record if phase >= 5 else validate_record)(record)
            summary.update(completed_inspections=len(history), pending_inspections=session.pending_count,
                           exactly_24_channels=all(len(r['mfl']['channels']) == 24 for r in history),
                           synchronized_healthy_records=phase < 5, history_storage='memory only',
                           station_state_transitions=state_counts,
                           all_five_detected=set(summary['detected_splices']) == set(SPLICES))
        if store is not None:
            summary.update(baselines_loaded=store.loaded_count, baselines_created=store.created_count,
                           baselines_preserved=store.preserved_count, baselines_stored=len(store),
                           baseline_splices=[s for s in SPLICES if store.get(s)],
                           pending_baselines=len(pending_baselines))
        if history_store is not None:
            summary.update(history_loaded=history_store.loaded_count,
                           history_appended=history_store.appended_count,
                           history_counts=history_store.counts(),
                           history_storage='per-splice JSON', history_run=history_store.run_sequence,
                           timestamp_offset_s=history_store.time_offset, history_ui_checks=ui_checks)
        if phase >= 5:
            summary.update(scenario='progressive' if phase >= 6 else args.scenario,
                           degradation_level=None if phase >= 6 else args.degradation_level,
                           comparison_count=len(anomaly_results), baselines_read_only=True,
                           anomaly_results=anomaly_results)
        if phase >= 6:
            summary.update(degradation_trend=trend, six_levels_complete={p['degradation_level'] for p in trend} == set(range(6)))
        if phase == 7:
            summary.update(health_results=health_results, health_snapshots=len(health_results))
        (ROOT / 'data' / f'{prefix}_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        print(f'PHASE{phase}_RESULT: ' + json.dumps(summary), flush=True)
    except BaseException:
        traceback.print_exc()
        exit_code = 1
    finally:
        if history_store is not None:
            history_store.close()
        print(f'PHASE{phase}_CLOSING: exit_code={exit_code}', flush=True)
        app.close(wait_for_replicator=False, exit_code=exit_code)
