#!/usr/bin/env python3
"""Validate SVT stage identities, summarize ROI traces and final syntax maps."""
import sys,json,hashlib,pathlib
import numpy as np
import grain_model as g
from texture import desc,BOXES
x=g.x
def analyze(case,tag='b-trace'):
    assert tag=='b-trace', 'This validator is baseline-only; allocation has CSVs but no raw stage images.'
    d=x.ROOT/case;t=d/'trace';src=g.mm(d/'source.yuv')
    ct=d/'coeff-trace' if case=='e04' else t
    assert len(list(ct.glob('luma_txs-*.csv')))==240
    if not (d/(tag+'-decoder.yuv')).exists():
        x.run([x.ROOT/'apply_grain',d/(tag+'.ivf'),d/(tag+'-decoder.yuv'),0,96,240,'-'],d,tag+'-independent')
    dec=g.mm(d/(tag+'-decoder.yuv'));out={'case':case,'frames':[],'original_all240_exact':True,'final_all240_decoder_exact':True,'stages':{}}
    for n in range(240):
        row={'frame':n,'stages':{}}
        for stage in ('original','tf','coding_input','pre_sb_dlf','post_dlf','final'):
            paths=list(t.glob(f'{stage}-{n+96:04d}-*.yuv'))
            if not paths:continue
            assert len(paths)==1,paths
            a=np.memmap(paths[0],dtype='<u2',mode='r',shape=(1920*1080*3//2,));y=a[:1920*1080].reshape(1080,1920).astype(float)/4
            if stage=='original':out['original_all240_exact'] &= bool(np.array_equal(a,src[n]))
            if stage=='final':out['final_all240_decoder_exact'] &= bool(np.array_equal(a,dec[n]))
            row['stages'][stage]={name:desc(y[cy:cy+h,cx:cx+w]) for name,(cx,cy,w,h) in BOXES[case].items()}
        sb=list(t.glob(f'sb-{n+96:04d}-*.csv'));tx=list(ct.glob(f'luma_txs-{n+96:04d}-*.csv'))
        assert len(tx)==1
        if sb:
            a=np.atleast_2d(np.loadtxt(sb[0],delimiter=','));last={int(r[0]):r for r in a};a=np.array(list(last.values()))
            row['sb_qindex']={'all_mean':float(a[:,4].mean()),'frame_base':float(a[0,5]),'sb_count':len(a),'regions':{}}
            for name,(cx,cy,w,h) in BOXES[case].items():
                weights=np.maximum(0,np.minimum(a[:,1]+a[:,3],cx+w)-np.maximum(a[:,1],cx))*np.maximum(0,np.minimum(a[:,2]+a[:,3],cy+h)-np.maximum(a[:,2],cy))
                row['sb_qindex']['regions'][name]=float(np.average(a[:,4],weights=weights))
        if tx:
            a=np.atleast_2d(np.loadtxt(tx[0],delimiter=','));row['final_luma_coefficients']={}
            for name,(cx,cy,w,h) in {'all':(0,0,1920,1080),**BOXES[case]}.items():
                # Interior transforms only: their extents map directly into ROI.
                b=a[(a[:,0]>=cx)&(a[:,1]>=cy)&(a[:,0]+a[:,2]<=cx+w)&(a[:,1]+a[:,3]<=cy+h)]
                row['final_luma_coefficients'][name]={'transforms':len(b),'samples':float((b[:,2]*b[:,3]).sum()),'eob_sum':float(b[:,5].sum()),'nonzero_levels':float(b[:,6].sum()),'abs_quantized_level_sum':float(b[:,7].sum()),'note':'Final entropy-input coefficient counts/magnitudes, NOT bit counts; skips covered separately in blocks CSV.'}
        out['frames'].append(row)
    assert out['original_all240_exact'] and out['final_all240_decoder_exact'],out
    mids=(120,126,132,138,144) if case=='e04' else (116,118,120,122,124)
    for stage in ('original','tf','coding_input','pre_sb_dlf','post_dlf','final'):
        out['stages'][stage]={}
        for name in BOXES[case]:
            vals=[out['frames'][n]['stages'][stage][name] for n in mids if stage in out['frames'][n]['stages']]
            out['stages'][stage][name]={k:float(np.mean([v[k] for v in vals])) for k in ('hf_sigma','acf1')} if vals else None
    x.dump(d/'b-stages.json',out);print(case,out['stages'],flush=True)
if __name__=='__main__':analyze(sys.argv[1])
