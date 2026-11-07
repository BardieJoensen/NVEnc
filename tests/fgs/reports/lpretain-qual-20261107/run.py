import sys, glob, threading
from common import *
import metrics
from concurrent.futures import ThreadPoolExecutor
BASE = ['--avsw', '--codec', 'av1', '--output-depth', '10']
TAIL = ['--max-bitrate', '50000', '--preset', 'quality', '--tune', 'hq', '--lookahead', '32', '--lookahead-level', '3', '--aq', '--aq-temporal']
PROD = 'denoise=auto,chroma=auto,denoiser=bilateral'
BIN = '/tmp/downloads/codex-work/fgs-lpretain-build/bin/nvencc-lpretain-ff65b832'
DOCKER = ['docker','run','--rm','--gpus','all','--user',f'{os.getuid()}:{os.getgid()}','-e','HOME=/tmp','-v','/tmp/downloads:/tmp/downloads','-v','/media:/media:ro','nvenc-fgs-build:cuda13.3-deps',BIN]
VAR = {'r050lp15': PROD+',retain=0.5,retain-lp=1.5', 'r090lp15': PROD+',retain=0.9,retain-lp=1.5', 'r090lp3': PROD+',retain=0.9,retain-lp=3', 'prod': PROD, 'plain': None, 'r050': PROD + ',retain=0.5', 'r075': PROD + ',retain=0.75', 'r090': PROD + ',retain=0.9', 'auto': PROD + ',retain=auto'}
QS = [26, 30, 34]
ARMS = [(v, 0) for v in ('prod','r090lp3')]
_shell = campaign.shell
campaign.shell = lambda cmd, timeout=1800: _shell(cmd.replace(' -pix_fmt yuv420p10le', ' -fps_mode passthrough -pix_fmt yuv420p10le'), timeout)
man = jload(MANIFEST)
rows = jload(RESULTS)
lock = threading.Lock()
def save():
    with lock: jsave(RESULTS, rows)
def encode(wid, tag, q, fg, off=0, log=False):
    d = f'{W}/{wid}/enc'; os.makedirs(d, exist_ok=True)
    out = f'{d}/{tag}.mkv'
    if campaign.valid_video(out) and (not log or os.path.exists(f'{d}/{tag}.log')): return out
    wait_gpu()
    cmd = DOCKER + ['-i', f'{CW}/{wid}/win.mkv'] + BASE + ['--qvbr', str(q)] + TAIL
    if WINDOWS[wid][0] == 'tf': cmd += ['--colorprim', 'bt2020', '--transfer', 'smpte2084', '--colormatrix', 'bt2020nc']
    if fg: cmd += ['--av1-film-grain', fg]
    if off: cmd += ['--chroma-qp-offset', str(off)]
    if log: cmd += ['--log-level', 'debug']
    cmd += ['-o', f'{CW}/{wid}/enc/{tag}.mkv']
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if r.returncode: raise RuntimeError(r.stderr[-500:] + r.stdout[-500:])
    open(f'{d}/{tag}.log', 'w').write(' '.join(cmd) + '\n' + r.stdout + r.stderr if log else ' '.join(cmd) + '\n' + r.stdout[-1500:] + r.stderr[-1500:])
    return out
