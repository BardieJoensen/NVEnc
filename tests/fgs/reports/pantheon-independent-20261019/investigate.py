#!/usr/bin/env python3
"""Isolated Pantheon experiment driver. No production/library writes.

All subprocess arguments, durations and stdout/stderr are retained in scratch.
Uses campaign.score with a decoded-input CUDA adapter (incl. supplementary CAMBI).
"""
import argparse, functools, hashlib, json, os, pathlib, shutil, subprocess, sys, time
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO/'tests/fgs'))
import campaign
from matched_rate_sweep import high_pass, autocorr
ROOT = pathlib.Path(os.environ.get('PANTHEON_INDEPENDENT_DIR', '/tmp/downloads/codex-work/pantheon-independent-investigation'))
NV = '/opt/docker-apps/build/tdarr-node/nvencc'
SVT = ROOT/'svt-source/Bin/Release/SvtAv1EncApp'
N, PRE, W, H = 240, 96, 1920, 1080
E4 = json.loads((HERE.parent/'pantheon-encoder-control-20261019/inputs.json').read_text())
E5 = json.loads((HERE.parent/'pantheon-s02e05-grain-20261019/inputs.json').read_text())
CASES = {'e04': (E4, 1243.493, 24000/1001), **{f'e05-{t}': (E5, t, 24) for t in (1420,1440,1460)}}
COLOR = ['-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709']

def dump(p, obj):
    p.write_text(json.dumps(obj, indent=2)+'\n')

@functools.lru_cache(maxsize=128)
def _sha(path, size, mtime):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        while b:=f.read(4*1024*1024):h.update(b)
    return h.hexdigest()

def fingerprint(p):
    p=pathlib.Path(p);s=p.stat()
    return {'path':str(p.resolve()),'sha256':_sha(str(p),s.st_size,s.st_mtime_ns)}

def cache_guard(stamp,identity,artifacts):
    """Refuse ambiguous/stale caches; never relabel old pixels with a new input.

    The first investigation predates these stamps; reproduce it in fresh scratch.
    Raising preserves all existing evidence instead of deleting/replacing it.
    """
    if stamp.exists():
        if json.loads(stamp.read_text())!=identity:raise RuntimeError(f'Stale cache {stamp}; use fresh scratch/tag')
    elif any(p.exists() for p in artifacts):
        raise RuntimeError(f'Unverified existing cache {stamp}; use fresh scratch/tag')
    else:dump(stamp,identity)

def run(cmd, d=None, tag='command', binary=False):
    cmd = list(map(str, cmd))
    t=time.monotonic()
    r=subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if d:
        dump(d/(tag+'-command.json'), {'argv':cmd,'seconds':time.monotonic()-t,'returncode':r.returncode})
        (d/(tag+'.log')).write_bytes(r.stderr if binary else r.stdout+r.stderr)
    if r.returncode: raise RuntimeError(f'{tag}: {r.stderr.decode(errors="replace")[-2000:]}')
    return r.stdout if binary else r.stdout.decode()

def hashes(cmd):
    return [x.rsplit(',',1)[-1].strip() for x in run(cmd+['-map','0:v:0','-an','-sn','-f','framemd5','-']).splitlines() if x and not x.startswith('#')]

def probe(p):
    return json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',p]))

def packets(p, interval=None):
    return json.loads(run(['ffprobe','-v','error',*(['-read_intervals',interval] if interval else []),'-select_streams','v:0','-show_packets','-show_entries','packet=pts_time,dts_time,duration_time,size,flags','-of','json',p]))['packets']

