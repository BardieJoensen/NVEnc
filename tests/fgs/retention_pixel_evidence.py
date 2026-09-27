"""Native pixel evidence for finite retention candidates.

This computes necessary checks from actual pixels. It never supplies source
classification, missing-target validity, a model fit or independent detail
truth. Those missing proofs remain unmeasured in the returned selector mask.
All signal statistics are in 8-bit code units, not perceptual HDR units.
"""
from __future__ import annotations
import hashlib
import numpy as np
from native_geometry_reference import measure as spatial_moments

ROUNDED_BASE, FINITE_SYNTHESIS, AMPLITUDE = 1, 16, 128


def native_picture(planes, depth, shape=None):
    if depth not in (8, 10) or len(planes) != 3:
        raise ValueError('three native 8/10-bit planes required')
    arrays = [np.asarray(p) for p in planes]
    if arrays[0].ndim != 2:
        raise ValueError('native luma must be two-dimensional')
    height, width = arrays[0].shape
    if (width < 64 or height < 64 or width > 4096 or height > 2160
            or width % 2 or height % 2 or (shape and shape != (height, width))):
        raise ValueError('native candidate layout differs')
    for c, a in enumerate(arrays):
        if (a.shape != (height//(2 if c else 1), width//(2 if c else 1))
                or a.dtype.kind not in 'iu' or np.any(a < 0)
                or np.any(a >= (1 << depth))):
            raise ValueError('native candidate plane/range differs')
    return arrays


def hashes(planes):
    return [hashlib.sha256(p.astype('<u2').tobytes()).hexdigest() for p in planes]


def matrix_check(source, actual):
    source, actual = np.asarray(source), np.asarray(actual)
    if (source.ndim != 2 or source.shape[0] != source.shape[1]
            or actual.shape != source.shape or not np.isfinite(source).all()
            or not np.isfinite(actual).all() or np.any(np.diag(source) <= 1e-12)
            or np.any(np.diag(actual) < 0)):
        return dict(valid=False, pass_bounds=False)
    denominator = np.sqrt(np.diag(source))
    errors = np.abs(actual-source)/denominator[:, None]/denominator[None, :]
    variance = float(np.diag(errors).max())
    covariance = float(errors[~np.eye(len(errors), dtype=bool)].max())
    return dict(valid=True, variance=variance, covariance=covariance,
                pass_bounds=variance <= .08 and covariance <= .08)


def compare_moments(source, actual):
    """Keep full spatial failures; caller may separately measure an 8-frame window."""
    folds = []
    for s, a in zip(source['folds'], actual['folds']):
        errors = (np.asarray(a['mean'])-s['mean']).tolist()
        checks = [matrix_check(s['y'], a['y'])]
        checks += [matrix_check(s['colour'][c], a['colour'][c]) for c in range(2)]
        common = matrix_check(s['common'], a['common'])
        diagonal = np.diag(s['common'])
        cross = (float(np.max(np.abs(np.asarray(a['cross'])-s['cross']))
                       / np.sqrt(diagonal[1])/np.sqrt(diagonal[2]))
                 if diagonal[1] > 1e-12 and diagonal[2] > 1e-12 else None)
        folds.append(dict(components=checks, common=common, cbcr_lag=cross,
                          mean_error=errors,
                          mean_pass=max(map(abs, errors)) <= .125))
    means = (np.asarray(actual['mean'])-source['mean']).tolist()
    components = []
    for c in range(3):
        spatial = all(f['components'][c]['pass_bounds'] for f in folds)
        amplitude = all(f['components'][c]['valid']
                        and f['components'][c]['variance'] <= .08 for f in folds)
        mean = abs(means[c]) <= .125 and all(abs(f['mean_error'][c]) <= .125 for f in folds)
        valid = all(f['components'][c]['valid'] for f in folds)
        components.append(dict(valid=valid, spatial_pass=spatial, amplitude_pass=amplitude,
                               mean_pass=mean, full_pass=spatial and mean))
    joint = all(f['common']['pass_bounds'] and f['cbcr_lag'] is not None
                and f['cbcr_lag'] <= .08 and f['mean_pass'] for f in folds)
    return dict(folds=folds, mean_error=means, components=components,
                joint_spatial_pass=joint,
                full_pass=joint and all(c['full_pass'] for c in components))


def measure(source, pristine, rounded_base, reconstructed, decoded, depth, fractions):
    """Bind every stage by native content and measure each component separately.

    `decoded` is the actual grain-on decoded output; this function does not
    assert that it came from a particular model. The caller must establish that
    model/packet/decoder association independently before using these facts.
    """
    source = native_picture(source, depth)
    shape = source[0].shape
    stages = [native_picture(p, depth, shape) for p in
              (pristine, rounded_base, reconstructed, decoded)]
    pristine, rounded_base, reconstructed, decoded = stages
    if (not isinstance(fractions, (list, tuple, np.ndarray)) or len(fractions) != 3
            or any(not isinstance(f, (int, float, np.integer, np.floating))
                   or isinstance(f, (bool, np.bool_)) for f in fractions)
            or not np.isfinite(fractions).all() or np.any(np.asarray(fractions) < 0)
            or np.any(np.asarray(fractions) > 1)):
        raise ValueError('three finite numeric fractions in [0,1] required')
    fractions = np.asarray(fractions, dtype=np.float32)
    rounding = []
    for s, b, actual, fraction in zip(source, pristine, rounded_base, fractions):
        expected = np.rint(b.astype(np.float32)
                           + fraction*(s.astype(np.float32)-b.astype(np.float32)))
        rounding.append(dict(samples=s.size,
                             mismatch_samples=int(np.count_nonzero(actual != expected)),
                             changed_source_samples=int(np.count_nonzero(actual != s))))
    source_moments, _ = spatial_moments(source, depth)
    output_moments, _ = spatial_moments(decoded, depth)
    comparison = compare_moments(source_moments, output_moments)
    checks = []
    for c, row in enumerate(rounding):
        observed = comparison['components'][c]
        measured = ROUNDED_BASE
        passed = (ROUNDED_BASE if row['mismatch_samples'] == 0 else 0)
        if observed['valid']:
            measured |= FINITE_SYNTHESIS | AMPLITUDE
            if observed['full_pass']:
                passed |= FINITE_SYNTHESIS
            if observed['amplitude_pass']:
                passed |= AMPLITUDE
        checks.append(dict(measured=measured, passed=passed,
                           unmeasured=255 & ~measured))
    return dict(source_admission=False, model_association_proven=False,
                fractions=fractions.tolist(), depth=depth,
                hashes={k: hashes(p) for k, p in zip(
                    ('source', 'pristine', 'rounded', 'reconstructed', 'decoded'), [source, *stages])},
                rounding=rounding, spatial=comparison, checks=checks,
                source_moments=source_moments, output_moments=output_moments)
