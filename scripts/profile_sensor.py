"""Small synthetic surface-height deviations in millimetres."""
import math


def generate_profile_observation(splice_id, inspection_index):
    phase = int(splice_id[1:]) * 0.21 + inspection_index * 0.07
    samples = [round(0.020 + 0.007 * math.sin(i * math.tau / 16 + phase), 4)
               for i in range(16)]
    return {'deviation': max(abs(v) for v in samples), 'samples': samples,
            'unit': 'mm', 'status': 'NORMAL'}
