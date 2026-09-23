"""Source-only temporal evidence for structured retention populations.

This is an offline measurement, NOT a new population acceptance rule. Under a
stationary scene and independent zero-mean grain, disjoint history averages
cancel persistent detail without sharing their noise with the current picture.
Motion, temporal grain correlation and scene changes invalidate that inference.
Report the signed estimates and competing temporal evidence; never clip an
inconvenient covariance into an admissible model or certify a rejected tile.
All returned covariances use 8-bit code units, not light or display units.
"""
import numpy as np


def covariance(a, b):
    """Asymmetric cross covariance; retain source/base orientation."""
    a = np.asarray(a, dtype=np.float64).reshape(3, -1)
    b = np.asarray(b, dtype=np.float64).reshape(3, -1)
    a = a - a.mean(axis=1, keepdims=True)
    b = b - b.mean(axis=1, keepdims=True)
    return a @ b.T / (a.shape[1] - 1)


def measure(source, base, depth, frame_ids, timestamps):
    """Exactly eight adjacent source tiles and the actual current rounded base.

    Y must be the 2x2 source average co-located with each 4:2:0 colour sample.
    No spatial registration, denoising, clipping or classification is performed.
    Identity/clock checks establish adjacency only, not scene stationarity.
    """
    source = np.asarray(source)
    base = np.asarray(base)
    if (depth not in (8, 10) or source.shape != (8, 3, 32, 32)
            or base.shape != (3, 32, 32)):
        raise ValueError('requires eight 3x32x32 source tiles and one current base')
    ids = np.asarray(frame_ids)
    clocks = np.asarray(timestamps)
    if (ids.shape != (8,) or ids.dtype.kind not in 'iu' or np.any(ids < 0)
            or np.any(np.diff(ids.astype(np.float64)) != 1)
            or clocks.shape != (8,) or clocks.dtype.kind not in 'iuf'
            or not np.isfinite(clocks).all() or np.any(clocks[1:] <= clocks[:-1])):
        raise ValueError('requires adjacent source IDs and strictly increasing clocks')
    for data in (source, base):
        if (data.dtype.kind not in 'iuf' or not np.isfinite(data).all()
                or np.any(data < 0) or np.any(data > (1 << depth) - 1)):
            raise ValueError('invalid native-depth source/base values')
    source = source.astype(np.float64) / (1 << (depth - 8))
    base = base.astype(np.float64) / (1 << (depth - 8))
    current = source[-1]
    first, second = source[:3].mean(axis=0), source[3:7].mean(axis=0)
    symmetric = lambda value: (value + value.T) * .5
    source_residual = symmetric(covariance(current-first, current-second))
    base_residual = symmetric(covariance(base-first, base-second))
    cross_residual = .5 * (covariance(current-first, base-second)
                           + covariance(current-second, base-first))
    lag_covariance = []
    for lag in (1, 2, 3):
        differences = source[lag:] - source[:-lag]
        lag_covariance.append(sum(covariance(d, d) for d in differences)
                              / (2 * len(differences)))
    return dict(
        hypothesis_only=True, stationarity_qualified=False,
        frame_id=int(ids[-1]), samples=32*32, history_split=[3, 4],
        source_covariance=covariance(current, current),
        persistent_covariance=symmetric(covariance(first, second)),
        source_residual_covariance=source_residual,
        base_residual_covariance=base_residual,
        source_base_residual_covariance=cross_residual,
        removed_structure_covariance=.5*(covariance(current-base, first)
                                         + covariance(current-base, second)),
        history_difference_covariance=covariance(first-second, first-second),
        history_difference_expected_if_stationary=source_residual*(1/3+1/4),
        lag_difference_covariance=np.array(lag_covariance),
        history_mean_difference=first.mean(axis=(1, 2))-second.mean(axis=(1, 2)),
        current_mean_difference=current.mean(axis=(1, 2))
            -.5*(first.mean(axis=(1, 2))+second.mean(axis=(1, 2))))
