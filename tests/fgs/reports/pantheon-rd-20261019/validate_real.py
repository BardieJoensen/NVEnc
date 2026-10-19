#!/usr/bin/env python3
"""Verify real final-EncDec retention and fixed source-defined whole-window controls."""
import json
import sys
import numpy as np
from analyze import ROOT, read_tu, paired, W, H, desc, x

case,tag=sys.argv[1:];d=ROOT/'parent/real'/case/tag
mapmeta=json.loads((d/'absolute-map.json').read_text());q=mapmeta['qindex']
rx,ry,rw,rh=mapmeta['aligned_roi_xywh']
def target(xx,yy):return rx<=xx<rx+rw and ry<=yy<ry+rh
tu_counts={'retained':0,'unselected_quantized':0,'selected_bypass':0,'other_bypass':0};by_frame={}
for path in sorted((d/'detail').glob('*.tu')):
    r=read_tu(path);m=r['meta'];selected=target(m['block_x'],m['block_y'])
    if selected:assert m['effective_qindex']==q
    ran='actual_forward' in r
    if ran:
        assert bool(r['retention_meta']['keep_fp'])==selected
        assert np.array_equal(r['input'].astype(int)-r['predictor'].astype(int),r['prediction_residual'])
        assert np.array_equal(r['private_forward'][:len(r['actual_forward'])],r['actual_forward'])
        assert np.array_equal(r['actual_recon'],r['final_recon'])
        if selected:
            assert np.array_equal(r['initial_qcoeff'],r['final_qcoeff'])
            assert np.array_equal(r['initial_dqcoeff'],r['final_dqcoeff'])
            assert int(r['initial_eob'][0])==int(r['final_eob'][0])
        tu_counts['retained' if selected else 'unselected_quantized']+=1
    else:tu_counts['selected_bypass' if selected else 'other_bypass']+=1
    if selected:
        f=by_frame.setdefault(str(m['poc']-96),{'selected_pixels':0,'quantizer_run_pixels':0})
        f['selected_pixels']+=m['w']*m['h'];f['quantizer_run_pixels']+=m['w']*m['h']*ran
source=np.memmap(ROOT/'fixtures'/case/'source.yuv',dtype='<u2',mode='r',shape=(240,W*H*3//2))
recon=np.memmap(d/'recon.yuv',dtype='<u2',mode='r',shape=(336,W*H*3//2))
prior=x.pathlib.Path('/media/merged-storage/cold-storage/docker-apps/pantheon-quantization-20261019')/case/'whole-window-controls.json'
old=json.loads(prior.read_text());base='detail' if case=='e04' else 'detail2';rows=[]
for oldrow in old['tiles']:
    n,xx,yy=oldrow['frame'],oldrow['x'],oldrow['y'];sl=np.s_[yy:yy+32,xx:xx+32]
    s=source[n,:W*H].reshape(H,W)[sl].astype(float)/4
    z=recon[n+96,:W*H].reshape(H,W)[sl].astype(float)/4
    sd=desc(s)
    assert all(oldrow['source'][k] is None and sd[k] is None or abs(oldrow['source'][k]-sd[k])<1e-10 for k in sd)
    rows.append({'frame':n,'x':xx,'y':yy,'kind':oldrow['kind'],
        'outside_target':not(xx<rx+rw and xx+32>rx and yy<ry+rh and yy+32>ry),
        'source':sd,'baseline':{**oldrow[base],'mse':oldrow['mse'][base]},'candidate':paired(s,z)})
summary={}
for kind in ['all','quiet','edge','flat_texture','other']:
    for outside in [False,True]:
        pool=[r for r in rows if (kind=='all' or r['kind']==kind) and (not outside or r['outside_target'])]
        obj={'tiles':len(pool)}
        for arm in ['baseline','candidate']:
            obj[arm]={metric:float(np.mean(values)) if values else None for metric,values in {
                'mse_mean':[r[arm]['mse'] for r in pool],
                'hf_abs_error':[abs(r[arm]['hf_sigma']-r['source']['hf_sigma']) for r in pool],
                'acf1_abs_error':[abs(r[arm]['acf1']-r['source']['acf1']) for r in pool if r[arm]['acf1'] is not None and r['source']['acf1'] is not None]}.items()}
        summary[kind+('_outside' if outside else '')]=obj
face={}
if case=='e05-1440':
    n=120;sl=np.s_[600:1080,160:660];s=source[n,:W*H].reshape(H,W)[sl].astype(float)/4;z=recon[n+96,:W*H].reshape(H,W)[sl].astype(float)/4
    sg=np.abs(np.diff(s,axis=1));zg=np.abs(np.diff(z,axis=1));edge=sg>12
    face={'baseline':old['face'][base],'candidate':{'mse':float(np.mean((z-s)**2)),
           'edge_gradient_mae':float(np.abs(zg[edge]-sg[edge]).mean()),'edge_gradient_ratio':float(zg[edge].sum()/sg[edge].sum())}}
x.dump(d/'controls.json',{'retention_TU_validation':tu_counts,'selected_frame_coverage':by_frame,
    'source_control_provenance':x.fingerprint(prior),'source_descriptors_match_prior':True,
    'summary':summary,'face':face,'tiles':rows})
print(case,tag,tu_counts,summary['all_outside'],face,flush=True)
