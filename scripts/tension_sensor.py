"""Synthetic healthy normalized tension score; no mechanical measurement."""


def generate_tension_observation(splice_id, inspection_index):
    return {'score': 0.96, 'status': 'NORMAL'}