def prepare(case):
    cfg, ts, fps=CASES[case]; d=ROOT/case; d.mkdir(exist_ok=True)
    if (d/'validity.json').exists():
        old=json.loads((d/'validity.json').read_text());s=os.stat(cfg['original'])
        assert old['source']==cfg['original'] and old['source_stat']=={'size':s.st_size,'mtime_ns':s.st_mtime_ns}, 'Source changed; use fresh scratch'
        assert old['requested_start']==ts and old['fps']==fps
    clip, ref=d/'input.mkv',d/'ref.mkv'
    if not clip.exists():
        run(['ffmpeg','-v','error','-threads','4','-ss',f'{ts-PRE/fps:.6f}','-i',cfg['original'],'-frames:v',PRE+N,'-map','0:v:0','-an','-sn','-c:v','ffvhuff','-threads','4','-pix_fmt','yuv420p',*COLOR,clip],d,'extract-input')
    if not ref.exists():
        run(['ffmpeg','-v','error','-threads','4','-ss',str(ts),'-i',cfg['original'],'-frames:v',N,'-map','0:v:0','-an','-sn','-c:v','ffvhuff','-threads','4','-pix_fmt','yuv420p10le',*COLOR,ref],d,'extract-ref')
    if not (d/'validity.json').exists():
        base=['ffmpeg','-v','error','-threads','4']
        hc=hashes(base+['-i',str(clip),'-vf',f'trim=start_frame={PRE},setpts=PTS-STARTPTS','-frames:v',str(N),'-pix_fmt','yuv420p10le'])
        hr=hashes(base+['-i',str(ref),'-frames:v',str(N),'-pix_fmt','yuv420p10le'])
        # Different seek point, then output-side discard: independent GOP decode.
        hi=hashes(base+['-ss',str(ts-30),'-i',cfg['original'],'-ss','30','-frames:v',str(N),'-pix_fmt','yuv420p10le'])
        assert len(hc)==N and hc==hr==hi, 'Extraction/reference mismatch'
        pk=packets(cfg['original'],f'{ts-15}%{ts+15}')
        selected=sorted([p for p in pk if float(p['pts_time'])>=ts],key=lambda p:float(p['pts_time']))[:N]
        assert len(selected)==N
        rate=sum(int(p['size']) for p in selected)*8/(N/fps)/1e6
        data={'case':case,'source':cfg['original'],'source_stat':{'size':os.stat(cfg['original']).st_size,'mtime_ns':os.stat(cfg['original']).st_mtime_ns},'source_probe':probe(cfg['original']),'library_probe':probe(cfg['library']),'requested_start':ts,'fps':fps,'source_packets':selected,'source_mbps':rate,'hashes_input':hc,'hashes_ref':hr,'hashes_independent_seek':hi,'all_240_equal':True,'first_pts':selected[0]['pts_time'],'last_pts':selected[-1]['pts_time']}
        dump(d/'validity.json',data)
    return d

def decode(enc, out, pre=PRE, grain=1):
    codec=probe(enc)['streams'][0]['codec_name']
    identity={'input':fingerprint(enc),'ffmpeg':fingerprint(shutil.which('ffmpeg')),'pre':pre,'frames':N,'grain':grain if codec=='av1' else None,'raw_bt709_assignment':True,'version':2}
    cache_guard(out.with_suffix('.decode-identity.json'),identity,[out])
    if out.exists(): return
    # Y4M does not carry the BT.709 matrix. Assign its known interpretation
    # before output negotiation; otherwise this FFmpeg converts assumed 601 to
    # the requested 709. setparams changes metadata only, never sample values.
    params='setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709,' if codec=='rawvideo' else ''
    run(['ffmpeg','-v','error','-threads','4',*(['-c:v','libdav1d','-filmgrain',str(grain)] if codec=='av1' else []),'-i',enc,'-vf',params+f'trim=start_frame={pre},setpts=PTS-STARTPTS','-frames:v',N,'-fps_mode','passthrough','-c:v','ffvhuff','-threads','4','-pix_fmt','yuv420p10le',*COLOR,out],out.parent,out.stem+'-decode')

