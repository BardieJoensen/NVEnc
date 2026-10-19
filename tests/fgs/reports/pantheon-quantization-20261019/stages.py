#!/usr/bin/env python3
"""Read native final-TU records and verify independently assembled stages."""
import sys,struct,json
import numpy as np
from study import ROOT,OLD,x
from texture import desc,corr,BOXES
W,H=1920,1080
def read(p):
 out={}
 with open(p,'rb') as f:
  while b:=f.read(40):
   name=b[:32].split(b'\0')[0].decode();n,size=struct.unpack('<II',b[32:]);v=f.read(n*size);assert len(v)==n*size
   if name.endswith('meta') or name=='meta':out[name]=json.loads(v)
   else:out[name]=np.frombuffer(v,dtype='<i4' if size==4 else ('<i2' if name=='prediction_residual' else '<u2')).copy()
 return out
def analyze(case,tag):
 d=ROOT/case;n=134 if case=='e04' else 120;poc=n+96
 src=np.memmap(d/'source.yuv',dtype='<u2',mode='r',shape=(240,W*H*3//2))[n,:W*H].reshape(H,W).astype(float)/4
 names=['input','predictor','actual_recon','unquantized','scalar0_recon','scalar1_recon','scalar2_recon','initial_recon','rdoq_recon','final_recon']
 maps={k:np.full((H,W),np.nan) for k in names};coverage=np.zeros((H,W),int);qmap=np.full((H,W),np.nan);skipmap=qmap.copy();rows=[];transform_errors=[];flags={'forward_exact':True,'private_final_recon_exact':True,'source_minus_predictor_exact':True};coeffstats=[]
 for p in sorted((d/(tag+'-detail')).glob('*.tu')):
  r=read(p);m=r['meta'];xx,yy,w,h=[m[k] for k in ('x','y','w','h')];sl=np.s_[yy:min(H,yy+h),xx:min(W,xx+w)];hh,ww=coverage[sl].shape
  assert m['poc']==poc and m['bypass']==0
  coverage[sl]+=1;qmap[sl]=m['effective_qindex'];skip=m['skip_mode'] or m['md_skip'];skipmap[sl]=skip
  flags['source_minus_predictor_exact'] &= np.array_equal(r['input'].astype(int)-r['predictor'].astype(int),r['prediction_residual'])
  if 'actual_forward' in r:
   flags['forward_exact'] &= np.array_equal(r['private_forward'][:len(r['actual_forward'])],r['actual_forward'])
   flags['private_final_recon_exact'] &= np.array_equal(r['actual_recon'],r['final_recon'])
   assert r['quant_meta']['effective_qindex']==m['effective_qindex']
  for k in names:
   # A skip is exactly predictor: no quantizer stage ran. Never fill with stale coeffs.
   a=r.get(k,r['predictor'] if k in ('initial_recon','rdoq_recon','final_recon') else None);assert a is not None,k
   maps[k][sl]=a.reshape(h,w)[:hh,:ww]/4
  c={'meta':m,'quant_meta':r.get('quant_meta'),'stages':{}}
  for k in ('private_forward','actual_forward','initial_qcoeff','rdoq_qcoeff','final_qcoeff','scalar0_qcoeff','scalar1_qcoeff','scalar2_qcoeff'):
   if k in r:c['stages'][k]={'nonzero':int(np.count_nonzero(r[k])),'sumabs':int(np.abs(r[k]).sum()),'sumsq':float(np.square(r[k].astype(float)).sum())}
  rows.append(c)
  err=(r['unquantized'].astype(float)-r['input'].astype(float)).reshape(h,w)/4
  transform_errors.append((m,err))
 assert np.all(coverage==1),(coverage.min(),coverage.max());assert all(flags.values()),flags
 checks={'all_visible_pixels_covered_once':True,**flags}
 if tag.startswith('detail'):
  for k,old in [('input','coding_input'),('actual_recon','pre_sb_dlf')]:
   a=np.fromfile(OLD/case/'selected-stages'/f'{old}-{poc:04d}-a0-o0.yuv',dtype='<u2',count=W*H).reshape(H,W)/4
   checks[k+'_matches_previous_stage']=np.array_equal(maps[k],a)
   assert checks[k+'_matches_previous_stage']
 roi=dict(BOXES[case]);roi.update({'center_control':[800,300,256,256],'top_control':[256,64,256,256]})
 summaries={}
 for name,(xx,yy,w,h) in roi.items():
  sl=np.s_[yy:yy+h,xx:xx+w];ss=src[sl];inp=maps['input'][sl]
  summaries[name]={'source':desc(ss),'qindex':{'min':float(qmap[sl].min()),'mean':float(qmap[sl].mean()),'max':float(qmap[sl].max())},'skip_area_fraction':float(skipmap[sl].mean()),'stages':{}}
  for k,a in maps.items():
   z=a[sl];summaries[name]['stages'][k]={**desc(z),'mae_to_source':float(np.abs(z-ss).mean()),'hf_corr_source':corr(x.high_pass(z),x.high_pass(ss)),'mae_to_input':float(np.abs(z-inp).mean())}
  ids=[r for r in rows if r['meta']['x']>=xx and r['meta']['y']>=yy and r['meta']['x']+r['meta']['w']<=xx+w and r['meta']['y']+r['meta']['h']<=yy+h]
  summaries[name]['fully_contained_tus']=len(ids)
  groups={}
  for m,err in transform_errors:
   bx,by,bw,bh=[m[k] for k in ('x','y','w','h')];l,t=max(bx,xx),max(by,yy);right,bottom=min(bx+bw,xx+w),min(by+bh,yy+h)
   if l>=right or t>=bottom:continue
   e=err[t-by:bottom-by,l-bx:right-bx];g=groups.setdefault(f'{bw}x{bh}',{'pixels':0,'sum_absolute_error':0.,'sse':0.,'max_error':0.})
   g['pixels']+=int(e.size);g['sum_absolute_error']+=float(abs(e).sum());g['sse']+=float((e**2).sum());g['max_error']=max(g['max_error'],float(abs(e).max()))
  summaries[name]['unquantized_error_by_transform']=groups
  summaries[name]['coefficient_proxies']={k:{stat:sum(r['stages'].get(k,{}).get(stat,0) for r in ids) for stat in ('nonzero','sumabs','sumsq')} for k in ('private_forward','actual_forward','initial_qcoeff','rdoq_qcoeff','final_qcoeff','scalar0_qcoeff','scalar1_qcoeff','scalar2_qcoeff')}
 np.savez_compressed(d/(tag+'-stages.npz'),source=src,qindex=qmap,skip=skipmap,**maps)
 x.dump(d/(tag+'-stages.json'),{'case':case,'frame':n,'checks':checks,'roi':summaries,'blocks':rows,'proxies_are_not_bits':True})
 print(case,tag,'validation',checks,flush=True)
 for name in BOXES[case]:
  s=summaries[name];print(name,s['qindex'],'skip',s['skip_area_fraction'],'sourceHF',s['source']['hf_sigma'],{k:round(v['hf_sigma'],4) for k,v in s['stages'].items()},flush=True)
if __name__=='__main__':analyze(*sys.argv[1:])
