#!/usr/bin/env python3
"""Original-rate gate, exact SVT/decoder samples, then established GPU campaign."""
import hashlib
import json
import os
import re
from pathlib import Path
import sys
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('PANTHEON_SOURCEBUDGET_ROOT','/tmp/downloads/codex-work/pantheon-sourcebudget-20261020'))
os.environ['PANTHEON_RD_ROOT']=str(ROOT)
os.environ['PANTHEON_INDEPENDENT_DIR']=str(ROOT/'parent/scores')
sys.path.insert(0,str(HERE.parent/'pantheon-rd-20261019'))
from analyze import x, paired, desc, W, H
from packet_window import measure
import texture

case,tag,*mode=sys.argv[1:];assert case in ('e04','e05-1440')
assert mode in ([],['--under-cap-screen'])
d=ROOT/'worker/runs'/case/tag;f=ROOT/'fixtures'/case;s=ROOT/'parent/scores'/case
s.mkdir(parents=True,exist_ok=True)
for name in ('ref.mkv','source.yuv','validity.json'):
    dest=s/name
    if not dest.exists():os.link(f/name,dest)
    assert os.path.samefile(dest,f/name) and not dest.is_symlink()
v=json.loads((f/'validity.json').read_text());fps=v['fps'];enc=d/'out.mkv'
rate,packets,start=measure(enc,fps);ratio=rate/v['source_mbps'];matched=.99<=ratio<=1
assert 0<ratio<=1,'Any practical screen must meet the hard original packet-rate ceiling.'
if not mode:assert matched,'Default decisive comparison requires99–100%; use explicit under-cap screen for cheaper arms.'
run=json.loads((d/'command.json').read_text())
assert x.fingerprint(f/'validity.json')['sha256']==run['validity']['sha256']
assert fps==run['validity']['fps'] and v['source_mbps']==run['validity']['source_mbps']
assert run['status']==('encoded' if matched else 'rate_gate_failed') and run['returncode']==0
assert run['packet_window']['decisive_rate_gate']==matched and run['packet_window']['within_source_ceiling']
assert abs(run['packet_window']['actual_mbps']-rate)<1e-10
assert json.loads((d/'packet-window.json').read_text())==run['packet_window']
assert x.fingerprint(enc)['sha256']==run['mkv_output']['sha256']
assert x.fingerprint(d/'recon.yuv')['sha256']==run['recon']['sha256']
assert x.fingerprint(f/'input10.y4m')['sha256']==run['input']['sha256']
assert x.fingerprint(d/'measured-runner.py')['sha256']==run['script']['sha256']
assert x.fingerprint(run['binary']['path'])['sha256']==run['binary']['sha256']=='5bd538283d52958ffd1756400e4b7b49178bf7895c68904a4670f5ab3a5ba215'
historical=f/'historical-input-validation.json';hi=json.loads(historical.read_text())
assert hi['all336_exact_Y4M_bytes_match_prior'] and hi['input']['sha256']==run['input']['sha256']
assert hi['prior_input_identity']['svt_input']['sha256']==run['input']['sha256']
assert x.fingerprint(hi['prior_receipt']['path'])['sha256']==hi['prior_receipt']['sha256']
assert x.fingerprint(historical)['sha256']==run['historical_input_validation']['sha256']
archived=Path('/media/merged-storage/cold-storage/docker-apps/pantheon-causal-20261019')/case/('b-baseline-try2-command.json' if case=='e05-1440' else 'b-baseline-command.json')
expected=list(json.loads(archived.read_text())['argv']);expected[6]=run['binary']['path']
for flag,value in {'-i':str(f/'input10.y4m'),'-b':str(d/'out.ivf'),'-o':str(d/'recon.yuv'),'--preset':'0','--tbr':str(run['request_kbps'])}.items():
    expected[expected.index(flag)+1]=value
