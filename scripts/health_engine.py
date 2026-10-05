"""Explainable current-condition/history fusion. No sensor rescoring or ML.

Window: current + up to four previous actual same-splice, same-run anomalies.
Direction: median adjacent delta >= .04 (or <= -.04), with at least two
corroborating deltas; fewer than three points cannot establish direction.
Trend degradation = clip(window mean + .5 * clip(median delta / .20))
when direction is DEGRADING; otherwise it is the window mean (persistence).
Health = 100 * (.70 * (1-current anomaly) + .30 * (1-trend degradation)).
One isolated jump cannot activate the additional deterioration penalty.
"""
from copy import deepcopy
from statistics import mean, median
from anomaly_detector import finite_number

WINDOW = 5
CURRENT_WEIGHT = .70
TREND_WEIGHT = .30
DIRECTION_THRESHOLD = .04
SLOPE_SPAN = .20
SLOPE_PENALTY = .50
HEALTH_THRESHOLDS = ((25, 'CRITICAL'), (50, 'AT RISK'), (75, 'DEGRADING'), (90, 'STABLE'))


def clip(value):
    return max(0.0, min(1.0, value))


def unit(value, name):
    if not finite_number(value) or not 0 <= value <= 1:
        raise ValueError(f'{name} must be finite and within 0-1')
    return value


def health_state(score):
    if not finite_number(score) or not 0 <= score <= 100:
        raise ValueError('Health score must be finite and within 0-100')
    return next((state for limit, state in HEALTH_THRESHOLDS if score < limit), 'HEALTHY')


def trend_direction(deltas):
    """Inclusive .04 boundary; two corroborating changes reject isolated noise."""
    if not all(finite_number(d) and -1 <= d <= 1 for d in deltas):
        raise ValueError('Invalid anomaly deltas')
    if len(deltas) < 2:
        return 'STABLE'
    slope = median(deltas)
    if slope >= DIRECTION_THRESHOLD and sum(d >= DIRECTION_THRESHOLD for d in deltas) >= 2:
        return 'DEGRADING'
    if slope <= -DIRECTION_THRESHOLD and sum(d <= -DIRECTION_THRESHOLD for d in deltas) >= 2:
        return 'IMPROVING'
    return 'STABLE'


def evaluate_health(current, previous=()):
    """Consume detector results, in chronological order; never alter inputs."""
    anomaly = unit(current['anomaly_score'], 'anomaly_score')
    channels = current['mfl_channel_deviations']
    if len(channels) != 24:
        raise ValueError('Complete 24-channel detector evidence required')
    for value in channels:
        unit(value, 'MFL channel deviation')
    if current['severity'] not in ('NORMAL','WATCH','WARNING','CRITICAL'):
        raise ValueError('Invalid anomaly severity')
    evidence = {}
    for name in ('mfl','camera','profile','tension'):
        evidence[name] = {'deviation':unit(current[name+'_deviation'], name),
                          'anomaly_contribution':unit(current['weighted_contributions'][name], name+' contribution')}
    points = list(previous)[-(WINDOW-1):] + [current]
    seen = set()
    last = None
    for point in points:
        unit(point['anomaly_score'], 'historical anomaly')
        if (point['splice_id'] != current['splice_id'] or point['baseline_source'] != current['baseline_source']
                or point.get('run_sequence') != current.get('run_sequence')):
            raise ValueError('History must use the same splice, original baseline and demonstration run')
        if point['inspection_id'] in seen:
            raise ValueError('Duplicate inspection in health window')
        seen.add(point['inspection_id'])
        if last is not None:
            for field in ('inspection_sequence','timestamp_s'):
                if field in point and field in last and point[field] <= last[field]:
                    raise ValueError('Health history must be chronological and precede current scan')
        last = point
    scores = [p['anomaly_score'] for p in points]
    deltas = [b-a for a,b in zip(scores,scores[1:])]
    direction = trend_direction(deltas)
    slope = median(deltas) if deltas else 0.0
    persistence = mean(scores)
    deterioration_penalty = SLOPE_PENALTY * clip(slope / SLOPE_SPAN) if direction == 'DEGRADING' else 0.0
    trend = clip(persistence + deterioration_penalty)
    current_component = 1-anomaly
    trend_component = 1-trend
    health = 100 * clip(CURRENT_WEIGHT*current_component + TREND_WEIGHT*trend_component)
    # Completeness rubric, not a statistical probability or model confidence.
    confidence = .70 + .30 * (len(points)-1)/(WINDOW-1)
    strongest = max(evidence, key=lambda name:evidence[name]['anomaly_contribution'])
    explanation = (f'Current anomaly {anomaly:.3f} ({current["severity"]}); '
                   f'{strongest.upper()} has the largest weighted sensor contribution '
                   f'({evidence[strongest]["anomaly_contribution"]:.3f}). ')
    if len(points) < 3:
        explanation += f'Only {len(points)} observation(s): insufficient history to establish a direction. '
    elif direction == 'DEGRADING':
        explanation += 'Repeated anomaly increases confirm deterioration. '
    elif direction == 'IMPROVING':
        explanation += 'Repeated anomaly decreases indicate improvement; prior abnormality still contributes. '
    else:
        explanation += 'No sustained directional change exceeds the trend threshold. '
    explanation += f'Historical degradation {trend:.3f}; 70% current condition plus 30% historical condition gives health {health:.2f}/100.'
    result = dict(health_version='phase7_fusion_v1', inspection_id=current['inspection_id'],
                  splice_id=current['splice_id'], baseline_source=current['baseline_source'],
                  health_score=health, health_state=health_state(health),
                  current_anomaly_score=anomaly, current_anomaly_severity=current['severity'],
                  **{name+'_evidence':value for name,value in evidence.items()},
                  affected_channels=deepcopy(current['affected_channels']),
                  trend_score=trend, trend_direction=direction, trend_median_delta=slope,
                  trend_window_mean=persistence, trend_deterioration_penalty=deterioration_penalty,
                  trend_observation_count=len(points), trend_source_inspections=[p['inspection_id'] for p in points],
                  trend_scope='same splice / same demonstration run / original baseline',
                  current_condition_component=current_component, historical_trend_health=trend_component,
                  fusion_weights={'current':CURRENT_WEIGHT,'history':TREND_WEIGHT},
                  health_point_contributions={'current':100*CURRENT_WEIGHT*current_component,
                                              'history':100*TREND_WEIGHT*trend_component},
                  data_confidence=confidence, confidence_basis='Evidence completeness rubric; not statistical probability',
                  explanation=explanation)
    for field in ('timestamp_s','inspection_sequence','run_sequence','simulation_time_s','synthetic_scenario'):
        if field in current:
            result[field] = deepcopy(current[field])
    return result


def health_from_history(current, history, fingerprints):
    """Event-only adapter: derive previous anomalies from actual persisted scans.

Never substitutes history for the original fingerprint. Simulation restarts
reset the demonstration scenario, so distinct run sequences are not mixed.
"""
    from anomaly_detector import compare_inspection
    rows = [r for r in history.records(current['splice_id'])
            if r['run_sequence'] == current['run_sequence']
            and r['inspection_sequence'] < current['inspection_sequence']][-(WINDOW-1):]
    baseline = fingerprints.get(current['splice_id'])
    prior = [compare_inspection(record, baseline) for record in rows]
    return evaluate_health(current, prior)
