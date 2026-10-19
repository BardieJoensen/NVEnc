#!/usr/bin/env python3
"""Diagnostic samples only: production encoder, QVBR/FGS ablations, GPU scoring."""
import importlib.util, json, os, pathlib, statistics, subprocess, sys
import numpy as np
sys.path.insert(0, '/home/bardie/git-repos/NVEnc/tests/fgs')
import campaign
from matched_rate_sweep import high_pass, autocorr
spec = importlib.util.spec_from_file_location('audit','/opt/docker-apps/scripts/library-fidelity/libvsorig.py')
audit = importlib.util.module_from_spec(spec); spec.loader.exec_module(audit)
ROOT = pathlib.Path(os.environ.get('PANTHEON_CONTROL_DIR','/tmp/downloads/codex-work/pantheon-encoder-control-20261019'))
cfg = json.loads((ROOT/'inputs.json').read_text())
N, PRE, FPS, TS = 240, 96, 24000/1001, 1243.493
ARGS = ('--codec av1 --output-depth 10 --max-bitrate 50000 --preset quality --tune hq '
        '--lookahead 32 --lookahead-level 3 --aq --aq-temporal --colormatrix auto --colorprim auto '
        '--transfer auto --colorrange auto --chromaloc auto --master-display copy --max-cll copy').split()
FGS = ['--av1-film-grain','denoise=auto,chroma=auto,denoiser=bilateral']

def command(cmd):
    r=subprocess.run([str(x) for x in cmd],capture_output=True,text=True)
    if r.returncode: raise RuntimeError(r.stderr[-3000:])
    return r

def vmaf(ref,enc,models,out,tag,frames):
    d=audit.vmaf(ref,enc,out,False)
    assert len(d['frames'])==N
    return d['pooled_metrics']
campaign.vmaf_run=vmaf

def thumb(p):
    b=subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-frames:v','24','-vf','scale=480:270','-pix_fmt','gray','-f','rawvideo','-'])
    return np.frombuffer(b,np.uint8).reshape(-1,270,480).astype(np.float32)

