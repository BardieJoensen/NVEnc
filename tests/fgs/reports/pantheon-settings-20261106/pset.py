"""Pantheon NVENC setting sweep helpers (2026-11-06). Imports (does not edit) the fgs-retention-reopen instrument."""
import sys, os, json, time, subprocess, shutil, glob, shlex, importlib.util, threading
import numpy as np
sys.path.insert(0, '/tmp/downloads/codex-work/fgs-retention-reopen')
sys.path.insert(0, '/home/bardie/git-repos/NVEnc/tests/fgs')
import common, metrics, campaign
from matched_rate_sweep import high_pass, autocorr
spec = importlib.util.spec_from_file_location('audit', '/opt/docker-apps/scripts/library-fidelity/libvsorig.py')
audit = importlib.util.module_from_spec(spec); spec.loader.exec_module(audit)

S = '/tmp/downloads/codex-work/pantheon-settings-20261106'
W = '/tmp/downloads/tdarr-temp/pantheon-settings-20261106'
CW = '/temp/pantheon-settings-20261106'
D = '/media/merged-storage/media/downloads/long-term-seeding/tv-shows/Pantheon.S02.REPACK.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb/'
EP = {'E01': 'Pantheon.S02E01.The.Gods.Have.Not.Died.in.Vain.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.mkv',
      'E04': 'Pantheon.S02E04.Olivia.&.Farhad.REPACK.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.mkv',
      'E05': 'Pantheon.S02E05.Yair.1080p.AMZN.WEB-DL.DDP5.1.H.264-NTb.mkv'}
FPS = 24000 / 1001
N, PRE = 240, 96
# p04b: contract says E04 at 50% == 1243.4925 s == p04a (same window); 75% used instead, deviation recorded.
WINS = {'p04a': ('E04', 1243.493), 'p04b': ('E04', 1865.239), 'p01': ('E01', 2021.0), 'p05': ('E05', 1440.0)}
ROI = (1400, 200, 400, 400); ROI_FR = [120, 126, 132, 138, 144]

def sh(cmd, **kw):
    r = subprocess.run([str(x) for x in cmd], capture_output=True, text=True, **kw)
    if r.returncode: raise RuntimeError(r.stderr[-2000:])
    return r
def jload(p, d=None): return json.load(open(p)) if os.path.exists(p) else (d if d is not None else {})
def jsave(p, o):
    json.dump(o, open(p + '.tmp', 'w'), indent=1); os.replace(p + '.tmp', p)
def wait_gpu(limit=360):
    for _ in range(limit):
        f = int(subprocess.run(['nvidia-smi', '--query-gpu=memory.free', '--format=csv,noheader,nounits'], capture_output=True, text=True).stdout.split()[0])
        if f > 6144: return
        time.sleep(20)
    raise RuntimeError('gpu not free for 2h')

# ---- stream_planes with preroll skip (patched into metrics) ----
SKIP = {}
def stream_planes(path, grain=None, decoder_threads=4):
    cmd = ['ffmpeg', '-v', 'error', '-threads', str(decoder_threads)]
    if grain is not None: cmd += ['-c:v', 'libdav1d', '-filmgrain', str(grain)]
    cmd += ['-i', path, '-map', '0:v:0']
    sk = SKIP.get(path, 0)
    if sk: cmd += ['-vf', f'select=gte(n\\,{sk})']
    cmd += ['-fps_mode', 'passthrough', '-frames:v', str(N), '-f', 'rawvideo', '-pix_fmt', 'yuv420p10le', '-']
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
metrics.stream_planes = stream_planes
metrics.W = W

def roi_texture(path, grain=None):
    ids = set(ROI_FR); ys = []
    for i, (Y, _, _) in enumerate(stream_planes(path, grain)):
        if i in ids: ys.append(Y.astype(np.float64) / 4)
        if i >= max(ids): break
    out = {}
    for name, sl in (('frame', (slice(None), slice(None))), ('roi', (slice(ROI[1], ROI[1]+ROI[3]), slice(ROI[0], ROI[0]+ROI[2])))):
        hp = [high_pass(y[sl]) for y in ys]
        out[name] = {'hf': round(float(np.mean([x.std() * (8/5) ** .5 for x in hp])), 4),
                     **{f'acf{k}': round(float(np.mean([autocorr(x, k) for x in hp])), 4) for k in (1, 2, 3)}}
    return out

