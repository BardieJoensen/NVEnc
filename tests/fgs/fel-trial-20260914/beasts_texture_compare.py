"""Frame-matched source/coded texture observations around synthesis fallbacks.

Sparse native patches and PQ luma code errors are diagnostics, not a perceptual
approval score. A grain-disabled decoder observes the coded base; it is not
equivalent to encoding without FGS.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import numpy as np
from run_encoder_trials import T,L,sha

W,H,N=3840,2160,165
FRAME_BYTES=W*H*3
SIDE=64
PATCHES=[(int(x),int(y)) for y in np.linspace(360,1736,5) for x in np.linspace(128,3648,10)]


def highpass(a):
    return a[1:-1,1:-1]-(a[:-2,1:-1]+a[2:,1:-1]+a[1:-1,:-2]+a[1:-1,2:])/4


def read_exact(stream,count):
    parts=[]
    while count:
        chunk=stream.read(count)
        if not chunk:raise RuntimeError('short decoded frame')
        parts.append(chunk);count-=len(chunk)
    return b''.join(parts)


def main():
    directory=T/'beasts-grain-followup';reference=directory/'reference-pq10.y4m'
    original=T/'outputs/1f373204e9b8d9b771a9-20-default/candidate-pq-av1.mkv'
    modes=[('fgs_on',original,True),('fgs_coded_base',original,False),('no_fgs_encode',directory/'no_fgs/candidate.mkv',True)]
    path=L/'beasts-texture-comparison.json'
    record=json.loads(path.read_text()) if path.exists() else dict(
        scope='All 165 frames; 50 fixed native 64x64 luma patches per frame. PQ 10-bit code values.',
        patch_origins=PATCHES,patch_side=SIDE,interpretation='High-pass texture includes edges and grain. Sparse observations do not certify full-frame HDR/DV fidelity.',modes=[])
    for mode,media,grain in modes:
        if not media.exists():continue
        digest=sha(media)
        prior=next((r for r in record['modes'] if r['mode']==mode),None)
        if prior:
            assert prior['output_sha256']==digest;continue
        command=['ffmpeg','-hide_banner','-v','warning','-nostdin','-xerror','-err_detect','explode',
            '-threads','4','-c:v','libdav1d','-filmgrain','1' if grain else '0','-i',str(media),
            '-map','0:v:0','-fps_mode','passthrough','-pix_fmt','yuv420p10le','-c:v','rawvideo',
            '-threads','2','-f','rawvideo','-']
        rows=[]
        with (directory/(mode+'-texture-decode.log')).open('w') as log, reference.open('rb') as ref:
            header=ref.readline();assert header.startswith(b'YUV4MPEG2') and b'F24000:1001' in header and b'C420p10' in header
            process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=log)
            try:
                for n in range(N):
                    marker=ref.readline();assert marker.startswith(b'FRAME')
                    src=np.frombuffer(read_exact(ref,FRAME_BYTES),dtype='<u2',count=W*H).reshape(H,W)
                    dst=np.frombuffer(read_exact(process.stdout,FRAME_BYTES),dtype='<u2',count=W*H).reshape(H,W)
                    patches=[]
                    for x,y in PATCHES:
                        a=src[y:y+SIDE,x:x+SIDE].astype(np.float32);b=dst[y:y+SIDE,x:x+SIDE].astype(np.float32)
                        ah,bh=highpass(a),highpass(b)
                        patches.append(dict(x=x,y=y,source_mean=float(a.mean()),source_hp_rms=float(np.sqrt(np.mean(ah**2))),
                            output_hp_rms=float(np.sqrt(np.mean(bh**2))),error_rms=float(np.sqrt(np.mean((a-b)**2))),
                            hp_error_rms=float(np.sqrt(np.mean((ah-bh)**2)))))
                    rows.append(dict(frame=n,patches=patches,
                        source_hp_rms=float(np.sqrt(np.mean([p['source_hp_rms']**2 for p in patches]))),
                        output_hp_rms=float(np.sqrt(np.mean([p['output_hp_rms']**2 for p in patches]))),
                        error_rms=float(np.sqrt(np.mean([p['error_rms']**2 for p in patches])))))
                assert not process.stdout.read(1) and not ref.read(1)
                assert process.wait(timeout=30)==0
            finally:
                if process.poll() is None:process.terminate()
        detail=directory/(mode+'-texture-frames.json');detail.write_text(json.dumps(rows,indent=2)+'\n')
        record['modes'].append(dict(mode=mode,output=str(media),output_sha256=digest,frames=N,command=command,detail=str(detail),
            frame_observations=[{k:v for k,v in rows[n].items() if k!='patches'} for n in [0,26,27,28,29,30,31,53,54,55,99,100,153,154,164]]))
        path.write_text(json.dumps(record,indent=2)+'\n');print(mode,'COMPLETE',flush=True)
    record['complete']=len(record['modes'])==3;path.write_text(json.dumps(record,indent=2)+'\n')


if __name__=='__main__':main()
