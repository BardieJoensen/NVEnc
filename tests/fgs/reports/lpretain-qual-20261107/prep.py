import sys
from common import *
def run(c, **kw): return subprocess.run(c, capture_output=True, text=True, **kw)
def keyframe_before(src, t):
    r = run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-read_intervals', f'{max(0,t-40)}%{t+1}', '-show_entries', 'packet=pts_time,flags', '-of', 'csv=p=0', src])
    ks = [float(l.split(',')[0]) for l in r.stdout.splitlines() if ',' in l and 'K' in l.split(',')[1]]
    ks = [k for k in ks if k <= t + 1e-6]
    return max(ks) if ks else None
def frames_y(path, n=None, every=1):
    cmd = ['ffmpeg', '-v', 'error', '-i', path, '-map', '0:v:0', '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'gray', '-']
    W_, H_ = DIMS['w'], DIMS['h']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE); i = 0
    while True:
        d = p.stdout.read(W_ * H_)
        if len(d) < W_ * H_: break
        if i % every == 0: yield i, np.frombuffer(d, np.uint8).reshape(H_, W_)
        i += 1
    p.wait()
def detect(path, nfr):
    fr = [y.astype(np.float32) for _, y in frames_y(path, every=4)]
    rm = np.max([f.mean(1) for f in fr], 0); rs = np.max([f.std(1) for f in fr], 0)
    ra = np.where((rm >= 10) & (rs > 1))[0]; y0, y1 = ra[0], ra[-1] + 1
    cm = np.max([f[y0:y1].mean(0) for f in fr], 0); cs = np.max([f[y0:y1].std(0) for f in fr], 0)
    ca_ = np.where((cm >= 10) & (cs > 1))[0]; x0, x1 = ca_[0], ca_[-1] + 1
    ay0 = -(-y0 // 32) * 32; ay1 = y1 // 32 * 32; ax0 = -(-x0 // 32) * 32; ax1 = x1 // 32 * 32
    return dict(raw=[int(x0), int(y0), int(x1 - x0), int(y1 - y0)], rect=[int(ax0), int(ay0), int(ax1 - ax0), int(ay1 - ay0)])
def prep(wid, shift=0, note=None):
    t, pct = WINDOWS[wid]; src, dur, cls = TITLES[t]; set_dim(wid)
    d = f'{W}/{wid}'; os.makedirs(d, exist_ok=True)
    T = round(start_of(wid) + shift, 1)
    out = f'{d}/win.mkv'
    if os.path.exists(out): os.unlink(out)
    tf = t == 'tf'
    cutp = f'{d}/cut_src.mkv' if tf else out
    r = run(['ffmpeg', '-v', 'error', '-y', '-ss', str(T), '-i', src, '-map', '0:v:0', '-c', 'copy', '-t', '12', cutp])
    assert r.returncode == 0, r.stderr
    first_pts = float(run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'packet=pts_time', '-read_intervals', '%+#1', '-of', 'csv=p=0', cutp]).stdout.split()[0].strip(','))
    ncut = int(run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0', cutp]).stdout.strip().strip(','))
    if tf:
        # base layer decode -> FFV1 yuv420p10le, half the scored frames of a 1080p window (~300 -> 150), same keyframe preroll
        half = ncut // 2
        r = run(['ffmpeg', '-v', 'error', '-y', '-i', cutp, '-map', '0:v:0', '-an', '-fps_mode', 'passthrough', '-frames:v', str(half), '-c:v', 'ffv1', '-level', '3', '-pix_fmt', 'yuv420p10le',
                 '-color_primaries', 'bt2020', '-color_trc', 'smpte2084', '-colorspace', 'bt2020nc', out])
        assert r.returncode == 0, r.stderr
        os.unlink(cutp)
    n = int(run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0', out]).stdout.strip().strip(','))
    info = json.loads(run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=avg_frame_rate,width,height,pix_fmt,r_frame_rate,color_space,color_transfer,color_primaries,codec_name', '-of', 'json', out]).stdout)['streams'][0]
    dec = run(['ffmpeg', '-v', 'error', '-i', out, '-f', 'null', '-']).stderr.strip()
    kf = keyframe_before(src, T)
    det = detect(out, n)
    x0, y0, w0, h0 = det['rect']
    low = [float(y[y0:y0+h0, x0:x0+w0].mean()) < 32 for _, y in frames_y(out)]
    lowfrac = sum(low) / len(low)
    return dict(wid=wid, title=t, cls=cls, src=src, nominal_start=start_of(wid), shift=shift, seek_target=T, actual_start_pts=kf, cut_first_packet_pts=first_pts, cut_frames_full=ncut,
             frames=n, fps=info['avg_frame_rate'], width=info['width'], height=info['height'], pix_fmt=info['pix_fmt'], codec=info['codec_name'], color=[info.get('color_space'), info.get('color_transfer'), info.get('color_primaries')],
             decode_errors=dec[:300], lowluma_frac=round(lowfrac, 3), v=3, active=det, shift_note=note)
if __name__ == '__main__':
    man = jload(MANIFEST)
    for wid in WINDOWS:
        if wid in man: continue
        m = prep(wid)
        if m['lowluma_frac'] > 0.5:
            f0 = m['lowluma_frac']
            m = prep(wid, 60, f'+60 s once: {f0} of scored frames in the nominal window had active-area mean luma < 32')
        man[wid] = m; jsave(MANIFEST, man)
        print(wid, m['seek_target'], m['actual_start_pts'], m['cut_first_packet_pts'], m['frames'], m['cut_frames_full'], m['fps'], m['lowluma_frac'], m['active'], m['decode_errors'][:80], m['shift_note'], flush=True)
