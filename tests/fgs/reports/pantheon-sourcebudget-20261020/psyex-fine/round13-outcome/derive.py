#!/usr/bin/env python3
"""Independent read-only reconstruction of the admitted R13 q1 diagnostic."""
import hashlib, importlib.util, json
from pathlib import Path
import numpy as np

ROOT=Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020')
RUN=ROOT/'worker/psyex-r13-fine/run-1'
RESULT=RUN/'result.json'; ARRAYS=RUN/'q1-arrays.npz'
EXPECTED_RESULT='4511e7223f5c9b8b721e5d2f8c5d01d062ffb5d981bd106ae85ff59e0e1dbb93'
EXPECTED_ARRAYS='11927240f6279d39f491885ab5b50ccd1b89da57ff59830b7265c8372719af09'
EXPECTED_EXPERIMENT='dd5dd4ae87a7101be0d580997dd125190f250f2363a0c0b2f894a03482966e11'
EXPECTED_CONTRACT='4dcd8abfffdc31455f8e020a518b1444bafccfe44b4084b97f78ef4b71dfd302'
R11=ROOT/'parent/psyex-coeff-r11'; VALIDATE=R11/'validate.py'
EXPECTED_VALIDATE='258db37595666efa153d6fc526d42de371fe0a7f0b21bff7c3334e84238378f3'
HELPER=Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020/analyze_psyex_boundary.py')
EXPECTED_HELPER='1027e9a0ec2a5f3b12a6aa908b97cad185df615fe48852a8acbe4daf5fb22ea3'
BOXES={'shirt':(1200,650,200,100),'background':(950,50,250,180),'face':(160,600,500,480)}

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ident(p):
 p=Path(p).resolve();return {'path':str(p),'sha256':sha(p),'size':p.stat().st_size}
def exact(d):
 assert ident(d['path'])==d,d
 return Path(d['path'])
def module(p,n,expected):
 assert sha(p)==expected
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def close(a,b,tol=1e-12):
 if isinstance(a,dict):
  assert a.keys()==b.keys(),(a.keys(),b.keys())
  for k in a:close(a[k],b[k],tol)
 elif isinstance(a,list):
  assert len(a)==len(b)
  for x,y in zip(a,b):close(x,y,tol)
 elif isinstance(a,(int,float)) and isinstance(b,(int,float)):
  assert abs(float(a)-float(b))<=tol,(a,b)
 else:assert a==b,(a,b)
