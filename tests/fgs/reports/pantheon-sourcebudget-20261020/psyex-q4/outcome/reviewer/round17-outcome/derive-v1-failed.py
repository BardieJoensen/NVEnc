#!/usr/bin/env python3
"""Independent R17 result reconstruction; no native calls or new metrics."""
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path

import numpy as np

ROOT = Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020')
P = ROOT / 'parent/psyex-q4-r17'
RUN = P / 'result-1'
OBS = ROOT / 'parent/psyex-tf0-r16-refine/r16-refine-tbr10042-observations'
RESULT_SHA = 'a04eb728936d62662afb4ab6dbc554db394c25f1ac433c563beff59278b3abdb'
RECEIPT_SHA = '4eb2aefae90ff65c2e985cafdfc14f878107c5f8df36d971aad9ad7d6c8728a6'
ARRAY_SHA = 'ee8c41ed2188efacd940ebf3a9fbb6dd5821e9bf2e6c56c75ff4e5d3e8a26b23'
MOSAIC_SHA = 'aba4ec13038906060b0ec59c1bee1ed342835e2a60caf472200a030b950af50c'
TOKENS_SHA = '899febd238c4baec09fdb389f1140266f4d2d6880db017b280e7fe89f10f85d0'
CONTROL_SHA = '62747b190b9facf89e96a626c54a1ee68c523dc7e68b2c5b2e2b3fb4bdbc6cac'
EXEC_SHA = '3efeacef74c8d95ca10816da6bea4c2567d207131a31a42e450afa26da263e93'
RUNNER_SHA = 'cb0e9a59adfde606ec489095ba71874bf476f5775e5d4223a6cb477fb44f19a6'
ADMISSION_SHA = 'a86db1bcc3e4ff49b8e0aa66dfc601ac8bc7b67bb4415b3886263df7daaf50ab'
PARSER_SHA = '45f11c246037e1a58a2762235a62db9a0bcb71e85fe992cfcc35897fa24983e3'
ANALYZE_SHA = '44b8037c2a922b7e893cd66c8488f3683c45b8859400ff6b082bd0910286f64e'
UNIT_SHA = 'd10bfb16859ad02f59ba876b7890f591fee592b690d4c65a6aa0f043a7ae3cb3'
BOUNDARY_SHA = '1027e9a0ec2a5f3b12a6aa908b97cad185df615fe48852a8acbe4daf5fb22ea3'
BOXES = {'shirt': (1200,650,200,100), 'background': (950,50,250,180), 'face': (160,600,500,480)}
H, W = 1080, 1920

def ident(path):
    p=Path(path).resolve()
    with p.open('rb') as f: h=hashlib.file_digest(f,'sha256').hexdigest()
    return {'path':str(p),'sha256':h,'size':p.stat().st_size}

def exact(path, sha):
    row=ident(path); assert row['sha256']==sha,(path,row['sha256'],sha); return Path(row['path'])

def exact_row(row):
    assert ident(row['path'])==row,row; return Path(row['path'])

def read(path): return json.loads(Path(path).read_text())

def load_module(path, name, sha):
    path=exact(path,sha)
    s=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def crop(a, box):
    x,y,w,h=box; return a[y:y+h,x:x+w]

def deep_close(a,b,path='root'):
    if isinstance(a,dict):
        assert isinstance(b,dict) and set(a)==set(b),(path,set(a)^set(b))
        for k in a: deep_close(a[k],b[k],path+'.'+str(k))
    elif isinstance(a,list):
        assert isinstance(b,list) and len(a)==len(b),(path,len(a),len(b))
        for i,(x,y) in enumerate(zip(a,b)): deep_close(x,y,f'{path}[{i}]')
    elif isinstance(a,float):
        if np.isnan(a): assert np.isnan(b),path
        else: assert abs(a-b) <= 1e-12*max(1.0,abs(a),abs(b)),(path,a,b)
    else: assert a==b,(path,a,b)

