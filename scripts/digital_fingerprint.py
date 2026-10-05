"""Healthy baseline snapshots copied from completed Phase 2 observations."""
from copy import deepcopy
import math
import re
from typing import TypedDict
from inspection_event import validate_record
from splice_tracker import SPLICES


class DigitalFingerprint(TypedDict):
    fingerprint_version: str
    splice_id: str
    created_from_inspection: str
    baseline_status: str
    baseline_position_m: float
    baseline_encoder_ticks: int
    source_simulation_time_s: float
    baseline_encoder: dict
    camera: dict
    mfl: dict
    profile: dict
    tension: dict


def validate_fingerprint(fp):
    if fp['fingerprint_version'] != '1.0' or fp['baseline_status'] != 'HEALTHY':
        raise ValueError('Unsupported or non-healthy fingerprint')
    if fp['splice_id'] not in SPLICES or not re.fullmatch(r'INS-[0-9]{4,}', fp['created_from_inspection']):
        raise ValueError('Invalid fingerprint identity')
    if not math.isfinite(fp['baseline_position_m']) or fp['baseline_position_m'] < 0:
        raise ValueError('Invalid baseline position')
    if type(fp['baseline_encoder_ticks']) is not int or fp['baseline_encoder_ticks'] < 0:
        raise ValueError('Invalid baseline ticks')
    if fp['mfl']['channel_count'] != 24 or fp['profile']['unit'] != 'mm':
        raise ValueError('Invalid baseline sensor schema')
    # Reuse the existing healthy synthetic observation contract, not a new model.
    record = {key: deepcopy(fp[key]) for key in ('camera', 'mfl', 'profile', 'tension')}
    record.update(inspection_id=fp['created_from_inspection'], splice_id=fp['splice_id'],
                  simulation_time_s=fp['source_simulation_time_s'])
    validate_record(record)


def from_inspection(record) -> DigitalFingerprint:
    if record.get('status') != 'COMPLETE' or record.get('synthetic') is not True:
        raise ValueError('A completed synthetic healthy inspection is required')
    validate_record(record)
    fp = DigitalFingerprint(
        fingerprint_version='1.0', splice_id=record['splice_id'],
        created_from_inspection=record['inspection_id'], baseline_status='HEALTHY',
        baseline_position_m=record['position_m'], baseline_encoder_ticks=record['encoder_ticks'],
        camera=deepcopy(record['camera']), mfl=deepcopy(record['mfl']),
        profile=deepcopy(record['profile']), tension=deepcopy(record['tension']))
    fp['source_simulation_time_s'] = record['simulation_time_s']
    fp['baseline_encoder'] = deepcopy(record['encoder'])
    fp['mfl']['channel_count'] = 24
    validate_fingerprint(fp)
    return fp
