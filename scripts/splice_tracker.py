"""Deterministic encoder tracking, independent of Isaac Sim and rendering."""
import math

STRAIGHT = 17.4
RADIUS = 0.30
LOOP_LENGTH = 2 * STRAIGHT + 2 * math.pi * RADIUS
STATION_POSITION = 14.2  # metres along the upper run, from the left drum centre
SPEED = 1.2
SPLICES = {f'S{i + 1:02d}': i * LOOP_LENGTH / 5 for i in range(5)}


def belt_pose(position):
    """Return x, z, Y rotation for a closed racetrack belt centreline."""
    s = position % LOOP_LENGTH
    half = STRAIGHT / 2
    if s < STRAIGHT:
        return s - half, 1.5, 0.0
    s -= STRAIGHT
    if s < math.pi * RADIUS:
        a = s / RADIUS
        return half + RADIUS * math.sin(a), 1.2 + RADIUS * math.cos(a), math.degrees(a)
    s -= math.pi * RADIUS
    if s < STRAIGHT:
        return half - s, 0.9, 180.0
    a = (s - STRAIGHT) / RADIUS
    return -half - RADIUS * math.sin(a), 1.2 - RADIUS * math.cos(a), 180 + math.degrees(a)


class SpliceTracker:
    def __init__(self):
        self.distance = 0.0

    def advance(self, distance):
        """Crossing detection on (previous, current]; handles skipped frames/laps."""
        if not math.isfinite(distance) or distance < self.distance:
            raise ValueError('Encoder distance must be finite and nondecreasing')
        events = []
        for splice, offset in SPLICES.items():
            first = STATION_POSITION - offset
            begin = math.floor((self.distance - first) / LOOP_LENGTH) + 1
            end = math.floor((distance - first) / LOOP_LENGTH)
            for lap in range(begin, end + 1):
                crossing = first + lap * LOOP_LENGTH
                events.append({'splice': splice, 'position_m': STATION_POSITION,
                               'encoder_m': crossing, 'time_s': crossing / SPEED,
                               'status': 'DETECTED'})
        self.distance = distance
        return sorted(events, key=lambda event: event['encoder_m'])

    def current_splice(self):
        # 0.32 m marker crossing a 0.10 m inspection zone.
        for splice, offset in SPLICES.items():
            delta = (offset + self.distance - STATION_POSITION + LOOP_LENGTH / 2) % LOOP_LENGTH - LOOP_LENGTH / 2
            if abs(delta) <= 0.21:
                return splice
        return None

