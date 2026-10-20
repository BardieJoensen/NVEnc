#!/usr/bin/env python3
"""R13 qindex-1 fixed-decision diagnostic; no encode or bitrate claim."""
import argparse,datetime as dt,hashlib,importlib.util,json,sys,time
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
R11=ROOT/'parent/psyex-coeff-r11'; R12=ROOT/'parent/psyex-scalar-r12'
R12_EXPERIMENT_SHA='87eb15f8a7c082bb875f91edb790ed66a8e592db9d64bc5f554943040f705ee2'
R12_RESULT_SHA='9caf06214e249306788a6e58a22d134ed86284b4183fb38f815d8ccf236029d9'
R12_ARRAYS_SHA='aaee0f9c89623023e5c0d541c38241092950e99e3f48e46de4544bc5caf9799c'
BUILD_SHA='4b56e9cbd1450f68ec42d02a70d6db2e082db065c6314f34ef17443ef6cb7df5'
LIB_SHA='07fe2554623523d8e6dfe5218d94a89cdb2437bb2221123a86678090af6f2228'
R11_ANALYZE_SHA='44b8037c2a922b7e893cd66c8488f3683c45b8859400ff6b082bd0910286f64e'
CONTRACT='/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020/ROUND13_FINE_CONTRACT.md'
CONTRACT_SHA='4dcd8abfffdc31455f8e020a518b1444bafccfe44b4084b97f78ef4b71dfd302'
BOXES={'shirt':(1200,650,200,100),'background':(950,50,250,180),'face':(160,600,500,480)}

def ident(p):
 p=Path(p).resolve()
 with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
 return {'path':str(p),'sha256':h,'size':p.stat().st_size}
def exact(d):
 assert ident(d['path'])==d,d
 return Path(d['path'])
def mod(p,name,sha):
 assert ident(p)['sha256']==sha,(p,ident(p),sha)
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def distance(a,b,mask):
 d=(a[mask].astype(np.float64)-b[mask].astype(np.float64)); ad=np.abs(d)
 pixels=int(mask.sum());exact_n=int(np.count_nonzero(d==0));changed=int(np.count_nonzero(d!=0))
 return {'pixels':pixels,'exact':exact_n,'exact_fraction':(exact_n/pixels if pixels else None),'changed':changed,'changed_fraction':(changed/pixels if pixels else None),
         'max_abs':float(ad.max()) if ad.size else None,'mae':float(ad.mean()) if ad.size else None,
         'mse':float(np.mean(d*d)) if d.size else None}
def coeff_delta(a,b):
 d=a.astype(np.int64)-b.astype(np.int64);ad=np.abs(d)
 return {'count':int(d.size),'changed':int(np.count_nonzero(d)),'max_abs':int(ad.max()) if ad.size else 0,
         'l1':int(ad.sum())}
def close_json(a,b,tol=1e-12):
 if isinstance(a,dict) and isinstance(b,dict):
  assert a.keys()==b.keys(),(a.keys(),b.keys())
  for k in a:close_json(a[k],b[k],tol)
 elif isinstance(a,list) and isinstance(b,list):
  assert len(a)==len(b)
  for x,y in zip(a,b):close_json(x,y,tol)
 elif isinstance(a,(int,float)) and isinstance(b,(int,float)):
  assert abs(float(a)-float(b))<=tol,(a,b)
 else: assert a==b,(a,b)
def intersection_mask(z,box):
 x,y,w,h=z['x'],z['y'],z['w'],z['h'];X,Y,W,H=box
 mask=np.zeros((h,w),bool);ix=max(x,X);iy=max(y,Y);ex=min(x+w,X+W);ey=min(y+h,Y+H)
 if ex>ix and ey>iy:mask[iy-y:ey-y,ix-x:ex-x]=True
 return mask