def masked_metrics(ref, raw, images, mask, metric):
    count=int(mask.sum())
    support=metric.minimum_filter(mask.astype(np.uint8),size=3,mode='constant')[1:-1,1:-1].astype(bool)
    base=metric.masked(ref,ref,mask)
    out={'pixels':count,'hf_pixels':int(support.sum()),
         'horizontal_pairs':int((support[:,:-1]&support[:,1:]).sum()),
         'vertical_pairs':int((support[:-1,:]&support[1:,:]).sum()),
         'original_masked':base,'stages':{}}
    for name,image in images.items():
        so=float(np.square(image[mask]-ref[mask]).sum())
        sr=float(np.square(image[mask]-raw[mask]).sum())
        d=metric.masked(ref,image,mask)
        for k in ('hf_sigma','acf1'):
            x,y=d.get(k),base.get(k); d[k+'_abs_error']=abs(x-y) if x is not None and y is not None else None
        out['stages'][name]={'sse_original':so,'sse_raw':sr,
          'mse_original':so/count if count else None,'mse_raw':sr/count if count else None,'masked':d}
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('output',type=Path); a=ap.parse_args()
    assert not a.output.exists()
    exact(__file__, hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    exact(P/'experiment.py',RUNNER_SHA); exact(P/'experiment-execution.json',EXEC_SHA)
    result=read(exact(RUN/'result.json',RESULT_SHA)); receipt=read(exact(RUN/'receipt.json',RECEIPT_SHA))
    arrays_path=exact(RUN/'native-arrays.npz',ARRAY_SHA); mosaics_path=exact(RUN/'mosaics.npz',MOSAIC_SHA)
    rows=read(exact(RUN/'tokens.json',TOKENS_SHA)); control=read(exact(RUN/'baseline-control.json',CONTROL_SHA))
    outer=read(P/'experiment-execution.json')
    assert outer['status']=='complete' and outer['returncode']==0
    assert receipt['status']=='complete' and receipt['result']==ident(RUN/'result.json')
    assert result['status']=='complete' and result['controls']==ident(RUN/'baseline-control.json')
    assert result['arrays']==ident(arrays_path) and result['mosaics']==ident(mosaics_path) and result['tokens']==ident(RUN/'tokens.json')
    assert receipt['inputs_before']==receipt['inputs_after']==result['inputs_before']==result['inputs_after']
    assert len(result['inputs_before'])==316
    for row in result['inputs_before'].values(): exact_row(row)
    assert control['status']=='exact' and control['baseline_c_runtime_capture_exact']==2169 and control['raw_c_runtime_capture_exact']==2169
    assert result['q4_c_runtime_exact']==2169

    ad=read(exact(OBS/'admitted/admission.json',ADMISSION_SHA)); target=210
    parser=load_module(ROOT/'parent/psyex-real-r15/parsers.py','r17_review_parser',PARSER_SHA)
    analyzer=load_module(ROOT/'parent/psyex-coeff-r11/analyze.py','r17_review_analyzer',ANALYZE_SHA)
    unit=load_module(ROOT/'worker/decoder-r10-analysis/analyze_decoder_units.py','r17_review_unit',UNIT_SHA)
    boundary=load_module(Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020/analyze_psyex_boundary.py'),'r17_review_boundary',BOUNDARY_SHA)
    tokens,terminal=parser.parse_coeff(exact_row(ad['trace']),target)
    assert terminal==ad['terminal'] and len(tokens)==2870
    rowmap={r['token']:r for r in rows}; assert len(rows)==len(rowmap)==2169
    invoked={k:t for k,t in tokens.items() if t['stages']}; assert set(invoked)==set(rowmap)
    aa=np.load(arrays_path); saved=np.load(mosaics_path)
    assert np.array_equal(aa['token_ids'],np.array(list(invoked),dtype='<u8'))

    dec=read(exact_row(ad['decoder_admission']))
    original=unit.load_luma(exact_row(ad['source_boundaries']['original']))
    coding=unit.load_luma(exact_row(ad['source_boundaries']['coding_input']))
    predictor_ref=unit.load_luma(exact_row(dec['artifacts']['predictor']))
    assert np.array_equal(original,coding)
    frames={k:np.full((H,W),np.nan) for k in ('original','raw','scalar','final','q4','predictor')}
    frames['original'][:]=original
    covered=np.zeros((H,W),bool); invmask=np.zeros((H,W),bool); txmap=np.full((H,W),-1,np.int16)
    q4_zero=0; q4_positive=0; q4_changed_eob=0
    for token,t in tokens.items():
        z=t['begin']; x,y,w,h=(z[k] for k in ('x','y','w','h')); vh=min(h,H-y); sl=np.s_[y:y+vh,x:x+w]
        assert not covered[sl].any(); covered[sl]=True; txmap[sl]=z['tx']
        pred=t['predictor'][:vh].astype(np.float64)/4
        frames['predictor'][sl]=pred
        frames['final'][sl]=t['reconstruction'][:vh].astype(np.float64)/4
        if token not in invoked:
            assert t.get('info') is None and not t['stages'] and t['end']['eob']==0
            assert np.array_equal(t['predictor'],t['reconstruction'])
            for name in ('raw','scalar','q4'): frames[name][sl]=pred
            continue
        invmask[sl]=True; r=rowmap[token]; co,po,n,pix=r['coefficient_offset'],r['pixel_offset'],r['n'],r['pixels']
        assert n==z['n']==min(w,32)*min(h,32) and pix==w*h
        assert r['actual_qindex']==t['info']['actual_qindex'] and r['q4_qindex']==4 and r['dc_delta']==0
        bq=aa['baseline_q'][co:co+n]; bdq=aa['baseline_dq'][co:co+n]; binv=aa['baseline_inverse'][po:po+pix].reshape(h,w)
        q4q=aa['q4_q'][co:co+n]; q4dq=aa['q4_dq'][co:co+n]; q4inv=aa['q4_inverse'][po:po+pix].reshape(h,w)
        rawinv=aa['raw_inverse'][po:po+pix].reshape(h,w)
        idx=list(invoked).index(token)
        assert np.array_equal(bq,t['stages'][0]['q']) and np.array_equal(bdq,t['stages'][0]['dq'])
        assert np.array_equal(binv,t['stages'][0]['inverse']) and int(aa['baseline_eob'][idx])==t['stages'][0]['eob']
        assert np.array_equal(rawinv,t['raw_inverse'])
        for q,e in ((bq,int(aa['baseline_eob'][idx])),(q4q,int(aa['q4_eob'][idx]))):
            nz=np.flatnonzero(q)
            expected=max((int(t['iscan'][i]) for i in nz),default=-1)+1
            assert e==expected and 0<=e<=n,(token,e,expected,n)
        qe=int(aa['q4_eob'][idx]); q4_zero += qe==0; q4_positive += qe>0
        q4_changed_eob += qe!=int(aa['baseline_eob'][idx])
        assert np.count_nonzero(q4q)==np.count_nonzero(q4dq)
        frames['raw'][sl]=rawinv[:vh].astype(np.float64)/4
        frames['scalar'][sl]=binv[:vh].astype(np.float64)/4
        frames['q4'][sl]=q4inv[:vh].astype(np.float64)/4
    assert covered.all() and np.array_equal(frames['predictor'],predictor_ref)
    for name in frames: assert np.array_equal(frames[name],saved[name]),name
    assert np.array_equal(covered,saved['covered']) and np.array_equal(invmask,saved['invoked']) and np.array_equal(txmap,saved['tx'])
    assert q4_zero==0 and q4_positive==2169 and q4_changed_eob==2154

    rebuilt={}
    for roi,box in BOXES.items():
        imgs={k:crop(v,box) for k,v in frames.items() if k in ('original','raw','scalar','final','q4')}
        ref,raw=imgs['original'],imgs['raw']; valid,inv,tx=crop(covered,box),crop(invmask,box),crop(txmap,box)
        whole={k:analyzer.descriptor(unit,boundary,ref,v) for k,v in imgs.items()}
        masks={'all':valid,'invoked':inv,'uninvoked':~inv}
        pops={k:masked_metrics(ref,raw,imgs,m,boundary.analyze_mod) for k,m in masks.items()}
        strata={}
        for pop in ('invoked','uninvoked'):
            strata[pop]={}
            for txid in sorted(np.unique(tx[masks[pop]]).tolist()):
                strata[pop][str(txid)]=masked_metrics(ref,raw,imgs,masks[pop]&(tx==txid),boundary.analyze_mod)
        rebuilt[roi]={'xywh':list(box),'whole':whole,'populations':pops,'transform_strata':strata}
        deep_close(rebuilt[roi],result['rois'][roi],roi)

    summary={'status':'verified','inputs':{
      'outer':ident(P/'experiment-execution.json'),'receipt':ident(RUN/'receipt.json'),'result':ident(RUN/'result.json'),
      'arrays':ident(arrays_path),'mosaics':ident(mosaics_path),'tokens':ident(RUN/'tokens.json'),'control':ident(RUN/'baseline-control.json')},
      'counts':result['counts'],'input_identity_count':len(result['inputs_before']),
      'controls':{'baseline_c_runtime_capture_exact':2169,'raw_c_runtime_capture_exact':2169,'q4_c_runtime_exact':2169,
                  'q4_positive_eob':q4_positive,'q4_zero_eob':q4_zero,'q4_changed_eob':q4_changed_eob,
                  'saved_mosaics_exact':True,'reported_metrics_exact':True,'all_inputs_live_and_unchanged':True},
      'rois':{}}
    for roi,v in rebuilt.items():
        src=v['whole']['original']; summary['rois'][roi]={'invoked_pixels':v['populations']['invoked']['pixels'],
          'uninvoked_pixels':v['populations']['uninvoked']['pixels'],'stages':{}}
        for s in ('raw','scalar','final','q4'):
            d=v['whole'][s]; summary['rois'][roi]['stages'][s]={
              'hf_sigma':d['hf_sigma'],'hf_ratio_source':d['hf_sigma']/src['hf_sigma'],
              'acf1':d['acf1'],'acf1_abs_error':d['acf1_abs_error'],
              'hf_corr_source':d['hf_corr_source'],'mse':d['mse']}
    a.output.write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')

if __name__=='__main__':
    if not __debug__: raise SystemExit('optimized Python prohibited')
    main()