def vmaf_decoded(ref,enc,models,out,tag,frames):
    out=pathlib.Path(out); d=out.parent
    if not out.exists():
        fifos=[d/(tag+'-'+x+'.fifo') for x in ('ref','dist')]; writers=[]
        try:
            for path,src in zip(fifos,(ref,enc)):
                os.mkfifo(path)
                writers.append(subprocess.Popen(['ffmpeg','-v','error','-threads','4','-i',str(src),'-frames:v',str(frames),'-pix_fmt','yuv420p10le','-strict','-1','-f','yuv4mpegpipe','-y',str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
            cmd=[campaign.VMAF,'--reference',fifos[0],'--distorted',fifos[1],'--gpumask','0','--threads','16']
            for key,val in models.items(): cmd+=['--model',val+':name='+key]
            cmd+=['--feature','psnr_cuda','--feature','ssim_cuda','--feature','ciede_cuda','--feature','cambi=full_ref=true','--json','--output',out]
            run(cmd,d,tag+'-vmaf')
        finally:
            for p in writers:
                if p.poll() is None: p.terminate()
                p.wait()
            for p in fifos: p.unlink(missing_ok=True)
    doc=json.loads(out.read_text())
    assert len(doc['frames'])==frames
    bad=[(i,k) for i,f in enumerate(doc['frames']) for k,v in f['metrics'].items() if not isinstance(v,(int,float)) or not np.isfinite(v)]
    if bad:
        # CUDA CIEDE is 45-20*log10(mean_deltaE), hence +inf for identical
        # pictures. JSON writes it as null. Prove exact identity for each such
        # frame; never admit null VMAF/VIF/motion or unexplained invalid scores.
        assert all(k=='ciede2000' for i,k in bad),bad
        hs=[hashes(['ffmpeg','-v','error','-threads','4','-i',str(p),'-frames:v',str(frames),'-pix_fmt','yuv420p10le']) for p in (ref,enc)]
        assert all(hs[0][i]==hs[1][i] for i,k in bad)
        dump(d/(tag+'-exact-ciede-frames.json'),{'frames':[i for i,k in bad],'interpretation':'positive infinity from zero DeltaE, verified exact decoded hashes'})
    pooled=json.loads(json.dumps(doc['pooled_metrics']))
    if bad and pooled['ciede2000']['mean'] is None:pooled['ciede2000']['mean']=float('inf')
    return pooled
campaign.vmaf_run=vmaf_decoded

def thumbs(p):
    b=run(['ffmpeg','-v','error','-threads','4','-i',p,'-vf','scale=240:135','-frames:v',N,'-pix_fmt','gray','-f','rawvideo','-'],binary=True)
    return np.frombuffer(b,np.uint8).reshape(N,135,240).astype(np.float32)

def alignment(ref,enc):
    a,b=thumbs(ref),thumbs(enc); rows=[]
    for start in range(0,N,24):
        end=min(start+24,N)
        costs={str(k):float(np.abs(a[start+k:end+k]-b[start:end]).mean()) for k in range(-3,4) if start+k>=0 and end+k<=N}
        assert costs['0']<=min(costs.values())+1e-6, costs
        rows.append({'start':start,'end':end,'costs':costs})
    return rows

def rate(p,fps):
    pk=packets(p); pk=sorted(pk,key=lambda x:float(x['pts_time']))
    selected=[x for x in pk if PRE<=round(float(x['pts_time'])*fps)<PRE+N]
    assert len(pk)==PRE+N and len(selected)==N, (len(pk),len(selected))
    return sum(int(x['size']) for x in selected)*8/(N/fps)/1e6

def score(case, enc, tag, pre=PRE, grain=1):
    d=ROOT/case; ref=d/'ref.mkv'; dec=d/(tag+'-decoded.mkv')
    decode(enc,dec,pre,grain)
    identity={'reference':fingerprint(ref),'distorted':fingerprint(dec),'vmaf':fingerprint(campaign.VMAF),'campaign':fingerprint(REPO/'tests/fgs/campaign.py'),'adapter':fingerprint(pathlib.Path(__file__)),'ffvship_image':run(['docker','image','inspect',campaign.FFVSHIP_IMG,'--format','{{.Id}}']).strip(),'frames':N}
    cache_guard(d/(tag+'-score-identity.json'),identity,[d/(prefix+tag+'.json') for prefix in ('metrics-cuda-','ssimu2-','butter-')])
    check=alignment(ref,dec)
    result=campaign.score(str(ref),str(dec),tag,str(d),H,N)
    if not np.isfinite(result['ciede2000']):result['ciede2000']='infinite: contains exact frames; see exact-ciede-frames.json'
    doc=json.loads((d/('metrics-cuda-'+tag+'.json')).read_text())
    for prefix in ('ssimu2-','butter-'): assert len(json.loads((d/(prefix+tag+'.json')).read_text()))==N
    codec=probe(enc)['streams'][0]['codec_name']
    result.update({'pooled':doc['pooled_metrics'],'vmaf_p1_excluding_frame0':float(np.percentile([f['metrics']['vmaf'] for f in doc['frames'][1:]],1)),'alignment_all_blocks':check,'encode':str(enc),'decoded_input_codec':codec,'decoder':'libdav1d' if codec=='av1' else 'ffmpeg default lossless decoder','grain_application':grain if codec=='av1' else None})
    if pre==PRE: result['actual_mbps']=rate(enc,CASES[case][2])
    dump(d/(tag+'-result.json'),result)
    print('SCORE',case,tag,{k:v for k,v in result.items() if k not in ('pooled','alignment_all_blocks')},flush=True)
    return result

def encode(case,kind,target,extra=None):
    d=prepare(case); fps=CASES[case][2]; target=float(target); request=target*1000
    stem=f'{kind}-{target:g}'; best=None
    for trial in range(1,7):
        tag=stem+f'-try{trial}'; enc=d/(tag+'.mkv')
        if kind.startswith('nv'):
            opts=['--codec','av1','--output-depth','10','--preset','quality','--tune','hq','--lookahead','32','--lookahead-level','3','--aq','--aq-temporal','--colormatrix','bt709','--colorprim','bt709','--transfer','bt709','--colorrange','limited','--chromaloc','auto']
            opts+=['--vbr',str(round(request)),'--max-bitrate','50000']
            if kind=='nv-fgs':opts+=['--av1-film-grain','denoise=auto,chroma=auto,denoiser=bilateral','--film-grain-table-out',str(d/(tag+'.tbl'))]
            cmd=[NV,'--avsw','-i',d/'input.mkv',*opts,*(extra or []),'-o',enc]
            identity={'argv':list(map(str,cmd)),'input':fingerprint(d/'input.mkv'),'encoder':fingerprint(NV),'auxiliary_inputs':{flag:fingerprint(cmd[cmd.index(flag)+1]) for flag in ('--keyfile','--film-grain-table') if flag in cmd}}
            cache_guard(d/(tag+'-encode-identity.json'),identity,[enc])
            if not enc.exists(): run(cmd,d,tag)
        else:
            y4m=d/'input10.y4m'
            if not y4m.exists():run(['ffmpeg','-v','error','-threads','4','-i',d/'input.mkv','-pix_fmt','yuv420p10le','-strict','-1','-f','yuv4mpegpipe',y4m],d,'make-y4m')
            ivf=d/(tag+'.ivf')
            cmd=['nice','-n','10','taskset','-c','0-7',SVT,'-i',y4m,'-b',ivf,'--preset','4','--tune','0','--rc','1','--tbr',str(round(request)),'--lp','2','--film-grain','0','--film-grain-denoise','0','--color-range','0','--color-primaries','1','--transfer-characteristics','1','--matrix-coefficients','1','--progress','0',*(extra or [])]
            cache_guard(d/(tag+'-encode-identity.json'),{'argv':list(map(str,cmd)),'input':fingerprint(y4m),'encoder':fingerprint(SVT)},[enc,ivf])
            if not enc.exists():
                run(cmd,d,tag)
                run(['ffmpeg','-v','error','-i',ivf,'-map','0:v:0','-c','copy',enc],d,tag+'-remux')
        actual=rate(enc,fps); err=abs(actual/target-1)
        print('RATE',case,tag,actual,'mismatch',err,flush=True)
        if best is None or err<best[0]:best=(err,enc,tag,actual)
        if err<=.01:break
        request*=target/actual
    err,enc,tag,actual=best
    dump(d/(stem+'-selection.json'),{'selected':str(enc),'target_mbps':target,'actual_mbps':actual,'relative_error':err,'extra':extra})
    return enc,stem

def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['prepare','encode','score']);ap.add_argument('case',choices=CASES);ap.add_argument('--kind',default='nv');ap.add_argument('--rate',type=float,default=10.02936);ap.add_argument('--extra',default='');ap.add_argument('--path');ap.add_argument('--tag');ap.add_argument('--pre',type=int,default=PRE);ap.add_argument('--grain',type=int,default=1);a=ap.parse_args()
    if a.action=='prepare':prepare(a.case)
    elif a.action=='encode':
        import shlex
        enc,tag=encode(a.case,a.kind,a.rate,shlex.split(a.extra));score(a.case,enc,tag)
    else:score(a.case,pathlib.Path(a.path),a.tag,a.pre,a.grain)
if __name__=='__main__':main()
