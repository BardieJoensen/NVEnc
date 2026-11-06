import sys
from pset import *
from concurrent.futures import ThreadPoolExecutor
RES = f'{S}/rows.json'
man = jload(f'{S}/manifest.json')
rows = jload(RES)
lock = threading.Lock()
def save():
    with lock: jsave(RES, rows)

def V(**k): return k
def variants():
    v = {}
    for q in (38, 34, 30, 26, 22): v[f'prod_q{q}'] = V(q=q)
    for q in (34, 30, 26): v[f'plain_q{q}'] = V(q=q, fg=False)
    for r in (0.5, 0.9):
        for q in (34, 30): v[f'ret{int(r*100):03d}_q{q}'] = V(q=q, retain=r)
    v['aqs1_q34'] = V(q=34, aqs=1); v['aqs15_q34'] = V(q=34, aqs=15); v['noaq_q34'] = V(q=34, aq=False)
    v['uhq_q34'] = V(q=34, tune='uhq'); v['tf4_q34'] = V(q=34, tf=4)
    return v

def cpu_metrics(w, tag, enc, cache, rect):
    SKIP[enc] = PRE
    r = metrics.measure_base(w, man, cache, enc)
    g = metrics.hf_probe(enc, rect, N, grain=1)
    r['frame_grain_on'] = g
    r['tex'] = roi_texture(enc, grain=1)
    return r

def process(w, tag, v, cache, pool, futs):
    key = f'{w}/{tag}'
    if key in rows and rows[key].get('_final'): return
    d = window_dir(w); row = {'window': w, 'tag': tag, 'variant': v}
    enc, err, meta = do_encode(w, tag, v)
    if enc is None and v.get('tf') and not v.get('bframes'):
        v = dict(v, bframes=4); row['variant'] = v; row['note'] = 'tf-level needed --bframes 4 (first attempt error: ' + (err or '')[-200:] + ')'
        enc, err, meta = do_encode(w, tag, v)
    if enc is None:
        row.update(error=err, _final=True); rows[key] = row; save(); print(key, 'ENCODE ERROR', err[-200:], flush=True); return
    row['encode_seconds'] = meta.get('secs'); row['cmd'] = ' '.join(meta['cmd'][3:]) if 'cmd' in meta else None
    pk = packets(enc); assert len(pk) == PRE + N, len(pk)
    row['mbps'] = round(sum(s for _, s in pk[PRE:]) * 8 / (N / FPS) / 1e6, 4)
    dec = f'{d}/dec_{tag}.mkv'
    wait_gpu()
    sh(['ffmpeg', '-v', 'error', '-y', '-c:v', 'libdav1d', '-filmgrain', '1', '-i', enc, '-vf', f'select=gte(n\\,{PRE}),setpts=PTS-STARTPTS', '-frames:v', str(N), '-fps_mode', 'passthrough', '-c:v', 'ffvhuff', '-pix_fmt', 'yuv420p10le', dec])
    rt, et = thumb(f'{d}/ref.mkv'), thumb(dec)
    costs = {k: float(np.abs(rt[4+k:20+k] - et[4:20]).mean()) for k in range(-3, 4)}
    row['align_costs'] = costs; row['aligned_zero'] = costs[0] <= min(costs.values()) + 1e-6
    nfr = int(sh(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0', dec]).stdout.strip().strip(','))
    row['dec_frames'] = nfr
    wait_gpu()
    sc = campaign.score(f'{d}/ref.mkv', dec, tag, d, 1080, N)
    row.update({k: v_ for k, v_ in sc.items() if not k.startswith('t_')})
    mj = json.load(open(f'{d}/metrics-cuda-{tag}.json'))
    row.update(audit.pooled(mj))
    os.makedirs(f'{S}/raw/{w}', exist_ok=True)
    for f in glob.glob(f'{d}/*-{tag}.json'): shutil.move(f, f'{S}/raw/{w}/')
    for f in (dec,) + tuple(glob.glob(f'{d}/*{tag}*.ffindex')): 
        if os.path.exists(f): os.remove(f)
    for f in glob.glob(f'{d}/*.ffindex'): pass
    row['_cpu'] = True
    rect = man[w]['active']['rect']
    futs.append((key, row, pool.submit(cpu_metrics, w, tag, enc, cache, rect)))

def collect(futs):
    for key, row, f in futs:
        row.update(f.result()); row['_final'] = True; rows[key] = row
    futs.clear(); save()
    for key in [k for k in list(rows)][-0:]: pass

def run_window(w, names, vs, pool):
    d = window_dir(w)
    cache = metrics.build_cache(w, man)
    futs = []
    for tag in names:
        t0 = time.time()
        process(w, tag, vs[tag], cache, pool, futs)
        if len(futs) >= 2: 
            f = futs.pop(0); f[1].update(f[2].result()); f[1]['_final'] = True; rows[f[0]] = f[1]; save()
        print(w, tag, round(time.time() - t0), 's', rows.get(f'{w}/{tag}', {}).get('mbps'), flush=True)
    collect(futs)
    for f in glob.glob(f'{d}/*.ffindex'): os.remove(f)

if __name__ == '__main__':
    vs = variants()
    names = sys.argv[2].split(',') if len(sys.argv) > 2 and sys.argv[2] != 'all' else list(vs)
    extra = json.load(open(f'{S}/combos.json')) if os.path.exists(f'{S}/combos.json') else {}
    vs.update(extra)
    if sys.argv[2:3] == ['combos']: names = list(extra)
    pool = ThreadPoolExecutor(1)
    for w in sys.argv[1].split(','):
        t0 = time.time(); run_window(w, names, vs, pool); print(w, 'DONE', round(time.time() - t0), flush=True)
    print('ALL DONE', flush=True)
