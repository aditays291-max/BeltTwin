"""One encoder crossing -> one synchronized record, retained in memory only."""
import math
from camera_sensor import generate_camera_observation
from mfl_sensor import CHANNEL_NAMES, generate_mfl_signal
from profile_sensor import generate_profile_observation
from tension_sensor import generate_tension_observation
from splice_tracker import LOOP_LENGTH, SPEED, SPLICES, STATION_POSITION

TICKS_PER_METRE = 100
SCAN_SECONDS = 0.6
DISPLAY_SECONDS = 2.5


def build_inspection_record(event, inspection_index):
    splice_id = event['splice']
    if splice_id not in SPLICES:
        raise ValueError(f'Unknown splice: {splice_id}')
    for key in ('position_m', 'encoder_m', 'time_s'):
        if not math.isfinite(event[key]) or event[key] < 0:
            raise ValueError(f'Invalid encoder event field: {key}')
    if not math.isclose(event['position_m'], STATION_POSITION, abs_tol=1e-8):
        raise ValueError('Event is not at the inspection station')
    if not math.isclose((event['encoder_m'] + SPLICES[splice_id]) % LOOP_LENGTH,
                        STATION_POSITION, abs_tol=1e-8):
        raise ValueError('Splice ID disagrees with encoder position')
    if not math.isclose(event['time_s'] * SPEED, event['encoder_m'], abs_tol=1e-8):
        raise ValueError('Encoder time and travel disagree')
    channels = generate_mfl_signal(splice_id, inspection_index)
    context = {'inspection_id': f'INS-{inspection_index:04d}', 'splice_id': splice_id,
               'simulation_time_s': event['time_s']}
    record = {
        **context, 'synthetic': True, 'status': 'COMPLETE',
        'position_m': event['position_m'],
        # Preserve Phase 1's local station scale; also retain actual running counts.
        'encoder_ticks': round(event['position_m'] * TICKS_PER_METRE),
        'encoder': {'travel_m': event['encoder_m'],
                    'travel_ticks': round(event['encoder_m'] * TICKS_PER_METRE),
                    'ticks_per_metre': TICKS_PER_METRE,
                    'station_tick_reference': 'local station coordinate'},
        'camera': {**context, **generate_camera_observation(splice_id, inspection_index)},
        'mfl': {**context, 'channel_names': list(CHANNEL_NAMES), 'channels': channels,
                'unit': 'normalized arbitrary units', 'status': 'NORMAL'},
        'profile': {**context, **generate_profile_observation(splice_id, inspection_index)},
        'tension': {**context, **generate_tension_observation(splice_id, inspection_index)},
    }
    validate_record(record)
    return record


def validate_record(record):
    """Fail a demo loudly if synchronization, shape or healthy-value bounds fail."""
    for sensor in ('camera', 'mfl', 'profile', 'tension'):
        observation = record[sensor]
        for field in ('inspection_id', 'splice_id', 'simulation_time_s'):
            if observation[field] != record[field]:
                raise ValueError(f'{sensor}: mismatched {field}')
        if observation['status'] != 'NORMAL':
            raise ValueError('Phase 2 observations must be healthy')
    mfl = record['mfl']
    if mfl['channel_names'] != list(CHANNEL_NAMES) or len(mfl['channels']) != 24:
        raise ValueError('Expected MFL01-MFL24 with exactly 24 values')
    if not all(math.isfinite(v) and 0.017 <= v <= 0.033 for v in mfl['channels']):
        raise ValueError('MFL value outside the synthetic healthy range')
    if record['camera']['score'] != 0.95 or record['tension']['score'] != 0.96:
        raise ValueError('Unexpected synthetic camera/tension score')
    profile = record['profile']
    if len(profile['samples']) != 16 or not all(math.isfinite(v) and 0 <= v <= 0.03 for v in profile['samples']):
        raise ValueError('Unexpected surface profile')
    if profile['deviation'] != max(abs(v) for v in profile['samples']):
        raise ValueError('Profile deviation does not match its samples')


class InspectionSession:
    """Small presentation lifecycle; no persistent history or baseline models."""
    def __init__(self, inspection_index_offset=0, record_transform=None):
        if type(inspection_index_offset) is not int or inspection_index_offset < 0:
            raise ValueError('Inspection index offset must be a non-negative integer')
        self.inspection_index_offset = inspection_index_offset
        self.record_transform = record_transform
        self.inspection_history = []
        self.total_inspections = 0
        self.latest_record = None
        self.started_at = None
        self._pending = []

    def start(self, event, simulation_time):
        record = build_inspection_record(event, self.inspection_index_offset + self.total_inspections + 1)
        if self.record_transform is not None:
            record = self.record_transform(record)
        self.total_inspections += 1
        self.latest_record = record
        self.started_at = simulation_time
        self._pending.append((simulation_time + SCAN_SECONDS, record))
        return record

    def advance(self, simulation_time):
        completed = []
        while self._pending and self._pending[0][0] <= simulation_time:
            _, record = self._pending.pop(0)
            self.inspection_history.append(record)
            completed.append(record)
        return completed

    def state(self, simulation_time):
        if self.started_at is None or simulation_time - self.started_at >= DISPLAY_SECONDS:
            return 'READY'
        return 'SCANNING' if simulation_time < self.started_at + SCAN_SECONDS else 'COMPLETE'

    @property
    def pending_count(self):
        return len(self._pending)
