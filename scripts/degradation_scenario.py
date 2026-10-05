"""Six repeatable S03 stages; observations only, never scores or severity.

The original fingerprint anchors the controlled experiment, removing the
healthy generator's inspection-index variation from the target splice.
Profile samples retain their shape with a gradually raised joint offset.
Every run starts at HEALTHY; after six passages the scenario holds SEVERE.
"""
from copy import deepcopy
from anomaly_detector import validate_current_record, validate_sensors
from phase5_config import MFL_BUMP

VERSION = 'phase6_progressive_v1'
TARGET = 'S03'
STAGES = ('HEALTHY', 'EARLY', 'DEVELOPING', 'MODERATE', 'ADVANCED', 'SEVERE')
AMPLITUDES = (0.0, .25, .55, .90, 1.25, 1.60)
CAMERA_DROP = .10
PROFILE_RISE_MM = .06
TENSION_DROP = .06


def validate_scenario(metadata):
    level = metadata.get('level')
    if (metadata.get('version') != VERSION or metadata.get('name') != 'progressive'
            or metadata.get('target_splice') != TARGET or type(level) is not int
            or not 0 <= level < len(STAGES) or metadata.get('stage') != STAGES[level]):
        raise ValueError('Invalid Phase 6 progressive scenario metadata')


def apply_degradation(record, baseline, level):
    """Return a new observation, preserving all current ID/time/encoder fields."""
    metadata = dict(version=VERSION, name='progressive', target_splice=TARGET,
                    level=level, stage=STAGES[level] if type(level) is int and 0 <= level < 6 else None)
    validate_scenario(metadata)
    validate_current_record(record)
    if baseline['splice_id'] != record['splice_id'] or baseline['baseline_status'] != 'HEALTHY':
        raise ValueError('Original healthy fingerprint of the same splice required')
    validate_sensors(baseline)
    changed = deepcopy(record)
    if record['splice_id'] != TARGET:
        return changed  # Keep the original strict Phase 2 healthy observation.
    changed['synthetic_scenario'] = metadata
    amplitude = AMPLITUDES[level]
    changed['mfl']['channels'] = list(baseline['mfl']['channels'])
    for channel, bump in MFL_BUMP.items():
        changed['mfl']['channels'][channel - 1] = round(baseline['mfl']['channels'][channel - 1] + amplitude * bump, 6)
    changed['camera']['score'] = round(baseline['camera']['score'] - CAMERA_DROP * amplitude, 6)
    changed['tension']['score'] = round(baseline['tension']['score'] - TENSION_DROP * amplitude, 6)
    changed['profile']['samples'] = [round(v + PROFILE_RISE_MM * amplitude, 6) for v in baseline['profile']['samples']]
    changed['profile']['deviation'] = max(changed['profile']['samples'])
    for name in ('camera', 'mfl', 'profile', 'tension'):
        changed[name]['status'] = 'NORMAL' if level == 0 else 'SYNTHETIC_CHANGE'
    validate_current_record(changed)
    return changed


class ProgressiveScenario:
    """Advance only on S03 inspection events, not frames or other splices."""
    def __init__(self, baseline_store):
        self.store = baseline_store
        self.target_inspections = 0

    def __call__(self, record):
        level = min(self.target_inspections, len(STAGES) - 1)
        result = apply_degradation(record, self.store.get(record['splice_id']), level)
        if record['splice_id'] == TARGET:
            self.target_inspections += 1
        return result


def trend_point(result):
    """Small reference to the detector output; raw sensors remain in history."""
    validate_scenario(result['synthetic_scenario'])
    if result['splice_id'] != TARGET:
        raise ValueError('The progression trend is for S03')
    fields = ('inspection_id', 'splice_id', 'inspection_sequence', 'timestamp_s',
              'run_sequence', 'baseline_source', 'anomaly_score', 'severity',
              'mfl_deviation', 'camera_deviation', 'profile_deviation',
              'tension_deviation', 'affected_channels')
    point = {key: deepcopy(result[key]) for key in fields}
    point.update(degradation_level=result['synthetic_scenario']['level'],
                 stage=result['synthetic_scenario']['stage'])
    return point
