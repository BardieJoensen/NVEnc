import sys
from prep import *
man = jload(MANIFEST); bad=0
for wid in WINDOWS:
    m = man[wid]; src = m['src']; T = m['seek_target']
    d = f'{W}/{wid}'; os.makedirs(d, exist_ok=True); out = f'{d}/win.mkv'
    if not os.path.exists(out):
        r = run(['ffmpeg','-v','error','-y','-ss',str(T),'-i',src,'-map','0:v:0','-c','copy','-t','12',out]); assert r.returncode==0, r.stderr
    n = int(run(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=nb_read_frames','-of','csv=p=0',out]).stdout.strip().strip(','))
    kf = keyframe_before(src, T)
    ok = n==m['frames'] and abs(kf-m['actual_start_pts'])<1e-6
    bad += not ok
    print(wid, n, m['frames'], kf, m['actual_start_pts'], 'OK' if ok else 'MISMATCH', flush=True)
print('bad', bad)
