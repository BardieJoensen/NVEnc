#!/usr/bin/env python3
"""R11 actual-stage observations, original-referenced and diagnostic only."""
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
import numpy as np
R=Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020')
P=R/'parent/psyex-coeff-r11';V=P/'validate.py'
VSHA='258db37595666efa153d6fc526d42de371fe0a7f0b21bff7c3334e84238378f3'
U=R/'worker/decoder-r10-analysis/analyze_decoder_units.py'
USHA='d10bfb16859ad02f59ba876b7890f591fee592b690d4c65a6aa0f043a7ae3cb3'
BOXES={'shirt':(1200,650,200,100),'background':(950,50,250,180),'face':(160,600,500,480)}
STAGES=('predictor','raw_executed','scalar','after_fast_or_requant','after_optimize','final')
def ident(p):
 p=Path(p).resolve()
 with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
 return dict(path=str(p),sha256=h,size=p.stat().st_size)
def exact(d):
 assert ident(d['path'])==d,d
 return Path(d['path'])
def mod(p,n,sha):
 assert ident(p)['sha256']==sha
 sp=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
def images(t):
 pred=t['predictor'];out={'predictor':pred,'raw_executed':t.get('raw_inverse',pred)}
 if t['stages']:
  current=t['stages'][0]['inverse'];assert t['stages'][0]['stage'] in ('scalar_fp','scalar_b')
 else:current=pred
 out['scalar']=current
 for stage in t['stages']:
  if stage['stage'] in ('fast_opt','requant_b'):current=stage['inverse']
 out['after_fast_or_requant']=current
 for stage in t['stages']:
  if stage['stage']=='optimize_b':current=stage['inverse']
 out['after_optimize']=current;out['final']=t['reconstruction']
 return out
def coeff_stats(c):
 q=c.astype(np.int64)
 return dict(count=len(q),nonzero=int(np.count_nonzero(q)),nonzero_excluding_index0=int(np.count_nonzero(q[1:])),
             l1=int(np.abs(q).sum()),squared_l2=int((q*q).sum()),max_abs=int(np.abs(q).max()))
def descriptor(unit_helper,h,ref,z):
 assert ref.shape==z.shape and ref.size and np.isfinite(ref).all() and np.isfinite(z).all()
 d=unit_helper.descriptor(h,ref,z)
 dx=np.abs(np.diff(z,axis=1)-np.diff(ref,axis=1))
 dy=np.abs(np.diff(z,axis=0)-np.diff(ref,axis=0))
 support=dx.size+dy.size
 d['gradient_mae']=float((dx.sum()+dy.sum())/support) if support else None
 d['gradient_support']=support;d['pixels']=ref.size
 return d
def crop(a,box):
 x,y,w,h=box;return a[y:y+h,x:x+w]
def make_mosaics(tokens,shape=(1080,1920),boxes=BOXES):
 frames={k:np.full(shape,np.nan) for k in STAGES};covered=np.zeros(shape,dtype=bool)
 for t in tokens.values():
  z=t['begin'];x,y,w,h=(z[k] for k in ('x','y','w','h'));vh=min(h,shape[0]-y)
  sl=np.s_[y:y+vh,x:x+w];assert not covered[sl].any();covered[sl]=True
  for name,a in images(t).items():
   assert a.shape==(h,w) and np.all(a<=1023)
   frames[name][sl]=a[:vh].astype(np.float64)/4
 for box in boxes.values():
  assert crop(covered,box).all()
  for f in frames.values():assert np.isfinite(crop(f,box)).all()
 return frames,covered
