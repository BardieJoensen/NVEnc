"""Architect follow-up (2026-11-07). Offsets -2/-4 move AV1 deltaQ_u_ac by only a few
qindex (0-255 scale) and barely changed size or chroma. Two checks:
1. prod and r050 at chroma offsets -16 and -32, at q30, on all 12 windows: does chroma
   structure respond to the chroma quantiser at all?
2. prod and r050 at --cqp 4 (near-lossless) on 6 windows, grain-off base only: is the
   chroma that reaches the encoder the same in both arms (retain touches only luma in
   NVEncFilterFilmGrain.cu:2702-2726)?
"""
import sys
sys.argv = sys.argv[:1]
from run import *

TWELVE = ['bd1', 'bd2', 'bb1', 'bb2', 'ca1', 'ca2', 'lob1', 'lob2', 'bat1', 'bat2', 'nc1', 'nc2']
NL = ['bd1', 'bb1', 'ca2', 'lob2', 'bat1', 'nc1']
EXTRA_OFFS = [-16, -32]

def encode_cqp(wid, tag, fg, qp):
    out = f'{W}/{wid}/enc/{tag}.mkv'
    if campaign.valid_video(out): return out
    wait_gpu()
    cmd = ['docker', 'exec', 'tdarr-node', 'nvencc', '-i', f'{CW}/{wid}/win.mkv'] + BASE + \
          ['--cqp', str(qp), '--preset', 'quality', '--tune', 'hq', '--av1-film-grain', fg,
           '-o', f'{CW}/{wid}/enc/{tag}.mkv']
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if r.returncode: raise RuntimeError(r.stderr[-500:] + r.stdout[-500:])
    return out

if __name__ == '__main__':
    pool = ThreadPoolExecutor(2)
    for wid in TWELVE:
        t0 = time.time()
        cache = prepare(wid); futs = []
        for var in ('prod', 'r050'):
            for off in EXTRA_OFFS: do_row(wid, var, off, 30, cache, pool, futs)
        collect(wid, futs)
        if wid in NL:
            for var in ('prod', 'r050'):
                tag = f'{var}_cqp4'
                if 'amp_Cb' in rows[wid].get(tag, {}): continue
                enc = encode_cqp(wid, tag, VAR[var], 4)
                r = metrics.measure_base(wid, man, cache, enc)
                r['size_bytes'] = os.path.getsize(enc); r['mbps'] = round(r['size_bytes'] * 8 / rows[wid]['_meta']['dur'] / 1e6, 3)
                rows[wid][tag] = r; save()
                subprocess.run(['docker', 'exec', 'tdarr-node', 'rm', '-f', f'{CW}/{wid}/enc/{tag}.mkv'])
        cleanup_window(wid)
        print(wid, 'extra done', round(time.time() - t0), 's', flush=True)
    print('EXTRA DONE', flush=True)
