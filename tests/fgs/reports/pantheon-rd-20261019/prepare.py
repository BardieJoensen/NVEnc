#!/usr/bin/env python3
"""Replay established original-download fixtures into new scratch, hash every frame."""
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'pantheon-independent-20261019'))
import investigate as x

ROOT = Path(os.environ.get('PANTHEON_RD_ROOT', '/tmp/downloads/codex-work/pantheon-rd-20261019'))
OLD = Path('/media/merged-storage/cold-storage/docker-apps/pantheon-causal-20261019')

def verify_source(case):
    d = ROOT / 'fixtures' / case
    v = json.loads((d / 'validity.json').read_text())
    hashes = []
    with (d / 'source.yuv').open('rb') as f:
        for n in range(240):
            raw = f.read(1920*1080*3)
            assert len(raw) == 1920*1080*3
            hashes.append(hashlib.md5(raw).hexdigest())
        assert not f.read(1)
    assert hashes == v['hashes_ref']
    receipt = d / 'fresh-validation.json'
    out = json.loads(receipt.read_text())
    out['source_raw_frame_md5'] = hashes
    out['source_raw'] = x.fingerprint(d / 'source.yuv')
    x.dump(receipt, out)

def prepare(case):
    assert case in ('e04', 'e05-1440')
    assert str(ROOT.resolve()).startswith('/tmp/downloads/codex-work/')
    d = ROOT / 'fixtures' / case
    d.mkdir(parents=True, exist_ok=False)
    v = json.loads((OLD / case / 'validity.json').read_text())
    st = Path(v['source']).stat()
    assert v['source_stat'] == {'size': st.st_size, 'mtime_ns': st.st_mtime_ns}
    x.dump(d / 'validity.json', v)
    for tag in ('extract-input', 'extract-ref'):
        cmd = json.loads((OLD / case / (tag + '-command.json')).read_text())['argv']
        cmd[-1] = str(d / Path(cmd[-1]).name)
        x.run(cmd, d, tag)
    x.run(['ffmpeg', '-v', 'error', '-threads', '4', '-i', d / 'input.mkv',
           '-pix_fmt', 'yuv420p10le', '-strict', '-1', '-f', 'yuv4mpegpipe', d / 'input10.y4m'], d, 'make-y4m')
    x.run(['ffmpeg', '-v', 'error', '-threads', '4', '-i', d / 'ref.mkv',
           '-pix_fmt', 'yuv420p10le', '-f', 'rawvideo', d / 'source.yuv'], d, 'source-raw')
    hashes = {}
    for name, trim in [('ref.mkv', []), ('input10.y4m', ['-vf', 'trim=start_frame=96,setpts=PTS-STARTPTS'])]:
        hs = x.hashes(['ffmpeg', '-v', 'error', '-threads', '4', '-i', str(d / name),
                       *trim, '-frames:v', '240', '-pix_fmt', 'yuv420p10le'])
        assert hs == v['hashes_ref'], name
        hashes[name] = hs
    x.dump(d / 'fresh-validation.json', {
        'all240_allplanes_match_archived_original': True,
        'source_stat_unchanged': True,
        'frames': hashes,
        'ffmpeg': x.fingerprint('/usr/bin/ffmpeg'),
        'script': x.fingerprint(__file__),
    })
    verify_source(case)
    print(case, 'source/input hashes verified', flush=True)

if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[2] == '--verify-source':
        verify_source(sys.argv[1])
    else:
        prepare(sys.argv[1])
