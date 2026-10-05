"""A fixed S03 sensor perturbation; no time-dependent degradation or randomness."""
from copy import deepcopy
import math
from phase5_config import (SCENARIO_VERSION, TARGET_SPLICE, MFL_BUMP, CAMERA_DROP,
                          TENSION_DROP, PROFILE_BUMP_MM)
from anomaly_detector import validate_current_record


def validate_scenario(metadata):
    if metadata['version'] != SCENARIO_VERSION or metadata['name'] not in ('healthy', 'degradation'):
        raise ValueError('Unsupported fixed sensor scenario')
    level = metadata['level']
    if type(level) not in (int, float) or not math.isfinite(level) or not 0 <= level <= 1:
        raise ValueError('Scenario level must be finite and between 0 and 1')
    if metadata['target_splice'] != TARGET_SPLICE:
        raise ValueError('Unsupported scenario target')


def apply_scenario(record, name='degradation', level=1.0):
    metadata = {'version': SCENARIO_VERSION, 'name': name, 'level': level, 'target_splice': TARGET_SPLICE}
    validate_scenario(metadata)
    current = deepcopy(record)
    current['synthetic_scenario'] = metadata
    if name == 'degradation' and current['splice_id'] == TARGET_SPLICE and level > 0:
        for channel, amplitude in MFL_BUMP.items():
            current['mfl']['channels'][channel - 1] += amplitude * level
        current['camera']['score'] -= CAMERA_DROP * level
        current['tension']['score'] -= TENSION_DROP * level
        for index, amplitude in PROFILE_BUMP_MM.items():
            current['profile']['samples'][index] += amplitude * level
        current['profile']['deviation'] = max(current['profile']['samples'])
        for sensor in ('camera', 'mfl', 'profile', 'tension'):
            current[sensor]['status'] = 'SYNTHETIC_CHANGE'
    validate_current_record(current)
    return current
