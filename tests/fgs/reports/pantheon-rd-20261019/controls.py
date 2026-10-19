#!/usr/bin/env python3
"""Freeze original-defined controls before examining a new candidate."""
import json
import os
from pathlib import Path
import sys
import numpy as np
from scipy.ndimage import gaussian_filter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'pantheon-independent-20261019'))
from texture import desc, BOXES
ROOT = Path(os.environ.get('PANTHEON_RD_ROOT', '/tmp/downloads/codex-work/pantheon-rd-20261019'))

def freeze(case, frame=None):
    n = (134 if case == 'e04' else 120) if frame is None else frame
    path = ROOT / 'fixtures' / case
    s = np.memmap(path / 'source.yuv', dtype='<u2', mode='r',
                  shape=(240, 1920 * 1080 * 3 // 2))[n, :1920 * 1080].reshape(1080, 1920).astype(float) / 4
    gy, gx = np.gradient(gaussian_filter(s, 2))
    grad = np.hypot(gx, gy)
    rows = []
    for yy in range(8, 1040, 48):
        for xx in range(8, 1880, 48):
            sl = np.s_[yy:yy+32, xx:xx+32]
            stats = desc(s[sl])
            edge = float(np.percentile(grad[sl], 95))
            kind = 'edge' if edge > 4 else 'quiet' if edge < .75 and stats['hf_sigma'] < .2 else 'flat_texture' if edge < .75 else 'other'
            rows.append({'xywh': [xx, yy, 32, 32], 'kind': kind, 'source': stats, 'gradient_p95': edge})
    out = {'case': case, 'frame': n, 'poc': n + 96, 'roi_xywh': BOXES[case],
           'definition': 'Identical source-only grid/thresholds to prior quantization controls.py; no encoded output used.',
           'counts': {k: sum(r['kind'] == k for r in rows) for k in ('edge', 'quiet', 'flat_texture', 'other')}, 'tiles': rows}
    dest = ROOT / 'parent' / (case + (f'-frame{n}' if frame is not None else '') + '-frozen-controls.json')
    with dest.open('x') as f:
        json.dump(out, f, indent=2)
        f.write('\n')
    print(case, out['counts'])

if __name__ == '__main__':
    freeze(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None)
