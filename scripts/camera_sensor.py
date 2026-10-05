"""Synthetic camera interface; no image acquisition or computer vision."""


def generate_camera_observation(splice_id, inspection_index):
    return {'score': 0.95, 'status': 'NORMAL'}