assert expected==run['argv']
log=(d/'encode.log').read_text()
assert re.search(r'preset / tune / pred struct\s*:\s*0\s*/\s*VQ\s*/',log)
assert re.search(r'BRC mode / target bitrate \(kbps\)\s*:\s*VBR\s*/',log)
stream=x.probe(enc)['streams'][0]
assert stream['codec_name']=='av1' and stream['pix_fmt']=='yuv420p10le'
assert (stream['width'],stream['height'])==(W,H)
assert [stream[k] for k in ('color_range','color_space','color_transfer','color_primaries')]==['tv','bt709','bt709','bt709']
cpu=['ffmpeg','-v','error','-threads','4','-c:v','libdav1d','-filmgrain','0','-i',enc,'-frames:v','336','-pix_fmt','yuv420p10le']
gpu=['/usr/bin/ffmpeg','-v','error','-threads','4','-hwaccel','cuda','-hwaccel_output_format','cuda','-c:v','av1_cuvid','-i',enc,
     '-vf','hwdownload,format=p010le,format=yuv420p10le','-frames:v','336','-pix_fmt','yuv420p10le']
hashes=x.hashes(cpu);gpu_hashes=x.hashes(gpu)
assert len(hashes)==336 and hashes==gpu_hashes
app=[];recon=d/'recon.yuv';assert recon.stat().st_size==336*W*H*3
with recon.open('rb') as raw:
    for n in range(336):
        frame=raw.read(W*H*3);assert len(frame)==W*H*3
        app.append(hashlib.md5(frame).hexdigest())
    assert not raw.read(1)
assert hashes==app,'App/dav1d/NVDEC must agree on all336 frames and all planes.'
x.dump(d/'decoder-validation.json',{'all336_allplanes_app_dav1d_NVDEC_exact':True,'hashes':hashes,
    'commands':[list(map(str,cpu)),list(map(str,gpu))],'output':x.fingerprint(enc),'app_recon':x.fingerprint(recon),
    'ffmpeg_CPU':x.fingerprint(x.shutil.which('ffmpeg')),'ffmpeg_GPU':x.fingerprint('/usr/bin/ffmpeg')})
