#!/usr/bin/env python3
"""Native original-source replay under frozen R11 decisions; diagnostic only."""
import argparse,ctypes as C,datetime as dt,hashlib,importlib.util,json,sys,time
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent;ROOT=P.parents[1];R11=P.parent/'psyex-coeff-r11';R12=P.parent/'psyex-scalar-r12';R13=ROOT/'worker/psyex-r13-fine'
CONTRACT=Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020/ROUND14_SOURCE_CONTRACT.md')
CSHA='0674ce053b27410e5bf184e861a7f88c77b902374984531089787d530e62106d'
BSHA='8ddbfd8c092185ff99181c68dd88cc25ff0cbec9af569cfae3a0b7d2fb202825'
LSHA='2d8a97ac78e7ec6986fb1d05ba2766dd28ed0cca6010ff17245195294af4f08a'
def ident(p):
 p=Path(p).resolve()
 with p.open('rb') as f:s=hashlib.file_digest(f,'sha256').hexdigest()
 return dict(path=str(p),sha256=s,size=p.stat().st_size)
def exact(d):
 assert ident(d['path'])==d,d
 return Path(d['path'])
def load(p,n,sha):
 assert ident(p)['sha256']==sha,p
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def dist(a,b):
 d=a.astype('f8')-b.astype('f8');return dict(pixels=int(d.size),changed=int(np.count_nonzero(d)),exact_fraction=float(np.mean(d==0)),mse=float(np.mean(d*d)),mae=float(np.mean(abs(d))),max_abs=float(abs(d).max()))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('out',type=Path);args=ap.parse_args();out=args.out;out.mkdir(exist_ok=False)
 start=time.monotonic();rec=dict(status='prepared',argv=sys.argv,python=ident(sys.executable),started_utc=dt.datetime.now(dt.timezone.utc).isoformat())
 def save():(out/'receipt.json').write_text(json.dumps(rec,indent=2)+'\n')
 save()
 try:
  r12=load(R12/'experiment.py','r14_nativebase','87eb15f8a7c082bb875f91edb790ed66a8e592db9d64bc5f554943040f705ee2')
  r13=load(R13/'experiment.py','r14_priorhelpers','dd5dd4ae87a7101be0d580997dd125190f250f2363a0c0b2f894a03482966e11')
  a=load(R11/'analyze.py','r14_analysis','44b8037c2a922b7e893cd66c8488f3683c45b8859400ff6b082bd0910286f64e')
  adp=R11/'admitted-1/admission.json';assert ident(adp)['sha256']=='f9aba0b6b1d5d8b73c606698130a64e46ec0bc7f55a6d7363ea113bd45e1548a'
  ad=json.loads(adp.read_text());assert ad['status']=='admitted'
  for k in ('all336_exact','source_predictor_preloop_exact','final_dq_eob_iqm_exact','actual_committed_owner'):assert ad[k] is True
  bp=P/'build-1/receipt.json';assert ident(bp)['sha256']==BSHA
  build=json.loads(bp.read_text());assert build['status']=='complete';lib=exact(build['library']);assert ident(lib)['sha256']==LSHA
  bi=json.loads(exact(build['inputs_before']).read_text());assert bi==json.loads(exact(build['inputs_after']).read_text())
  for d in bi:exact(d)
  for command in build['commands']:assert command['returncode']==0;exact(command['log'])
  result13=R13/'run-1/result.json';assert ident(result13)['sha256']=='4511e7223f5c9b8b721e5d2f8c5d01d062ffb5d981bd106ae85ff59e0e1dbb93'
  prior=json.loads(result13.read_text());assert prior['status']=='admitted_diagnostic' and prior['realized_qindex']==1
  apath=exact(prior['q1_arrays']);assert ident(apath)['sha256']=='11927240f6279d39f491885ab5b50ccd1b89da57ff59830b7265c8372719af09'
  with np.load(apath,allow_pickle=False) as nz:arrays13={k:nz[k] for k in nz.files}
  v=a.mod(a.V,'r14_validator',a.VSHA);u=a.mod(a.U,'r14_unithelper',a.USHA);h=u.helper()
  tokens,terminal=v.parse(exact(ad['trace']));assert terminal==ad['terminal'] and len(tokens)==2907
  dec=json.loads(exact(ad['decoder_admission']).read_text())
  refs={s:u.load_luma(exact(dec['r9_stages'][s])) for s in ('original','coding_input')}
  original10=np.asarray(refs['original']*4,dtype='<u2');coding10=np.asarray(refs['coding_input']*4,dtype='<u2')
  assert np.array_equal(original10.astype(float)/4,refs['original']) and np.array_equal(coding10.astype(float)/4,refs['coding_input'])
  assert dec['r9_stages']['original']['sha256']=='c2798d9c00f53bdbe7041575249b353a478a8f5557bc4dd5b61d9ae03f13ea12'
  assert dec['r9_stages']['coding_input']['sha256']=='b8ad2257c0bab9febd99eeefc05156f64c059bf028a19e72443a24af7af92b68'
  assert ident(CONTRACT)['sha256']==CSHA
  inherited_path=ROOT/'parent/psyex-boundary-r9/analysis-1.json';assert ident(inherited_path)['sha256']=='b2d4a19ac93eeab29cb78870cea45f03165f7741f22584955081498553ed5bc5'
  inherited=json.loads(inherited_path.read_text())['metric_helpers'];[exact(d) for d in inherited.values()]
  deps=[Path(__file__),P/'native.c',P/'build.py',bp,lib,CONTRACT,adp,result13,apath,R12/'experiment.py',R13/'experiment.py',R11/'analyze.py',a.V,a.U,u.HELPER,inherited_path,exact(ad['trace']),exact(ad['decoder_admission']),exact(ad['token_manifest'])]
  deps += [exact(d) for d in inherited.values()]+[exact(dec['r9_stages'][s]) for s in refs]
  before=[ident(p) for p in deps];rec['inputs_before']=before;save()
  native=r12.Native(lib);q1rows=native.tables(1);assert q1rows.tolist()==prior['q1_tables'];rec['runtime_cpu_flags']=native.flags
  native.lib.rp_forward.argtypes=[*([C.c_int]*6),*([C.c_void_p]*3)];native.lib.rp_forward.restype=C.c_int
  def forward(t,source):
   z=t['begin'];w,hh,n=z['w'],z['h'],z['n'];assert source.shape==(hh,w) and source.dtype==np.dtype('<u2')
   residual=np.asarray(source.astype('i4')-t['predictor'].astype('i4'),dtype='<i2');assert np.all(abs(residual.astype('i4'))<=1023)
   pair=[]
   for dispatch in (0,1):
    raw=np.zeros(n,dtype='<i4');energy=np.zeros(1,dtype='<u8')
    rc=native.lib.rp_forward(dispatch,z['tx'],z['type'],w,hh,n,r12.ptr(residual,'<i2'),r12.ptr(raw,'<i4'),r12.ptr(energy,'<u8'));assert rc==0,(z['token'],'forward',dispatch,rc)
    pair.append((raw,int(energy[0])))
   assert np.array_equal(pair[0][0],pair[1][0]) and pair[0][1]==pair[1][1],('forward C/runtime',z['token'])
   return pair[1]
  def raw_inverse(t,raw):
   nz=np.flatnonzero(raw[t['scan']]);eob=int(nz[-1])+1 if nz.size else 0
   c=native.inverse(t,raw,eob,0);r=native.inverse(t,raw,eob,1);assert np.array_equal(c,r),('raw inverse C/runtime',t['begin']['token'])
   return r,eob
  invoked={k:t for k,t in tokens.items() if t['stages']};assert len(invoked)==2187
  prior_rows={r['token']:r for r in prior['units']};assert set(prior_rows)==set(tokens)
  joined=json.loads(exact(ad['token_manifest']).read_text());jmap={r['token']:r for r in joined};assert set(jmap)==set(tokens)
  # Complete all newly introduced forward/library baseline controls before original-source work.
  old={};co=po=0
  for key,t in tokens.items():
   z=t['begin'];x,y,w,hh=(z[k] for k in ('x','y','w','h'));vh=min(hh,1080-y)
   assert np.array_equal(t['source'][:vh],coding10[y:y+vh,x:x+w]),('captured coding source',key)
   assert jmap[key]['begin']==z and prior_rows[key]['xywh']==[x,y,w,hh]
   if key not in invoked:continue
   assert t['info']['depth']==10 and t['info']['seg_delta']==0 and t['stages'][0]['stage']=='scalar_fp'
   raw,energy=forward(t,t['source']);assert np.array_equal(raw,t['raw']),('captured forward',key)
   inv,eob=raw_inverse(t,raw);assert eob==t['raw_eob'] and np.array_equal(inv,t['raw_inverse']),('captured raw inverse',key)
   table=t['tables'].copy();table[[0,1,6]]=q1rows
   q1=native.paired(t,0,table);pr=prior_rows[key];assert pr['coefficient_offset']==co and pr['pixel_offset']==po
   assert q1['eob']==pr['eob']
   for field,count,off,shape in [('q',z['n'],co,(z['n'],)),('dq',z['n'],co,(z['n'],)),('inverse',w*hh,po,(hh,w))]:
    assert np.array_equal(q1[field],arrays13['q1_'+field][off:off+count].reshape(shape)),('R13 q1 library parity',key,field)
   old[key]=q1;co+=z['n'];po+=w*hh
  assert co==arrays13['q1_q'].size and po==arrays13['q1_inverse'].size
  control=dict(status='exact_baseline',tokens=len(tokens),invoked=len(invoked),unchanged=len(tokens)-len(invoked),all_forward_C_runtime_capture_exact=True,all_raw_inverse_exact=True,all_q1_C_runtime_R13_exact=True)
  (out/'baseline-control.json').write_text(json.dumps(control,indent=2)+'\n');rec['baseline_control']=ident(out/'baseline-control.json');save()
  new={};changes={}
  for key,t in invoked.items():
   z=t['begin'];x,y,w,hh=(z[k] for k in ('x','y','w','h'));vh=min(hh,1080-y)
   source=t['source'].copy();source[:vh]=original10[y:y+vh,x:x+w]
   assert np.array_equal(source[vh:],t['source'][vh:]);assert np.array_equal(source[:vh],original10[y:y+vh,x:x+w])
   raw,energy=forward(t,source);inv,eob=raw_inverse(t,raw)
   nt=dict(t,source=source,raw=raw);table=t['tables'].copy();table[[0,1,6]]=q1rows;assert np.array_equal(table[[2,3,4,5]],t['tables'][[2,3,4,5]])
   q1=native.paired(nt,0,table)
   new[key]=dict(source=source,raw=raw,raw_inverse=inv,raw_eob=eob,energy=energy,**q1)
   changes[key]=dict(visible_pixels=w*vh,source_changed=int(np.count_nonzero(source[:vh]!=t['source'][:vh])),padding_pixels=w*(hh-vh),padding_changed=0,raw_coefficients_changed=int(np.count_nonzero(raw!=t['raw'])))
  frames,covered=a.make_mosaics(tokens);frames={k:frames[k] for k in ('predictor','raw_executed')};frames.update(refs)
  for name,pop,field in [('captured_q1',old,'inverse'),('original_raw',new,'raw_inverse'),('original_q1',new,'inverse')]:
   frame=np.full((1080,1920),np.nan)
   for key,t in tokens.items():
    z=t['begin'];x,y,w,hh=(z[k] for k in ('x','y','w','h'));vh=min(hh,1080-y);im=pop[key][field] if key in invoked else t['predictor']
    frame[y:y+vh,x:x+w]=im[:vh].astype(float)/4
   assert np.isfinite(frame[covered]).all();frames[name]=frame
  for roi,box in a.BOXES.items():
   for name,priorname in [('captured_q1','fp_q1'),('raw_executed','raw_inverse'),('coding_input','coding_input')]:
    r13.close_json(a.descriptor(u,h,a.crop(refs['original'],box),a.crop(frames[name],box)),prior['fixed_roi'][roi]['stages'][priorname])
  invmask=np.zeros((1080,1920),bool)
  for t in invoked.values():
   z=t['begin'];invmask[z['y']:min(1080,z['y']+z['h']),z['x']:z['x']+z['w']]=True
  roi_metrics={}
  for roi,box in a.BOXES.items():
   rr=a.crop(refs['original'],box);ci=a.crop(refs['coding_input'],box);mask=a.crop(invmask,box)
   roi_metrics[roi]=dict(xywh=list(box),pixels=int(rr.size),invoked_pixels=int(mask.sum()),unchanged_pixels=int((~mask).sum()),stages={})
   for name,frame in frames.items():
    local=a.crop(frame,box);roi_metrics[roi]['stages'][name]=dict(original_referenced=a.descriptor(u,h,rr,local),coding_input_referenced=a.descriptor(u,h,ci,local),full_to_original=dist(local,rr),full_to_coding_input=dist(local,ci),invoked_to_original=dist(local[mask],rr[mask]),uninvoked_to_original=dist(local[~mask],rr[~mask]),invoked_to_coding_input=dist(local[mask],ci[mask]),uninvoked_to_coding_input=dist(local[~mask],ci[~mask]))
  arrays={f:np.concatenate([new[k][f].ravel() for k in invoked]) for f in ('source','raw','raw_inverse','q','dq','inverse')};np.savez_compressed(out/'native-arrays.npz',**arrays)
  rows=[];co=po=0
  for key,t in tokens.items():
   z=t['begin'];r=dict(token=key,unit=jmap[key]['unit'],begin=z,invoked=key in invoked)
   if key in invoked:
    r.update(coefficient_offset=co,pixel_offset=po,source_offset=po,changes=changes[key],qindex=1,raw_eob=new[key]['raw_eob'],eob=new[key]['eob'],q=a.coeff_stats(new[key]['q']),dq=a.coeff_stats(new[key]['dq']))
    co+=z['n'];po+=z['w']*z['h']
   rows.append(r)
  after=[ident(p) for p in deps];assert before==after
  result=dict(status='admitted_diagnostic',scope='original visible samples only; fixed R11 local decisions and q1; no encode/rate/repair/playback',script=ident(__file__),build=ident(bp),library=ident(lib),contract=ident(CONTRACT),controls=control,q1_tables=q1rows.tolist(),r13_result=ident(result13),original=dec['r9_stages']['original'],coding_input=dec['r9_stages']['coding_input'],fixed_roi=roi_metrics,units=rows,array_file=ident(out/'native-arrays.npz'),all_new_C_runtime_exact=True)
  (out/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');rec.update(status='complete',inputs_after=after,result=ident(out/'result.json'),arrays=ident(out/'native-arrays.npz'))
 except BaseException as e:rec.update(status='failed',error=repr(e));raise
 finally:rec.update(seconds=time.monotonic()-start,ended_utc=dt.datetime.now(dt.timezone.utc).isoformat());save()
 print(json.dumps(dict(status=rec['status'],result=rec.get('result'),seconds=rec['seconds'])))
if __name__=='__main__':
 if not __debug__:raise SystemExit('optimized Python prohibited')
 main()