def smoke():
 pred=np.full((4,4),400,dtype='<u2')
 t={'begin':dict(x=0,y=0,w=4,h=4),'predictor':pred,'raw_inverse':pred+8,'reconstruction':pred+4,
    'stages':[dict(stage='scalar_b',inverse=pred+12),dict(stage='optimize_b',inverse=pred+4),dict(stage='final',inverse=pred+4)]}
 skipped={'begin':dict(x=4,y=0,w=4,h=4),'predictor':pred,'reconstruction':pred,'stages':[]}
 f,c=make_mosaics({1:t,2:skipped},shape=(8,8),boxes={'test':(0,0,8,4)})
 assert not c[4:].any() and np.isnan(f['final'][4:]).all()
 assert f['scalar'][0,0]==103 and f['raw_executed'][0,0]==102 and f['after_fast_or_requant'][0,0]==103
 assert f['after_optimize'][0,0]==f['final'][0,0]==101
 assert all(a[0,4]==100 for a in f.values())
 assert coeff_stats(np.array([4,0,-2],dtype='i4'))['nonzero_excluding_index0']==1
 print('mosaic/carry-forward/scaling/ROI-only support smoke passed')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('admitted',type=Path,nargs='?');ap.add_argument('output',type=Path,nargs='?');ap.add_argument('--smoke',action='store_true');a=ap.parse_args()
 if a.smoke:smoke();return
 assert a.admitted and a.output and not a.output.exists()
 script_before=ident(__file__)
 ad=json.loads(a.admitted.read_text());assert ad['status']=='admitted'
 assert ad['script']==ident(V) and ad['script']['sha256']==VSHA
 for key in ('all336_exact','source_predictor_preloop_exact','final_dq_eob_iqm_exact','actual_committed_owner'):assert ad[key] is True
 for key in ('pins','trace','boundary','decoder_admission','targets','token_manifest'):exact(ad[key])
 v=mod(V,'r11_admission',VSHA);u=mod(U,'r10_unit_helpers',USHA);h=u.helper()
 r9analysis=R/'parent/psyex-boundary-r9/analysis-1.json'
 assert ident(r9analysis)['sha256']=='b2d4a19ac93eeab29cb78870cea45f03165f7741f22584955081498553ed5bc5'
 inherited_helpers=json.loads(r9analysis.read_text())['metric_helpers']
 for d in inherited_helpers.values():exact(d)
 tokens,terminal=v.parse(exact(ad['trace']));assert terminal==ad['terminal'] and len(tokens)==ad['tokens']
 joins=json.loads(exact(ad['token_manifest']).read_text());jmap={r['token']:r for r in joins}
 assert set(tokens)==set(jmap)
 dec=json.loads(exact(ad['decoder_admission']).read_text())
 refs={name:u.load_luma(exact(dec['r9_stages'][name])) for name in ('original','coding_input','postloop')}
 refs.update({name:u.load_luma(exact(dec['artifacts'][name])) for name in ('predictor','preloop')})
 units=json.loads(exact(dec['artifacts']['units']).read_text())
 frames,covered=make_mosaics(tokens)
 assert np.array_equal(frames['predictor'][covered],refs['predictor'][covered])
 assert np.array_equal(frames['final'][covered],refs['preloop'][covered])
 frames.update({k:refs[k] for k in ('original','coding_input','postloop')})
 frames['preloop']=refs['preloop']
 original=refs['original'];fullroi={}
 for name,box in BOXES.items():
  fullroi[name]={'xywh':list(box),'stages':{s:descriptor(u,h,crop(original,box),crop(f,box)) for s,f in frames.items()}}
 rows=[];invocations={};changed={};comparisons={}
 for token,t in tokens.items():
  j=jmap[token];z=t['begin'];uid=j['unit'];unit=units[uid]
  assert j['begin']==z and j['end']==t['end'] and j['commit']==t['commit']
  x,y,w,hh=(z[k] for k in ('x','y','w','h'));vh=min(hh,1080-y);box=(x,y,w,vh)
  stage_images={s:im[:vh].astype(np.float64)/4 for s,im in images(t).items()}
  ref=crop(original,box)
  row=dict(token=token,unit=uid,category=unit['category'],xywh=list(box),native_wh=[w,hh],
           final_encdec_quantizer_invoked=bool(t['stages']),actual_quantizer=t.get('info'),
           full_visible_tu={s:descriptor(u,h,ref,im) for s,im in stage_images.items()},
           coefficients=[],intersections={})
  if 'raw' in t:row['raw_coefficients']=dict(**coeff_stats(t['raw']),eob=t['raw_eob'])
  previous=None
  for s in t['stages']:
   name=s['stage'];invocations[name]=invocations.get(name,0)+1
   changed.setdefault(name,0);comparisons.setdefault(name,0)
   change=None if previous is None else bool(not np.array_equal(s['q'],previous['q']) or not np.array_equal(s['dq'],previous['dq']) or s['eob']!=previous['eob'])
   if previous is not None:comparisons[name]+=1
   if change:changed[name]=changed.get(name,0)+1
   row['coefficients'].append(dict(stage=name,eob=s['eob'],q=coeff_stats(s['q']),dq=coeff_stats(s['dq']),changed_from_previous=change,
                                  full_visible_tu=descriptor(u,h,ref,s['inverse'][:vh].astype(np.float64)/4)))
   previous=s
  for roi,rbox in BOXES.items():
   q=u.overlap(*box,*rbox)
   if q:
    xx,yy,ww,h2=q;sl=np.s_[yy-y:yy-y+h2,xx-x:xx-x+ww]
    row['intersections'][roi]=dict(xywh=list(q),pixels=ww*h2,stages={s:descriptor(u,h,ref[sl],im[sl]) for s,im in stage_images.items()})
  rows.append(row)
 aggregates={}
 for roi in BOXES:
  aggregates[roi]={}
  for population in ('all','positive_eob','absent_residual'):
   selected=[r for r in rows if roi in r['intersections'] and (population=='all' or (r['category']==4)==(population=='positive_eob'))]
   weights=[r['intersections'][roi]['pixels'] for r in selected];out={}
   for s in STAGES:
    ds=[r['intersections'][roi]['stages'][s] for r in selected]
    out[s]={k:u.stat([d.get(k) for d in ds],weights) for k in ('hf_sigma','hf_sigma_abs_error','acf1_abs_error','hf_corr_source')}
    out[s]['gradient_mae']=u.stat([d.get('gradient_mae') for d in ds],[d['gradient_support'] for d in ds])
    out[s]['mse']=u.stat([d['pixel_error']['mse'] for d in ds],weights)
   aggregates[roi][population]=dict(units=len(selected),pixels=sum(weights),stages=out)
 assert len([r for r in rows if r['unit'] in ad['shirt_positive_ids']])==24
 result=dict(status='complete',scope='single-frame actual stages and local fixed-predictor diagnostics; no deployable encode, entropy bits or playback inference',
  admission=ident(a.admitted),script=script_before,validator=ident(V),metric_helpers={'units':ident(U),'boundary':ident(u.HELPER),**inherited_helpers},
  command={'argv':sys.argv,'python':ident(sys.executable)},source_reference=dec['r9_stages']['original'],
  stage_semantics={'raw_executed':'native inverse of raw coefficients only where forward transform actually ran; skipped calls retain predictor',
   'scalar':'first actual scalar result; skipped calls retain predictor','after_fast_or_requant':'carry scalar unless actual fast optimization or B requantization ran',
   'after_optimize':'carry preceding result unless actual full optimizer ran','final':'actual preloop reconstruction after any noise normalization',
   'limitations':'native predictors are fixed, sequential local predictors; no altered recon/reference propagation; uncovered pixels excluded',
   'gradient_mae':'mean absolute error of horizontal and vertical adjacent-sample differences, eight-bit-equivalent code values; aggregates weighted by gradient sample-pair support',
   'aggregate_semantics':'full-ROI descriptors primary; pixel-weighted per-intersection HF/ACF are nonlinear descriptive summaries, not additive loss fractions',
   'change_counts':'comparison count excludes the first scalar stage, which has no preceding quantized stage; invoked zero-change stages appear explicitly'},
  covered_pixels=int(covered.sum()),fixed_roi=fullroi,aggregates=aggregates,units=rows,invocations=invocations,numerically_changed=changed,change_comparisons=comparisons)
 a.output.parent.mkdir(parents=True,exist_ok=True)
 assert ident(__file__)==script_before
 for d in inherited_helpers.values():exact(d)
 with a.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
 print(json.dumps({'status':'complete','output':ident(a.output),'units':len(rows)}))
if __name__=='__main__':
 if not __debug__:raise SystemExit('optimized Python prohibited')
 main()
