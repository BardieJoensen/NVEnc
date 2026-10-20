#!/usr/bin/env python3
"""Score delivered R7 precision as an unconstrained diagnostic via GPU campaign."""
import hashlib
import json
import os
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

installed_tag, admission_name = sys.argv[1:]
case='e05-1440';tag='aom-'+installed_tag;tune='psnr'
d=ROOT/'worker/aom-qmax-r7/runs'/case/installed_tag
f=ROOT/'fixtures'/case;s=ROOT/'parent/scores'/case
s.mkdir(parents=True,exist_ok=True)
for name in ('ref.mkv','source.yuv','validity.json'):
    dest=s/name
    if not dest.exists():os.link(f/name,dest)
    assert os.path.samefile(dest,f/name) and not dest.is_symlink()
validation_path=ROOT/'parent/qmax-observation'/admission_name/'validation.json'
validation=json.loads(validation_path.read_text())
assert validation['status']=='admitted' and validation['precision_delivery_pass']
assert validation['all_visible_pixels_covered_once']
for record in validation['artifacts'].values():
    assert x.fingerprint(record['path'])['sha256']==record['sha256']
assert validation['script']['sha256']==x.fingerprint(HERE/'validate_aom_qmax_tu.py')['sha256']
run=json.loads((d/'command.json').read_text())
assert run['status']=='diagnostic_encoded' and run['tag']==installed_tag and run['returncode']==0
trace_run=json.loads(Path(validation['artifacts']['run']['path']).read_text())
assert trace_run['source_command']['sha256']==x.fingerprint(d/'command.json')['sha256']
assert trace_run['source_command']['path']==str((d/'command.json').resolve())
assert trace_run['exact_installed_ivf']
assert x.fingerprint(d/'out.ivf')['sha256']==trace_run['output']['sha256']==run['ivf_sha256']
installed_path=ROOT/'worker/runs/e05-1440/aom-psnr-1x2/command.json'
installed=json.loads(installed_path.read_text())
assert run['bound_r3_receipt']['sha256']==x.fingerprint(installed_path)['sha256']
assert run['ivf_sha256']!=installed['ivf_sha256'], 'No changed stream: close mechanism without repeating metrics.'
v=json.loads((f/'validity.json').read_text());fps=v['fps'];enc=d/'out.mkv'
assert x.fingerprint(f/'validity.json')['sha256']==installed['validity']['sha256']
assert fps==installed['validity']['fps'] and v['source_mbps']==installed['validity']['source_mbps']
assert x.fingerprint(f/'input10.y4m')['sha256']==run['input']['sha256']==run['input_after_sha256']
assert x.fingerprint('/usr/bin/ffmpeg')['sha256']==run['ffmpeg']['sha256']
assert run['identity_start']==run['identity_final']==run['expected_identity']
assert x.fingerprint(enc)['sha256']==run['mkv_sha256']
assert not (d/'assessment.json').exists(), 'Fresh scoring must not overwrite assessment.'
rate,packets,start=measure(enc,fps);ratio=rate/v['source_mbps'];matched=.99<=ratio<=1
parent_ratio=rate/installed['actual_mbps']
assert abs(rate-run['actual_mbps'])<1e-10 and abs(start)<1e-6
assert json.loads((d/'packet-window.json').read_text())==run['packet_window']
score_packets=d/'score-packet-window.json'
assert not score_packets.exists()
x.dump(score_packets,{'output':x.fingerprint(enc),'actual_mbps':rate,'source_mbps':v['source_mbps'],
    'relative_source_rate':ratio,'relative_parent_rate':parent_ratio,'source_matched':matched,
    'pairwise_within_1pct':abs(parent_ratio-1)<=.01,'selected_sorted_positions':[96,336],
    'selected_packets':packets,'first_pts':start,'fps':fps,'admission':x.fingerprint(validation_path),
    'parent_receipt':x.fingerprint(installed_path),'validity':x.fingerprint(f/'validity.json'),
    'input_ivf':x.fingerprint(d/'out.ivf'),'ffmpeg':x.fingerprint('/usr/bin/ffmpeg'),
    'encode_remux_receipt':run['remux'],
    'scope':'Actual uncapped diagnostic packet cost; eligibility is not repair acceptance.'})
