"""Direct NumPy reference for complete native rectangular measurements.

No integral-image optimization and no source eligibility decision. Fold means
include every native sample; spatial moments use explicit shifted vectors and
pool observations before normalization. Source/base products stay oriented.
"""
from __future__ import annotations
import numpy as np

OFFSETS = [(y, x) for y in range(-3, 1) for x in range(-3, 4)
           if y < 0 or x < 0] + [(0, 0)]


def rectangles(width, height):
    if (width < 64 or height < 64 or width > 4096 or height > 2160
            or width % 2 or height % 2):
        raise ValueError('unsupported even native geometry')
    xs = (np.linspace(0, width // 2, (width + 63) // 64 + 1)
          .astype(np.int64) * 2).tolist()
    ys = (np.linspace(0, height // 2, (height + 63) // 64 + 1)
          .astype(np.int64) * 2).tolist()
    if len(xs) == len(ys) == 2:
        raise ValueError('both independent folds must be populated')
    for by, (top, bottom) in enumerate(zip(ys, ys[1:])):
        for bx, (left, right) in enumerate(zip(xs, xs[1:])):
            yield (bx + by) % 2, left, top, right, bottom


def detrend(tile):
    height, width = tile.shape
    xx = np.arange(width, dtype=np.float64) - (width - 1) / 2
    yy = np.arange(height, dtype=np.float64) - (height - 1) / 2
    sx = np.sum(tile * xx) / (height * (xx @ xx))
    sy = np.sum(tile * yy[:, None]) / (width * (yy @ yy))
    return tile - tile.mean() - sx * xx - sy * yy[:, None]


def vectors(tile):
    height, width = tile.shape
    return np.stack([tile[3+y:height-3+y, 3+x:width-3+x].ravel()
                     for y, x in OFFSETS])


def fields(planes, rect, scale):
    _, left, top, right, bottom = rect
    y = planes[0][top:bottom, left:right].astype(np.float64) / scale
    ly = y.reshape(y.shape[0]//2, 2, y.shape[1]//2, 2).mean(axis=(1, 3))
    cc = [p[top//2:bottom//2, left//2:right//2].astype(np.float64) / scale
          for p in planes[1:]]
    return [y, ly, *cc]


def spatial_vectors(tiles):
    y = vectors(tiles[0])
    ly = tiles[1][3:-3, 3:-3].ravel()
    colour = []
    for tile in tiles[2:]:
        c = vectors(tile)
        colour.append(np.concatenate((c[:24], ly[None], c[24:]), axis=0))
    common = np.stack([tile[3:-3, 3:-3].ravel() for tile in tiles[1:]])
    return y, colour, common


def measure(planes, depth, base=None):
    height, width = planes[0].shape
    if depth not in (8, 10):
        raise ValueError('unsupported depth')
    for pp in ([planes, base] if base is not None else [planes]):
        if len(pp) != 3 or any(p.shape != (height//(2 if c else 1), width//(2 if c else 1))
                               for c, p in enumerate(pp)):
            raise ValueError('plane layout differs')
        if any(np.any(p < 0) or np.any(p >= (1 << depth)) for p in pp):
            raise ValueError('native range differs')
    scale = 1 << (depth - 8)
    folded = [{'y': np.zeros((25, 25)), 'colour': np.zeros((2, 26, 26)),
               'common': np.zeros((3, 3)), 'cross': np.zeros((7, 7)),
               'mean': np.zeros(3), 'pixels': 0, 'blocks': 0,
               'yn': 0, 'cn': 0} for _ in range(2)]
    pairs = [[{'source': np.zeros((n, n)), 'base': np.zeros((n, n)),
               'sourceBase': np.zeros((n, n)), 'blocks': 0, 'observations': 0}
              for _ in range(2)] for n in (25, 26, 26)]
    for rect in rectangles(width, height):
        f, left, top, right, bottom = rect
        row = folded[f]
        raw = fields(planes, rect, scale)
        tile = [detrend(a) for a in raw]
        yy, cc, common = spatial_vectors(tile)
        row['mean'] += [raw[c].sum() for c in (0, 2, 3)]
        row['pixels'] += (right - left) * (bottom - top)
        row['blocks'] += 1
        row['yn'] += yy.shape[1]
        row['cn'] += common.shape[1]
        row['y'] += yy @ yy.T
        for c in range(2):
            row['colour'][c] += cc[c] @ cc[c].T
        row['common'] += common @ common.T
        h, w = tile[3].shape
        for iy, dy in enumerate(range(-3, 4)):
            for ix, dx in enumerate(range(-3, 4)):
                row['cross'][iy, ix] += common[1] @ tile[3][3+dy:h-3+dy, 3+dx:w-3+dx].ravel()
        if base is not None:
            by, bc, _ = spatial_vectors([detrend(a) for a in fields(base, rect, scale)])
            for kind, (sv, bv) in enumerate(zip([yy, *cc], [by, *bc])):
                pair = pairs[kind][f]
                pair['blocks'] += 1
                pair['observations'] += sv.shape[1]
                pair['source'] += sv @ sv.T
                pair['base'] += bv @ bv.T
                pair['sourceBase'] += sv @ bv.T
    output = {'valid': True, 'width': width, 'height': height, 'depth': depth,
              'mean': [p.mean()/scale for p in planes],
              'blocks': [r['blocks'] for r in folded], 'folds': []}
    for r in folded:
        output['folds'].append({'mean_valid': True,
            'mean': (r['mean'] / [r['pixels'], r['pixels']/4, r['pixels']/4]).tolist(),
            **{k: (r[k] / (r['yn'] if k == 'y' else r['cn'])).tolist()
               for k in ('y', 'colour', 'common', 'cross')}})
    for component in pairs:
        for p in component:
            for k in ('source', 'base', 'sourceBase'):
                p[k] = p[k].ravel().tolist()
    return output, {'luma': pairs[0], 'colour': pairs[1:]}