x.rate=lambda path,rate_fps:measure(path,rate_fps)[0]
result=x.score(case,enc,tag,grain=0)
decoded=s/(tag+'-decoded.mkv');t=texture.analyze(case,tag,decoded)
scored_hashes=x.hashes(['ffmpeg','-v','error','-threads','4','-i',decoded,'-frames:v','240','-pix_fmt','yuv420p10le'])
assert scored_hashes==hashes[96:336]
oldpath=Path('/media/merged-storage/cold-storage/docker-apps/pantheon-quantization-20261019')/case/'whole-window-controls.json'
old=json.loads(oldpath.read_text());base='detail' if case=='e04' else 'detail2'
baseline_receipt=oldpath.parent/(base+'-encode.json');br=json.loads(baseline_receipt.read_text())
baseline_ivf=oldpath.parent/(base+'.ivf')
assert br['identical_prior_baseline'] and x.fingerprint(baseline_ivf)['sha256']==br['sha256']
baseline_ratio=rate/br['rate_mbps']
if matched:assert abs(baseline_ratio-1)<=.01
source=np.memmap(f/'source.yuv',dtype='<u2',mode='r',shape=(240,W*H*3//2))
fresh=json.loads((f/'fresh-validation.json').read_text())
assert fresh['all240_allplanes_match_archived_original'] and fresh['source_raw']==x.fingerprint(f/'source.yuv')
recons=np.memmap(recon,dtype='<u2',mode='r',shape=(336,W*H*3//2))
keys={(r['frame'],r['x'],r['y']) for r in old['tiles']}
assert len(keys)==len(old['tiles'])==12870 and len({k[0] for k in keys})==15
rows=[]
for r in old['tiles']:
    n,xx,yy=r['frame'],r['x'],r['y'];sl=np.s_[yy:yy+32,xx:xx+32]
    sy=source[n,:W*H].reshape(H,W)[sl].astype(float)/4
    ey=recons[n+96,:W*H].reshape(H,W)[sl].astype(float)/4
    sd=desc(sy)
    assert all((r['source'][k] is None and sd[k] is None) or (r['source'][k] is not None and sd[k] is not None and abs(r['source'][k]-sd[k])<1e-10) for k in sd)
    rows.append({'frame':n,'x':xx,'y':yy,'kind':r['kind'],'outside_target':r['outside_target'],'source':sd,
                 'baseline':{**r[base],'mse':r['mse'][base]},'candidate':paired(sy,ey)})
summary={}
for kind in ('all','quiet','edge','flat_texture','other'):
    for outside in (False,True):
        pool=[r for r in rows if (kind=='all' or r['kind']==kind) and (not outside or r['outside_target'])];obj={'tiles':len(pool)}
        for arm in ('baseline','candidate'):
            obj[arm]={k:float(np.mean(a)) if a else None for k,a in {
                'mse_mean':[r[arm]['mse'] for r in pool],
                'hf_abs_error':[abs(r[arm]['hf_sigma']-r['source']['hf_sigma']) for r in pool],
                'acf1_abs_error':[abs(r[arm]['acf1']-r['source']['acf1']) for r in pool if r[arm]['acf1'] is not None and r['source']['acf1'] is not None]}.items()}
            obj[arm]['mse_p95']=float(np.percentile([r[arm]['mse'] for r in pool],95)) if pool else None
            obj[arm]['hf_signed_delta_p95']=float(np.percentile([r[arm]['hf_sigma']-r['source']['hf_sigma'] for r in pool],95)) if pool else None
        summary[kind+('_outside' if outside else '')]=obj
face={}
if case=='e05-1440':
    sy=source[120,:W*H].reshape(H,W)[600:1080,160:660].astype(float)/4
    ey=recons[216,:W*H].reshape(H,W)[600:1080,160:660].astype(float)/4
    sg=np.abs(np.diff(sy,axis=1));eg=np.abs(np.diff(ey,axis=1));mask=sg>12
    face={'baseline':old['face'][base],'candidate':{'mse':float(np.mean((sy-ey)**2)),
         'edge_gradient_mae':float(np.abs(eg[mask]-sg[mask]).mean()),'edge_gradient_ratio':float(eg[mask].sum()/sg[mask].sum())}}
x.dump(d/'controls.json',{'source_control_provenance':x.fingerprint(oldpath),'source':x.fingerprint(f/'source.yuv'),
    'baseline_encode_identity':x.fingerprint(baseline_receipt),'baseline_ivf':x.fingerprint(baseline_ivf),
    'outside_mask_scope':'Legacy manual-ROI mask retained for comparison; this preset arm has no selected ROI.',
    'source_descriptors_match_prior':True,'summary':summary,'face':face,'tiles':rows})
screen={}
for name,q in t['midpoint_summary'].items():
    hf=q['target']['hf_sigma']/q['source']['hf_sigma']-1;acf=abs(q['target']['acf1']-q['source']['acf1'])
    screen[name]={'hf_relative_error':hf,'acf1_abs_error':acf,'source_hf_correlation':q['paired_hf_correlation'],
                  'provisional_hf_acf_pass':abs(hf)<=.1 and acf<=.05}
receipt={'actual_mbps':rate,'source_mbps':v['source_mbps'],'relative_source_rate':ratio,
    'baseline_actual_mbps':br['rate_mbps'],'relative_baseline_rate':baseline_ratio,
    'practical_rate_eligible':True,'matched_comparison_eligible':matched,
    'comparison_kind':'matched-source comparison' if matched else 'under-cap practical screen; not a matched preset comparison',
    'sorted_scored_positions':[96,336],'selected_packets':packets,'output':x.fingerprint(enc),
    'all336_decoder_identity':True,'all240_scored_planes_match':True,'texture_screen':screen,
    'controls':summary,'face':face,'playback_observed':False,'script':x.fingerprint(__file__),
    'scope':'Known-fixture numeric screen, not perceptual repair acceptance.'}
x.dump(d/'assessment.json',receipt)
print(case,tag,json.dumps({'mbps':rate,'texture_screen':screen,'controls':summary,'face':face}),flush=True)