def thumb(p, skip=0):
    vf = f'select=gte(n\\,{skip}),' if skip else ''
    b = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(p), '-vf', vf + 'scale=480:270', '-frames:v', '24', '-fps_mode', 'passthrough', '-pix_fmt', 'gray', '-f', 'rawvideo', '-'])
    return np.frombuffer(b, np.uint8).reshape(-1, 270, 480).astype(np.float32)

def packets(path, t0=None, span=None):
    cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'packet=pts_time,size', '-of', 'json']
    if t0 is not None: cmd += ['-read_intervals', f'{max(0, t0-1):.3f}%+{span}']
    pk = json.loads(sh(cmd + [path]).stdout)['packets']
    return sorted(((float(p['pts_time']), int(p['size'])) for p in pk))

def window_dir(w): return f'{W}/{w}'

def setup(w):
    ep, ts = WINS[w]; src = D + EP[ep]
    d = window_dir(w); os.makedirs(d + '/enc', exist_ok=True)
    m = jload(f'{S}/manifest.json')
    if w in m and m[w].get('ok'): return m[w]
    shift = 0; note = None
    for attempt in range(2):
        T = ts + shift
        for f in ('preroll.mkv', 'ref.mkv'):
            if os.path.exists(f'{d}/{f}'): os.unlink(f'{d}/{f}')
        sh(['ffmpeg', '-v', 'error', '-ss', f'{T-PRE/FPS:.3f}', '-i', src, '-frames:v', str(PRE+N), '-map', '0:v:0', '-an', '-sn', '-c:v', 'ffvhuff', '-pix_fmt', 'yuv420p', f'{d}/preroll.mkv'])
        sh(['ffmpeg', '-v', 'error', '-ss', f'{T:.3f}', '-i', src, '-frames:v', str(N), '-map', '0:v:0', '-an', '-sn', '-fps_mode', 'passthrough', '-c:v', 'ffvhuff', '-pix_fmt', 'yuv420p10le', f'{d}/ref.mkv'])
        # near-black check on the scored frames
        import prep
        det = prep.detect(f'{d}/ref.mkv', N)
        x0, y0, w0, h0 = det['rect']
        low = [float(y[y0:y0+h0, x0:x0+w0].mean()) < 32 for _, y in prep.frames_y(f'{d}/ref.mkv')]
        lowfrac = sum(low) / len(low)
        if lowfrac > .5 and attempt == 0:
            shift = 60; note = f'+60 s once: {lowfrac:.3f} of scored frames had active-area mean luma < 32'; continue
        break
    def hashes(path, pre=0):
        cmd = ['ffmpeg', '-v', 'error', '-i', path, '-vf', f'select=gte(n\\,{pre}),setpts=PTS-STARTPTS', '-frames:v', str(N), '-fps_mode', 'passthrough', '-pix_fmt', 'yuv420p10le', '-f', 'framemd5', '-']
        return [x.rsplit(',', 1)[1].strip() for x in sh(cmd).stdout.splitlines() if not x.startswith('#')]
    hp, hr = hashes(f'{d}/preroll.mkv', PRE), hashes(f'{d}/ref.mkv')
    exact = hp == hr and len(hr) == N
    nfr_pre = int(sh(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0', f'{d}/preroll.mkv']).stdout.strip().strip(','))
    nfr_ref = int(sh(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0', f'{d}/ref.mkv']).stdout.strip().strip(','))
    T = ts + shift
    pk = packets(src, T, 16)
    i0 = next(i for i, (t, _) in enumerate(pk) if t >= T)
    sel = pk[i0:i0+N]; assert len(sel) == N
    orig_mbps = sum(s for _, s in sel) * 8 / (N / FPS) / 1e6
    # source stats
    os.makedirs(f'{d}/wmeta', exist_ok=True)
    link = f'{W}/{w}/win.mkv'
    if os.path.lexists(link): os.unlink(link)
    os.symlink(f'{d}/ref.mkv', link)
    rect = det['rect']
    m = jload(f'{S}/manifest.json')
    m[w] = dict(ok=exact and nfr_pre == PRE+N and nfr_ref == N, ep=ep, src=src, nominal_start=ts, shift=shift, shift_note=note, start=T,
                first_ref_pts=sel[0][0], preroll_frames=nfr_pre, ref_frames=nfr_ref, framemd5_exact=exact, lowluma_frac=round(lowfrac, 3),
                active=det, frames=N, orig_mbps=round(orig_mbps, 4), src_hf=None)
    jsave(f'{S}/manifest.json', m)
    return m[w]

def source_stats(w, man):
    d = window_dir(w); rect = man[w]['active']['rect']
    src = metrics.hf_probe(f'{d}/ref.mkv', rect, N)
    out = {'hf': src}
    out['tex'] = roi_texture(f'{d}/ref.mkv')
    return out

def vmaf_fn(ref, enc, models, out_json, tag, frames):
    if os.path.isfile(out_json):
        doc = json.load(open(out_json)); return doc['pooled_metrics']
    d = os.path.dirname(out_json); q = shlex.quote
    rp, dp = os.path.join(d, 'rp-' + tag), os.path.join(d, 'dp-' + tag)
    m = 'vmaf_v0.6.1'
    cmd = (f"rm -f {q(rp)} {q(dp)}; mkfifo {q(rp)} {q(dp)} || exit 1; "
           f"ffmpeg -v error -i {q(ref)} -fps_mode passthrough -pix_fmt yuv420p10le -strict -1 -f yuv4mpegpipe -y {q(rp)} >/dev/null 2>&1 & w1=$!; "
           f"ffmpeg -v error -i {q(enc)} -fps_mode passthrough -pix_fmt yuv420p10le -strict -1 -f yuv4mpegpipe -y {q(dp)} >/dev/null 2>&1 & w2=$!; "
           f"{q(campaign.VMAF)} --reference {q(rp)} --distorted {q(dp)} --gpumask 0 --threads 16 "
           f"--model version={m}:name=vmaf --model version={m}neg:name=vmaf_neg "
           f"--feature psnr_cuda --feature ssim_cuda --feature ciede_cuda --feature cambi=full_ref=true "
           f"--json --output {q(out_json)} >/dev/null 2>&1; st=$?; "
           f"kill $w1 $w2 2>/dev/null; wait 2>/dev/null; rm -f {q(rp)} {q(dp)}; exit $st")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=1800)
    if r.returncode: raise RuntimeError('vmaf failed ' + r.stderr[-500:])
    doc = json.load(open(out_json))
    assert len(doc['frames']) == frames, len(doc['frames'])
    for k in ('vmaf', 'vmaf_neg'):
        if any(f['metrics'].get(k) is None for f in doc['frames']): raise RuntimeError('null frames')
    return doc['pooled_metrics']
campaign.vmaf_run = vmaf_fn

BASE = ['--avsw', '--codec', 'av1', '--output-depth', '10']
FG = 'denoise=auto,chroma=auto,denoiser=bilateral'
def build_args(v):
    """v: dict q, fg(None|str), aq(bool), aqs(None|int), tune, tf(None|int), bframes"""
    a = BASE + ['--qvbr', str(v['q']), '--max-bitrate', '50000', '--preset', 'quality', '--tune', v.get('tune', 'hq'),
                '--lookahead', '32', '--lookahead-level', '3']
    if v.get('aq', True): a += ['--aq', '--aq-temporal']
    if v.get('aqs'): a += ['--aq-strength', str(v['aqs'])]
    if v.get('tf'): a += ['--tf-level', str(v['tf'])]
    if v.get('bframes'): a += ['--bframes', str(v['bframes'])]
    fg = FG + (f",retain={v['retain']}" if v.get('retain') is not None else '') if v.get('fg', True) else None
    if fg: a += ['--av1-film-grain', fg]
    return a

def do_encode(w, tag, v):
    d = window_dir(w); out = f'{d}/enc/{tag}.mkv'; logp = f'{S}/logs/{w}-{tag}.log'
    os.makedirs(f'{S}/logs', exist_ok=True)
    if os.path.exists(out) and os.path.exists(logp) and os.path.getsize(out) > 0:
        return out, None, json.load(open(logp + '.json'))
    wait_gpu()
    cmd = ['docker', 'exec', 'tdarr-node', 'nvencc', '-i', f'{CW}/{w}/preroll.mkv'] + build_args(v) + ['-o', f'{CW}/{w}/enc/{tag}.mkv']
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    secs = time.time() - t0
    open(logp, 'w').write(' '.join(cmd) + '\n' + r.stdout[-3000:] + r.stderr[-3000:])
    if r.returncode:
        return None, (r.stderr + r.stdout)[-600:], {'cmd': cmd, 'secs': secs}
    meta = {'cmd': cmd, 'secs': round(secs, 1)}
    json.dump(meta, open(logp + '.json', 'w'))
    return out, None, meta