def main():
 ap=argparse.ArgumentParser();ap.add_argument('out',type=Path);args=ap.parse_args();out=args.out
 assert not out.exists();out.mkdir(parents=True)
 rec={'status':'prepared','argv':sys.argv,'python':ident(sys.executable),'started_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
 rp=out/'receipt.json';rp.write_text(json.dumps(rec,indent=2)+'\n');start=time.monotonic()
 try:
  r12=mod(R12/'experiment.py','r12_native',R12_EXPERIMENT_SHA)
  a=mod(R11/'analyze.py','r11_metrics',R11_ANALYZE_SHA)
  adp=R11/'admitted-1/admission.json';ad=json.loads(adp.read_text());assert ad['status']=='admitted'
  for k in ('all336_exact','source_predictor_preloop_exact','final_dq_eob_iqm_exact','actual_committed_owner'):assert ad[k] is True
  for k in ('pins','trace','boundary','decoder_admission','targets','token_manifest','script'):exact(ad[k])
  bp=R12/'build-2/receipt.json';assert ident(bp)['sha256']==BUILD_SHA
  build=json.loads(bp.read_text());assert build['status']=='complete'
  lib=exact(build['library']);assert ident(lib)['sha256']==LIB_SHA
  r12result=R12/'run-1/result.json';assert ident(r12result)['sha256']==R12_RESULT_SHA
  prior_result=json.loads(r12result.read_text());assert prior_result['status']=='admitted_diagnostic'
  assert prior_result['r11_admission']==ident(adp)
  r12arrays=R12/'run-1/native-arrays.npz';assert ident(r12arrays)['sha256']==R12_ARRAYS_SHA
  prior_npz=np.load(r12arrays,allow_pickle=False);prior={k:prior_npz[k] for k in prior_npz.files};prior_npz.close()
  contract=Path(CONTRACT);assert ident(contract)['sha256']==CONTRACT_SHA
  r9path=a.R/'parent/psyex-boundary-r9/analysis-1.json';assert ident(r9path)['sha256']=='b2d4a19ac93eeab29cb78870cea45f03165f7741f22584955081498553ed5bc5'
  u=a.mod(a.U,'r10_helpers',a.USHA);h=u.helper()
  inherited=json.loads(r9path.read_text())['metric_helpers'];[exact(d) for d in inherited.values()]
  tokens,terminal=mod(R11/'validate.py','r11_validator',a.VSHA).parse(exact(ad['trace']));assert terminal==ad['terminal'] and len(tokens)==2907
  joins=json.loads(exact(ad['token_manifest']).read_text());jmap={r['token']:r for r in joins};assert set(tokens)==set(jmap)
  dec=json.loads(exact(ad['decoder_admission']).read_text())
  refs={s:u.load_luma(exact(dec['r9_stages'][s])) for s in ('original','coding_input','postloop')}
  units=json.loads(exact(dec['artifacts']['units']).read_text())
  dependency=[Path(__file__),R11/'analyze.py',R12/'experiment.py',R12/'run-1/result.json',r12arrays,bp,lib,adp,a.V,a.U,u.HELPER,exact(ad['trace']),exact(ad['token_manifest']),exact(ad['decoder_admission']),r9path,contract]
  dependency += [exact(d) for d in inherited.values()]+[exact(dec['r9_stages'][s]) for s in refs]
  before=[ident(p) for p in dependency];rec['inputs_before']=before;rp.write_text(json.dumps(rec,indent=2)+'\n')
  native=r12.Native(lib);rec['runtime_cpu_flags']=native.flags;q1rows=native.tables(1);assert q1rows.shape==(3,8)
  assert dec['r9_stages']['original']==prior_result['original'] and dec['r9_stages']['coding_input']==prior_result['coding_input']
  assert BOXES==a.BOXES
  invoked={k:t for k,t in tokens.items() if t['stages']};assert len(invoked)==2187 and len(tokens)-len(invoked)==720
  rows_by_token={r['token']:r for r in prior_result['units']};assert set(rows_by_token)==set(tokens)
  # Prior arrays are the reference; only q1 invokes Native.paired anew.
  base_inv={};q32_inv={};base_q={};base_dq={};q32_q={};q32_dq={};expected_co=expected_po=0
  q1_inv={};q1_q={};q1_dq={};q1_eob={};q1_tables={}
  for key,t in invoked.items():
   row=rows_by_token[key];z=t['begin'];n=z['n'];co=row['coefficient_offset'];po=row['pixel_offset'];pix=z['w']*z['h']
   assert row['begin']==z and co==expected_co and po==expected_po
   assert t['raw'].shape==(n,) and t['predictor'].shape==(z['h'],z['w']) and t['raw_inverse'].shape==(z['h'],z['w'])
   base_q[key]=prior['fp_baseline_q'][co:co+n].copy();base_dq[key]=prior['fp_baseline_dq'][co:co+n].copy();base_inv[key]=prior['fp_baseline_inverse'][po:po+pix].reshape(z['h'],z['w']).copy()
   q32_q[key]=prior['fp_q32_q'][co:co+n].copy();q32_dq[key]=prior['fp_q32_dq'][co:co+n].copy();q32_inv[key]=prior['fp_q32_inverse'][po:po+pix].reshape(z['h'],z['w']).copy()
   assert row['invoked'] and row['actual_qindex']==t['info']['actual_qindex']>1 and t['info']['depth']==10 and t['info']['seg_delta']==0
   capture=t['stages'][0];assert capture['stage']=='scalar_fp' and row['arms']['fp_baseline']['eob']==capture['eob']
   for field,value in [('q',base_q[key]),('dq',base_dq[key]),('inverse',base_inv[key])]:assert np.array_equal(value,capture[field]),(key,field)
   table=t['tables'].copy();table[[0,1,6]]=q1rows;assert np.array_equal(table[[2,3,4,5]],t['tables'][[2,3,4,5]])
   q1=native.paired(t,0,table);q1_q[key]=q1['q'];q1_dq[key]=q1['dq'];q1_inv[key]=q1['inverse'];q1_eob[key]=q1['eob'];q1_tables[key]=table.tolist()
   expected_co+=n;expected_po+=pix
  # Exact prior baseline/q32 array identity is checked without recomputation.
  assert np.array_equal(np.concatenate([base_q[k] for k in invoked]),prior['fp_baseline_q'])
  assert np.array_equal(np.concatenate([q32_q[k] for k in invoked]),prior['fp_q32_q'])
  assert expected_co==prior['fp_baseline_q'].size==prior['fp_q32_q'].size
  assert expected_po==prior['fp_baseline_inverse'].size==prior['fp_q32_inverse'].size
  # Assemble fixed-support mosaics and masks; uninvoked owners remain predictors.
  shape=(1080,1920); arms={'fp_baseline':base_inv,'fp_q32':q32_inv,'fp_q1':q1_inv}; raw=np.full(shape,np.nan);original=refs['original'];coding_input=refs['coding_input']
  mosaics={name:np.full(shape,np.nan) for name in arms};inv_mask=np.zeros(shape,bool);covered=np.zeros(shape,bool)
  for key,t in tokens.items():
   z=t['begin'];x,y,w,hh=(z[k] for k in ('x','y','w','h'));vh=min(hh,1080-y);sl=np.s_[y:y+vh,x:x+w];pred=t['predictor'][:vh].astype(float)/4
   assert not covered[sl].any();covered[sl]=True
   raw[sl]=t.get('raw_inverse',t['predictor'])[:vh].astype(float)/4
   if key in invoked:
    inv_mask[sl]=True
    for name,d in arms.items():mosaics[name][sl]=d[key][:vh].astype(float)/4
   else:
    for name in arms:mosaics[name][sl]=pred
  assert np.isfinite(raw[inv_mask]).all() and inv_mask.sum()>0
  assert int(inv_mask.sum())==sum(t['begin']['w']*min(t['begin']['h'],1080-t['begin']['y']) for t in invoked.values())
  for box in BOXES.values():assert a.crop(covered,box).all()
  for m in [raw,*mosaics.values()]:assert np.isfinite(m[covered]).all()
  # Existing R12 baseline/q32 fixed-ROI descriptors must match before q1 metrics.
  for roi,box in BOXES.items():
   ref=a.crop(original,box)
   check_maps=dict(mosaics);check_maps.update(original=original,coding_input=coding_input,raw_executed=raw)
   for name in ('fp_baseline','fp_q32','original','coding_input','raw_executed'):
    close_json(a.descriptor(u,h,ref,a.crop(check_maps[name],box)),prior_result['fixed_roi'][roi]['stages'][name])
  metrics={}
  for name,m in mosaics.items():
   metrics[name]={'raw':distance(m,raw,inv_mask),'coding_input':distance(m,coding_input,inv_mask)}
   metrics[name]['rois']={roi:{'raw':distance(m,raw,inv_mask & roi_mask(shape,box)), 'coding_input':distance(m,coding_input,inv_mask & roi_mask(shape,box))} for roi,box in BOXES.items()}
   metrics[name]['full_roi_secondary']={roi:{'raw':distance(m,raw,roi_mask(shape,box)), 'coding_input':distance(m,coding_input,roi_mask(shape,box))} for roi,box in BOXES.items()}
  # Per-token coefficient deltas and support, plus fixed ROI original-reference descriptors.
  arrays={'q1_q':np.concatenate([q1_q[k] for k in invoked]),'q1_dq':np.concatenate([q1_dq[k] for k in invoked]),'q1_inverse':np.concatenate([q1_inv[k].ravel() for k in invoked])}
  np.savez_compressed(out/'q1-arrays.npz',**arrays)
  fullroi={}
  for roi,box in BOXES.items():
   ref=a.crop(original,box);stage_maps=dict(mosaics);stage_maps.update({'raw_inverse':raw,'coding_input':coding_input})
   fullroi[roi]={'xywh':list(box),'stages':{name:a.descriptor(u,h,ref,a.crop(m,box)) for name,m in stage_maps.items()}}
  per=[]
  for key,t in tokens.items():
   z=t['begin'];row={'token':key,'unit':rows_by_token[key]['unit'],'invoked':key in invoked,'xywh':[z[k] for k in ('x','y','w','h')]}
   if key in invoked:
    row.update(coefficient_offset=rows_by_token[key]['coefficient_offset'],pixel_offset=rows_by_token[key]['pixel_offset'],actual_qindex=t['info']['actual_qindex'],eob=q1_eob[key],raw_eob=t['raw_eob'],q1_tables=q1_tables[key],
      distance_raw={name:distance(arms[name][key].astype(float)/4,t['raw_inverse'].astype(float)/4,np.ones(arms[name][key].shape,bool)) for name in arms},
      intersection_distance_raw={roi:distance(q1_inv[key].astype(float)/4,t['raw_inverse'].astype(float)/4,intersection_mask(z,box)) for roi,box in BOXES.items() if intersection_mask(z,box).any()},
      coefficient_deltas={'q1_vs_baseline':coeff_delta(q1_q[key],base_q[key]),'q1_dq_vs_raw':coeff_delta(q1_dq[key],t['raw']),'q1_dq_vs_baseline':coeff_delta(q1_dq[key],base_dq[key]),'q1_vs_q32':coeff_delta(q1_q[key],q32_q[key]),'q1_dq_vs_q32':coeff_delta(q1_dq[key],q32_dq[key])},
      support_pixels=int(z['w']*z['h']))
   row['roi_intersections']={roi:{'pixels':int(intersection_mask(z,box).sum())} for roi,box in BOXES.items() if intersection_mask(z,box).any()}
   per.append(row)
  after=[ident(p) for p in dependency];assert before==after
  out_result={'status':'admitted_diagnostic','scope':'fixed-decision invoked support; q1 only; no encode/rate/repair/playback inference',
   'script':ident(__file__),'r12_result':ident(r12result),'r12_arrays':ident(r12arrays),'library':ident(lib),'contract':ident(contract),
   'counts':{'tokens':len(tokens),'invoked':len(invoked),'uninvoked':len(tokens)-len(invoked),'invoked_pixels':int(inv_mask.sum())},
   'realized_qindex':1,'runtime_cpu_flags':native.flags,'distance_units':'all pixel distances use 8-bit units, from native10bit/4; coefficient deltas remain native units','q1_tables':q1rows.tolist(),'q1_arrays':ident(out/'q1-arrays.npz'),'distance_metrics':metrics,'fixed_roi':fullroi,'units':per,
   'checks':['R12 baseline/q32 arrays reused and exact','q1 C/runtime q/DQ/EOB/inverse paired exact','only FP rows 0,1,6 changed','raw/coding_input distances use identical invoked support','baseline/q32/original/coding_input/raw wholeROI descriptors matchR12 within1e-12','reused baseline q/DQ/inverse exactly equal R11 capture']}
  (out/'result.json').write_text(json.dumps(out_result,indent=2,allow_nan=False)+'\n');rec.update(status='complete',result=ident(out/'result.json'),q1_arrays=ident(out/'q1-arrays.npz'),inputs_after=after)
 except BaseException as e:rec.update(status='failed',error=repr(e));raise
 finally:rec.update(seconds=time.monotonic()-start,ended_utc=dt.datetime.now(dt.timezone.utc).isoformat());rp.write_text(json.dumps(rec,indent=2)+'\n')

def roi_mask(shape,box):
 x,y,w,h=box;m=np.zeros(shape,bool);m[y:y+h,x:x+w]=True;return m
if __name__=='__main__':
 if not __debug__:raise SystemExit('optimized Python prohibited')
 main()
