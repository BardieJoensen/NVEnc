#!/usr/bin/env python3
"""HF energy and residual ACF together for S02E04's weak textured scene."""
import json, os, pathlib, subprocess, sys
import numpy as np
sys.path.insert(0, '/home/bardie/git-repos/NVEnc/tests/fgs')
from matched_rate_sweep import high_pass, autocorr

root = pathlib.Path(os.environ.get('PANTHEON_AUDIT_DIR', '/tmp/downloads/codex-work/pantheon-quality-20261019'))
inv = json.loads((root/'inventory.json').read_text())
item = next(i for i in inv if i['episode']=='S02E04')
window = json.loads((root/'results.json').read_text())['S02E04-50']
frames = [120,126,132,138,144]
result = {'episode':'S02E04', 'sample_start_seconds':window['timestamp_seconds'],
          'frame_indices':frames, 'roi_xywh':[1400,200,400,400],
          'note':'HF sigma in 8-bit luma code units; ACF is the average of horizontal and vertical normalized residual correlation. Read together; whole-frame edges also contribute.'}
for arm in ('source','on','off'):
    cmd = ['ffmpeg','-v','error']
    if arm != 'source':
        cmd += ['-c:v','libdav1d','-filmgrain',str(int(arm=='on'))]
    cmd += ['-ss',str(window['timestamp_seconds']),'-i',item['original' if arm=='source' else 'library'],
            '-vf','select='+ '+'.join(f'eq(n\\,{n})' for n in frames),
            '-frames:v',str(len(frames)),'-fps_mode','passthrough','-pix_fmt','yuv420p10le','-f','rawvideo','-']
    data = subprocess.check_output(cmd)
    raw = np.frombuffer(data,dtype=np.uint16).reshape(len(frames),1080*1920*3//2)
    y = raw[:,:1080*1920].reshape(len(frames),1080,1920).astype(np.float64)/4
    result[arm] = {}
    for label,planes in [('whole_frame',y),('background_roi',y[:,200:600,1400:1800])]:
        residuals = [high_pass(a) for a in planes]
        result[arm][label] = {'hf_sigma':round(float(np.mean([r.std()*(8/5)**.5 for r in residuals])),4),
                             **{f'acf{k}':round(float(np.mean([autocorr(r,k) for r in residuals])),4) for k in (1,2,3)}}
(root/'texture-check.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
