#!/usr/bin/env python3
import hashlib, importlib.util, json, math
from pathlib import Path
import numpy as np

ROOT=Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020')
P=ROOT/'parent/psyex-scalar-r12/run-1'
R11=ROOT/'parent/psyex-coeff-r11'
V=R11/'validate.py'; VSHA='258db37595666efa153d6fc526d42de371fe0a7f0b21bff7c3334e84238378f3'
BOXES={'shirt':(1200,650,200,100),'background':(950,50,250,180),'face':(160,600,500,480)}
ARMS=('fp_baseline','b_same_q','fp_q32')

def sha(p):
    with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def hp(a):
    b=(a[:-2,1:-1]+a[2:,1:-1]+a[1:-1,:-2]+a[1:-1,2:]+4*a[1:-1,1:-1])/8
    return a[1:-1,1:-1]-b
def acf(r,lag=1):
    q=r-r.mean();v=np.mean(q*q)
    return float((np.mean(q[:,:-lag]*q[:,lag:])+np.mean(q[:-lag]*q[lag:]))/(2*v)) if v>1e-18 else None
def corr(a,b):
    a=a-a.mean();b=b-b.mean(); den=math.sqrt(float(np.mean(a*a)*np.mean(b*b)))
    return float(np.mean(a*b)/den) if den>1e-18 else None
def desc(src,z):
    hs,hz=hp(src),hp(z); ss=float(hs.std()*math.sqrt(8/5)); sz=float(hz.std()*math.sqrt(8/5))
    return {'hf_sigma':sz,'hf_ratio_source':sz/ss,'acf1':acf(hz),'acf1_abs_error':abs(acf(hz)-acf(hs)),
            'hf_corr_source':corr(hs,hz),'mse':float(np.mean((z-src)**2))}
def crop(a,b):x,y,w,h=b;return a[y:y+h,x:x+w]

