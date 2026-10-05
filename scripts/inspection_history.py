"""History metadata around an unchanged, completed Phase 2 observation."""
from copy import deepcopy
import math
import re
from inspection_event import validate_record
from splice_tracker import SPLICES, STATION_POSITION, LOOP_LENGTH, SPEED


def inspection_number(inspection_id):
    if not isinstance(inspection_id, str) or not re.fullmatch(r'INS-[0-9]{4,}', inspection_id):
        raise ValueError('Invalid inspection ID')
    number = int(inspection_id[4:])
    if number < 1:
        raise ValueError('Inspection ID must be positive')
    return number


def validate_observation(record):
    if record['splice_id'] not in SPLICES or record['status'] != 'COMPLETE':
        raise ValueError('History requires a completed observation of a known splice')
    inspection_number(record['inspection_id'])
    if 'synthetic_scenario' in record:
        # Backward-compatible raw observation extension for the fixed Phase 5
        # scenario. Untagged Phase 1-4 records keep their strict healthy contract.
        from sensor_scenario import validate_scenario
        from anomaly_detector import validate_current_record
        metadata = record['synthetic_scenario']
        if metadata.get('version') == 'phase6_progressive_v1':
            from degradation_scenario import validate_scenario as validate_progressive
            validate_progressive(metadata)
            if record['splice_id'] != 'S03':
                raise ValueError('Progressive scenario is restricted to S03')
        else:
            validate_scenario(metadata)
        validate_current_record(record)
    else:
        validate_record(record)
    for value in (record['simulation_time_s'], record['position_m'], record['encoder']['travel_m']):
        if not math.isfinite(value) or value < 0:
            raise ValueError('Invalid observation position/time')
    if record['position_m'] != STATION_POSITION or record['encoder_ticks'] != round(STATION_POSITION * 100):
        raise ValueError('Incorrect station reference')
    travel = record['encoder']['travel_m']
    if not math.isclose((travel + SPLICES[record['splice_id']]) % LOOP_LENGTH, STATION_POSITION, abs_tol=1e-8):
        raise ValueError('Encoder and splice identity disagree')
    if not math.isclose(record['simulation_time_s'] * SPEED, travel, abs_tol=1e-8):
        raise ValueError('Encoder and simulation time disagree')


def history_record(record, sequence, run_sequence, time_offset):
    validate_observation(record)
    result = deepcopy(record)
    result.update(inspection_sequence=sequence, run_sequence=run_sequence,
                  timestamp_s=time_offset + record['simulation_time_s'],
                  timestamp_offset_s=time_offset, baseline_splice_id=record['splice_id'])
    result['mfl']['channel_count'] = 24
    validate_history_record(result)
    return result


def validate_history_record(record):
    validate_observation(record)
    for field in ('inspection_sequence', 'run_sequence'):
        if type(record[field]) is not int or record[field] < 1:
            raise ValueError(f'Invalid {field}')
    for field in ('timestamp_s', 'timestamp_offset_s'):
        if not math.isfinite(record[field]) or record[field] < 0:
            raise ValueError(f'Invalid {field}')
    if not math.isclose(record['timestamp_s'], record['timestamp_offset_s'] + record['simulation_time_s'], abs_tol=1e-8):
        raise ValueError('History timestamp disagrees with simulation time')
    if record['mfl']['channel_count'] != 24 or record['baseline_splice_id'] != record['splice_id']:
        raise ValueError('Invalid history sensor count or baseline reference')
