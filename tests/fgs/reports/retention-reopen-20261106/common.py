import json, os, re, shutil, subprocess, sys, time
import numpy as np
sys.path.insert(0, os.path.expanduser('~/git-repos/NVEnc/tests/fgs'))
import campaign
S = '/tmp/downloads/codex-work/fgs-retention-reopen'
W = '/tmp/downloads/tdarr-temp/fgs-retention-reopen'
CW = '/temp/fgs-retention-reopen'
D = '/media/merged-storage/media/downloads/long-term-seeding/'
TITLES = {
 'bd': (D+'tv-shows/Black.Doves.S02.1080p.NF.WEB-DL.DDP5.1.Atmos.H.264-RAWR/Black.Doves.S02E04.The.Opportunity.to.Become.Savage.1080p.NF.WEB-DL.DDP5.1.Atmos.H.264-RAWR.mkv', 3466.9, 'WEB fine grain'),
 'bb': (D+'movies/Brokeback.Mountain.2005.1080p.BluRay.Remux.AVC.DTS-HD.MA.5.1-CiNEPHiLES/Brokeback.Mountain.2005.1080p.Blu-ray.Remux.AVC.DTS-HD.MA.5.1-CiNEPHiLES.mkv', 8068.4, 'moderate 35mm'),
 'ca': (D+'movies/Coming.to.America.1988.BluRay.1080p.DTS-HD.MA.5.1.AVC.REMUX-FraMeSToR.mkv', 7009.0, 'moderate 35mm'),
 'lob': (D+'movies/Life of Brian 1979 BluRay 1080p DTS-HD MA 5 1 AVC REMUX-FraMeSToR/Life of Brian 1979 BluRay 1080p DTS-HD MA 5 1 AVC REMUX-FraMeSToR.mkv', 5623.6, 'older heavier 35mm'),
 'bat': (D+'movies/Breakfast.at.Tiffanys.1961.1080p.BluRay.REMUX.AVC.DTS-HD.MA.5.1-EPSiLON/Breakfast.at.Tiffanys.1961.1080p.BluRay.REMUX.AVC.DTS-HD.MA.5.1-EPSiLON.mkv', 6905.9, 'older heavier 35mm'),
 'nc': (D+'movies/Nightcrawler.2014.1080p.BluRay.Hybrid.REMUX.AVC.Atmos-TRiToN.mkv', 7080.1, 'digital clean'),
 'dkr': (D+'movies/Batman.The.Dark.Knight.Returns.Part.1.2012.1080p.Blu-ray.Remux.AVC.DTS-HD.MA.5.1-LEGi0N/Batman.The.Dark.Knight.Returns.Part.1.2012.1080p.Blu-ray.Remux.AVC.DTS-HD.MA.5.1-LEGi0N.mkv', 4582.6, 'animation control'),
}
ORDER = ['bd', 'bb', 'ca', 'lob', 'bat', 'nc', 'dkr']
WINDOWS = {}  # wid -> (title, pct)
for t in ORDER:
    for k, p in (('1', .30), ('2', .65)):
        WINDOWS[t + k] = (t, p)
def start_of(wid): return round(TITLES[WINDOWS[wid][0]][1] * WINDOWS[wid][1], 1)
MANIFEST = f'{S}/manifest.json'
RESULTS = f'{S}/results_rows.json'
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
