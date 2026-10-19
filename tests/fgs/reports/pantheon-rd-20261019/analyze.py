#!/usr/bin/env python3
"""Validate and summarize fixed-decision initial-FP versus final reconstruction."""
import argparse
import json
import os
from pathlib import Path
import struct
import sys
import numpy as np
from scipy.ndimage import minimum_filter

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('PANTHEON_RD_ROOT', '/tmp/downloads/codex-work/pantheon-rd-20261019'))
sys.path.insert(0, str(HERE.parent / 'pantheon-independent-20261019'))
import investigate as x
from texture import desc, corr, BOXES
W, H = 1920, 1080

def read_tu(path):
    out = {}
    with path.open('rb') as f:
        while header := f.read(40):
            assert len(header) == 40
            name = header[:32].split(b'\0')[0].decode()
            n, size = struct.unpack('<II', header[32:])
            raw = f.read(n*size)
            assert len(raw) == n*size
            if name.endswith('meta') or name == 'meta':
                out[name] = json.loads(raw)
            else:
                out[name] = np.frombuffer(raw, dtype='<i4' if size == 4 else '<i2' if name == 'prediction_residual' else '<u2').copy()
    return out

def paired(s, z):
    return {**desc(z), 'mse': float(np.mean((z-s)**2)),
            'hf_corr_source': corr(x.high_pass(s), x.high_pass(z))}

def masked(s, z, valid):
    """Pairwise valid ACF; never concatenate disconnected pixels for lag statistics."""
    hs, hz = x.high_pass(s), x.high_pass(z)
    mask = minimum_filter(valid.astype(np.uint8), size=3, mode='constant')[1:-1, 1:-1].astype(bool)
    if not mask.any():
        return {'pixels': 0}
    centered = hz - hz[mask].mean()
    variance = np.mean(centered[mask]**2)
    hmask = mask[:, :-1] & mask[:, 1:]
    vmask = mask[:-1, :] & mask[1:, :]
    acf = None
    if variance > 1e-18 and hmask.any() and vmask.any():
        acf = float((np.mean((centered[:, :-1]*centered[:, 1:])[hmask])+
                     np.mean((centered[:-1, :]*centered[1:, :])[vmask]))/(2*variance))
    return {'pixels': int(mask.sum()), 'hf_sigma': float(hz[mask].std()*np.sqrt(8/5)),
            'acf1': acf, 'hf_corr_source': corr(hs[mask], hz[mask]),
            'pixel_mse': float(np.mean((z[1:-1, 1:-1][mask]-s[1:-1, 1:-1][mask])**2))}

