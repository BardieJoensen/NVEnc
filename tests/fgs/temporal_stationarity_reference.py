"""Bounded offline diagnostics for the temporal population hypothesis.

Passing these necessary checks does NOT classify material as film grain. In
particular, unobserved motion, repeated patterns and temporally correlated noise
can evade a short history. No encoder policy or population identity is changed.
Native code values are normalized by the depth scale, not an HDR light model.
"""
import numpy as np

from temporal_population_reference import measure


def _motion(source):
    # A fixed binomial low-pass reduces independent noise before matching. All
    # translations use the same interior samples, without padding or wraparound.
    smooth = sum(source[:, :, y:y+30, x:x+30] * wy * wx
                 for y, wy in enumerate((1, 2, 1))
                 for x, wx in enumerate((1, 2, 1))) / 16
    coordinates = np.arange(4, 26, 2)
    target = smooth[1:, :, coordinates[:, None], coordinates]
    shifts = [(0, 0)] + [(dy, dx) for dy in range(-4, 5)
                        for dx in range(-4, 5) if dy or dx]
    costs = np.array([np.mean((target - smooth[:-1, :,
                      (coordinates+dy)[:, None], coordinates+dx])**2,
                      axis=(-2, -1)) for dy, dx in shifts])
    # The unshifted comparison wins exact ties, including a completely quiet tile.
    best = np.argmin(costs, axis=0)
    minimum = np.take_along_axis(costs, best[None], axis=0)[0]
    improvement = np.zeros_like(minimum)
    np.divide(costs[0]-minimum, costs[0], out=improvement, where=costs[0] > 0)
    return dict(offsets=np.array(shifts)[best], unshifted_mse=costs[0],
                best_mse=minimum, relative_improvement=improvement,
                samples_per_pair=11*11, search_radius=4)


def consistency(evidence):
    """Original frozen lag/history/mean diagnostics, without a motion search."""
    variance = np.diag(evidence['source_residual_covariance'])
    lags = np.diagonal(evidence['lag_difference_covariance'], axis1=1, axis2=2)
    history = np.diag(evidence['history_difference_covariance'])
    conflicts = []
    for c in range(3):
        reasons = []
        v = variance[c]
        if v < .04 or v > 256:
            reasons.append('conditional_variance_outside_study_range')
        if v <= 0 or np.any(np.abs(lags[:, c]-v) > .2*v):
            reasons.append('lag_energy_inconsistent')
        if v <= 0 or abs(history[c]-(1/3+1/4)*v) > .3*(1/3+1/4)*v:
            reasons.append('disjoint_histories_inconsistent')
        if (abs(evidence['history_mean_difference'][c]) > 1
                or abs(evidence['current_mean_difference'][c]) > 1):
            reasons.append('mean_changed')
        conflicts.append(reasons)
    return conflicts


def diagnose(source, base, depth, frame_ids, timestamps):
    """Eight adjacent 3x32x32 tiles; return measurements, never admission bits.

    These frozen exploratory bounds test whether short-history consistency plus
    small-translation evidence could justify a later classifier. They are not
    visibility thresholds or sufficient evidence of source-detail preservation.
    Motion cannot establish that a residual is noise, even after registration.
    """
    evidence = measure(source, base, depth, frame_ids, timestamps)
    motion = _motion(np.asarray(source, dtype=np.float64) / (1 << (depth-8)))
    conflicts = consistency(evidence)
    for c in range(3):
        translated = ((motion['relative_improvement'][:, c] > .2)
                      & (motion['unshifted_mse'][:, c] > .04))
        if np.count_nonzero(translated) >= 4:
            conflicts[c].append('small_translation_evidence')
    return dict(hypothesis_only=True, stationarity_qualified=False,
                population_acceptance=False, evidence=evidence, motion=motion,
                conflicts=conflicts)
