from common import *
from concurrent.futures import ThreadPoolExecutor
SIG = (3.0, 1.5)
STEP = 2
def stream_planes(path, grain=None, decoder_threads=4):
    """yield (Y,Cb,Cr) float32 in 8-bit scale for every frame, full frame"""
    cmd = ['ffmpeg', '-v', 'error', '-threads', str(decoder_threads)]
    if grain is not None: cmd += ['-c:v', 'libdav1d', '-filmgrain', str(grain)]
    cmd += ['-i', path, '-map', '0:v:0', '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'yuv420p10le', '-']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    size = 1920 * 1080 * 3
    try:
        while True:
            data = p.stdout.read(size)
            if len(data) < size: break
            a = np.frombuffer(data, np.uint16)
            yield (a[:1920*1080].reshape(1080, 1920), a[1920*1080:1920*1080*5//4].reshape(540, 960), a[1920*1080*5//4:].reshape(540, 960))
    finally:
        p.kill(); p.wait()
def tiles(a, x, y, w, h):
    rows, cols = h // 16, w // 16
    return a[y:y+rows*16, x:x+cols*16].reshape(rows, 16, cols, 16).swapaxes(1, 2).reshape(rows, cols, 256)
def crop_f(a, rect, sub=1):
    x, y, w, h = [v // sub for v in rect]
    return a[y:y+h, x:x+w].astype(np.float32) / 4.0
def sel_mask(sd):
    use = sd > 0
    if not use.any(): return use
    return use & (sd >= np.quantile(sd[use], 0.9))
def hf_stats(a):
    """a: 2D array (10-bit units). probe_struct formula, restricted to given area"""
    a = a.astype(np.float64)
    r = (a[1:-1, 1:-1] - (a[0:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, 0:-2] + a[1:-1, 2:] + a[1:-1, 1:-1] * 4) / 8)
    hf = float(r.std()) * (8 / 5.0) ** 0.5
    rr = r - r.mean(); v = (rr * rr).mean(); ac = {}
    for lag in (1, 2, 3):
        ac[lag] = ((rr[:, :-lag] * rr[:, lag:]).mean() + (rr[:-lag, :] * rr[lag:, :]).mean()) / (2 * v)
    return hf, ac
def hf_frames(n):
    return sorted(set(int(round(v)) for v in np.linspace(4, n - 5, 12)))
def hf_probe(path, rect, n, grain=None):
    want = hf_frames(n); hs = []; acs = {1: [], 2: [], 3: []}
    for i, (Y, _, _) in enumerate(stream_planes(path, grain)):
        if i in want:
            x, y, w, h = rect
            hf, ac = hf_stats(Y[y:y+h, x:x+w]); hs.append(hf)
            for k in ac: acs[k].append(ac[k])
        if i >= want[-1]: break
    return {'hf': round(float(np.mean(hs)), 4), **{f'acf{k}': round(float(np.mean(v)), 4) for k, v in acs.items()}}
ALIGN_I = list(range(20, 28)); ALIGN_KEEP = range(18, 30)
def build_cache(wid, man):
    """source cache: selected-patch statistics + alignment frames"""
    m = man[wid]; rect = m['active']['rect']; n = m['frames']
    d = f'{W}/{wid}'
    cache = {'luma': {s: [] for s in SIG}, 'cb': [], 'cr': [], 'align': {}}
    pool = ThreadPoolExecutor(6)
    def one(Y):
        out = {}
        y8 = crop_f(Y, rect)
        for s in SIG:
            lp = gauss_lp(y8, s)
            T = tiles(lp, 0, 0, rect[2], rect[3]); sd = T.std(-1); sm = sel_mask(sd)
            sel = T[sm]
            out[s] = (sm, sel, float(sel.var(-1).sum()))
        return out
    futs = []; chroma = []; hfs = []
    for i, (Y, Cb, Cr) in enumerate(stream_planes(f'{d}/win.mkv')):
        if i in ALIGN_KEEP: cache['align'][i] = crop_f(Y, rect)[::2, ::2].copy()  # decimated for alignment psnr
        if i % STEP: continue
        futs.append(pool.submit(one, Y.copy()))
        cc = []
        for pl in (Cb, Cr):
            T = tiles(crop_f(pl, rect, 2), 0, 0, rect[2] // 2, rect[3] // 2); sd = T.std(-1); sm = sel_mask(sd)
            sel = T[sm]
            cc.append((sm, sel, float(sel.var(-1).sum()), float(np.percentile(np.abs(sel - 128), 95, axis=-1).sum())))
        chroma.append(cc)
        while len(futs) > 12:  # bound memory
            cache['luma_res'] = cache.get('luma_res', []); cache['luma_res'].append(futs.pop(0).result())
    for f in futs: cache.setdefault('luma_res', []).append(f.result())
    cache['chroma'] = chroma
    pool.shutdown()
    cache['nsel'] = len(chroma)
    return cache
def measure_base(wid, man, cache, path, extra_noise=None, seed=1, grain=0):
    """grain-off decode of `path` vs source cache. extra_noise: sigma (8-bit scale) of iid gaussian added to base luma before lowpass"""
    m = man[wid]; rect = m['active']['rect']; n = m['frames']
    rng = np.random.default_rng(seed)
    acc = {s: np.zeros(3) for s in SIG}  # var_base, mse, var_src
    cacc = [np.zeros(4) for _ in range(2)]  # var_base, mse, peak_base, (var_src placeholder)
    csrc = [np.zeros(2) for _ in range(2)]
    base_align = {}
    pool = ThreadPoolExecutor(6); futs = []; k = 0; nfr = 0
    def one(Y, idx):
        y8 = crop_f(Y, rect)
        if extra_noise: y8 = y8 + rng_noise(idx, y8.shape, extra_noise)
        res = {}
        for s in SIG:
            lp = gauss_lp(y8, s)
            sm, sel_s, vs = cache['luma_res'][idx][s]
            sel_b = tiles(lp, 0, 0, rect[2], rect[3])[sm]
            res[s] = (float(sel_b.var(-1).sum()), float(((sel_b - sel_s) ** 2).mean(-1).sum()), vs)
        return res
    def rng_noise(idx, shape, sd): return np.random.default_rng(seed * 100000 + idx).normal(0, sd, shape).astype(np.float32)
    for i, (Y, Cb, Cr) in enumerate(stream_planes(path, grain)):
        nfr += 1
        if i in ALIGN_KEEP: base_align[i] = crop_f(Y, rect)[::2, ::2].copy()
        if i % STEP: continue
        futs.append(pool.submit(one, Y.copy(), i // STEP))
        for p, pl in enumerate((Cb, Cr)):
            sm, sel_s, vs, ps = cache['chroma'][i // STEP][p]
            sel_b = tiles(crop_f(pl, rect, 2), 0, 0, rect[2] // 2, rect[3] // 2)[sm]
            cacc[p] += (float(sel_b.var(-1).sum()), float(((sel_b - sel_s) ** 2).mean(-1).sum()), float(np.percentile(np.abs(sel_b - 128), 95, axis=-1).sum()), 0)
            csrc[p] += (vs, ps)
        while len(futs) > 12:
            r = futs.pop(0).result()
            for s in SIG: acc[s] += r[s]
    for f in futs:
        r = f.result()
        for s in SIG: acc[s] += r[s]
    pool.shutdown()
    out = {'frames_decoded': nfr}
    for s in SIG:
        vb, mse, vs = acc[s]
        out[f'amp_Y_s{s}'] = round(float(np.sqrt(vb / vs)), 5); out[f'err_Y_s{s}'] = round(float(np.sqrt(mse / vs)), 5)
    for p, nm in enumerate(('Cb', 'Cr')):
        vb, mse, pk, _ = cacc[p]; vs, ps = csrc[p]
        out[f'amp_{nm}'] = round(float(np.sqrt(vb / vs)), 5); out[f'peak_{nm}'] = round(float(pk / ps), 5); out[f'err_{nm}'] = round(float(np.sqrt(mse / vs)), 5)
    # alignment: psnr of base vs src at offsets
    al = {}
    for off in range(-2, 3):
        ps = []
        for i in ALIGN_I:
            if i + off in base_align:
                e = ((base_align[i + off] - cache['align'][i]) ** 2).mean(); ps.append(10 * np.log10(255 ** 2 / max(e, 1e-9)))
        al[off] = round(float(np.mean(ps)), 2)
    out['align_psnr'] = al
    out['aligned'] = max(al, key=al.get) == 0
    return out
