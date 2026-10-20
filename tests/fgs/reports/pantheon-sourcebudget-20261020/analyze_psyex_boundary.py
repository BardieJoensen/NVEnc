#!/usr/bin/env python3
"""Analyze admitted R9 frame-boundary stages with frozen 858 controls.

This is a single-frame diagnostic. It binds the parent validator/admission and
uses the repository's exact ``analyze.paired`` descriptor implementation.
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPORT = Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-rd-20261019')
INDEP = Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-independent-20261019')
sys.path.insert(0, str(INDEP)); sys.path.insert(0, str(REPORT))
from texture import desc  # noqa: E402
import analyze as analyze_mod  # noqa: E402
from analyze import paired  # noqa: E402

W,H=1920,1080; CW,CH=W//2,H//2
STAGES=('original','coding_input','preloop','postloop')
CONTROLS=Path('/media/merged-storage/cold-storage/docker-apps/pantheon-quantization-20261019/e05-1440/whole-window-controls.json')
VALIDATOR=Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020/validate_psyex_boundary.py')
CONTROL_SHA='bd6a6bfef9b96dbdbc41fbbc136701ec2be2b2030e11e37a7b7ae08e0dc72884'
BOXES={'shirt':(1200,650,200,100),'background':(950,50,250,180),'face':(160,600,500,480)}
KINDS=('all','quiet','edge','flat_texture','other')
PLANES=('y','u','v')

def ident(p):
 p=Path(p).resolve(); return {'path':str(p),'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest(),'size':p.stat().st_size}
def exact_ident(obj, expected_size=None):
 assert isinstance(obj,dict) and all(k in obj for k in ('path','sha256','size')),obj
 got=ident(obj['path']); assert got=={k:obj[k] for k in ('path','sha256','size')},(got,obj)
 if expected_size is not None: assert got['size']==expected_size,got
 return Path(got['path'])
def load_frame(p):
 a=np.fromfile(p,dtype='<u2'); n=W*H+2*CW*CH; assert a.size==n,(p,a.size,n)
 return {'y':a[:W*H].reshape(H,W).astype(np.float64)/4,'u':a[W*H:W*H+CW*CH].reshape(CH,CW).astype(np.float64)/4,'v':a[W*H+CW*CH:].reshape(CH,CW).astype(np.float64)/4}
def plane_err(a,b):
 d=a-b; return {'mse':float(np.mean(d*d)),'mae':float(np.mean(np.abs(d))),'max_abs':float(np.max(np.abs(d))),'exact_fraction':float(np.mean(d==0))}
def pixel_errors(a,b):
 out={p:plane_err(a[p],b[p]) for p in PLANES}
 aa=np.concatenate([a[p].ravel() for p in PLANES]); bb=np.concatenate([b[p].ravel() for p in PLANES]); out['combined']=plane_err(aa,bb); return out
def luma_pair(src,z):
 q=paired(src,z); sd=desc(src)
 q['hf_abs_error']=abs(q['hf_sigma']-sd['hf_sigma'])
 q['signed_hf_delta']=q['hf_sigma']-sd['hf_sigma']
 for k in ('acf1','acf2','acf3','acf4','acf8'):
  q[k+'_abs_error']=(abs(q[k]-sd[k]) if q[k] is not None and sd[k] is not None else None)
 return q
def crop(a,x,y,w,h):
 cs=np.s_[y:y+h,x:x+w]; cc=np.s_[y//2:(y+h)//2,x//2:(x+w)//2]
 return {'y':a['y'][cs],'u':a['u'][cc],'v':a['v'][cc]}
def validate_admission(p):
 a=json.loads(Path(p).read_text()); assert a.get('status')=='admitted'; assert a.get('case')=='e05-1440'
 assert a.get('input_frame')==216 and a.get('scored_frame')==120 and a.get('dimensions')==[W,H] and a.get('pix_fmt')=='yuv420p10le'
 for k in ('all_attempts_exact_visible_coverage','postloop_exact_admitted_R8_frame','off_on_exact_original_IVF_and_recon'): assert a.get(k) is True,k
 assert isinstance(a.get('terminal'),dict) and 'Single-frame' in a.get('scope','')
 assert isinstance(a.get('stages'),dict)
 assert a.get('script') == ident(VALIDATOR), (a.get('script'), ident(VALIDATOR))
 paths={s:exact_ident(a['stages'][s],(W*H+2*CW*CH)*2) for s in STAGES}
 return a,paths
def check_controls():
 assert ident(CONTROLS)['sha256']==CONTROL_SHA,(ident(CONTROLS),CONTROL_SHA)
 c=json.loads(CONTROLS.read_text()); rows=[r for r in c['tiles'] if r.get('frame')==120]
 assert len(rows)==858 and len({(r['x'],r['y']) for r in rows})==858
 return c,rows
def descriptor_assert(got,expected):
 for k,v in expected.items():
  if v is None: assert got[k] is None,(k,got[k],v)
  else: assert got[k] is not None and np.isclose(got[k],v,rtol=1e-10,atol=1e-10),(k,got[k],v)
def stats(vals):
 v=np.asarray([x for x in vals if x is not None],dtype=float)
 return {'total':len(vals),'evaluable':len(v),'mean':float(v.mean()) if len(v) else None,
         'p95':float(np.percentile(v,95)) if len(v) else None}
def luma8(a):
 """Input is already in 8-bit-equivalent code levels, from load_frame."""
 return np.clip(np.rint(a),0,255).astype(np.uint8)
def summarize(rows):
 out={}
 for kind in KINDS:
  for outside in (False,True):
   key=f'{kind}|outside={str(outside).lower()}'
   # Legacy controls define outside=False as the complete population;
   # outside=True narrows to explicitly outside-target tiles.
   pool=[r for r in rows if (kind=='all' or r['kind']==kind) and (not outside or r['outside_target'])]
   st={}
   for s in STAGES:
    lm=[r['stages'][s]['luma'] for r in pool]; pe=[r['stages'][s]['pixels'] for r in pool]
    def field(k): return stats([x.get(k) for x in lm])
    st[s]={'tiles':len(pool),'luma_mse':field('mse'),'hf_abs_error':field('hf_abs_error'),'acf1_abs_error':field('acf1_abs_error'),'signed_hf_delta':field('signed_hf_delta'),
      'pixel_mse':{p:stats([x[p]['mse'] for x in pe]) for p in PLANES+('combined',)}}
   out[key]=st
 return out
def main():
 if not __debug__: raise RuntimeError('Do not disable admission assertions')
 ap=argparse.ArgumentParser(); ap.add_argument('admission',type=Path); ap.add_argument('output',type=Path); ap.add_argument('--plot-dir',type=Path); a=ap.parse_args()
 assert not a.output.exists(); admission,paths=validate_admission(a.admission); stages={s:load_frame(paths[s]) for s in STAGES}; controls,control_rows=check_controls(); original=stages['original']
 whole={'stage_descriptors':{s:{p:desc(stages[s][p]) for p in PLANES} for s in STAGES},'stage_errors_to_original':{s:pixel_errors(stages[s],original) for s in STAGES},'pairwise_errors':{f'{x}_to_{y}':pixel_errors(stages[y],stages[x]) for x,y in zip(STAGES,STAGES[1:])}}
 roi={}
 for name,(x,y,w,h) in BOXES.items():
  ref=crop(original,x,y,w,h); roi[name]={'xywh':[x,y,w,h],'stages':{s:{'luma':luma_pair(ref['y'],crop(stages[s],x,y,w,h)['y']),'pixels':pixel_errors(crop(stages[s],x,y,w,h),ref)} for s in STAGES}}
 tiles=[]
 for r in control_rows:
  x,y=int(r['x']),int(r['y']); ref=crop(original,x,y,32,32); descriptor_assert(desc(ref['y']),r['source']); ts={}
  for s in STAGES:
   z=crop(stages[s],x,y,32,32); ts[s]={'luma':luma_pair(ref['y'],z['y']),'pixels':pixel_errors(z,ref)}
  tiles.append({'x':x,'y':y,'kind':r['kind'],'outside_target':bool(r['outside_target']),'source':r['source'],'stages':ts})
 visual_artifacts={}
 if a.plot_dir:
  from PIL import Image, ImageDraw
  import matplotlib.pyplot as plt
  a.plot_dir.mkdir(parents=True,exist_ok=False)
  # load_frame already converted raw10 to 8-bit-equivalent sample levels.
  # These rounded luma views preserve pixel geometry, not exact10bit samples.
  panel_images=[]
  for s in STAGES:
   arr=luma8(stages[s]['y'])
   im=Image.fromarray(arr,'L'); im.save(a.plot_dir/f'native-luma-{s}.png'); panel_images.append(im)
  panel=Image.new('L',(W*2,H*2),0)
  for i,im in enumerate(panel_images): panel.paste(im,((i%2)*W,(i//2)*H))
  panel.save(a.plot_dir/'native-luma-panels.png')
  for name,(x,y,w,h) in BOXES.items():
   strip=Image.new('L',(4*w,h+30),0); draw=ImageDraw.Draw(strip)
   for i,(s,im) in enumerate(zip(STAGES,panel_images)):
    strip.paste(im.crop((x,y,x+w,y+h)),(i*w,30)); draw.text((i*w+3,5),s,fill=255)
   strip.save(a.plot_dir/(name+'-luma-boundaries.png'))
  (a.plot_dir/'README.md').write_text('Single-frame luma views at native pixel geometry. '
   '10-bit samples divided by4 once, rounded/clipped to8-bit luma code values. '
   'No RGB/color or motion/playback assessment. Exact samples remain in admitted raw frames. '
   'Full contact sheet: original/coding input top row; preloop/postloop bottom row.\n')
  fig,ax=plt.subplots(1,2,figsize=(12,5))
  for name in BOXES:
   ax[0].plot(STAGES,[roi[name]['stages'][s]['luma']['hf_sigma'] for s in STAGES],marker='o',label=name)
   ax[1].plot(STAGES,[roi[name]['stages'][s]['luma']['acf1'] for s in STAGES],marker='o',label=name)
  for q,t in zip(ax,('HF sigma','ACF1')): q.set_title(t); q.set_xticks(range(4),STAGES,rotation=25); q.legend()
  fig.tight_layout(); fig.savefig(a.plot_dir/'texture-boundary-panels.png',dpi=150); plt.close(fig)
  visual_artifacts={p.name:ident(p) for p in a.plot_dir.iterdir() if p.is_file()}
 report={'status':'complete','scope':'SINGLEFRAME','frame':120,'input_picture':216,'stages':list(STAGES),'whole_frame':whole,'roi':roi,'control_groups':summarize(tiles),'tiles':tiles,
  'controls':ident(CONTROLS),'admission':ident(a.admission),'validator':ident(VALIDATOR),'validator_admission':{k:admission[k] for k in ('status','input_frame','scored_frame','dimensions','pix_fmt','terminal')},'script':ident(__file__),
  'metric_helpers':{'analyze_py':ident(REPORT/'analyze.py'),'texture_py':ident(INDEP/'texture.py'),'high_pass_py':ident(Path(analyze_mod.x.__file__))},
  'group_semantics':{'outside=false':'Complete population, including inside and outside target','outside=true':'Only original frozen outside_target=true tiles','nullable_stats':'total and evaluable counts shown; undefined ACF excluded only from ACF aggregation'},
  'command':{'argv':sys.argv,'python':ident(sys.executable),'python_version':sys.version},
  'visual_artifacts':visual_artifacts,
  'interpretation':'Single-frame boundary descriptors only; no repair, bitrate, playback, or preservation claim.'}
 a.output.parent.mkdir(parents=True,exist_ok=True); a.output.open('x').write(json.dumps(report,indent=2,allow_nan=False)+'\n')
if __name__=='__main__': main()