# Metadata for shared assessment fields; no historical command receipt is changed.
run['encoder_stack']='libaom-3.8.2-public-qmax8'
stream=x.probe(enc)['streams'][0]
assert stream['codec_name']=='av1' and stream['pix_fmt']=='yuv420p10le'
assert (stream['width'],stream['height'])==(W,H)
assert [stream[k] for k in ('color_range','color_space','color_transfer','color_primaries')]==['tv','bt709','bt709','bt709']
decoder_path=d/'decoder-validation/decoder-validation.json'
decoder=json.loads(decoder_path.read_text())
binding=json.loads(Path(validation['artifacts']['binding']['path']).read_text())
assert binding['inputs']['decoder_validation']['sha256']==x.fingerprint(decoder_path)['sha256']
assert decoder['status']=='admitted' and decoder['all336_allplanes_libaom_dav1d_NVDEC_exact']
assert decoder['run_receipt']['sha256']==x.fingerprint(d/'command.json')['sha256']
assert decoder['output']['sha256']==x.fingerprint(enc)['sha256']
hashes=decoder['hashes'];assert len(hashes)==336
recon=Path(decoder['decoded_raw']['path'])
assert x.fingerprint(recon)['sha256']==decoder['decoded_raw']['sha256']
assert recon.stat().st_size==336*W*H*3
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
    'outside_mask_scope':'Legacy manual-ROI mask retained for comparison; this implementation-policy arm has no selected ROI.',
    'source_descriptors_match_prior':True,'summary':summary,'face':face,'tiles':rows})
screen={}
for name,q in t['midpoint_summary'].items():
    hf=q['target']['hf_sigma']/q['source']['hf_sigma']-1;acf=abs(q['target']['acf1']-q['source']['acf1'])
    screen[name]={'hf_relative_error':hf,'acf1_abs_error':acf,'source_hf_correlation':q['paired_hf_correlation'],
                  'provisional_hf_acf_pass':abs(hf)<=.1 and acf<=.05}
receipt={'encoder_stack':run['encoder_stack'],'tune_policy':tune,'actual_mbps':rate,'source_mbps':v['source_mbps'],'relative_source_rate':ratio,
    'baseline_actual_mbps':br['rate_mbps'],'relative_baseline_rate':baseline_ratio,
    'practical_rate_eligible':0<ratio<=1,'matched_comparison_eligible':matched,
    'comparison_kind':'unconstrained actual-precision diagnostic; not a matched-rate causal contrast',
    'sorted_scored_positions':[96,336],'selected_packets':packets,'output':x.fingerprint(enc),
    'decoder_set':['libdav1d','libaom-av1','av1_cuvid'],'all336_decoder_identity':True,'all240_scored_planes_match':True,'texture_screen':screen,
    'controls':summary,'face':face,'playback_observed':False,'script':x.fingerprint(__file__),
    'probe_tool':x.fingerprint(x.shutil.which('ffprobe')),
    'precision_admission':x.fingerprint(validation_path),'relative_parent_rate':parent_ratio,
    'packet_receipt':x.fingerprint(score_packets), 'decoder_validation':x.fingerprint(decoder_path),
    'two_pass_wall_seconds':run['wall_seconds'],
    'scope':'Known-fixture numeric diagnostic with measured two-pass cost; not perceptual repair acceptance or full-episode speed.'}
x.dump(d/'assessment.json',receipt)
print(case,tag,json.dumps({'mbps':rate,'texture_screen':screen,'controls':summary,'face':face}),flush=True)
