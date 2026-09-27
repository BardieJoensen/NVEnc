"""Independent native NumPy quiet/range scan; no detail/population admission.

The constant-strength model scope is checked by the caller against the actual
emitted model. This measures code-domain criteria, not perceptual HDR quality.
"""
import numpy as np
from retention_pixel_evidence import native_picture


def regions(source, rounded, reconstructed, decoded, depth, side, coarse, nonzero):
    result = dict(regions=0, samples=0, quiet_regions=0, quiet_samples=0,
                  changed_quiet=0, nonzero_quiet=0, output_changed_quiet=0)
    scale = 1 << (depth-8)
    height, width = source.shape
    for top in range(0, height, side):
        for left in range(0, width, side):
            sl = np.s_[top:min(top+side, height), left:min(left+side, width)]
            tile = source[sl].astype(np.float64)/scale
            n = tile.size
            if coarse:
                y, x = np.indices(tile.shape, dtype=np.float64)
                design = np.column_stack((np.ones(n), x.ravel(), y.ravel()))
                fitted = design @ np.linalg.lstsq(design, tile.ravel(), rcond=None)[0]
                variance = np.mean((tile.ravel()-fitted)**2)
                quiet = variance < .04
            else:
                raw = source[sl].astype(np.int64)
                quiet = 100*(n*np.sum(raw*raw)-np.sum(raw)**2) <= 9*scale*scale*n*n
            result['regions'] += 1
            result['samples'] += n
            if quiet:
                result['quiet_regions'] += 1
                result['quiet_samples'] += n
                result['nonzero_quiet'] += n if nonzero else 0
                result['changed_quiet'] += int(np.count_nonzero(source[sl] != rounded[sl]))
                result['output_changed_quiet'] += int(np.count_nonzero(reconstructed[sl] != decoded[sl]))
    result['pass'] = not any(result[k] for k in ('changed_quiet', 'nonzero_quiet', 'output_changed_quiet'))
    return result


def measure(source, rounded, reconstructed, decoded, depth, model):
    source = native_picture(source, depth)
    rounded, reconstructed, decoded = [native_picture(p, depth, source[0].shape)
                                       for p in (rounded, reconstructed, decoded)]
    if (type(model['apply']) is not bool or type(model['restricted']) is not bool
            or type(model['matrix']) is not int or model['matrix'] not in (1, 9)
            or len(model['strength']) != 3
            or any(type(s) is not int or not 0 <= s <= 255 for s in model['strength'])
            or (not model['apply'] and any(model['strength']))):
        raise ValueError('native quiet constant-curve scope differs')
    scale = 1 << (depth-8)
    components = []
    for c in range(3):
        planes = [p[c] for p in (source, rounded, reconstructed, decoded)]
        nonzero = model['apply'] and model['strength'][c] > 0
        fine = regions(*planes, depth, 8, False, nonzero)
        coarse = regions(*planes, depth, 32 if c else 64, True, nonzero)
        r, d = planes[2:]
        low = 16*scale if model['restricted'] else 0
        high = (240 if c else 235)*scale if model['restricted'] else (1 << depth)-1
        inside = (d >= low) & (d <= high)
        if not model['apply']:
            safe = int(np.count_nonzero(r == d)); failed = d.size-safe; ambiguous = 0
        elif not nonzero:
            safe = int(np.count_nonzero((r == d) & inside)); failed = d.size-safe; ambiguous = 0
        else:
            safe = int(np.count_nonzero((d > low) & (d < high)))
            ambiguous = int(np.count_nonzero((d == low) | (d == high)))
            failed = int(np.count_nonzero(~inside))
        clamp = dict(samples=d.size, safe=safe, ambiguous=ambiguous, failed=failed,
                     measured=not ambiguous or failed > 0, **{'pass': safe == d.size})
        components.append(dict(fine=fine, coarse=coarse, quiet_pass=fine['pass'] and coarse['pass'], range=clamp))
    return dict(complete=True, source_admission=False, components=components)
