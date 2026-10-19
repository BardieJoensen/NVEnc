#!/usr/bin/env python3
"""Diagnostic samples only: production encoder, QVBR/FGS ablations, GPU scoring."""
import importlib.util, json, os, pathlib, statistics, subprocess, sys
import numpy as np
sys.path.insert(0, '/home/bardie/git-repos/NVEnc/tests/fgs')
import campaign
from matched_rate_sweep import high_pass, autocorr
spec = importlib.util.spec_from_file_location('audit','/opt/docker-apps/scripts/library-fidelity/libvsorig.py')
audit = importlib.util.module_from_spec(spec); spec.loader.exec_module(audit)
ROOT = pathlib.Path(os.environ.get('PANTHEON_FIX_DIR','/tmp/downloads/codex-work/pantheon-fix-20261019'))
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

clip,ref=ROOT/'preroll.mkv',ROOT/'ref.mkv'
if not clip.exists():
    command(['ffmpeg','-v','error','-ss',f'{TS-PRE/FPS:.3f}','-i',cfg['original'],'-frames:v',str(PRE+N),'-map','0:v:0','-an','-sn','-c:v','ffvhuff','-pix_fmt','yuv420p',clip])
audit.decode(cfg['original'],TS,str(ref))
rt=thumb(ref)
results=json.loads((ROOT/'comparison.json').read_text()) if (ROOT/'comparison.json').exists() else {}
if 'source_texture' not in results: results['source_texture']=texture(ref)
variants=[('library',None,None)]+[(f'q{q}-'+('fgs' if fg else 'plain'),q,fg) for q,fg in [(34,True),(30,True),(26,True),(22,True),(30,False),(26,False),(22,False)]]+[('matched-q30fgs-plain',None,False),('window-matched-q30fgs-plain',None,False)]
for tag,q,fg in variants:
    if tag in results:continue
    print(tag,'start',flush=True)
    on=ROOT/f'{tag}-on.mkv';enc=ROOT/f'{tag}.mkv'
    row={}
    if tag=='library':
        audit.decode(cfg['library'],TS,str(on),dav1d=True)
    else:
        target=round(results['q30-fgs']['kbps_all']) if q is None else None
        if tag=='window-matched-q30fgs-plain':
            target=round(target*results['q30-fgs']['kbps_window']/results['matched-q30fgs-plain']['kbps_window'])
        rate=['--qvbr',str(q)] if q is not None else ['--vbr',str(target)]
        cmd=[cfg['encoder'],'--avsw','-i',str(clip),*rate,*ARGS,*(FGS if fg else []),'-o',str(enc)]
        (ROOT/f'{tag}-command.json').write_text(json.dumps(cmd,indent=2))
        if not enc.exists():
            log=command(cmd);(ROOT/f'{tag}-encode.log').write_text(log.stdout+log.stderr)
        sizes=[int(x) for x in command(['ffprobe','-v','error','-select_streams','v:0','-show_entries','packet=size','-of','csv=p=0',enc]).stdout.split()]
        assert len(sizes)==PRE+N
        row['kbps_window']=round(sum(sizes[PRE:])*8/(N/FPS)/1000,2)
        row['kbps_all']=round(sum(sizes)*8/(len(sizes)/FPS)/1000,2)
        if not on.exists():
            command(['ffmpeg','-v','error','-c:v','libdav1d','-i',enc,'-vf',f'select=gte(n\\,{PRE})','-frames:v',str(N),'-fps_mode','passthrough','-c:v','ffvhuff','-pix_fmt','yuv420p10le',on])
    et=thumb(on)
    costs={k:float(np.abs(rt[4+k:20+k]-et[4:20]).mean()) for k in range(-3,4)}
    assert costs[0]<=min(costs.values())+1e-6,(tag,costs)
    row['alignment_costs']=costs
    row.update(campaign.score(str(ref),str(on),tag,str(ROOT),1080,N))
    doc=json.loads((ROOT/f'metrics-cuda-{tag}.json').read_text())
    row.update(audit.pooled(doc))
    for prefix in ('ssimu2','butter'):
        assert len(json.loads((ROOT/f'{prefix}-{tag}.json').read_text()))==N
    row['texture']=texture(on)
    results[tag]=row
    (ROOT/'comparison.json').write_text(json.dumps(results,indent=2))
    print(tag,json.dumps(row),flush=True)
    on.unlink()
print('COMPLETE',flush=True)
