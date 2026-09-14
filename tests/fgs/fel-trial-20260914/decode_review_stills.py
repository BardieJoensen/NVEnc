"""Select source-indexed AV1 frames with host libdav1d, without colour conversion."""
from pathlib import Path
import hashlib
import json
import subprocess
from run_encoder_trials import T,L

records=[]
for clip in sorted((T/'clips').glob('*-20')):
    n=json.loads((clip/'reconstruction-summary.json').read_text())['strongest_residual_frame']
    for mode in ['default','noresidual','hdr10base-fps-corrected']:
        directory=T/'outputs'/(clip.name+'-'+mode)
        output=directory/f'review-frame-{n}.yuv'
        command=['ffmpeg','-v','warning','-nostdin','-xerror','-err_detect','explode',
            '-threads','4','-c:v','libdav1d','-i',str(directory/'candidate-pq-av1.mkv'),
            '-vf',f'select=eq(n\\,{n})','-frames:v','1','-fps_mode','passthrough',
            '-pix_fmt','yuv420p10le','-c:v','rawvideo','-threads','2','-f','rawvideo',str(output)]
        with (directory/'review-frame-decode.log').open('w') as log:
            subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
        assert output.stat().st_size==3840*2160*3
        with output.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
        records.append(dict(name=clip.name,mode=mode,frame=n,path=str(output),sha256=digest,command=command))
(L/'review-stills-decode.json').write_text(json.dumps(records,indent=2)+'\n')
subprocess.run(['docker','exec','fgs-fel-trial-20260914','bash','/trial/scripts/env.sh',
    'python3','/trial/scripts/review_outputs.py'],check=True,timeout=180)
