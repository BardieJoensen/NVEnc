import sys
from common import *
import metrics
man = jload(MANIFEST); rows = jload(RESULTS)
out = jload(f'{S}/controls.json', {})
_shell = campaign.shell
for wid in ('bd1', 'bb1'):
    c = out.setdefault(wid, {})
    cache = metrics.build_cache(wid, man)
    f = lambda **k: metrics.measure_base(wid, man, cache, **k)
    if 'self' not in c:
        r = f(path=f'{W}/{wid}/win.mkv', grain=None); c['self'] = {k: v for k, v in r.items() if k.startswith(('amp', 'err', 'peak'))}
    enc = f'{W}/{wid}/enc/prod_q30.mkv'
    if 'confound' not in c:
        sig = rows[wid]['_src']['hf'] / 4.0
        base = f(path=enc); noisy = f(path=enc, extra_noise=sig)
        c['confound'] = {'noise_sigma_8bit': round(sig, 4), 'base': {k: base[k] for k in base if k.startswith('amp_Y') or k.startswith('err_Y')},
                         'noisy': {k: noisy[k] for k in noisy if k.startswith('amp_Y') or k.startswith('err_Y')}}
    jsave(f'{S}/controls.json', out)
    if 'ffvship' not in c:
        d = f'{W}/controls_{wid}'; os.makedirs(d, exist_ok=True)
        n = man[wid]['frames']
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f'{W}/{wid}/win.mkv', '-an', '-fps_mode', 'passthrough', '-c:v', 'ffvhuff', '-pix_fmt', 'yuv420p10le', f'{d}/ref10.mkv'], check=True)
        shutil.copyfile(enc, f'{d}/enc.mkv')
        for nm, g in (('grainon', 1), ('grainoff', 0)):
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-c:v', 'libdav1d', '-filmgrain', str(g), '-i', enc, '-an', '-fps_mode', 'passthrough', '-c:v', 'ffvhuff', '-pix_fmt', 'yuv420p10le', f'{d}/{nm}.mkv'], check=True)
        res = {}
        for nm in ('enc', 'grainon', 'grainoff'):
            wait_gpu()
            b = campaign.ffvship(f'{d}/ref10.mkv', f'{d}/{nm}.mkv', nm, d, n, 'Butteraugli', f'butter-{nm}.json')
            res[nm] = {'butter_max_p95': round(campaign.pct(sorted(x[2] for x in b), 95), 3), 'butter_2norm': round(float(np.mean([x[0] for x in b])), 4), 'frames': len(b)}
        c['ffvship'] = res
        shutil.rmtree(d)
    jsave(f'{S}/controls.json', out)
print(json.dumps(out, indent=1))
