"""Deterministic healthy magnetic signal, in arbitrary normalized units."""
import math
from splice_tracker import SPLICES

CHANNEL_NAMES = tuple(f'MFL{i:02d}' for i in range(1, 25))


def generate_mfl_signal(splice_id, inspection_index):
    if splice_id not in SPLICES:
        raise ValueError(f'Unknown splice: {splice_id}')
    if type(inspection_index) is not int or inspection_index < 1:
        raise ValueError('inspection_index must be a positive integer')
    phase = int(splice_id[1:]) * 0.37 + inspection_index * 0.13
    return [round(0.025 + 0.006 * math.sin(i * math.tau / 24 + phase)
                  + 0.002 * math.cos(i * math.tau / 8), 4) for i in range(24)]
