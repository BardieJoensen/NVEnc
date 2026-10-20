#!/usr/bin/env python3
"""Independent read-only reconstruction of R14 from admitted arrays and R11 trace."""
import hashlib,importlib.util,json
from pathlib import Path
import numpy as np
ROOT=Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020');P=ROOT/'parent/psyex-source-r14';RUN=P/'run-1';R11=ROOT/'parent/psyex-coeff-r11';R13=ROOT/'worker/psyex-r13-fine'
RESULT_SHA='0dcfb0f808ae9a34d0c707de828a4dd5ad88cc23a2bda3c0971585a0476008b8';ARRAY_SHA='c8bdbaf904334a00c710ae89d34d65272af0b50be5898b2c18c8679226821592'
EXPERIMENT_SHA='181ce1e3c9d9c2b55497da12bcbf10c56ce79f1c3f35fa2d0dca91f0f6d7ad59';RUNNER_SHA='65639acb29a5d255a8523b821d403fa6c0923e31b7d7494391248cce06aafe7d'
VALIDATE_SHA='258db37595666efa153d6fc526d42de371fe0a7f0b21bff7c3334e84238378f3';HELPER=Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020/analyze_psyex_boundary.py');HELPER_SHA='1027e9a0ec2a5f3b12a6aa908b97cad185df615fe48852a8acbe4daf5fb22ea3'
BOXES={'shirt':(1200,650,200,100),'background':(950,50,250,180),'face':(160,600,500,480)}
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ident(p):p=Path(p).resolve();return {'path':str(p),'sha256':sha(p),'size':p.stat().st_size}
def exact(d):assert ident(d['path'])==d,d;return Path(d['path'])
def mod(p,n,s):
 assert sha(p)==s;spe=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(spe);spe.loader.exec_module(m);return m
