#!/usr/bin/env python3
"""R17 fixed-decision native FP q4 diagnostic; prepared, not executed."""
from __future__ import annotations
if not __debug__: raise SystemExit("optimized Python is rejected")
import argparse, datetime as dt, hashlib, importlib.util, json, sys, time
from pathlib import Path
import numpy as np
ROOT=Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020'); W,H=1920,1080
CONTRACT=Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020/ROUND17_FIXED_Q4_CONTRACT.md'); CONTRACT_SHA='c207781f7fd77d488df17a9892988c78d660cf88c3ab8216209a91c73ab29f8c'
R12=ROOT/'parent/psyex-scalar-r12'; R12_SHA='87eb15f8a7c082bb875f91edb790ed66a8e592db9d64bc5f554943040f705ee2'; LIB_SHA='07fe2554623523d8e6dfe5218d94a89cdb2437bb2221123a86678090af6f2228'; BUILD_SHA='4b56e9cbd1450f68ec42d02a70d6db2e082db065c6314f34ef17443ef6cb7df5'; NATIVE_SHA='8f1cf5b69700e1a1b2d26d8bf29a0cb87cfe2f2e0b2351881be20106731934fc'
PARSER=ROOT/'parent/psyex-real-r15/parsers.py'; PARSER_SHA='45f11c246037e1a58a2762235a62db9a0bcb71e85fe992cfcc35897fa24983e3'; ANALYZE=ROOT/'parent/psyex-coeff-r11/analyze.py'; ANALYZE_SHA='44b8037c2a922b7e893cd66c8488f3683c45b8859400ff6b082bd0910286f64e'; PRODUCER_SHA='fd190fae6a20aa3cd2efd06e6d6fc9c32471d602272a214b7168667aab511cbb'
DCLOG=ROOT/'parent/psyex-tf0-r16-refine/r16-refine-tbr10042-observations/syntax-binding/trace_headers.log'; DCLOG_SHA='af82740d0c84a2a55c72aa9f1ba794e630431b3b2729618d5cf9ffd8fc2f5ee8'
DC_EVENT=(314,210)
BOXES={'shirt':(1200,650,200,100),'background':(950,50,250,180),'face':(160,600,500,480)}
def sha(p):
 h=hashlib.sha256();
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()
def ident(p):
 p=Path(p).resolve(); return {'path':str(p),'sha256':sha(p),'size':p.stat().st_size}
def exact(row):
 assert isinstance(row,dict) and {'path','sha256','size'}<=row.keys(); d=ident(row['path']); assert d==row,d; return Path(row['path'])
def mod(p,name,h):
 assert ident(p)['sha256']==h,(p,ident(p),h); sp=importlib.util.spec_from_file_location(name,p); m=importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m
def gen_tables(native,r12,q,delta):
 out=np.zeros((3,8),dtype='<i2'); assert native.lib.rp_fp_tables(q,delta,r12.ptr(out,'<i2'))==0; return out
def dc_evidence(binding):
 target=binding['target_coded_event']; assert (int(target['event_index']),int(target['coded_ordinal']))==DC_EVENT
 text=DCLOG.read_text(); assert 'delta_q_y_dc.delta_coded' in text and '0 = 0' in text
 return 0
def crop(a,box): x,y,w,h=box; return a[y:y+h,x:x+w]
def frame_for(tokens, selector, shape=(H,W)):
 out=np.full(shape,np.nan); covered=np.zeros(shape,bool)
 for key,t in tokens.items():
  z=t['begin']; x,y,w,h=(int(z[k]) for k in ('x','y','w','h')); vh=min(h,H-y); sl=np.s_[y:y+vh,x:x+w]
  assert not covered[sl].any(); covered[sl]=True
  if selector=='predictor': img=t['predictor']
  elif selector=='raw': img=t.get('raw_inverse',t['predictor'])
  elif selector=='scalar': img=t['stages'][0]['inverse'] if t['stages'] else t['predictor']
  elif selector=='final': img=t['stages'][-1]['inverse'] if t['stages'] else t['predictor']
  else: raise ValueError(selector)
  out[sl]=img[:vh].astype(np.float64)/4.0
 return out,covered
