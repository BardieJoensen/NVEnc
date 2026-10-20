#!/usr/bin/env python3
"""Score runtime-admitted PSYEX policy through unchanged GPU campaign/controls."""
if not __debug__: raise SystemExit("optimized Python is rejected")
import json
import os
from pathlib import Path
import sys
import numpy as np

HERE=Path(__file__).resolve().parent
REPORT=Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-rd-20261019')
ROOT=Path(os.environ.get('PANTHEON_SOURCEBUDGET_ROOT','/tmp/downloads/codex-work/pantheon-sourcebudget-20261020'))
os.environ['PANTHEON_RD_ROOT']=str(ROOT)
os.environ['PANTHEON_INDEPENDENT_DIR']=str(ROOT/'parent/scores')
sys.path.insert(0,str(REPORT))
from analyze import x, paired, desc, W, H

def verify_identities(obj):
    if isinstance(obj, dict):
        if {"path", "sha256", "size"} <= set(obj):
            path = Path(obj["path"])
            fp = x.fingerprint(path)
            assert fp["path"] == obj["path"], obj.get("path")
            assert fp["sha256"] == obj["sha256"], obj.get("path")
            assert path.stat().st_size == obj["size"], obj.get("path")
        for value in obj.values(): verify_identities(value)
    elif isinstance(obj, list):
        for value in obj: verify_identities(value)
from packet_window import measure
import texture

run_tag, admission_path, expected_run_sha, expected_admission_sha = sys.argv[1:]
assert '/' not in run_tag and run_tag not in ('', '.', '..')
case='e05-1440';tag=run_tag;tune='r16-tf0-original-budget'
d=ROOT/'worker/psyex-r16-calibration-refine/runs/e05-1440'/run_tag
f=ROOT/'fixtures'/case;s=ROOT/'parent/scores'/case
s.mkdir(parents=True,exist_ok=True)
for name in ('ref.mkv','source.yuv','validity.json'):
    dest=s/name
    if not dest.exists():os.link(f/name,dest)
    assert os.path.samefile(dest,f/name) and not dest.is_symlink()
assert not (d/'assessment.json').exists()
assert x.fingerprint(d/'command.json')['sha256']==expected_run_sha
run=json.loads((d/'command.json').read_text())
assert run['status']=='encoded' and run['returncode']==0 and run['tag']==run_tag
assert run['identity_before']==run['identity_after']
for p,h in run['identity_after'].items():assert x.fingerprint(p)['sha256']==h
for name,key in [('out.ivf','ivf_output'),('out.mkv','mkv_output'),('recon.yuv','recon')]:
    assert x.fingerprint(d/name)['sha256']==run[key]['sha256']
validation_path=Path(admission_path)
assert x.fingerprint(validation_path)['sha256']==expected_admission_sha
validation=json.loads(validation_path.read_text())
verify_identities(validation)
assert validation['status']=='admitted' and validation['case']==case and validation['tag']==run_tag
assert validation.get('script',{}).get('path') and validation['script']['sha256']=='fd190fae6a20aa3cd2efd06e6d6fc9c32471d602272a214b7168667aab511cbb' and x.fingerprint(validation['script']['path'])['sha256']==validation['script']['sha256']
assert validation['original_receipt']['sha256']==expected_run_sha
assert validation['unmodified_ivf']['sha256']==run['ivf_output']['sha256']
for key in ('actual_committed_owner','all336_exact','all_traced_roi_owners_source_predictor_preloop_exact','all_traced_positive_units_dq_iqm_exact_with_all_traced_eob_q_exact'):
    assert validation.get(key) is True, key
for key in ('decoder_admission','token_manifest','trace','boundary'):
    ident_row=validation[key]; assert x.fingerprint(ident_row['path'])['sha256']==ident_row['sha256'], key
for mode in ('off','on'):
    binding=validation['commands'][mode]
    assert x.fingerprint(binding['path'])['sha256']==binding['sha256']
    replay=json.loads(Path(binding['path']).read_text())
    assert replay['mode']==mode and replay['status']=='neutral'
    assert replay['original_receipt']['sha256']==expected_run_sha
    assert replay['out.ivf']['sha256']==run['ivf_output']['sha256']
    assert replay['recon.yuv']['sha256']==run['recon']['sha256']
