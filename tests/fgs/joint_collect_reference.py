"""Independent NumPy oracle and finite synthetic fixtures for the CUDA collector.

Manual prepare/compare only; this does not run an encoder or change Tdarr.
Coordinates/counts/lookup histograms are exact. Matrix error is normalized by
the largest source diagonal with a 5e-6 tolerance declared before GPU trials.
"""
import argparse
import json
from pathlib import Path
import numpy as np

SIDE = 32
Y, X = np.mgrid[:SIDE, :SIDE].astype(np.float64)
X -= X.mean()
Y -= Y.mean()
NORM = np.sum(X * X)
OFFSETS = [(y, x) for y in range(-3, 1) for x in range(-3, 4) if y < 0 or x < 0]


def detrend(a):
    return a - a.mean() - np.sum(a * X) / NORM * X - np.sum(a * Y) / NORM * Y


def rounded(source, base, fraction):
    return np.rint(base.astype(np.float32) + np.float32(fraction)
                   * (source.astype(np.float32) - base.astype(np.float32))).astype(np.int32)


def read_frame(frame):
    if not frame['complete']:
        return None
    dtype = np.dtype('u1' if frame['depth'] == 8 else '<u2')
    result = []
    for p, view in enumerate(frame['planes']):
        rows = frame['height'] // (2 if p else 1)
        cols = frame['width'] // (2 if p else 1)
        raw = np.fromfile(view['path'], dtype=dtype).reshape(rows, view['pitch'] // dtype.itemsize)
        result.append((raw[:, view['offset'] // dtype.itemsize::view['stride']][:, :cols]
                       .astype(np.int32) >> frame['shift']))
    return result


def block_reference(case, source, base, previous, tile, native_base=None):
    x, y, component = tile
    cur, prev = case['source'], case['previous']
    history = previous is not None and cur['epoch'] == prev['epoch'] and cur['frame_id'] > 0 \
        and cur['frame_id'] - 1 == prev['frame_id'] and cur['pts'] > prev['pts'] \
        and all(cur[k] == prev[k] for k in ('width', 'height', 'depth', 'shift'))
    reasons = 0 if history else 1
    if component not in (1, 2) or x % 32 or y % 32 or x > cur['width']//2-32 or y > cur['height']//2-32:
        reasons |= 2
    if reasons:
        return dict(reasons=reasons, observations=0)
    sl = np.s_[y:y+32, x:x+32]
    ysl = np.s_[2*y:2*y+64, 2*x:2*x+64]
    maximum = (1 << cur['depth']) - 1
    if any(np.max(a[p][ysl if p == 0 else sl]) > maximum for a in (source, base, previous) for p in (0, 1, 2)):
        return dict(reasons=1024, observations=0)
    if native_base is None:
        native_base = [rounded(s, b, r) for s, b, r in zip(source, base, case['retain'])]
    scale = 1 << (cur['depth'] - 8)
    fields = []
    for a in (source, native_base, previous):
        fields.extend([a[0][ysl].reshape(32, 2, 32, 2).mean(axis=(1, 3))/scale,
                       a[component][sl].astype(np.float64)/scale])
    fields.extend([a[3-component][sl].astype(np.float64)/scale for a in (source, native_base, previous)])
    centered = [detrend(a) for a in fields]
    variances = [float(np.mean(a*a)) for a in centered]
    means = [float(a.mean()) for a in fields]
    correlations, coherences = [], []
    other_reasons = 0
    for p in range(3):
        index, prior = (6, 8) if p == 2 else (p, p+4)
        a, b = centered[index], centered[prior]
        v, r = variances[index], variances[prior]
        rejected = 0
        if not .04 <= v <= 256 or r <= 0:
            rejected |= 4 << min(p, 1)
        if abs(means[index]-means[prior]) > 1 or not .5*v <= r <= 2*v:
            rejected |= 16 << min(p, 1)
        correlation = float(np.mean(a*b)/np.sqrt(v*r)) if v > 0 and r > 0 else 0.
        if abs(correlation) > .15:
            rejected |= 64 << min(p, 1)
        gx = (a[1:-1, 2:]-a[1:-1, :-2])*.5
        gy = (a[2:, 1:-1]-a[:-2, 1:-1])*.5
        ax, ay, xy = np.sum(gx*gx), np.sum(gy*gy), np.sum(gx*gy)
        coherence = float(np.hypot(ax-ay, 2*xy)/max(1e-12, ax+ay))
        if coherence > .18:
            rejected |= 256 << min(p, 1)
        if p == 2:
            other_reasons = rejected
        else:
            reasons |= rejected
        correlations.append(correlation)
        coherences.append(coherence)
    result = dict(reasons=reasons, observations=0 if reasons else 676,
                  other_colour_reasons=other_reasons,
                  brightness_group=min(19, int(means[0]*20/256)), check_fold=(x//32+y//32) % 2,
                  mean=means, variance=variances, temporal_correlation=correlations, coherence=coherences)
    if not reasons:
        def vector(c, luma):
            return np.stack([c[3+dy:29+dy, 3+dx:29+dx].ravel() for dy, dx in OFFSETS]
                            + [luma[3:29, 3:29].ravel(), c[3:29, 3:29].ravel()], axis=1)
        sv, bv = vector(centered[1], centered[0]), vector(centered[3], centered[2])
        result.update(source=sv.T @ sv, base=bv.T @ bv, sourceBase=sv.T @ bv)
        sc = [centered[0], centered[1] if component == 1 else centered[6], centered[1] if component == 2 else centered[6]]
        bc = [centered[2], centered[3] if component == 1 else centered[7], centered[3] if component == 2 else centered[7]]
        s = np.stack([a[3:29, 3:29].ravel() for a in sc], axis=1)
        b = np.stack([a[3:29, 3:29].ravel() for a in bc], axis=1)
        result.update(colourSource=s.T@s, colourBase=b.T@b, colourSourceBase=s.T@b)
        cross = {k: [] for k in ('colourLagSource', 'colourLagBase', 'colourLagSourceBase', 'colourLagBaseSource')}
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                si, bi = sc[1][3:29, 3:29], bc[1][3:29, 3:29]
                sj, bj = sc[2][3+dy:29+dy, 3+dx:29+dx], bc[2][3+dy:29+dy, 3+dx:29+dx]
                for key, first, second in [('colourLagSource', si, sj), ('colourLagBase', bi, bj),
                                           ('colourLagSourceBase', si, bj), ('colourLagBaseSource', bi, sj)]:
                    cross[key].append(float(np.sum(first*second)))
        result.update({k: np.array(v) for k, v in cross.items()})
    return result


def write_frame(root, name, arrays, depth, semi, shift, frame_id):
    h, w = arrays[0].shape
    dtype = np.dtype('u1' if depth == 8 else '<u2')
    descriptions = []
    for p, a in enumerate(arrays):
        stride = 2 if semi and p else 1
        # Different nontrivial source/base/previous pitches, filled with sentinels.
        padding = {'source': 18, 'base': 34, 'previous': 50}[name]
        row_samples = a.shape[1]*stride + padding
        raw = np.full((a.shape[0], row_samples), 0xa5, dtype=dtype)
        offset = dtype.itemsize if semi and p == 2 else 0
        raw[:, offset//dtype.itemsize:offset//dtype.itemsize+a.shape[1]*stride:stride] = (a << shift).astype(dtype)
        path = root/f'{name}-{p}.raw'
        raw.tofile(path)
        descriptions.append(dict(path=str(path), pitch=raw.strides[0], stride=stride, offset=offset))
    return dict(width=w, height=h, depth=depth, shift=shift, frame_id=frame_id,
                pts=frame_id*40, epoch=1, complete=True, planes=descriptions)


def prepare(root):
    root.mkdir(parents=True, exist_ok=False)
    cases = []
    # All four production layouts, bright/dark noise, both colour signs, invalid
    # history, structured/quiet negatives, border occupancy and rounding fractions.
    specifications = [(8, False, 0, 'noise'), (8, True, 0, 'noise'),
                      (10, False, 0, 'noise'), (10, True, 6, 'noise'),
                      (10, False, 0, 'quiet'), (10, False, 0, 'persistent'),
                      (10, False, 0, 'directional'), (10, False, 0, 'level_jump'),
                      (10, True, 6, 'missing_history'), (10, False, 0, 'bad_codes'),
                      (10, False, 0, 'high_contrast')]
    for index, (depth, semi, shift, style) in enumerate(specifications):
        directory = root/f'case-{index:02d}'
        directory.mkdir()
        rng = np.random.default_rng(80403+index)
        h, w = 196, 260 # deliberate partial tile borders
        yy, xx = np.mgrid[:h, :w]
        signal = 24 + xx*.6 + yy*.02
        chroma_signal = 125 + xx[::2, ::2]*.02
        full = []
        for previous in (False, True):
            noise = rng.normal(0, 2, (h, w))
            luma = signal+noise
            driver = noise.reshape(h//2, 2, w//2, 2).mean(axis=(1, 3))
            cb = chroma_signal+rng.normal(0, 2, driver.shape)+.8*driver
            cr = chroma_signal+rng.normal(0, 3, driver.shape)-.8*driver
            if style == 'high_contrast':
                luma = signal+rng.normal(0, 80, (h, w))
                cb = chroma_signal+rng.normal(0, 80, driver.shape)
                cr = chroma_signal+rng.normal(0, 80, driver.shape)
            if style == 'quiet':
                luma, cb, cr = np.full_like(luma, 90), np.full_like(cb, 128), np.full_like(cr, 128)
            if style == 'directional':
                phase = np.pi/2 if previous else 0
                luma += 5*np.sin(xx*np.pi/4+phase)
                cb += 5*np.sin(xx[::2, ::2]*np.pi/4+phase)
            if style == 'level_jump' and previous:
                luma += 8
                cb += 8
            scale = 1 << (depth-8)
            full.append([np.rint(a*scale).clip(0, (1 << depth)-1).astype(np.int32) for a in (luma, cb, cr)])
        source, previous = full
        if style == 'persistent':
            previous = [a.copy() for a in source]
        base = [np.rint((a+np.roll(a, 1, axis=0)+np.roll(a, 1, axis=1))/3).astype(np.int32) for a in source]
        if style == 'bad_codes':
            source[0][0, 0] = 1024
        frames = {name: write_frame(directory, name, data, depth, semi, shift, number)
                  for name, data, number in [('source', source, 2), ('base', base, 2), ('previous', previous, 1)]}
        if style == 'missing_history':
            frames['previous']['complete'] = False
        tiles = [[x, y, p] for p in (1, 2) for y in range(0, h//2-31, 32) for x in range(0, w//2-31, 32)]
        tiles += [[1, 0, 1], [w//2, 0, 2], [0, 0, 0]]
        for r in ([0, .1, .25, .5, .75, 1] if index == 3 else [.25]):
            cases.append(dict(id=f'{index}-{style}-r{r}', **frames, retain=[.1, r, .5], tiles=tiles, repeats=3))
    manifest = dict(schema=1, matrix_energy_relative_tolerance=5e-6,
                    statistics_absolute_tolerance=2e-5, cases=cases)
    (root/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


def compare(manifest_path, report_path, output_path):
    manifest = json.loads(manifest_path.read_text())
    report = json.loads(report_path.read_text())
    assert report['complete'] and len(manifest['cases']) == len(report['cases'])
    summary = dict(complete=False, cases=[], matrix_energy_relative_tolerance=manifest['matrix_energy_relative_tolerance'])
    total_matrices = 0
    for case, measured in zip(manifest['cases'], report['cases']):
        assert case['id'] == measured['id'] and len(case['tiles']) == len(measured['tiles'])
        source, base, previous = [read_frame(case[k]) for k in ('source', 'base', 'previous')]
        native_base = [rounded(s, b, r) for s, b, r in zip(source, base, case['retain'])]
        maximum = (1 << case['source']['depth'])-1
        retained = native_base[0]
        invalid = (source[0] > maximum) | (base[0] > maximum)
        bad_c = invalid[::2, ::2] | invalid[::2, 1::2]
        upper = (retained[::2, ::2]+retained[::2, 1::2]+1)//2
        assert measured['lookup_y'] == np.bincount(retained[~invalid], minlength=1024).tolist()
        assert measured['lookup_c'] == np.bincount(upper[~bad_c], minlength=1024).tolist()
        assert measured['invalid_lookup_samples'] == int(invalid.sum()+bad_c.sum())
        accepted = 0
        worst = 0.
        grouped = [dict(blocks=0, observations=0, other_colour_supported_blocks=0,
                        moments=np.zeros(2251)) for _ in range(80)]
        for tile, gpu in zip(case['tiles'], measured['tiles']):
            cpu = block_reference(case, source, base, previous, tile, native_base)
            for key in ('reasons', 'observations', 'brightness_group', 'check_fold', 'other_colour_reasons'):
                if key in cpu:
                    assert cpu[key] == gpu[key], (case['id'], tile, key, cpu[key], gpu[key])
            for key in ('mean', 'variance', 'temporal_correlation', 'coherence'):
                if key in cpu:
                    error = float(np.max(np.abs(np.array(cpu[key])-gpu[key])))
                    assert error <= manifest['statistics_absolute_tolerance'], (case['id'], tile, key, error)
            if cpu['observations']:
                accepted += 1
                norm = max(1., float(np.max(np.diag(cpu['source']))))
                for key in ('source', 'base', 'sourceBase', 'colourSource', 'colourBase', 'colourSourceBase',
                            'colourLagSource', 'colourLagBase', 'colourLagSourceBase', 'colourLagBaseSource'):
                    error = float(np.max(np.abs(cpu[key]-np.array(gpu[key]).reshape(cpu[key].shape)))/norm)
                    worst = max(worst, error)
                    assert error <= manifest['matrix_energy_relative_tolerance'], (case['id'], tile, key, error)
                    total_matrices += 1
                group = grouped[(tile[2]-1)*40+cpu['check_fold']*20+cpu['brightness_group']]
                group['blocks'] += 1
                group['observations'] += 676
                group['other_colour_supported_blocks'] += cpu['other_colour_reasons'] == 0
                group['moments'] += np.concatenate([cpu[k].ravel() for k in ('source', 'base', 'sourceBase',
                    'colourSource', 'colourBase', 'colourSourceBase', 'colourLagSource', 'colourLagBase',
                    'colourLagSourceBase', 'colourLagBaseSource')])
            else:
                assert all(not np.any(gpu[k]) for k in ('source', 'base', 'sourceBase', 'colourSource', 'colourBase',
                    'colourSourceBase', 'colourLagSource', 'colourLagBase', 'colourLagSourceBase', 'colourLagBaseSource'))
        assert len(measured['groups']) == 80
        group_worst = 0.
        for cpu, gpu in zip(grouped, measured['groups']):
            for key in ('blocks', 'observations', 'other_colour_supported_blocks'):
                assert cpu[key] == gpu[key], (case['id'], 'group', key, cpu[key], gpu[key])
            norm = max(1., float(np.max(cpu['moments'][:676].reshape(26, 26).diagonal())))
            error = float(np.max(np.abs(cpu['moments']-gpu['moments'])))/norm
            group_worst = max(group_worst, error)
            assert error <= manifest['matrix_energy_relative_tolerance'], (case['id'], 'group error', error)
        summary['cases'].append(dict(id=case['id'], tiles=len(case['tiles']), accepted=accepted,
                                     maximum_matrix_error=worst, maximum_group_error=group_worst,
                                     milliseconds=measured['milliseconds']))
        print(case['id'], accepted, worst, flush=True)
    assert any(c['accepted'] for c in summary['cases'])
    # Real pictures may contain both valid and rejected tiles. Negative coverage
    # requires actual rejections, not an arbitrary wholly rejected picture.
    assert any(c['accepted'] < c['tiles'] for c in summary['cases'])
    summary.update(complete=True, matrices=total_matrices)
    output_path.write_text(json.dumps(summary, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare'); p.add_argument('directory', type=Path)
    p = sub.add_parser('compare'); p.add_argument('manifest', type=Path); p.add_argument('report', type=Path); p.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.directory)
    else:
        compare(args.manifest, args.report, args.output)