def sse(a,b,mask):
 d=a[mask].astype(np.float64)-b[mask].astype(np.float64); return {'pixels':int(mask.sum()),'sse':float(np.square(d).sum()),'mse':float(np.square(d).mean()) if d.size else None}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('admission',type=Path); ap.add_argument('admission_sha'); ap.add_argument('out',type=Path); a=ap.parse_args(); assert not a.out.exists(); a.out.mkdir(parents=True)
 rec={'status':'prepared','argv':sys.argv,'script':ident(__file__),'started_utc':dt.datetime.now(dt.timezone.utc).isoformat()}; rp=a.out/'receipt.json'; rp.write_text(json.dumps(rec,indent=2)+'\n'); start=time.monotonic()
 try:
  assert ident(CONTRACT)['sha256']==CONTRACT_SHA; adp=a.admission; assert ident(adp)['sha256']==a.admission_sha
  ad=json.loads(adp.read_text()); assert ad.get('status')=='admitted' and ad.get('case')=='e05-1440'; assert ad.get('script',{}).get('sha256')==PRODUCER_SHA and sha(ad['script']['path'])==PRODUCER_SHA
  for k in ('actual_committed_owner','all336_exact','all_traced_roi_owners_source_predictor_preloop_exact','all_traced_positive_units_dq_iqm_exact_with_all_traced_eob_q_exact'): assert ad[k] is True
  cmd=exact(ad['original_receipt']); assert ad['original_receipt']['sha256']=='00bb9243453fb55f1c878842e2ecfd3760f8403144e1e5b507530477a03ef497'; cmdj=json.loads(cmd.read_text()); assert cmdj.get('status')=='encoded' and cmdj.get('returncode')==0
  binding_path=ad['artifacts']['syntax_binding']['path']; binding=json.loads(exact(ad['artifacts']['syntax_binding']).read_text()); coded=int(binding['target_coded_event']['coded_ordinal']); dc_delta=dc_evidence(binding)
  parser=mod(PARSER,'r17_parser',PARSER_SHA); tokens,terminal=parser.parse_coeff(exact(ad['trace']),coded); assert terminal==ad['terminal'] and len(tokens)==int(ad['tokens'])
  joined=json.loads(exact(ad['token_manifest']).read_text()); jmap={int(x['token']):x for x in joined}; assert len(jmap)==len(joined)==len(tokens) and set(jmap)==set(tokens)
  native_path=R12/'build-2/native.so'; build_path=R12/'build-2/receipt.json'; native_source=R12/'native.c'; assert ident(native_path)['sha256']==LIB_SHA and ident(build_path)['sha256']==BUILD_SHA and ident(native_source)['sha256']==NATIVE_SHA
  build=json.loads(build_path.read_text()); assert build.get('status')=='complete' and build.get('library',{}).get('sha256')==LIB_SHA
  assert build.get('inputs_before')==build.get('inputs_after')
  for row in build.get('commands',[]):
   assert row.get('returncode')==0; exact(row['log'])
  for row in build.get('inputs_before',[]) + build.get('inputs_after',[]): exact(row)
  for key in ('source_manifest','library','object'):
   if isinstance(build.get(key),dict): exact(build[key])
  r12=mod(R12/'experiment.py','r12_native',R12_SHA)
  native=r12.Native(native_path); rec['runtime_cpu_flags']=int(native.flags)
  metric=mod(ANALYZE,'r17_metric',ANALYZE_SHA); unit=mod(metric.U,'r17_units',metric.USHA); helper=unit.helper()
  tracked_pre={'contract':CONTRACT,'admission':adp,'command':cmd,'producer':Path(ad['script']['path']),'parser':PARSER,'analyze':ANALYZE,'unit_helper':Path(unit.__file__),'native_source':native_source,'build':build_path,'library':native_path,'decoder_admission':Path(ad['decoder_admission']['path']),'syntax_binding':Path(ad['artifacts']['syntax_binding']['path']),'trace':Path(ad['trace']['path']),'token_manifest':Path(ad['token_manifest']['path']),'dc_header_log':DCLOG}; deps_before={k:ident(v) for k,v in tracked_pre.items()}
  dec=json.loads(exact(ad['decoder_admission']).read_text()); refs={k:unit.load_luma(exact(ad['source_boundaries'][k])) for k in ('original','coding_input','preloop','postloop')}; predref=unit.load_luma(exact(dec['artifacts']['predictor']))
  assert np.array_equal(refs['original'],refs['coding_input'])
  invoked={}; baseline={}; q4={}; dcs={}; rows=[]; coeff_off=pix_off=0
  for key,t in tokens.items():
   z=t['begin']; j=jmap[key]; assert j['begin']==z and j.get('info')==t.get('info') and j.get('end')==t.get('end') and j.get('commit')==t.get('commit') and j.get('payload_offsets')==t.get('payload_offsets')
   assert len(j.get('stages',[]))==len(t.get('stages',[]))
   for js,ts in zip(j.get('stages',[]),t.get('stages',[])):
    assert {k:v for k,v in js.items() if k not in ('q','dq','inverse')} == {k:v for k,v in ts.items() if k not in ('q','dq','inverse')}
   if not t['stages']:
    assert t.get('info') is None and t['end']['eob']==0; continue
   info=t.get('info'); assert isinstance(info,dict) and isinstance(info.get('actual_qindex'),int) and info['depth']==10
   n=int(z['n']); assert n==len(t['raw'])==len(t['scan'])==len(t['iscan'])<=1024 and z['w']*z['h']<=4096
   assert t['predictor'].shape==(z['h'],z['w']) and t['raw_inverse'].shape==(z['h'],z['w'])
   explicit=[int(info[k]) for k in ('dc_delta','y_dc_delta') if k in info]; delta=explicit[0] if explicit else dc_delta
   assert all(v==delta for v in explicit); assert np.array_equal(gen_tables(native,r12,int(info['actual_qindex']),delta),t['tables'][[0,1,6]])
   cap=t['stages'][0]; assert cap['stage']=='scalar_fp'; b=native.paired(t,0,t['tables']); assert b['eob']==cap['eob']
   for f in ('q','dq','inverse'): assert np.array_equal(b[f],cap[f]),(key,'baseline',f)
   rawc=native.inverse(t,t['raw'],t['raw_eob'],0); rawr=native.inverse(t,t['raw'],t['raw_eob'],1); assert np.array_equal(rawc,rawr) and np.array_equal(rawr,t['raw_inverse'])
   table=t['tables'].copy(); table[[0,1,6]]=gen_tables(native,r12,4,delta); assert np.array_equal(table[[2,3,4,5]],t['tables'][[2,3,4,5]])
   q=native.paired(t,0,table); invoked[key]=t; baseline[key]=b; q4[key]=q; dcs[str(key)]=delta
   rows.append({'token':int(key),'coefficient_offset':coeff_off,'pixel_offset':pix_off,'n':n,'native_wh':[int(z['w']),int(z['h'])],'tx':int(z['tx']),'type':int(z['type']),'eob_baseline':int(b['eob']),'eob_q4':int(q['eob']),'dc_delta':delta,'qindex_baseline':int(info['actual_qindex'])}); coeff_off+=n; pix_off+=z['w']*z['h']
  assert len(tokens)==2870 and len(invoked)==2169 and len(tokens)-len(invoked)==701 and sum(len(t['stages'])==2 for t in tokens.values())==39
  assert invoked
  frames={}; masks={}
  for selector in ('predictor','raw','scalar','final'):
   frames[selector],masks[selector]=frame_for(tokens,selector)
  q4frame,_=frame_for({k:{**t,'stages':[{'inverse':q4[k]['inverse']}] } if k in q4 else t for k,t in tokens.items()},'final'); frames['q4']=q4frame
  assert np.array_equal(frames['predictor'][masks['predictor']],predref[masks['predictor']]); assert np.array_equal(frames['final'][masks['final']],refs['preloop'][masks['final']])
  fullroi={}; decomposition={}; strata={}; original=refs['original']
  invmask=np.zeros((H,W),bool)
  for k,t in invoked.items(): z=t['begin']; x,y,w,h=(int(z[v]) for v in ('x','y','w','h')); invmask[y:y+h,x:x+w]=True
  for name,box in BOXES.items():
   fullroi[name]={s:metric.descriptor(unit,helper,crop(original,box),crop(frames[s],box)) for s in ('predictor','raw','scalar','final','q4')}
   roi=np.zeros((H,W),bool); x,y,w,h=box; roi[y:y+h,x:x+w]=True; decomposition[name]={}
   for pop,mask in (('all',roi),('invoked',roi&invmask),('uninvoked',roi&~invmask)):
    decomposition[name][pop]={s:sse(frames[s],original,mask) for s in ('predictor','raw','scalar','final','q4')}
   for stage in ('predictor','raw','scalar','final','q4'):
    assert abs(decomposition[name]['all'][stage]['sse']-decomposition[name]['invoked'][stage]['sse']-decomposition[name]['uninvoked'][stage]['sse'])<1e-8
   strata[name]={}
   for pop,popmask in (('invoked',invmask),('uninvoked',~invmask)):
    strata[name][pop]={}
    sizes=sorted({f"{int(t['begin']['w'])}x{int(t['begin']['h'])}" for t in (invoked.values() if pop=='invoked' else tokens.values())})
    for size in sizes:
     txmask=np.zeros((H,W),bool)
     for t in tokens.values():
      z=t['begin']; key=f"{int(z['w'])}x{int(z['h'])}"; x0,y0,w0,h0=(int(z[v]) for v in ('x','y','w','h'))
      if key==size and ((t in invoked.values()) if pop=='invoked' else (t not in invoked.values())): txmask[y0:y0+h0,x0:x0+w0]=True
     mask=roi&popmask&txmask; hp=int((mask[:,:-1]&mask[:,1:]).sum()+(mask[:-1,:]&mask[1:,:]).sum()); ac=int((mask[:-1,:-1]&mask[1:,:-1]&mask[:-1,1:]&mask[1:,1:]).sum())
     strata[name][pop][size]={'pixels':int(mask.sum()),'hf_pair_support':hp,'acf1_support':ac,'sse':{s:sse(frames[s],original,mask) for s in ('raw','scalar','final','q4')}}
  arrays={}
  for nm,dct in (('baseline',baseline),('q4',q4)):
   arrays[nm+'_q']=np.concatenate([v['q'] for v in dct.values()]); arrays[nm+'_dq']=np.concatenate([v['dq'] for v in dct.values()]); arrays[nm+'_inverse']=np.concatenate([v['inverse'].ravel() for v in dct.values()]); arrays[nm+'_eob']=np.asarray([v['eob'] for v in dct.values()],dtype='<u2')
  arrays['raw_inverse']=np.concatenate([t['raw_inverse'].ravel() for t in invoked.values()]); arrays['token_ids']=np.asarray(list(invoked),dtype='<u8'); np.savez_compressed(a.out/'native-arrays.npz',**arrays)
  np.savez_compressed(a.out/'mosaics.npz',**{k:v.astype('<f4') for k,v in frames.items()})
  (a.out/'tokens.json').write_text(json.dumps(rows,indent=2)+'\n')
  deps=deps_before; deps_after={k:ident(Path(v['path'])) for k,v in deps.items()}; assert deps_after==deps
  rec['inputs_before']=deps; rec['inputs_after']=deps_after
  rec.update(status='complete',token_count=len(tokens),invoked=len(invoked),uninvoked=len(tokens)-len(invoked),invoked_pixels=int(invmask.sum()),runtime_cpu_flags=int(native.flags),dc_delta_by_token=dcs,dc_evidence={'event_index':314,'coded_ordinal':210,'delta_q_y_dc':0,'trace_log':ident(DCLOG)},control_counts={'tokens':len(tokens),'invoked':len(invoked),'uninvoked':len(tokens)-len(invoked),'two_stage_tokens':sum(len(t['stages'])==2 for t in tokens.values()),'positive_eob_tokens':sum(int(t['end']['eob'])>0 for t in tokens.values())},full_roi=fullroi,error_decomposition=decomposition,transform_strata=strata,arrays=ident(a.out/'native-arrays.npz'),mosaics=ident(a.out/'mosaics.npz'),token_map=ident(a.out/'tokens.json'),dependencies=deps,scope='fixed-decision invoked-token q4 only; uninvoked predictors descriptive; no rate/deployment claim')
  (a.out/'result.json').write_text(json.dumps(rec,indent=2,allow_nan=False)+'\n')
 except BaseException as e: rec.update(status='failed',error=repr(e)); raise
 finally: rec['ended_utc']=dt.datetime.now(dt.timezone.utc).isoformat(); rec['seconds']=time.monotonic()-start; rp.write_text(json.dumps(rec,indent=2)+'\n')
if __name__=='__main__': main()
