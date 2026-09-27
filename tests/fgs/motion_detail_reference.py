"""Independent native translation/removal measurements; necessary veto only.

Motion is selected from source pairs 0/1 and 2/3, then checked on 4/5 and 6/7.
Neither the candidate nor validation frames can change the proposal. Detail is
measured at native resolution along the aligned previous source direction.
Absence of a conflict never grants detail, population or stationarity approval.
"""
import numpy as np


def validate(source, base, depth, side, radius, step, ids, pts):
    source, base = np.asarray(source), np.asarray(base)
    if (type(depth) is not int or depth not in (8, 10) or type(side) is not int
            or side not in (32, 64) or type(radius) is not int or not 1 <= radius <= 32
            or type(step) is not int or step not in (2, 4) or source.ndim != 3
            or source.shape[0] != 8 or source.shape[1:] != base.shape or base.ndim != 2
            or not 32 <= base.shape[0] <= 2160 or not 32 <= base.shape[1] <= 4096):
        raise ValueError('invalid native motion geometry/scope')
    for a in (source, base):
        if a.dtype.kind not in 'iu' or np.any(a < 0) or np.any(a >= 1 << depth):
            raise ValueError('native integer source/base required')
    ids, pts = np.asarray(ids), np.asarray(pts)
    if (ids.shape != (8,) or ids.dtype.kind not in 'iu' or np.any(ids < 0)
            or np.any(ids > 2147483647) or np.any(ids[1:]-ids[:-1] != 1)
            or pts.shape != (8,) or pts.dtype.kind not in 'iu'
            or np.any(pts <= -9223372036854775808) or np.any(pts > 9223372036854775807)
            or np.any(pts[1:] <= pts[:-1])):
        raise ValueError('adjacent IDs and increasing integer clocks required')
    return source, base


def tile(source, base, depth, side, radius, step, x, y, native_match=False):
    """Internal measurement on validated pictures and canonical coordinates."""
    h, w = base.shape; tw, th = min(side, w-x), min(side, h-y)
    current = source[7, y:y+th, x:x+tw]
    candidate = base[y:y+th, x:x+tw]
    xs = np.array([v for v in range(x, x+tw, step) if radius < v < w-radius-1])
    ys = np.array([v for v in range(y, y+th, step) if radius < v < h-radius-1])
    result = dict(x=x, y=y, width=tw, height=th, fit_samples=int(xs.size*ys.size),
                  dx=0, dy=0, training_mse=0., zero_mse=[0., 0.], shifted_mse=[0., 0.],
                  improvement=[0., 0.], relative_defined=[False, False],
                  motion_supported=False, anchor_supported=False, conflict=False,
                  samples=tw*th, changed_samples=int(np.count_nonzero(current != candidate)),
                  projected_samples=0, correlation=0., contrast_change=0.,
                  removed_projection_rms=0., mean_error=0.)
    if result['fit_samples'] < 16: return result
    # Independently construct local weighted images and vectorized search costs.
    x0, y0 = int(xs[0]-radius), int(ys[0]-radius)
    cw, ch = int(xs[-1]+radius-x0+1), int(ys[-1]+radius-y0+1)
    patch = source[:, y0-1:y0+ch+1, x0-1:x0+cw+1].astype(np.int32)
    smooth = (patch[:, 1:ch+1, 1:cw+1]*16 if native_match else
              sum(patch[:, j:j+ch, i:i+cw]*wy*wx
                  for j, wy in enumerate((1, 2, 1)) for i, wx in enumerate((1, 2, 1))))
    yy, xx = np.meshgrid(ys-y0, xs-x0, indexing='ij'); yy=yy.ravel(); xx=xx.ravel()
    shifts = [(0, 0)] + [(dy, dx) for dy in range(-radius, radius+1)
                        for dx in range(-radius, radius+1) if dy or dx]
    costs = []
    for begin in range(0, len(shifts), 64):
        offsets = np.array(shifts[begin:begin+64])
        iy = yy[None, :]+offsets[:, 0, None]; ix=xx[None, :]+offsets[:, 1, None]
        a = smooth[1, yy, xx]-smooth[0, iy, ix]
        b = smooth[3, yy, xx]-smooth[2, iy, ix]
        costs.extend((np.sum(a.astype(np.int64)**2, axis=1)
                      + np.sum(b.astype(np.int64)**2, axis=1)).tolist())
    index = int(np.argmin(costs)); dy, dx = shifts[index]
    scale = 1 << (depth-8); denominator=result['fit_samples']*256*scale*scale
    result.update(dx=dx, dy=dy, training_mse=costs[index]/(2*denominator))
    for i, (before, after) in enumerate(((4, 5), (6, 7))):
        target = smooth[after, yy, xx]
        zero = np.mean(((target-smooth[before, yy, xx]).astype(np.float64)/(16*scale))**2)
        shifted = np.mean(((target-smooth[before, yy+dy, xx+dx]).astype(np.float64)/(16*scale))**2)
        result['zero_mse'][i] = float(zero); result['shifted_mse'][i] = float(shifted)
        result['relative_defined'][i] = bool(zero > 0)
        if zero > 0: result['improvement'][i] = float((zero-shifted)/zero)
    result['motion_supported'] = bool((dx or dy) and all(
        z > .04 and improvement > .2 for z, improvement in zip(result['zero_mse'], result['improvement'])))
    if not result['motion_supported']: return result
    yy, xx = np.mgrid[y:y+th, x:x+tw]; keep=(yy+dy >= 0)&(xx+dx >= 0)&(yy+dy < h)&(xx+dx < w)
    yy, xx = yy[keep], xx[keep]
    if not yy.size: return result
    s=source[7, yy, xx].astype(np.float64)/scale
    a=source[6, yy+dy, xx+dx].astype(np.float64)/scale
    removed=s-base[yy, xx].astype(np.float64)/scale
    sc, ac, dc = s-s.mean(), a-a.mean(), removed-removed.mean()
    vs, va, cross = np.mean(sc*sc), np.mean(ac*ac), np.mean(sc*ac)
    result['mean_error'] = float(removed.mean())
    if vs > 0 and va > 0:
        result['correlation'] = float(cross/np.sqrt(vs*va))
        result['anchor_supported'] = bool(result['correlation'] >= .5)
        if result['anchor_supported']:
            projection = np.mean(dc*ac)
            result['projected_samples'] = int(s.size)
            result['contrast_change'] = float(projection/cross)
            result['removed_projection_rms'] = float(abs(projection)/np.sqrt(va))
            result['conflict'] = bool(abs(result['contrast_change']) > .02
                or result['removed_projection_rms'] > .125 or abs(result['mean_error']) > .125)
    return result


def measure(source, base, depth, side, radius, step, ids, pts, native_match=False):
    if type(native_match) is not bool: raise ValueError('native matching flag must be boolean')
    source, base = validate(source, base, depth, side, radius, step, ids, pts)
    return dict(valid=True, source_admission=False, detail_admission=False, tiles=[
        tile(source, base, depth, side, radius, step, x, y, native_match)
        for y in range(0, base.shape[0], side) for x in range(0, base.shape[1], side)])