def main():
    result=json.load(open(P/'result.json')); receipt=json.load(open(P/'receipt.json'))
    assert result['status']=='admitted_diagnostic' and receipt['status']=='complete'
    assert result['all_arms_C_runtime_exact'] is True and result['controls']['invoked']==2187
    assert result['controls']['unchanged_owners']==720
    assert sha(P/'result.json')==receipt['result']['sha256']=='9caf06214e249306788a6e58a22d134ed86284b4183fb38f815d8ccf236029d9'
    assert sha(V)==VSHA
    sp=importlib.util.spec_from_file_location('r11v',V);v=importlib.util.module_from_spec(sp);sp.loader.exec_module(v)
    admission=json.load(open(R11/'admitted-1/admission.json'))
    tokens,terminal=v.parse(Path(admission['trace']['path']))
    assert terminal==admission['terminal'] and len(tokens)==2907
    arrays=np.load(P/'native-arrays.npz'); rows=result['units']; assert len(rows)==2907
    assert {r['token'] for r in rows}==set(tokens)
    original=np.fromfile(result['original']['path'],dtype='<u2',count=1920*1080).reshape(1080,1920).astype('f8')/4
    coding=np.fromfile(result['coding_input']['path'],dtype='<u2',count=1920*1080).reshape(1080,1920).astype('f8')/4
    frames={a:np.full((1080,1920),np.nan) for a in ARMS}
    covered=np.zeros((1080,1920),bool)
    counts={a:{'q_nonzero':0,'q_l1':0,'dq_l1':0,'positive_units':0,'zero_units':0,
               'changed_units_from_fp':0,'changed_pixels_from_fp':0} for a in ARMS}
    total_coeff=total_pixels=0
    row_by_token={r['token']:r for r in rows}
    for token,t in tokens.items():
        r=row_by_token[token];z=t['begin'];x,y,w,h=(z[k] for k in ('x','y','w','h'));vh=min(h,1080-y)
        sl=np.s_[y:y+vh,x:x+w];assert not covered[sl].any();covered[sl]=True
        if r['invoked']:
            co,po=r['coefficient_offset'],r['pixel_offset'];n=z['n'];pix=w*h
            baseq=arrays['fp_baseline_q'][co:co+n];baseim=arrays['fp_baseline_inverse'][po:po+pix].reshape(h,w)
            total_coeff+=n;total_pixels+=pix
            for a in ARMS:
                q=arrays[a+'_q'][co:co+n];dq=arrays[a+'_dq'][co:co+n];im=arrays[a+'_inverse'][po:po+pix].reshape(h,w)
                assert r['arms'][a]['eob']==(int(np.flatnonzero(q[t['scan']])[-1])+1 if np.any(q) else 0)
                counts[a]['q_nonzero']+=int(np.count_nonzero(q));counts[a]['q_l1']+=int(np.abs(q.astype('i8')).sum())
                counts[a]['dq_l1']+=int(np.abs(dq.astype('i8')).sum())
                counts[a]['positive_units']+=int(r['arms'][a]['eob']>0);counts[a]['zero_units']+=int(r['arms'][a]['eob']==0)
                counts[a]['changed_units_from_fp']+=int(not np.array_equal(im,baseim))
                counts[a]['changed_pixels_from_fp']+=int(np.count_nonzero(im!=baseim))
                frames[a][sl]=im[:vh].astype('f8')/4
        else:
            for a in ARMS:frames[a][sl]=t['predictor'][:vh].astype('f8')/4
    assert total_coeff==sum(a.size for a in [arrays['fp_baseline_q']])
    assert total_pixels==arrays['fp_baseline_inverse'].size
    assert all(np.isfinite(f[covered]).all() for f in frames.values())
    roi={}
    for name,box in BOXES.items():
        src=crop(original,box);ci=crop(coding,box)
        roi[name]={'original_hf':desc(src,src)['hf_sigma'],'coding_input':desc(src,ci),'arms':{},'raw':result['fixed_roi'][name]['stages']['raw_executed']}
        for a in ARMS:
            d=desc(src,crop(frames[a],box)); parent=result['fixed_roi'][name]['stages'][a]
            for k in ('hf_sigma','acf1','acf1_abs_error','hf_corr_source','mse'):
                assert abs(d[k]-parent[k])<1e-12,(name,a,k,d[k],parent[k])
            d['changed_pixels_vs_fp']=int(np.count_nonzero(crop(frames[a],box)!=crop(frames['fp_baseline'],box)))
            d['hf_ratio_raw']=d['hf_sigma']/roi[name]['raw']['hf_sigma']
            roi[name]['arms'][a]=d
    # Per-ROI unit/coefficient changes from the preserved offsets.
    roi_changes={}
    for name in BOXES:
        selected=[r for r in rows if name in r['intersections']]
        invoked=[r for r in selected if r['invoked']]
        rr={'owners':len(selected),'invoked':len(invoked),'not_invoked':len(selected)-len(invoked),'arms':{}}
        for a in ARMS:
            changed_q=changed_dq=changed_eob=0
            for r in invoked:
                z=r['begin'];co=r['coefficient_offset'];n=z['n']
                changed_q+=int(not np.array_equal(arrays[a+'_q'][co:co+n],arrays['fp_baseline_q'][co:co+n]))
                changed_dq+=int(not np.array_equal(arrays[a+'_dq'][co:co+n],arrays['fp_baseline_dq'][co:co+n]))
                changed_eob+=int(r['arms'][a]['eob']!=r['arms']['fp_baseline']['eob'])
            rr['arms'][a]={'q_changed_units':changed_q,'dq_changed_units':changed_dq,'eob_changed_units':changed_eob,
                           'changed_pixels_vs_fp':roi[name]['arms'][a]['changed_pixels_vs_fp']}
        roi_changes[name]=rr
    out={'status':'complete','inputs':{'result_sha256':sha(P/'result.json'),'arrays_sha256':sha(P/'native-arrays.npz'),
         'trace_sha256':sha(admission['trace']['path']),'validator_sha256':sha(V)},
         'controls':{'all_arms_C_runtime_exact':result['all_arms_C_runtime_exact'],'invoked':2187,'unchanged':720,
                     'actual_qindex':result['controls']['actual_qindex'],'q32_tables':result['generated_fp_tables']['32']},
         'total_coefficients':total_coeff,'total_invoked_pixels':total_pixels,'arm_counts':counts,'roi':roi,'roi_changes':roi_changes,
         'limits':['single frame120 local mosaics','no feedback, packet rate, full-window/quiet, repair or playback inference']}
    op=Path(__file__).with_name('derived.json');op.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'status':'complete','output':str(op),'sha256':sha(op)}))
if __name__=='__main__':main()