def count_frames(p):
    return int(subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0', p], capture_output=True, text=True).stdout.split()[0].strip(','))
def auto_stats(wid, tag):
    txt = open(f'{W}/{wid}/enc/{tag}.log').read()
    lines = [l for l in txt.splitlines() if 'fgs-model' in l]
    risk = [float(m) for l in lines for m in re.findall(r'\brisk=([-\d.eE+]+)', l)]
    ret = [float(m) for l in lines for m in re.findall(r'\bretain=([-\d.eE+]+)', l)]
    fr = {}
    for l in lines:
        m = re.search(r'frame=(\d+)', l); rr = re.search(r'\bretain=([-\d.eE+]+)', l)
        fr[int(m.group(1))] = float(rr.group(1)) if rr else 0.0
    out = {'n_lines': len(lines), 'n_frames_unique': len(fr), 'retain_active_frac': round(sum(v > 0 for v in fr.values()) / max(len(fr), 1), 4), 'sample': lines[:1] + lines[-1:]}
    if risk: out['risk_mean'] = round(float(np.mean(risk)), 4)
    if ret: out['retain_mean'] = round(float(np.mean(ret)), 4); out['retain_min'] = min(ret); out['retain_max'] = max(ret)
    return out
def gpu_score(wid, tag, enc, n, dur):
    d = f'{W}/{wid}/s'
    for f in glob.glob(f'{d}/*{tag}*'): os.remove(f)
    link = f'{d}/enc_{tag}.mkv'
    shutil.copyfile(enc, link)
    wait_gpu()
    r = campaign.score(f'{d}/ref10.mkv', link, tag, d, DIMS['h'], n, clip=f'{W}/{wid}/win.mkv')
    r = {k: v for k, v in r.items() if not k.startswith('t_')}
    mj = json.load(open(f'{d}/metrics-cuda-{tag}.json'))
    for nm, model in (('vmaf_p1', 'vmaf'), ('vmaf_neg_p1', 'vmaf_neg')):
        r[nm] = round(float(np.percentile(sorted(f['metrics'][model] for f in mj['frames']), 1)), 3)
    for f in glob.glob(f'{d}/*{tag}*'): os.remove(f)
    return r
def cpu_metrics(wid, tag, enc, cache):
    r = metrics.measure_base(wid, man, cache, enc)
    src = rows[wid]['_src']
    g = metrics.hf_probe(enc, man[wid]['active']['rect'], man[wid]['frames'], grain=1)
    r.update(g); r['hf_ratio'] = round(g['hf'] / src['hf'], 4)
    return r
def prepare(wid):
    d = f'{W}/{wid}'; os.makedirs(f'{d}/s', exist_ok=True)
    ref = f'{d}/s/ref10.mkv'
    if not campaign.valid_video(ref):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f'{d}/win.mkv', '-an', '-fps_mode', 'passthrough', '-c:v', 'ffvhuff', '-pix_fmt', 'yuv420p10le', ref], check=True)
    rows.setdefault(wid, {})
    if '_src' not in rows[wid]:
        rows[wid]['_src'] = metrics.hf_probe(f'{d}/win.mkv', man[wid]['active']['rect'], man[wid]['frames']); save()
    m = man[wid]
    rows[wid].setdefault('_meta', {'frames': m['frames'], 'dur': round(m['frames'] / eval(m['fps']), 4), 'ref_frames_ffvhuff': count_frames(ref)})
    cache = metrics.build_cache(wid, man)
    return cache
def do_row(wid, var, off, q, cache, pool, futs, log=False):
    tag = f'{var}_o{off}_q{q}'
    if tag in rows[wid] and 'amp_Y_s3.0' in rows[wid][tag] and 'vmaf_p1' in rows[wid][tag]: return
    meta = rows[wid]['_meta']
    enc = encode(wid, tag, q, VAR[var], off, log=log or (var.endswith('lp3') and q==30))
    nf = count_frames(enc)
    row = {'variant': var, 'off': off, 'q': q, 'fg': VAR[var], 'size_bytes': os.path.getsize(enc), 'enc_frames': nf, 'src_frames': meta['frames']}
    row['mbps'] = round(os.path.getsize(enc) * 8 / meta['dur'] / 1e6, 4)
    if os.path.exists(f'{W}/{wid}/enc/{tag}.log') and var.endswith('lp3') and q==30: row['auto'] = auto_stats(wid, tag)
    futs.append((tag, row, pool.submit(cpu_metrics, wid, tag, enc, cache)))
    row.update(gpu_score(wid, tag, enc, meta['frames'], meta['dur']))
    with lock: rows[wid][tag] = row
def collect(wid, futs):
    for tag, row, f in futs:
        row.update(f.result())
        rows[wid][tag] = row
    futs.clear(); save()
def run_window(wid, pool):
    set_dim(wid); cache = prepare(wid); futs = []
    for var, off in ARMS:
        for q in QS: do_row(wid, var, off, q, cache, pool, futs)
    collect(wid, futs)
    rows[wid]['_done'] = True; save()
def cleanup_window(wid):
    d = f'{W}/{wid}'
    shutil.rmtree(f'{d}/s', ignore_errors=True)
    if WINDOWS[wid][0] == 'tf' and os.path.exists(f'{d}/win.mkv'): os.unlink(f'{d}/win.mkv')
    for f in glob.glob(f'{d}/enc/*_q26.mkv') + glob.glob(f'{d}/enc/*_q34.mkv'): os.unlink(f)
if __name__ == '__main__':
    pool = ThreadPoolExecutor(2)
    wids = sys.argv[1:] or list(WINDOWS)
    for wid in wids:
        if rows.get(wid, {}).get('_done'): continue
        t0 = time.time(); run_window(wid, pool); cleanup_window(wid)
        print(wid, 'peak df', subprocess.run(['df','-h','/tmp/downloads'],capture_output=True,text=True).stdout.splitlines()[1], flush=True)
        print(wid, 'done', round(time.time() - t0), 's', flush=True)
    print('ALL DONE', flush=True)