def load_luma(p):
 a=np.fromfile(p,dtype='<u2');assert a.size in (1920*1080,1920*1080*3//2)
 return a[:1920*1080].reshape(1080,1920).astype(np.float64)/4
def mask(box):
 x,y,w,h=box;m=np.zeros((1080,1920),bool);m[y:y+h,x:x+w]=True;return m
def distance(a,b,m):
 d=a[m]-b[m];ad=np.abs(d);n=d.size
 return {'pixels':int(n),'exact':int(np.count_nonzero(d==0)),'exact_fraction':float(np.count_nonzero(d==0)/n),
         'changed':int(np.count_nonzero(d)),'changed_fraction':float(np.count_nonzero(d)/n),
         'max_abs':float(ad.max()),'mae':float(ad.mean()),'mse':float(np.mean(d*d))}
def descriptor(h,ref,z):
 d=h.luma_pair(ref,z);base=h.luma_pair(ref,ref)
 for k in ('hf_sigma','acf1','acf2','acf3','acf4','acf8'):d[k+'_abs_error']=abs(d[k]-base[k])
 e=z-ref;d['pixel_error']={'pixels':int(e.size),'mse':float(np.mean(e*e)),'mae':float(np.mean(np.abs(e))),'max_abs':float(np.max(np.abs(e)))}
 dx=np.abs(np.diff(z,axis=1)-np.diff(ref,axis=1));dy=np.abs(np.diff(z,axis=0)-np.diff(ref,axis=0));support=dx.size+dy.size
 d['gradient_mae']=float((dx.sum()+dy.sum())/support);d['gradient_support']=support;d['pixels']=int(ref.size)
 return d
def coeff_delta(a,b):
 d=a.astype(np.int64)-b.astype(np.int64);ad=np.abs(d)
 return {'count':int(d.size),'exact':int(np.count_nonzero(d==0)),'changed':int(np.count_nonzero(d)),
         'changed_fraction':float(np.count_nonzero(d)/d.size),'max_abs':int(ad.max()),'l1':int(ad.sum()),'mse':float(np.mean(d*d))}

def main():
 assert sha(RESULT)==EXPECTED_RESULT and sha(ARRAYS)==EXPECTED_ARRAYS
 result=json.loads(RESULT.read_text());assert result['status']=='admitted_diagnostic'
 assert result['script']['sha256']==EXPECTED_EXPERIMENT and exact(result['script'])
 assert result['contract']['sha256']==EXPECTED_CONTRACT and exact(result['contract'])
 inner=json.loads((RUN/'receipt.json').read_text());outer=json.loads((RUN.parent/'run-1-execution.json').read_text())
 assert inner['status']==outer['status']=='complete';assert inner['inputs_before']==inner['inputs_after'];assert outer['inputs_before']==outer['inputs_after']
 assert inner['result']==ident(RESULT) and inner['q1_arrays']==ident(ARRAYS) and outer['result']==ident(RESULT) and outer['q1_arrays']==ident(ARRAYS)
 admission=json.loads((R11/'admitted-1/admission.json').read_text());assert admission['status']=='admitted'
 v=module(VALIDATE,'r11_validate_independent',EXPECTED_VALIDATE);tokens,terminal=v.parse(exact(admission['trace']));assert terminal==admission['terminal']
 rows={r['token']:r for r in result['units']};assert set(rows)==set(tokens) and len(tokens)==2907
 invoked=[k for k,r in rows.items() if r['invoked']];assert len(invoked)==2187
 z=np.load(ARRAYS,allow_pickle=False);q1={k:z[k].copy() for k in z.files};z.close()
 pz=np.load(exact(result['r12_arrays']),allow_pickle=False);prior={k:pz[k].copy() for k in pz.files};pz.close()
 assert q1['q1_q'].shape==prior['fp_baseline_q'].shape==prior['fp_q32_q'].shape
 assert q1['q1_dq'].shape==prior['fp_baseline_dq'].shape==prior['fp_q32_dq'].shape
 assert q1['q1_inverse'].shape==prior['fp_baseline_inverse'].shape==prior['fp_q32_inverse'].shape
 dec=json.loads(exact(admission['decoder_admission']).read_text())
 original=load_luma(exact(dec['r9_stages']['original']));coding=load_luma(exact(dec['r9_stages']['coding_input']))
 stages={n:np.full((1080,1920),np.nan) for n in ('raw','baseline','q32','q1')};covered=np.zeros((1080,1920),bool);inv_mask=np.zeros((1080,1920),bool)
 raw_coeff=np.empty_like(q1['q1_dq']);co_end=po_end=0
 table_rows=np.array(result['q1_tables'],dtype=np.int32)
 qindices=[];eob_stats={'q1_zero':0,'q1_positive':0,'q1_equals_raw':0,'q1_less_than_raw':0}
 for k in rows:
  t=tokens[k];r=rows[k];b=t['begin'];x,y,w,hh=(b[n] for n in ('x','y','w','h'));vh=min(hh,1080-y);sl=np.s_[y:y+vh,x:x+w]
  assert not covered[sl].any();covered[sl]=True
  pred=t['predictor'][:vh].astype(np.float64)/4;stages['raw'][sl]=t.get('raw_inverse',t['predictor'])[:vh].astype(np.float64)/4
  if r['invoked']:
   co,po=r['coefficient_offset'],r['pixel_offset'];n=t['begin']['n'];pix=w*hh
   assert co==co_end and po==po_end and t['stages']
   scan=t['scan'];qseg=q1['q1_q'][co:co+n];nz=np.flatnonzero(qseg[scan]);calc_eob=int(nz[-1]+1) if nz.size else 0
   raw_nz=np.flatnonzero(t['raw'][scan]);calc_raw_eob=int(raw_nz[-1]+1) if raw_nz.size else 0
   assert calc_eob==r['eob'] and calc_raw_eob==r['raw_eob']
   eob_stats['q1_zero']+=calc_eob==0;eob_stats['q1_positive']+=calc_eob>0;eob_stats['q1_equals_raw']+=calc_eob==calc_raw_eob;eob_stats['q1_less_than_raw']+=calc_eob<calc_raw_eob
   raw_coeff[co:co+n]=t['raw'];co_end+=n;po_end+=pix;inv_mask[sl]=True;qindices.append(r['actual_qindex'])
   for name,key in [('baseline','fp_baseline_inverse'),('q32','fp_q32_inverse'),('q1','q1_inverse')]:
    flat=q1['q1_inverse'] if key=='q1_inverse' else prior[key]
    stages[name][sl]=flat[po:po+pix].reshape(hh,w)[:vh]/4
   tabs=np.asarray(r['q1_tables']);assert np.array_equal(tabs[[0,1,6]],table_rows)
   assert np.array_equal(tabs[[2,3,4,5]],t['tables'][[2,3,4,5]])
  else:
   for name in ('baseline','q32','q1'):stages[name][sl]=pred
 assert co_end==q1['q1_q'].size and po_end==q1['q1_inverse'].size and int(inv_mask.sum())==result['counts']['invoked_pixels']
 for box in BOXES.values():assert covered[mask(box)].all()
 metrics={}
 for name in ('baseline','q32','q1'):
  metrics[name]={'raw':distance(stages[name],stages['raw'],inv_mask),'coding_input':distance(stages[name],coding,inv_mask),'rois':{},'full_roi_secondary':{}}
  for roi,box in BOXES.items():
   rm=mask(box);metrics[name]['rois'][roi]={'raw':distance(stages[name],stages['raw'],inv_mask&rm),'coding_input':distance(stages[name],coding,inv_mask&rm)}
   metrics[name]['full_roi_secondary'][roi]={'raw':distance(stages[name],stages['raw'],rm),'coding_input':distance(stages[name],coding,rm)}
  close(metrics[name],result['distance_metrics'][{'baseline':'fp_baseline','q32':'fp_q32','q1':'fp_q1'}[name]])
 h=module(HELPER,'boundary_helper_independent',EXPECTED_HELPER)
 fixed={}
 for roi,box in BOXES.items():
  rm=mask(box);ys,xs=np.where(rm);sl=np.s_[ys.min():ys.max()+1,xs.min():xs.max()+1];ref=original[sl]
  fixed[roi]={}
  for name,source in [('fp_baseline',stages['baseline']),('fp_q32',stages['q32']),('fp_q1',stages['q1']),('raw_inverse',stages['raw']),('coding_input',coding)]:
   fixed[roi][name]=descriptor(h,ref,source[sl]);close(fixed[roi][name],result['fixed_roi'][roi]['stages'][name])
 coeff={'q1_dq_vs_raw':coeff_delta(q1['q1_dq'],raw_coeff),'q32_dq_vs_raw':coeff_delta(prior['fp_q32_dq'],raw_coeff),'baseline_dq_vs_raw':coeff_delta(prior['fp_baseline_dq'],raw_coeff),'q1_q_vs_q32_q':coeff_delta(q1['q1_q'],prior['fp_q32_q'])}
 ratios={};support_original={}
 for roi in BOXES:
  rm=mask(BOXES[roi]);im=inv_mask&rm;um=(~inv_mask)&rm
  ratios[roi]={'invoked_fraction':float(im.sum()/rm.sum()),
               'q1_vs_q32_raw_mse_ratio':metrics['q1']['rois'][roi]['raw']['mse']/metrics['q32']['rois'][roi]['raw']['mse'],
               'q1_vs_q32_coding_mse_ratio':metrics['q1']['rois'][roi]['coding_input']['mse']/metrics['q32']['rois'][roi]['coding_input']['mse']}
  support_original[roi]={'invoked':{n:distance(a,original,im) for n,a in [('coding_input',coding),('raw',stages['raw']),('q32',stages['q32']),('q1',stages['q1'])]},
                         'uninvoked':{n:distance(a,original,um) for n,a in [('coding_input',coding),('predictor_raw',stages['raw']),('q1_unchanged',stages['q1'])]}}
 out={'status':'verified','inputs':{'result':ident(RESULT),'arrays':ident(ARRAYS),'inner_receipt':ident(RUN/'receipt.json'),'outer_receipt':ident(RUN.parent/'run-1-execution.json'),'trace':admission['trace'],'validator':ident(VALIDATE),'metric_helper':ident(HELPER)},
      'counts':{'tokens':len(tokens),'invoked':len(invoked),'uninvoked':len(tokens)-len(invoked),'coefficient_values':co_end,'invoked_pixels':int(inv_mask.sum()),'eob':eob_stats},
      'q1_table_rows_0_1_6':table_rows.tolist(),'baseline_actual_qindex':{'min':min(qindices),'max':max(qindices),'unique':sorted(set(qindices))},
      'pixel_distances':metrics,'fixed_roi_descriptors':fixed,'coefficient_distances':coeff,'derived_ratios':ratios,'original_error_by_support':support_original,
      'checks':['receipt/input identity complete','trace-to-array offsets gap-free','q1 rows 0/1/6 exact in every invoked TU','non-q1 table rows exact trace baseline','reported pixel distances reproduced','reported fixed-ROI descriptors reproduced']}
 target=Path(__file__).with_name('derived.json');target.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');print(json.dumps({'status':'verified','output':ident(target)},indent=2))
if __name__=='__main__':main()
