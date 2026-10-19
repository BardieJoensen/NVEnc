#!/usr/bin/env python3
"""Score a completed real encode with the established campaign GPU adapter."""
import argparse
import json
import os
from pathlib import Path
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('PANTHEON_RD_ROOT', '/tmp/downloads/codex-work/pantheon-rd-20261019'))
SCORES = ROOT / 'parent' / 'scores'
os.environ['PANTHEON_INDEPENDENT_DIR'] = str(SCORES)
sys.path.insert(0, str(HERE.parent / 'pantheon-independent-20261019'))
import investigate as x
import texture

def main():
    p = argparse.ArgumentParser()
    p.add_argument('case', choices=['e04', 'e05-1440'])
    p.add_argument('tag')
    p.add_argument('ivf', type=Path)
    p.add_argument('recon', type=Path)
    p.add_argument('--resume', action='store_true')
    a = p.parse_args()
    d = SCORES / a.case
    d.mkdir(parents=True, exist_ok=True)
    for name in ('ref.mkv', 'source.yuv', 'validity.json'):
        dest = d / name
        target = ROOT / 'fixtures' / a.case / name
        if dest.exists():
            assert not dest.is_symlink() and os.path.samefile(dest, target)
        else:
            os.link(target, dest)  # FFVship sees only the mounted scores directory.
    mkv = d / (a.tag + '.mkv')
    identity = d/(a.tag+'-input-identity.json')
    if a.resume:
        saved = json.loads(identity.read_text())
        assert saved == {'ivf': x.fingerprint(a.ivf), 'mkv': x.fingerprint(mkv)}
    else:
        assert not mkv.exists(), 'Use a fresh tag; never overwrite scored artifacts.'
        x.run(['ffmpeg', '-v', 'error', '-i', a.ivf.resolve(), '-c', 'copy', mkv], d, a.tag+'-remux')
        x.dump(identity, {'ivf': x.fingerprint(a.ivf), 'mkv': x.fingerprint(mkv)})
    result = x.score(a.case, mkv, a.tag, grain=0)
    texture.analyze(a.case, a.tag, d / (a.tag+'-decoded.mkv'))
    recon = np.memmap(a.recon, dtype='<u2', mode='r', shape=(336, 1920*1080*3//2))
    proc = texture.reader(d / (a.tag+'-decoded.mkv'))
    count = 0
    try:
        for n in range(240):
            raw = proc.stdout.read(1920*1080*3)
            assert len(raw) == 1920*1080*3
            assert np.array_equal(np.frombuffer(raw, dtype='<u2'), recon[n+96]), n
            count += 1
    finally:
        proc.stdout.close()
        proc.wait()
    assert proc.returncode == 0
    pk = sorted(x.packets(mkv), key=lambda r: float(r['pts_time']))
    fps = x.CASES[a.case][2]
    selected = [r for r in pk if 96 <= round(float(r['pts_time'])*fps) < 336]
    assert len(pk) == 336 and len(selected) == 240
    rate = sum(int(r['size']) for r in selected)*8/(240/fps)/1e6
    assert abs(rate-result['actual_mbps']) < 1e-10
    x.dump(d / (a.tag+'-validation.json'), {'all240_allplanes_app_dav1d_exact': count == 240,
            'packet_mbps': rate, 'selected_packets': selected,
            'ivf': x.fingerprint(a.ivf), 'app_recon': x.fingerprint(a.recon),
            'score_script': x.fingerprint(__file__)})

if __name__ == '__main__':
    main()