def load_y(p):
 a=np.fromfile(p,dtype='<u2');assert a.size in (1920*1080,1920*1080*3//2);return a[:1920*1080].reshape(1080,1920).astype(float)/4
def rm(box):x,y,w,h=box;m=np.zeros((1080,1920),bool);m[y:y+h,x:x+w]=1;return m
def distance(a,b,m):
 d=a[m]-b[m];ad=abs(d);n=d.size
 return {'pixels':int(n),'changed':int(np.count_nonzero(d)),'exact_fraction':float(np.mean(d==0)),'mse':float(np.mean(d*d)),'mae':float(np.mean(ad)),'max_abs':float(ad.max())}
def desc(h,ref,z):
 d=h.luma_pair(ref,z);base=h.luma_pair(ref,ref)
 for k in ('hf_sigma','acf1','acf2','acf3','acf4','acf8'):d[k+'_abs_error']=abs(d[k]-base[k])
 e=z-ref;d['pixel_error']={'pixels':int(e.size),'mse':float(np.mean(e*e)),'mae':float(np.mean(abs(e))),'max_abs':float(abs(e).max())}
 dx=abs(np.diff(z,axis=1)-np.diff(ref,axis=1));dy=abs(np.diff(z,axis=0)-np.diff(ref,axis=0));s=dx.size+dy.size;d['gradient_mae']=float((dx.sum()+dy.sum())/s);d['gradient_support']=s;d['pixels']=int(ref.size);return d
def close(a,b,tol=1e-12):
 if isinstance(a,dict):assert a.keys()==b.keys(),(a.keys(),b.keys());[close(a[k],b[k],tol) for k in a]
 elif isinstance(a,list):assert len(a)==len(b);[close(x,y,tol) for x,y in zip(a,b)]
 elif isinstance(a,(int,float)) and isinstance(b,(int,float)):assert abs(float(a)-float(b))<=tol,(a,b)
 else:assert a==b,(a,b)
def coeff(a,b):
 d=a.astype(np.int64)-b.astype(np.int64);return {'count':int(d.size),'changed':int(np.count_nonzero(d)),'changed_fraction':float(np.mean(d!=0)),'max_abs':int(abs(d).max()),'l1':int(abs(d).sum()),'mse':float(np.mean(d*d))}
def main():
 rp=RUN/'result.json';ap=RUN/'native-arrays.npz';assert sha(rp)==RESULT_SHA and sha(ap)==ARRAY_SHA and sha(P/'experiment.py')==EXPERIMENT_SHA and sha(P/'run.py')==RUNNER_SHA
 r=json.loads(rp.read_text());assert r['status']=='admitted_diagnostic' and r['all_new_C_runtime_exact'] is True
 inner=json.loads((RUN/'receipt.json').read_text());outer=json.loads((P/'run-1-execution.json').read_text());assert inner['status']==outer['status']=='complete' and inner['inputs_before']==inner['inputs_after'] and outer['inputs_before']==outer['inputs_after'];assert inner['result']==outer['result']==ident(rp) and inner['arrays']==outer['arrays']==ident(ap)
 ctl=json.loads((RUN/'baseline-control.json').read_text());assert ctl==r['controls'] and all(ctl[k] is True for k in ('all_forward_C_runtime_capture_exact','all_raw_inverse_exact','all_q1_C_runtime_R13_exact'))
 ad=json.loads((R11/'admitted-1/admission.json').read_text());v=mod(R11/'validate.py','v',VALIDATE_SHA);tokens,term=v.parse(exact(ad['trace']));assert term==ad['terminal']
 dec=json.loads(exact(ad['decoder_admission']).read_text());original=load_y(exact(dec['r9_stages']['original']));coding=load_y(exact(dec['r9_stages']['coding_input']))
 rows={x['token']:x for x in r['units']};assert set(rows)==set(tokens) and len(rows)==2907
 with np.load(ap,allow_pickle=False) as z:new={k:z[k].copy() for k in z.files}
 r13=json.loads(exact(r['r13_result']).read_text());with13=np.load(exact(r13['q1_arrays']),allow_pickle=False);old={k:with13[k].copy() for k in with13.files};with13.close()
 frames={k:np.full((1080,1920),np.nan) for k in ('predictor','raw_executed','captured_q1','original_raw','original_q1')};covered=np.zeros((1080,1920),bool);invm=np.zeros((1080,1920),bool)
 old_raw=[];co=po=0;changed=visible=padding=rawchanged=0;eobs={'raw_positive':0,'q1_positive':0,'q1_less_raw':0,'q1_equal_raw':0}
 for k,t in tokens.items():
  z=t['begin'];x,y,w,hh=(z[n] for n in ('x','y','w','h'));vh=min(hh,1080-y);sl=np.s_[y:y+vh,x:x+w];assert not covered[sl].any();covered[sl]=1
  pred=t['predictor'][:vh].astype(float)/4;frames['predictor'][sl]=pred;frames['raw_executed'][sl]=t.get('raw_inverse',t['predictor'])[:vh].astype(float)/4
  row=rows[k];assert row['begin']==z and row['invoked']==bool(t['stages'])
  if t['stages']:
   n=z['n'];pix=w*hh;assert row['coefficient_offset']==co and row['pixel_offset']==row['source_offset']==po
   source=new['source'][po:po+pix].reshape(hh,w);raw=new['raw'][co:co+n];rinv=new['raw_inverse'][po:po+pix].reshape(hh,w);q=new['q'][co:co+n];dq=new['dq'][co:co+n];inv=new['inverse'][po:po+pix].reshape(hh,w)
   assert np.array_equal(source[:vh],np.asarray(original[y:y+vh,x:x+w]*4,dtype='<u2'))
   assert np.array_equal(source[vh:],t['source'][vh:])
   calc_change=int(np.count_nonzero(source[:vh]!=t['source'][:vh]));assert row['changes']=={'visible_pixels':w*vh,'source_changed':calc_change,'padding_pixels':w*(hh-vh),'padding_changed':0,'raw_coefficients_changed':int(np.count_nonzero(raw!=t['raw']))}
   scan=t['scan'];rn=np.flatnonzero(raw[scan]);qn=np.flatnonzero(q[scan]);re=int(rn[-1]+1) if rn.size else 0;qe=int(qn[-1]+1) if qn.size else 0;assert (re,qe)==(row['raw_eob'],row['eob']) and np.all(dq[q==0]==0)
   for name,arr in [('captured_q1',old['q1_inverse'][po:po+pix].reshape(hh,w)),('original_raw',rinv),('original_q1',inv)]:frames[name][sl]=arr[:vh]/4
   invm[sl]=1;old_raw.append(t['raw']);changed+=calc_change;visible+=w*vh;padding+=w*(hh-vh);rawchanged+=row['changes']['raw_coefficients_changed'];eobs['raw_positive']+=re>0;eobs['q1_positive']+=qe>0;eobs['q1_less_raw']+=qe<re;eobs['q1_equal_raw']+=qe==re;co+=n;po+=pix
  else:
   for name in ('captured_q1','original_raw','original_q1'):frames[name][sl]=pred
 assert co==new['q'].size==old['q1_q'].size and po==new['source'].size==old['q1_inverse'].size and padding==0
 for box in BOXES.values():assert covered[rm(box)].all()
 h=mod(HELPER,'h',HELPER_SHA);metrics={}
 sources={'original':original,'coding_input':coding};allframes={**frames,**sources}
 for roi,box in BOXES.items():
  m=rm(box);ys,xs=np.where(m);sl=np.s_[ys.min():ys.max()+1,xs.min():xs.max()+1];im=invm&m;um=(~invm)&m;metrics[roi]={'pixels':int(m.sum()),'invoked_pixels':int(im.sum()),'unchanged_pixels':int(um.sum()),'stages':{}}
  for name,f in allframes.items():
   x={'original_referenced':desc(h,original[sl],f[sl]),'coding_input_referenced':desc(h,coding[sl],f[sl]),'full_to_original':distance(f,original,m),'full_to_coding_input':distance(f,coding,m),'invoked_to_original':distance(f,original,im),'uninvoked_to_original':distance(f,original,um),'invoked_to_coding_input':distance(f,coding,im),'uninvoked_to_coding_input':distance(f,coding,um)}
   close(x,r['fixed_roi'][roi]['stages'][name]);metrics[roi]['stages'][name]=x
 oracles={}
 for roi,box in BOXES.items():
  m=rm(box);ys,xs=np.where(m);sl=np.s_[ys.min():ys.max()+1,xs.min():xs.max()+1];oracles[roi]={}
  for name in ('original_raw','original_q1'):
   f=frames[name].copy();f[(~invm)&m]=original[(~invm)&m];oracles[roi][name+'_with_exact_uninvoked']=desc(h,original[sl],f[sl])
 out={'status':'verified','inputs':{'result':ident(rp),'arrays':ident(ap),'inner':ident(RUN/'receipt.json'),'outer':ident(P/'run-1-execution.json'),'trace':ad['trace'],'experiment':ident(P/'experiment.py'),'runner':ident(P/'run.py')},'population':{'tokens':len(tokens),'invoked':sum(bool(t['stages']) for t in tokens.values()),'uninvoked':sum(not t['stages'] for t in tokens.values()),'visible_invoked_pixels':visible,'source_changed':changed,'source_changed_fraction':changed/visible,'padding_pixels':padding,'raw_coefficients_changed':rawchanged,'eob':eobs},'coefficient_deltas':{'original_raw_vs_captured_raw':coeff(new['raw'],np.concatenate(old_raw)),'original_q1_vs_captured_q1':coeff(new['q'],old['q1_q']),'original_q1_dq_vs_captured_q1_dq':coeff(new['dq'],old['q1_dq'])},'fixed_roi':metrics,'exact_uninvoked_oracle':oracles,'checks':['all reported ROI descriptors/distances reproduced','original source exact on every invoked visible sample','padding preserved','720 uninvoked owners retain predictor','gap-free offsets and scan-derived EOB exact']}
 op=Path(__file__).with_name('derived.json');op.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');print(json.dumps({'status':'verified','output':ident(op)},indent=2))
if __name__=='__main__':main()
