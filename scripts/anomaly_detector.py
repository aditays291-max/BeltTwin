"""Explainable, deterministic current-vs-original-fingerprint comparison only."""
import math
from phase5_config import (WEIGHTS, MFL_RMS_MULTIPLIER, MFL_SCALE_FLOOR,
    CAMERA_DROP_SPAN, PROFILE_INCREASE_SPAN_MM, TENSION_DROP_SPAN,
    AFFECTED_CHANNEL_THRESHOLD, SEVERITY_THRESHOLDS)
from splice_tracker import SPLICES


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_sensors(data):
    channels = data['mfl']['channels']
    if len(channels) != 24 or not all(finite_number(v) for v in channels):
        raise ValueError('Exactly 24 finite MFL values are required')
    for name in ('camera', 'tension'):
        value = data[name]['score']
        if not finite_number(value) or not 0 <= value <= 1:
            raise ValueError(f'Invalid {name} score')
    profile = data['profile']
    if not finite_number(profile['deviation']) or profile['deviation'] < 0 or profile['unit'] != 'mm':
        raise ValueError('Profile deviation must be a finite non-negative millimetre value')


def validate_current_record(record):
    """Structural/physical validity; intentionally not the Phase 2 healthy-only contract."""
    validate_sensors(record)
    if record['splice_id'] not in SPLICES or record['status'] != 'COMPLETE':
        raise ValueError('Expected a completed inspection of a known splice')
    if not finite_number(record['simulation_time_s']) or record['simulation_time_s'] < 0:
        raise ValueError('Invalid simulation time')
    for name in ('camera', 'mfl', 'profile', 'tension'):
        for key in ('inspection_id', 'splice_id', 'simulation_time_s'):
            if record[name][key] != record[key]:
                raise ValueError(f'{name}: mismatched {key}')
    if record['mfl']['channel_names'] != [f'MFL{i:02d}' for i in range(1, 25)]:
        raise ValueError('Invalid MFL channel identities')
    samples = record['profile']['samples']
    if len(samples) != 16 or not all(finite_number(v) and v >= 0 for v in samples):
        raise ValueError('Expected 16 finite non-negative profile samples')
    if record['profile']['deviation'] != max(samples):
        raise ValueError('Profile summary and samples disagree')


def clamp(value):
    return min(1.0, max(0.0, value))


def severity(score):
    if not finite_number(score) or not 0 <= score <= 1:
        raise ValueError('Anomaly score must be between 0 and 1')
    for limit, name in SEVERITY_THRESHOLDS:
        if score < limit:
            return name
    return 'CRITICAL'


def compare_inspection(current, baseline):
    validate_current_record(current)
    validate_sensors(baseline)
    if baseline['splice_id'] != current['splice_id'] or baseline['baseline_status'] != 'HEALTHY':
        raise ValueError('Comparison requires the SAME splice healthy fingerprint')
    source = baseline['mfl']['channels']
    raw = [abs(c - b) for c, b in zip(current['mfl']['channels'], source)]
    # Relative vector RMS removes dependence on absolute MFL magnitude. The floor
    # keeps a zero/near-zero baseline stable. Twice baseline RMS allows ordinary
    # low-amplitude Phase 2 variation without dominating the combined score.
    scale = max(MFL_RMS_MULTIPLIER * math.sqrt(sum(v*v for v in source) / 24), MFL_SCALE_FLOOR)
    channel_deviations = [clamp(v / scale) for v in raw]
    deviations = {
        'mfl': clamp(math.sqrt(sum(v*v for v in raw) / 24) / scale),
        'camera': clamp((baseline['camera']['score'] - current['camera']['score']) / CAMERA_DROP_SPAN),
        'profile': clamp((current['profile']['deviation'] - baseline['profile']['deviation']) / PROFILE_INCREASE_SPAN_MM),
        'tension': clamp((baseline['tension']['score'] - current['tension']['score']) / TENSION_DROP_SPAN),
    }
    contributions = {key: WEIGHTS[key] * value for key, value in deviations.items()}
    score = clamp(sum(contributions.values()))
    maximum = max(range(24), key=lambda i: raw[i])
    affected = [f'MFL{i+1:02d}' for i, value in enumerate(channel_deviations)
                if value >= AFFECTED_CHANNEL_THRESHOLD]
    result = {
        'inspection_id': current['inspection_id'], 'splice_id': current['splice_id'],
        'baseline_source': baseline['created_from_inspection'],
        'baseline_splice_id': baseline['splice_id'], 'fingerprint_version': baseline['fingerprint_version'],
        'anomaly_score': score, 'severity': severity(score),
        **{f'{key}_deviation': value for key, value in deviations.items()},
        'mfl_max_channel_deviation': raw[maximum],  # original signal units, not clipped
        'mfl_max_channel_index': maximum + 1,  # one-based, matching MFL01-MFL24
        'mfl_channel_deviations': channel_deviations, 'mfl_normalization_scale': scale,
        'affected_channels': affected, 'weights': dict(WEIGHTS), 'weighted_contributions': contributions,
        'normalization': {'camera_drop_span': CAMERA_DROP_SPAN, 'profile_increase_span_mm': PROFILE_INCREASE_SPAN_MM,
                          'tension_drop_span': TENSION_DROP_SPAN, 'mfl_scale_floor': MFL_SCALE_FLOOR},
    }
    for key in ('simulation_time_s', 'timestamp_s', 'inspection_sequence', 'run_sequence', 'synthetic_scenario'):
        if key in current:
            from copy import deepcopy
            result[key] = deepcopy(current[key])
    return result
