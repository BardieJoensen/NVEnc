#!/usr/bin/env python3
from __future__ import annotations

if not __debug__:
    raise SystemExit('optimized Python prohibited')

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

W, H = 1920, 1080
ROIS = {
    'shirt': (1200, 650, 200, 100),
    'background': (950, 50, 250, 180),
    'face': (160, 600, 500, 480),
}
EXPECTED = {
    'admission_review': 'f693e8069524d3c471f15b4dd6022d33aa8e08253b6ae5ac2c95bccb1dff5777',
    'stages': '02007de9587f0ad958f49abbcc0b425ba40e5eb855e76a5f24400193f8b36106',
    'support': 'f329a6416f3304130fb07a1cb153b88ad039b13e1392c868499cc70a4ad861bb',
    'admission': 'a86db1bcc3e4ff49b8e0aa66dfc601ac8bc7b67bb4415b3886263df7daaf50ab',
}


def ident(path: Path) -> dict:
    path = path.resolve()
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'path': str(path), 'sha256': digest, 'size': path.stat().st_size}


def exact_record(row: dict) -> Path:
    path = Path(row['path'])
    assert ident(path) == {key: row[key] for key in ('path', 'sha256', 'size')}
    return path


def load_luma(path: Path) -> np.ndarray:
    values = np.fromfile(path, dtype='<u2')
    assert values.size == W * H * 3 // 2
    values = values[:W * H]
    assert int(values.max()) <= 1023
    return values.reshape(H, W).astype(np.float64) / 4.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--admission-review', type=Path, required=True)
    parser.add_argument('--stages', type=Path, required=True)
    parser.add_argument('--support', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists() and not args.receipt.exists()

    script_before = ident(Path(__file__))
    supplied = {
        'admission_review': ident(args.admission_review),
        'stages': ident(args.stages),
        'support': ident(args.support),
    }
    for name, digest in EXPECTED.items():
        if name in supplied:
            assert supplied[name]['sha256'] == digest

    review = json.loads(args.admission_review.read_text())
    stages = json.loads(args.stages.read_text())
    support = json.loads(args.support.read_text())
    admission_path = Path(review['inputs']['admission']['path'])
    assert ident(admission_path) == review['inputs']['admission']
    assert ident(admission_path)['sha256'] == EXPECTED['admission']
    admission = json.loads(admission_path.read_text())
    assert support['admission'] == review['inputs']['admission'] == stages['admission']

    token_path = exact_record(admission['token_manifest'])
    tokens = json.loads(token_path.read_text())
    assert isinstance(tokens, list) and len(tokens) == admission['tokens'] == 2870
    source_paths = {name: exact_record(admission['source_boundaries'][name]) for name in ('original', 'preloop', 'postloop')}
    dependencies = [Path(__file__), args.admission_review, args.stages, args.support, admission_path, token_path, *source_paths.values()]
    before = [ident(path) for path in dependencies]
    receipt = {
        'status': 'running',
        'argv': sys.argv,
        'python': ident(Path(sys.executable)),
        'script': script_before,
        'inputs_before': before,
        'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    args.receipt.write_text(json.dumps(receipt, indent=2) + '\n')

    original = load_luma(source_paths['original'])
    surfaces = {name: load_luma(source_paths[name]) for name in ('preloop', 'postloop')}
    assert admission['source_change_count'] == 0
    verified = {}
    for roi, (rx, ry, rw, rh) in ROIS.items():
        owner = np.full((rh, rw), -1, dtype=np.int32)
        group_masks: dict[str, np.ndarray] = {}
        group_counts: dict[str, dict] = {}
        intersecting = 0
        for token in tokens:
            begin = token['begin']
            x, y, width, height = (int(begin[key]) for key in ('x', 'y', 'w', 'h'))
            ix0, iy0 = max(x, rx), max(y, ry)
            ix1, iy1 = min(x + width, rx + rw), min(y + height, ry + rh)
            if ix0 >= ix1 or iy0 >= iy1:
                continue
            local = np.s_[iy0 - ry:iy1 - ry, ix0 - rx:ix1 - rx]
            assert np.all(owner[local] == -1)
            owner[local] = int(token['token'])
            invoked = bool(token['stages'])
            eob = int(token['end']['eob'])
            if invoked:
                assert isinstance(token['info'], dict) and isinstance(token['info']['actual_qindex'], int)
            else:
                assert token['info'] is None and eob == 0
            group = ('invoked' if invoked else 'uninvoked') + '_' + ('positive_eob' if eob > 0 else 'zero_eob')
            mask = group_masks.setdefault(group, np.zeros((rh, rw), dtype=bool))
            assert not mask[local].any()
            mask[local] = True
            count = (iy1 - iy0) * (ix1 - ix0)
            row = group_counts.setdefault(group, {'pixels': 0, 'units': 0, 'q_values': {}, 'geometry': {}})
            row['pixels'] += count
            row['units'] += 1
            if invoked:
                q = str(token['info']['actual_qindex'])
                row['q_values'][q] = row['q_values'].get(q, 0) + count
            geometry = f'{width}x{height}'
            row['geometry'][geometry] = row['geometry'].get(geometry, 0) + count
            intersecting += 1
        assert np.all(owner >= 0)
        assert sum(int(mask.sum()) for mask in group_masks.values()) == rw * rh
        assert intersecting == support['rois'][roi]['groups']['_totals']['units']
        assert set(group_masks) == set(support['rois'][roi]['groups']) - {'_totals'}

        crop_original = original[ry:ry + rh, rx:rx + rw]
        recomputed = {}
        for group, mask in group_masks.items():
            expected_group = support['rois'][roi]['groups'][group]
            assert group_counts[group]['pixels'] == expected_group['pixels'] == int(mask.sum())
            assert group_counts[group]['units'] == expected_group['units']
            assert group_counts[group]['q_values'] == expected_group['q_values']
            assert group_counts[group]['geometry'] == expected_group['geometry']
            recomputed[group] = {}
            for stage, surface in surfaces.items():
                crop = surface[ry:ry + rh, rx:rx + rw]
                sse = float(np.square(crop[mask] - crop_original[mask]).sum())
                assert sse == expected_group['sse'][stage]['vs_original'], (roi, group, stage, sse, expected_group['sse'][stage]['vs_original'])
                recomputed[group][stage] = sse

        aggregate = {}
        for stage in ('raw_executed', 'scalar', 'final'):
            sse = sum(group['sse'][stage]['vs_original'] for name, group in support['rois'][roi]['groups'].items() if name != '_totals')
            mse = sse / (rw * rh)
            assert mse == stages['fixed_roi'][roi]['stages'][stage]['mse']
            aggregate[stage] = {'sse': sse, 'mse': mse}
        assert aggregate['final']['sse'] == sum(value['preloop'] for value in recomputed.values())
        verified[roi] = {
            'pixels': rw * rh,
            'owner_tokens': intersecting,
            'group_counts': group_counts,
            'native_surface_sse': recomputed,
            'aggregate_only_checks': aggregate,
        }

    after = [ident(path) for path in dependencies]
    assert before == after and script_before == ident(Path(__file__))
    output = {
        'status': 'complete',
        'script': script_before,
        'inputs': supplied,
        'admission': ident(admission_path),
        'token_manifest': ident(token_path),
        'source_surfaces': {name: ident(path) for name, path in source_paths.items()},
        'verified': verified,
        'scope': 'Independent geometry masks and native original-referenced preloop/postloop SSE; raw/scalar/final are aggregate closure checks only.',
    }
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')
    receipt.update(
        status='complete',
        inputs_after=after,
        output=ident(args.output),
        ended_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
    )
    args.receipt.write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