v=json.loads((f/'validity.json').read_text());fps=v['fps'];enc=d/'out.mkv'
assert run['validity']['sha256']==x.fingerprint(f/'validity.json')['sha256']
assert run['input']['sha256']==x.fingerprint(f/'input10.y4m')['sha256']
rate,packets,start=measure(enc,fps);ratio=rate/v['source_mbps']
assert abs(start)<1e-6 and abs(rate-run['actual_mbps'])<1e-10
assert x.fingerprint(d/'packet-window.json')['sha256']==run['packet_window']['sha256']
packet=json.loads((d/'packet-window.json').read_text())
assert abs(packet['actual_mbps']-rate)<1e-10
assert run['within_source_ceiling'] == (rate <= v['source_mbps'])
assert run['matched_rate_comparable'] == (.99 <= ratio <= 1.0)
assert run['within_source_ceiling'] and run['matched_rate_comparable']

score_packets=d/'score-packet-window.json';assert not score_packets.exists()
x.dump(score_packets,{'actual_mbps':rate,'source_mbps':v['source_mbps'],
    'relative_source_rate':ratio,'relative_parent_rate':None,
    'selected_sorted_positions':[96,336],'selected_packets':packets,'first_pts':start,
    'output':x.fingerprint(enc),'run_receipt':x.fingerprint(d/'command.json'),
    'runtime_admission':x.fingerprint(validation_path)})
native_identity=validation['decoder_admission']
assert x.fingerprint(native_identity['path'])['sha256']==native_identity['sha256']
native=json.loads(Path(native_identity['path']).read_text())
assert native['status']=='admitted' and native['all336_allplanes_exact'] and native['complete_visible_luma_ownership']
verify_identities(native)
checker_identity=validation['artifacts']['all336_decoder_check']
assert x.fingerprint(checker_identity['path'])['sha256']==checker_identity['sha256']
decoder_path=Path(checker_identity['path'])
decoder=json.loads(decoder_path.read_text())
assert decoder['status']=='admitted' and decoder.get('all336_allplanes_app_dav1d_libaom_NVDEC_exact')
assert decoder['source_script']['sha256']=='f9bcdfca7e8782dda55e39770148c46a4d2ea7c2070c9c252040f166e4e3938a'
assert decoder['inputs']['command.json']['sha256']==expected_run_sha
assert decoder['inputs']['out.mkv']['sha256']==run['mkv_output']['sha256']
assert decoder['identity_before']==decoder['identity_after']
for key in ('script','source_script','shared_helper','probe'):
    assert x.fingerprint(decoder[key]['path'])['sha256']==decoder[key]['sha256']
for row in decoder['commands']:
    assert row['returncode']==0
    for key in ('log','output'):assert x.fingerprint(row[key]['path'])['sha256']==row[key]['sha256']
recon=d/'recon.yuv';hashes=decoder['hashes'];assert len(hashes)==336
assert x.fingerprint(recon)['sha256']==decoder['recon']['sha256']==run['recon']['sha256']
run['encoder_stack']='SVT-AV1-PSYEX-master59d1a025-private'
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
    'practical_rate_eligible':0<ratio<=1,'matched_comparison_eligible':.99 <= ratio <= 1.0,
    'comparison_kind':'TF-off PSYEX policy at the original packet budget; bundled source/reference/search contrast',
    'sorted_scored_positions':[96,336],'selected_packets':packets,'output':x.fingerprint(enc),
    'decoder_set':['libdav1d','libaom-av1','av1_cuvid'],'all336_decoder_identity':True,'all240_scored_planes_match':True,'texture_screen':screen,
    'controls':summary,'face':face,'playback_observed':False,'script':x.fingerprint(__file__),
    'probe_tool':x.fingerprint(x.shutil.which('ffprobe')),
    'runtime_admission':x.fingerprint(validation_path),'relative_parent_rate':None,
    'packet_receipt':x.fingerprint(score_packets), 'decoder_validation':x.fingerprint(decoder_path),
    'two_pass_wall_seconds':run['wall_seconds'],
    'scope':'Decoder and numerical quality measurements at the original packet budget; playback unobserved; no repair acceptance.'}
x.dump(d/'assessment.json',receipt)
print(case,tag,json.dumps({'mbps':rate,'texture_screen':screen,'controls':summary,'face':face}),flush=True)