def main():
    p = argparse.ArgumentParser()
    p.add_argument('case', choices=['e04', 'e05-1440'])
    p.add_argument('tag')
    p.add_argument('detail', type=Path)
    p.add_argument('frame', type=int)
    a = p.parse_args()
    fixture = ROOT/'fixtures'/a.case
    receipt = json.loads((fixture/'fresh-validation.json').read_text())
    validity = json.loads((fixture/'validity.json').read_text())
    assert receipt['source_raw_frame_md5'] == validity['hashes_ref']
    assert receipt['source_raw'] == x.fingerprint(fixture/'source.yuv')
    maps = {k: np.full((H, W), np.nan) for k in ('input', 'predictor', 'baseline', 'retained')}
    coverage = np.zeros((H, W), np.int16)
    quantized = np.zeros((H, W), bool)
    qmap = np.full((H, W), -1, np.int16)
    flags = {'residual_exact': True, 'forward_exact': True, 'final_inverse_exact': True}
    counts = {'tus': 0, 'quantizer_run': 0, 'bypass': 0, 'full_optimize_b': 0, 'other_quantizer_path': 0}
    rows = []
    for path in sorted(a.detail.glob(f'{a.frame+96:04d}-*.tu')):
        r = read_tu(path)
        m = r['meta']
        xx, yy, w, h = [m[k] for k in ('x', 'y', 'w', 'h')]
        assert m['poc'] == a.frame+96
        sl = np.s_[yy:min(yy+h, H), xx:min(xx+w, W)]
        hh, ww = coverage[sl].shape
        coverage[sl] += 1
        qmap[sl] = m['effective_qindex']
        flags['residual_exact'] &= bool(np.array_equal(r['input'].astype(int)-r['predictor'].astype(int), r['prediction_residual']))
        ran = 'actual_forward' in r
        counts['tus'] += 1
        counts['quantizer_run' if ran else 'bypass'] += 1
        quantized[sl] = ran
        if ran:
            assert w <= 32 and h <= 32, (w, h)
            flags['forward_exact'] &= bool(np.array_equal(r['private_forward'][:len(r['actual_forward'])], r['actual_forward']))
            flags['final_inverse_exact'] &= bool(np.array_equal(r['final_recon'], r['actual_recon']))
            qm = r['quant_meta']
            assert qm['effective_qindex'] == m['effective_qindex']
            density = int(r['initial_eob'][0])*100//(w*h)
            full = qm['rdoq_enabled'] and int(r['initial_eob'][0]) > 0 and density < min(qm['eob_threshold'], qm['eob_fast_threshold'])
            counts['full_optimize_b' if full else 'other_quantizer_path'] += 1
            if not np.array_equal(r['initial_qcoeff'], r['final_qcoeff']):
                assert full and not qm['shaving_enabled'], 'Changed coefficient path is not isolated full optimize_b'
        for name, key in [('input', 'input'), ('predictor', 'predictor'), ('baseline', 'actual_recon'), ('retained', 'initial_recon')]:
            # No residual is invented for bypassed TUs.
            vals = r.get(key, r['predictor'])
            maps[name][sl] = vals.reshape(h, w)[:hh, :ww]/4
        rows.append({'meta': m, 'quant_meta': r.get('quant_meta'), 'quantizer_ran': ran,
                     'initial_eob': int(r.get('initial_eob', [0])[0]), 'final_eob': int(r.get('final_eob', [0])[0])})
    assert np.all(coverage == 1), (coverage.min(), coverage.max())
    assert all(flags.values()), flags
    main_frame = 134 if a.case == 'e04' else 120
    if a.frame == main_frame:
        assert np.all(qmap == 32), ('Primary CQP8 target must realize q32', np.unique(qmap))
    else:
        assert np.all((qmap >= 9) & (qmap <= 32)), ('CQP8 hierarchy outside established range', np.unique(qmap))
    src = np.memmap(ROOT/'fixtures'/a.case/'source.yuv', dtype='<u2', mode='r', shape=(240, W*H*3//2))[a.frame, :W*H].reshape(H, W).astype(float)/4
    rois = {}
    for name, (xx, yy, w, h) in BOXES[a.case].items():
        sl = np.s_[yy:yy+h, xx:xx+w]
        s = src[sl]
        rois[name] = {'source': desc(s), 'qindex_unique': np.unique(qmap[sl]).tolist(),
                      'quantizer_run_fraction': float(quantized[sl].mean()),
                      'source_input_exact': bool(np.array_equal(s, maps['input'][sl])),
                      'whole_roi': {k: paired(s, z[sl]) for k, z in maps.items()},
                      'quantizer_run_neighborhoods': {k: masked(s, z[sl], quantized[sl]) for k, z in {'source': src, **maps}.items()}}
    control_name = a.case + (f'-frame{a.frame}' if a.frame != main_frame else '') + '-frozen-controls.json'
    controls = json.loads((ROOT/'parent'/control_name).read_text())
    assert (controls['case'], controls['frame'], controls['poc']) == (a.case, a.frame, a.frame+96)
    expected_grid = [[xx, yy, 32, 32] for yy in range(8, 1040, 48) for xx in range(8, 1880, 48)]
    assert [t['xywh'] for t in controls['tiles']] == expected_grid
    assert controls['counts'] == {k: sum(t['kind'] == k for t in controls['tiles']) for k in controls['counts']}
    control_rows = []
    for tile in controls['tiles']:
        xx, yy, w, h = tile['xywh']
        sl = np.s_[yy:yy+h, xx:xx+w]
        s = src[sl]
        assert tile['source'] == desc(s), 'Frozen source control descriptor mismatch'
        control_rows.append({**tile, 'quantizer_run_fraction': float(quantized[sl].mean()),
                             **{k: paired(s, z[sl]) for k, z in maps.items()}})
    summary = {}
    for kind in ('quiet', 'edge', 'flat_texture', 'other'):
        pool = [r for r in control_rows if r['kind'] == kind]
        summary[kind] = {'tiles': len(pool)}
        for arm in ('baseline', 'retained'):
            summary[kind][arm] = {
                'mse_mean': float(np.mean([r[arm]['mse'] for r in pool])) if pool else None,
                'hf_abs_error_mean': float(np.mean([abs(r[arm]['hf_sigma']-r['source']['hf_sigma']) for r in pool])) if pool else None,
                'added_hf_mean': float(np.mean([r[arm]['hf_sigma']-r['source']['hf_sigma'] for r in pool])) if pool else None,
            }
    out = ROOT/'parent'/(a.case+'-'+a.tag+f'-frame{a.frame}')
    assert not out.with_suffix('.json').exists()
    x.dump(out.with_suffix('.json'), {'case': a.case, 'tag': a.tag, 'frame': a.frame, 'checks': flags,
           'all_visible_pixels_covered_once': True, 'counts': counts, 'roi': rois,
           'controls': summary, 'control_tiles': control_rows, 'tus': rows,
           'interpretation': 'Private initial-FP reconstruction with fixed actual predictor and exercised transforms; no predictor feedback, filters or deployable stream claim.'})
    np.savez_compressed(out.with_suffix('.npz'), source=src, qindex=qmap, quantizer_run=quantized, **maps)
    print(json.dumps({'case': a.case, 'frame': a.frame, 'counts': counts, 'roi': rois, 'controls': summary}, indent=2))

if __name__ == '__main__':
    main()
