"""Bounded native source/output measurements for offline recovery audits.

This is not source admission or a visibility classifier. Two-frame flat-region
screening cannot resolve persistent grain or fast moving texture. Unsupported
regions and partial borders remain explicitly unqualified. HDR measurements
are in native code values scaled to 8-bit units, not light or display units.
"""
import numpy as np


def _residual(values):
    h, w = values.shape[-2:]
    x = np.arange(w, dtype=np.float64) - (w-1)/2
    y = np.arange(h, dtype=np.float64) - (h-1)/2
    mean = values.mean(axis=(-2, -1))
    sx = np.sum(values*x, axis=(-2, -1))/(h*(x@x))
    sy = np.sum(values*y[:, None], axis=(-2, -1))/(w*(y@y))
    return values-mean[:, None, None]-sx[:, None, None]*x-sy[:, None, None]*y[:, None]


def _screen(current, previous):
    """Source-only necessary evidence; candidates cannot select coordinates."""
    a, b = _residual(current), _residual(previous)
    variance = np.mean(a*a, axis=(-2, -1))
    old_variance = np.mean(b*b, axis=(-2, -1))
    denom = np.sqrt(variance*old_variance)
    correlation = np.divide(np.mean(a*b, axis=(-2, -1)), denom,
                            out=np.zeros_like(denom), where=denom > 0)
    gx = (a[:, 1:-1, 2:]-a[:, 1:-1, :-2])*.5
    gy = (a[:, 2:, 1:-1]-a[:, :-2, 1:-1])*.5
    ax, ay, xy = [np.sum(v, axis=(-2, -1)) for v in (gx*gx, gy*gy, gx*gy)]
    coherence = np.hypot(ax-ay, 2*xy)/np.maximum(1e-12, ax+ay)
    reasons = ((variance < .04) | (variance > 256) | (old_variance <= 0)).astype(np.uint8)
    reasons |= (((np.abs(current.mean(axis=(-2, -1))-previous.mean(axis=(-2, -1))) > 1)
                 | (old_variance < .5*variance) | (old_variance > 2*variance)).astype(np.uint8) << 1)
    reasons |= ((np.abs(correlation) > .15).astype(np.uint8) << 2)
    reasons |= ((coherence > .18).astype(np.uint8) << 3)
    constant = np.all(current == current[:, :1, :1], axis=(-2, -1))
    quiet = constant & np.all(current == previous, axis=(-2, -1))
    return dict(reasons=reasons, stable_constant=quiet, temporal_correlation=correlation,
                gradient_coherence=coherence, source_variance=variance), a


def measure_plane(source, previous, base, output, depth, component):
    """Native Y64/C32 tiles, at most 128 simultaneous floating-point tiles.

    Callers must verify native source/output alignment and timestamps first.
    Selection is per component and does not certify joint colour compatibility.
    The returned arrays preserve every full tile, including rejected ones.
    """
    if depth not in (8, 10) or type(component) is not int or component not in (0, 1, 2):
        raise ValueError('native 8/10-bit component required')
    side = 32 if component else 64
    arrays = [np.asarray(a) for a in (source, previous, base, output)]
    shape = arrays[0].shape
    if (len(shape) != 2 or min(shape) < side
            or any(a.shape != shape or a.dtype.kind not in 'iu' for a in arrays)
            or any(np.any(a < 0) or np.any(a >= 1 << depth) for a in arrays)):
        raise ValueError('equal valid native integer planes required')
    h, w = shape
    coordinates = [(x, y) for y in range(0, h-side+1, side)
                   for x in range(0, w-side+1, side)]
    chunks = []
    for begin in range(0, len(coordinates), 128):
        positions = coordinates[begin:begin+128]
        source_tiles, previous_tiles, base_tiles, output_tiles = [
            np.array([a[y:y+side, x:x+side] for x, y in positions], dtype=np.float64)
            / (1 << (depth-8)) for a in arrays]
        result, src = _screen(source_tiles, previous_tiles)
        coded, final = _residual(base_tiles), _residual(output_tiles)
        grain = output_tiles-base_tiles
        for name, residual in [('base', coded), ('output', final)]:
            result[name+'_variance'] = np.mean(residual*residual, axis=(-2, -1))
        for name, values in [('base', base_tiles), ('output', output_tiles)]:
            error = values-source_tiles
            result[name+'_mean_error'] = error.mean(axis=(-2, -1))
            result[name+'_source_rms'] = np.sqrt(np.mean(error*error, axis=(-2, -1)))
        result['added_grain_rms'] = np.sqrt(np.mean(grain*grain, axis=(-2, -1)))
        result['source_output_covariance'] = np.mean(src*final, axis=(-2, -1))
        chunks.append(result)
    return dict(source_admission=False, component=component, side=side,
                width=w, height=h, unmeasured_border_samples=w*h-len(coordinates)*side*side,
                coordinates=np.array(coordinates, dtype=np.int32),
                **{k: np.concatenate([r[k] for r in chunks]) for k in chunks[0]})