def texture(p):
    ids=[120,126,132,138,144]
    b=subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-vf','select='+ '+'.join(f'eq(n\\,{n})' for n in ids),'-frames:v','5','-fps_mode','passthrough','-pix_fmt','yuv420p10le','-f','rawvideo','-'])
    y=np.frombuffer(b,np.uint16).reshape(5,1080*1920*3//2)[:,:1080*1920].reshape(5,1080,1920).astype(np.float64)/4
    result={}
    for name,a in [('whole_frame',y),('background_roi',y[:,200:600,1400:1800])]:
        hp=[high_pass(x) for x in a]
        result[name]={'hf_sigma':round(float(np.mean([x.std()*(8/5)**.5 for x in hp])),4),
                      **{f'acf{k}':round(float(np.mean([autocorr(x,k) for x in hp])),4) for k in (1,2,3)}}
    return result

import time, hashlib
TARGET=10029.36
clip,ref=ROOT/'preroll.mkv',ROOT/'ref.mkv'
def logged(cmd,tag):
    (ROOT/f'{tag}-command.json').write_text(json.dumps([str(x) for x in cmd],indent=2))
    started=time.monotonic()
    with (ROOT/f'{tag}.log').open('w') as log:
        p=subprocess.run([str(x) for x in cmd],stdout=log,stderr=subprocess.STDOUT)
    if p.returncode: raise RuntimeError(f'{tag} failed: see log')
    return time.monotonic()-started
if not clip.exists():
    logged(['ffmpeg','-v','error','-ss',f'{TS-PRE/FPS:.3f}','-i',cfg['original'],'-frames:v',str(PRE+N),'-map','0:v:0','-an','-sn','-c:v','ffvhuff','-pix_fmt','yuv420p',clip],'extract')
audit.decode(cfg['original'],TS,str(ref))
# Verify lossless input and independent reference agree exactly after preroll.
def hashes(path,pre=0):
    cmd=['ffmpeg','-v','error','-i',str(path),'-vf',f'trim=start_frame={pre},setpts=PTS-STARTPTS','-frames:v',str(N),'-pix_fmt','yuv420p10le','-f','framemd5','-']
    return [x.rsplit(',',1)[1].strip() for x in command(cmd).stdout.splitlines() if not x.startswith('#')]
if not (ROOT/os.environ.get('PANTHEON_CONTROL_RESULTS','comparison.json')).exists():
    assert hashes(clip,PRE)==hashes(ref), 'Input clip differs from independent original reference'
print('Exact input/reference equality verified',flush=True)
rt=thumb(ref)
results=json.loads((ROOT/os.environ.get('PANTHEON_CONTROL_RESULTS','comparison.json')).read_text()) if (ROOT/os.environ.get('PANTHEON_CONTROL_RESULTS','comparison.json')).exists() else {'target_kbps':TARGET,'input_reference_exact':True,'source_texture':texture(ref),'attempts':[],'variants':{}}
def save(): (ROOT/os.environ.get('PANTHEON_CONTROL_RESULTS','comparison.json')).write_text(json.dumps(results,indent=2))
def bitrate(enc):
    packets=json.loads(command(['ffprobe','-v','error','-select_streams','v:0','-show_entries','packet=pts_time,size','-of','json',enc]).stdout)['packets']
    assert len(packets)==PRE+N
    # Container PTS rounded to milliseconds; select by presentation-frame index.
    selected=[p for p in packets if PRE<=round(float(p['pts_time'])*FPS)<PRE+N]
    assert len(selected)==N, len(selected)
    return sum(int(p['size']) for p in selected)*8/(N/FPS)/1000
for kind in os.environ.get('PANTHEON_CONTROL_KINDS','nvenc,svt,svt-tf-off,nvenc-noaq,x264-grain').split(','):
    if kind in results['variants']: continue
    target=TARGET
    best=None
    for attempt in range(1,5):
        tag=f'{kind}-{attempt}';enc=ROOT/f'{tag}.mkv'
        if kind.startswith('nvenc'):
            enc_args=[x for x in ARGS if kind!='nvenc-noaq' or x not in ('--aq','--aq-temporal')]
            cmd=[cfg['encoder'],'--avsw','-i',clip,'--vbr',str(round(target)),*enc_args,'-o',enc]
        elif kind=='x264-grain':
            cmd=['/usr/bin/ffmpeg','-hide_banner','-nostdin','-y','-i',clip,'-map','0:v:0','-an','-sn','-c:v','libx264','-preset','slow','-tune','grain','-b:v',str(round(target*1000)),'-threads','8','-pix_fmt','yuv420p',enc]
        else:
            cmd=['/usr/bin/ffmpeg','-hide_banner','-nostdin','-y','-i',clip,'-map','0:v:0','-an','-sn','-c:v','libsvtav1','-preset','4','-b:v',str(round(target*1000)),'-pix_fmt','yuv420p10le','-svtav1-params','film-grain=0:film-grain-denoise=0:tune=0:lp=8'+(':enable-tf=0' if kind=='svt-tf-off' else ''),'-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-color_range','tv',enc]
        print(tag,'encode target',target,flush=True)
        secs=logged(cmd,tag)
        kbps=bitrate(enc);error=abs(kbps/TARGET-1)
        entry={'kind':kind,'tag':tag,'requested_kbps':target,'kbps_window':kbps,'encode_seconds':secs,'relative_rate_error':error}
        results['attempts'].append(entry);save()
        print(json.dumps(entry),flush=True)
        if best is None or error<best['relative_rate_error']:best=entry
        if error<=.015:break
        target*=TARGET/kbps
    assert best['relative_rate_error']<=.03, ('rate matching failed',best)
    tag=best['tag']; enc=ROOT/f'{tag}.mkv'; on=ROOT/f'{tag}-decoded.mkv'
    logged(['ffmpeg','-v','error',*(['-c:v','libdav1d','-filmgrain','0'] if kind!='x264-grain' else []),'-i',enc,'-vf',f'select=gte(n\\,{PRE})','-frames:v',str(N),'-fps_mode','passthrough','-c:v','ffvhuff','-pix_fmt','yuv420p10le',on],tag+'-decode')
    et=thumb(on); costs={k:float(np.abs(rt[4+k:20+k]-et[4:20]).mean()) for k in range(-3,4)}
    assert costs[0]<=min(costs.values())+1e-6, costs
    row=dict(best,alignment_costs=costs)
    row.update(campaign.score(str(ref),str(on),tag,str(ROOT),1080,N))
    doc=json.loads((ROOT/f'metrics-cuda-{tag}.json').read_text()); row.update(audit.pooled(doc))
    for prefix in ('ssimu2','butter'):assert len(json.loads((ROOT/f'{prefix}-{tag}.json').read_text()))==N
    row['texture']=texture(on)
    results['variants'][kind]=row;save()
    print('RESULT',kind,json.dumps(row),flush=True)
    for label,path in [(kind,on),('source',ref)]:
        out=ROOT/f'{label}-frame134.png'
        if not out.exists():logged(['ffmpeg','-v','error','-i',path,'-vf','select=eq(n\\,134)','-frames:v','1',out],label+'-screenshot')
print('COMPLETE',flush=True)
