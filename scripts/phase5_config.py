"""Fixed demonstration calibration, not a physical model or progressive schedule."""
WEIGHTS = {'mfl': 0.50, 'camera': 0.20, 'profile': 0.20, 'tension': 0.10}
MFL_RMS_MULTIPLIER = 2.0
MFL_SCALE_FLOOR = 0.02
CAMERA_DROP_SPAN = 0.20
PROFILE_INCREASE_SPAN_MM = 0.10
TENSION_DROP_SPAN = 0.20
AFFECTED_CHANNEL_THRESHOLD = 0.35
SEVERITY_THRESHOLDS = ((0.20, 'NORMAL'), (0.40, 'WATCH'), (0.70, 'WARNING'))
SCENARIO_VERSION = 'phase5_fixed_change_v1'
TARGET_SPLICE = 'S03'
# One-based MFL channels: a compact leakage-like bump, added to the generated signal.
MFL_BUMP = {9: 0.035, 10: 0.060, 11: 0.080, 12: 0.060, 13: 0.035}
CAMERA_DROP = 0.10
TENSION_DROP = 0.06
PROFILE_BUMP_MM = {6: 0.024, 7: 0.042, 8: 0.060, 9: 0.042, 10: 0.024}
