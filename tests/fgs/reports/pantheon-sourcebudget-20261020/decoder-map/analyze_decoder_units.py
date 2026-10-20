#!/usr/bin/env python3
"""Fail-closed R10 decoder-stage/unit analysis; preparation only."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path
import numpy as np
W,H=1920,1080; FRAME10=W*H*3
STAGES=('original','coding_input','predictor','preloop','postloop')
KINDS=('all','quiet','edge','flat_texture','other'); BOXES={'shirt':(1200,650,200,100),'background':(950,50,250,180),'face':(160,600,500,480)}
REPORT=Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020'); HELPER=REPORT/'analyze_psyex_boundary.py'; HELPER_SHA='1027e9a0ec2a5f3b12a6aa908b97cad185df615fe48852a8acbe4daf5fb22ea3'; CONTROL=Path('/media/merged-storage/cold-storage/docker-apps/pantheon-quantization-20261019/e05-1440/whole-window-controls.json'); CONTROL_SHA='bd6a6bfef9b96dbdbc41fbbc136701ec2be2b2030e11e37a7b7ae08e0dc72884'
def sha(p):
 h=hashlib.sha256();
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def ident(p):
 p=Path(p).resolve();return {'path':str(p),'sha256':sha(p),'size':p.stat().st_size}
def helper():
 assert sha(HELPER)==HELPER_SHA
 sp=importlib.util.spec_from_file_location('boundary_helper',HELPER);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
def exact(d):
 assert isinstance(d,dict) and set(('path','sha256','size'))<=set(d); got=ident(d['path']); assert got=={k:d[k] for k in ('path','sha256','size')};return Path(got['path'])
def load_luma(path):
 p=Path(path); n=p.stat().st_size
 if n==W*H*2: a=np.fromfile(p,dtype='<u2');
 else:
  assert n==FRAME10,(p,n);a=np.fromfile(p,dtype='<u2')[:W*H]
 assert a.size==W*H and int(a.max())<=1023
 return a.reshape(H,W).astype(np.float64)/4.0
def rect(a,x,y,w,h):return a[y:y+h,x:x+w]
def mse(a,b):
 d=a-b;return {'pixels':int(d.size),'mse':float(np.mean(d*d)),'mae':float(np.mean(np.abs(d))),'max_abs':float(np.max(np.abs(d)))}
def stat(vals,weights=None):
 total=len(vals); pairs=[(float(v),1.0 if weights is None else float(w)) for v,w in zip(vals,[1]*total if weights is None else weights) if v is not None and np.isfinite(v)]
 if not pairs:return {'total':total,'evaluable':0,'support':0,'mean':None,'p95_unweighted':None}
 v=np.array([x[0] for x in pairs]);w=np.array([x[1] for x in pairs]);return {'total':total,'evaluable':len(v),'support':float(w.sum()),'mean':float(v.mean()),'weighted_mean':float(np.average(v,weights=w)),'p95_unweighted':float(np.percentile(v,95))}
def safe_desc(h,src,z):
 if src.shape[0]<3 or src.shape[1]<3:return {'hf_sigma':None,'acf1':None,'acf2':None,'acf3':None,'acf4':None,'acf8':None,'hf_corr_source':None,'hf_abs_error':None,'signed_hf_delta':None}
 try:d=h.luma_pair(src,z)
 except (ValueError,RuntimeWarning):d={}
 out={}
 for k,v in d.items():out[k]=None if isinstance(v,(float,np.floating)) and not np.isfinite(v) else v
 for k in ('hf_sigma','acf1','acf2','acf3','acf4','acf8'): 
  if k not in out:out[k]=None
 return out
def descriptor(h,src,z):
 d=safe_desc(h,src,z); base=safe_desc(h,src,src)
 for k in ('hf_sigma','acf1','acf2','acf3','acf4','acf8'):
  v=d.get(k); b=base.get(k); d[k+'_abs_error']=abs(v-b) if v is not None and b is not None else None
 d['pixel_error']=mse(z,src);return d
def overlap(x,y,w,h,bx,by,bw,bh):
 q=(max(x,bx),max(y,by),min(x+w,bx+bw)-max(x,bx),min(y+h,by+bh)-max(y,by));return q if q[2]>0 and q[3]>0 else None
def readj(p):return json.loads(Path(p).read_text())
def load_admission(root,validator_sha):
 a=readj(root/'admission.json');assert a.get('status')=='admitted' and a.get('dimensions')==[W,H] and a.get('input_frame')==216 and a.get('scored_frame')==120
 for k in ('all336_allplanes_exact','complete_visible_luma_ownership','preloop_luma_exact_R9','postloop_allplanes_exact_R9','all502_events_independently_bound'):assert a.get(k) is True,k
 for k in ('script','helper','build_pins','trace','payload','independent_events','pristine_receipt'): exact(a[k])
 validator=Path(a['script']['path']).resolve(); assert validator.name=='validate.py'; assert a['script']['sha256']==validator_sha; assert ident(validator)==a['script']
 a['_validator_path']=str(validator)
 for group in ('artifacts','commands','r9_stages'):
  assert isinstance(a.get(group),dict),group
 for group in (a['artifacts'],a['commands'],a['r9_stages']):
  for v in group.values():exact(v)
 return a
def validate_data(root,a):
 units=readj(exact(a['artifacts']['units']));leaves=readj(exact(a['artifacts']['leaves']))
 owner=np.load(exact(a['artifacts']['owner']),allow_pickle=False);umap=np.load(exact(a['artifacts']['unit']),allow_pickle=False);cat=np.load(exact(a['artifacts']['category']),allow_pickle=False)
 assert owner.shape==umap.shape==cat.shape==(H,W);assert units and leaves
 cover=np.zeros((H,W),np.uint8);uids=set()
 for u in units:
  for k in ('id','leaf','x','y','w','h','category','eob','coded_qindex'):assert k in u
  x,y,w,h=[int(u[k]) for k in ('x','y','w','h')];uid=int(u['id']);leaf=int(u['leaf']);c=int(u['category']);assert uid not in uids;uids.add(uid);assert c in (1,2,3,4) and 0<=x and 0<=y and w>0 and h>0 and x+w<=W and y+h<=H
  sl=np.s_[y:y+h,x:x+w];assert not cover[sl].any();cover[sl]=1;assert np.all(owner[sl]==leaf);assert np.all(umap[sl]==uid);assert np.all(cat[sl]==c)
 assert np.all(cover==1) and np.all(owner>=0)
 return units,leaves,owner,umap,cat
def control_report(h,stages,orig,rows_override=None):
 if rows_override is None:
  assert ident(CONTROL)['sha256']==CONTROL_SHA;c=readj(CONTROL);rows=[r for r in c['tiles'] if r.get('frame')==120];assert len(rows)==858
 else:
  rows=rows_override
 out={}
 for kind in KINDS:
  for outside in (False,True):
   pool=[r for r in rows if (kind=='all' or r['kind']==kind) and (not outside or bool(r['outside_target']))];groups={}
   for r in pool:
    x,y=int(r['x']),int(r['y']); h.descriptor_assert(h.desc(rect(orig,x,y,32,32)),r['source'])
   for s in STAGES:
    ds=[]
    for r in pool:
     x,y=int(r['x']),int(r['y']);src=rect(orig,x,y,32,32);ds.append(descriptor(h,src,rect(stages[s],x,y,32,32)))
    groups[s]={'tiles':len(ds),'pixels':len(ds)*1024,'mse':stat([d['pixel_error']['mse'] for d in ds]),'hf_abs_error':stat([d['hf_sigma_abs_error'] for d in ds]),'hf_corr_source':stat([d.get('hf_corr_source') for d in ds]),'signed_hf_delta':stat([d.get('signed_hf_delta') for d in ds]),'acf1_abs_error':stat([d['acf1_abs_error'] for d in ds])}
   out[f'{kind}|outside={str(outside).lower()}']=groups
 return {'identity':ident(CONTROL),'rows':len(rows),'groups':out}
def roi_report(h,units,stages,orig):
 out={}
 for name,box in BOXES.items():
  rows=[]
  for u in units:
   q=overlap(int(u['x']),int(u['y']),int(u['w']),int(u['h']),*box)
   if q is None:continue
   x,y,w,hh=q;src=rect(orig,x,y,w,hh);rows.append({'unit_id':int(u['id']),'category':int(u['category']),'xywh':[x,y,w,hh],'pixels':w*hh,'stages':{s:descriptor(h,src,rect(stages[s],x,y,w,hh)) for s in STAGES}})
  cats={}
  for c in (1,2,3,4):
   rs=[r for r in rows if r['category']==c];g={}
   for s in STAGES:
    ds=[r['stages'][s] for r in rs];weights=[r['pixels'] for r in rs];g[s]={'intersections':len(ds),'pixels':sum(weights),'mse_unweighted':stat([d['pixel_error']['mse'] for d in ds]),'mse_pixel_weighted':stat([d['pixel_error']['mse'] for d in ds],weights),'hf_abs_error':stat([d['hf_sigma_abs_error'] for d in ds],weights),'hf_corr_source':stat([d.get('hf_corr_source') for d in ds],weights),'signed_hf_delta':stat([d.get('signed_hf_delta') for d in ds],weights),'acf1_abs_error':stat([d['acf1_abs_error'] for d in ds],weights)}
   cats[str(c)]={'units':len(rs),'stages':g}
  out[name]={'xywh':list(box),'intersections':rows,'category_aggregates':cats}
 return out
def smoke(h):
 import tempfile
 with tempfile.TemporaryDirectory() as td:
  td=Path(td); raw=np.full(W*H,512,dtype='<u2'); raw.tofile(td/'x.y'); assert np.all(load_luma(td/'x.y')==128)
  np.concatenate([raw,raw[:W*H//4],raw[:W*H//4]]).astype('<u2').tofile(td/'x.yuv'); assert np.all(load_luma(td/'x.yuv')==128)
  units=[]; leaves=[]; owner=np.empty((H,W),np.int32);umap=np.empty((H,W),np.int32);cat=np.empty((H,W),np.uint8)
  for i,(x,y,w,hh,c) in enumerate(((0,0,W//2,H//2,1),(W//2,0,W//2,H//2,2),(0,H//2,W//2,H//2,3),(W//2,H//2,W//2,H//2,4))):
   leaves.append({'id':i}); units.append({'id':i,'leaf':i,'x':x,'y':y,'w':w,'h':hh,'category':c,'eob':0,'coded_qindex':0});owner[y:y+hh,x:x+w]=i;umap[y:y+hh,x:x+w]=i;cat[y:y+hh,x:x+w]=c
  for name,obj in (('units',units),('leaves',leaves)): (td/(name+'.json')).write_text(json.dumps(obj))
  np.save(td/'owner.npy',owner);np.save(td/'unit.npy',umap);np.save(td/'category.npy',cat)
  a={'artifacts':{k:{'path':str(td/(k+'.json' if k in ('units','leaves') else k+'.npy')),'sha256':sha(td/(k+'.json' if k in ('units','leaves') else k+'.npy')),'size':(td/(k+'.json' if k in ('units','leaves') else k+'.npy')).stat().st_size} for k in ('units','leaves','owner','unit','category')}}
  got=validate_data(td,a); assert len(got[0])==4 and sum(int((got[4]==c).sum()) for c in (1,2,3,4))==W*H
  stages={s:np.zeros((H,W)) for s in STAGES}; rows=[]
  for i,(kind,outside) in enumerate((('quiet',False),('edge',True))):
   src=rect(stages['original'],0,0,32,32); rows.append({'x':0,'y':0,'kind':kind,'outside_target':outside,'source':h.desc(src)})
  cr=control_report(h,stages,stages['original'],rows); assert cr['rows']==2 and 'quiet|outside=false' in cr['groups']
  rr=roi_report(h,got[0],stages,stages['original']); assert set(rr['shirt']['category_aggregates'])=={'1','2','3','4'}; assert rr['shirt']['category_aggregates']['1']['units']>=0
  assert safe_desc(h,np.zeros((4,4)),np.zeros((4,4)))['acf1'] is None; assert safe_desc(h,np.zeros((1,1)),np.zeros((1,1)))['hf_sigma'] is None
  assert overlap(0,0,1,1,2,2,1,1) is None and overlap(0,0,3,3,2,2,2,2)==(2,2,1,1)
  assert stat([None,1],[3,2])['total']==2 and stat([None,1],[3,2])['evaluable']==1
  bad=dict(a);bad['status']='rejected'
  try: assert bad.get('status')=='admitted'
  except AssertionError: pass
  else: raise AssertionError('unadmitted input accepted')
 print('smoke=pass')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('admitted',type=Path,nargs='?');ap.add_argument('output',type=Path,nargs='?');ap.add_argument('--smoke',action='store_true');ap.add_argument('--validator-sha');args=ap.parse_args();
 if not __debug__: raise SystemExit('optimized Python prohibited')
 h=helper()
 if args.smoke:smoke(h);return
 assert args.admitted and args.output and args.validator_sha and not args.output.exists();root=args.admitted;a=load_admission(root,args.validator_sha);units,leaves,owner,umap,cat=validate_data(root,a);stages={}
 for s in ('original','coding_input','postloop'):stages[s]=load_luma(exact(a['r9_stages'][s]))
 for s in ('predictor','preloop'):stages[s]=load_luma(exact(a['artifacts'][s]))
 report={'status':'complete','scope':'SINGLEFRAME_DECODER_UNITS','frame':120,'input_frame':216,'admission':ident(root/'admission.json'),'admission_validator':ident(Path(a['_validator_path'])),'analyzer_script':ident(Path(__file__)),'stages':{s:ident(exact(a['r9_stages'][s])) for s in ('original','coding_input','postloop')},'predictor':ident(exact(a['artifacts']['predictor'])),'preloop_luma':ident(exact(a['artifacts']['preloop'])),'units':ident(exact(a['artifacts']['units'])),'leaves':ident(exact(a['artifacts']['leaves'])),'owner':ident(exact(a['artifacts']['owner'])),'unit':ident(exact(a['artifacts']['unit'])),'category':ident(exact(a['artifacts']['category'])),'helper':ident(HELPER),'controls':control_report(h,stages,stages['original']),'outside_semantics':{'outside=false':'complete frozen population (inside and outside target)','outside=true':'only frozen outside_target=true tiles'},'roi_categories':roi_report(h,units,stages,stages['original']),'category_legend':{'1':'skip_mode','2':'block_no_coded_residual','3':'TU_EOB0','4':'TU_EOBpositive'},'population':{'units':len(units),'leaves':len(leaves),'categories':{str(c):int((cat==c).sum()) for c in (1,2,3,4)}},'command':{'argv':sys.argv,'python':ident(sys.executable)},'interpretation':'Owner-conditioned decoder descriptors only; final syntax categories do not establish encoder execution or repair.'}
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
if __name__=='__main__':main()
