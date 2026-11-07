import json, os, re, shutil, subprocess, sys, time
import numpy as np
sys.path.insert(0, os.path.expanduser('~/git-repos/NVEnc/tests/fgs'))
import campaign
S = '/tmp/downloads/codex-work/fgs-lpretain-qual'
W = S + '/win'
CW = W
D = '/media/merged-storage/media/downloads/long-term-seeding/'
BEAR = D+'tv-shows/The.Bear.S04.1080p.DSNP.WEB-DL.DDP5.1.H.264-NTb/The.Bear.S04E10.1080p.DSNP.WEB-DL.DDP5.1.H.264-NTb.mkv'
PAN = D+'tv-shows/Pantheon.S02.REPACK.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb/Pantheon.S02E08.Deep.Time.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.mkv'
TF = D+'movies/Transformers.The.Last.Knight.2017.NORDiC.REMUX.2160p.DV.HDR.UHD-BluRay.HEVC.TrueHD.Atmos.7.1-RAPiDCOWS/Transformers.The.Last.Knight.2017.NORDiC.REMUX.2160p.DV.HDR.UHD-BluRay.HEVC.TrueHD.Atmos.7.1-RAPiDCOWS.mkv'
TITLES = {'bear': (BEAR, 2026.9, 'WEB 1080p'), 'pan': (PAN, 2756.709, 'WEB 1080p'), 'tf': (TF, 9278.784, 'UHD DV remux (BL)')}
ORDER = ['bear', 'pan', 'tf']
PCTS = {'bear': (.25, .5, .75), 'pan': (.25, .5, .75), 'tf': (.30, .55, .80)}
PFX = {'bear': 'bear', 'pan': 'pan', 'tf': 'tf'}
WINDOWS = {}
for t in ORDER:
    for k, p in zip('123', PCTS[t]):
        WINDOWS[PFX[t] + k] = (t, p)
DIMS = {'w': 1920, 'h': 1080}
def set_dim(wid):
    if WINDOWS[wid][0] == 'tf': DIMS.update(w=3840, h=2160)
    else: DIMS.update(w=1920, h=1080)
def start_of(wid): return round(TITLES[WINDOWS[wid][0]][1] * WINDOWS[wid][1], 1)
MANIFEST = f'{S}/manifest.json'
RESULTS = f'{S}/results_rows.json'
import json
def jload(p, d=None):
    return json.load(open(p)) if os.path.exists(p) else (d if d is not None else {})
def jsave(p, o):
    json.dump(o, open(p + '.tmp', 'w'), indent=1); os.replace(p + '.tmp', p)
def wait_gpu(limit=360):
    for _ in range(limit):
        f = int(subprocess.run(['nvidia-smi', '--query-gpu=memory.free', '--format=csv,noheader,nounits'], capture_output=True, text=True).stdout.split()[0])
        if f > 6144: return
        time.sleep(20)
    raise RuntimeError('gpu never free (2h)')
def gauss_lp(a, sigma):
    """separable gaussian, truncate 4 sigma, reflect borders (scipy-compatible), float32"""
    r = int(4 * sigma + 0.5)
    x = np.arange(-r, r + 1, dtype=np.float32)
    k = np.exp(-0.5 * (x / sigma) ** 2); k /= k.sum()
    out = a.astype(np.float32)
    for ax in (0, 1):
        p = [(0, 0), (0, 0)]; p[ax] = (r, r)
        pa = np.pad(out, p, mode='symmetric')
        n = out.shape[ax]
        acc = np.zeros_like(out)
        for i, w in enumerate(k):
            acc += w * (pa[i:i + n] if ax == 0 else pa[:, i:i + n])
        out = acc
    return out
