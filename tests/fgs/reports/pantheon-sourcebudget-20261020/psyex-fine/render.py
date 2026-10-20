#!/usr/bin/env python3
"""Render native-size rounded-luma R13 fixed-ROI panels from admitted arrays."""
import argparse,datetime as dt,hashlib,importlib.util,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
R11=ROOT/'parent/psyex-coeff-r11'; R12=ROOT/'parent/psyex-scalar-r12'; RUN=HERE/'run-1'
R13_RESULT_SHA='4511e7223f5c9b8b721e5d2f8c5d01d062ffb5d981bd106ae85ff59e0e1dbb93'
R13_ARRAYS_SHA='11927240f6279d39f491885ab5b50ccd1b89da57ff59830b7265c8372719af09'
R12_RESULT_SHA='9caf06214e249306788a6e58a22d134ed86284b4183fb38f815d8ccf236029d9'
R12_ARRAYS_SHA='aaee0f9c89623023e5c0d541c38241092950e99e3f48e46de4544bc5caf9799c'
ANALYZE_SHA='44b8037c2a922b7e893cd66c8488f3683c45b8859400ff6b082bd0910286f64e'
BOXES={'shirt':(1200,650,200,100),'background':(950,50,250,180),'face':(160,600,500,480)}

def ident(p):
 p=Path(p).resolve()
 with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
 return {'path':str(p),'sha256':h,'size':p.stat().st_size}
def mod(p,name,sha):
 assert ident(p)['sha256']==sha
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def close(a,b,tol=1e-12):
 if isinstance(a,dict):
  assert a.keys()==b.keys()
  for k in a:close(a[k],b[k],tol)
 elif isinstance(a,list):
  assert len(a)==len(b)
  for x,y in zip(a,b):close(x,y,tol)
 elif isinstance(a,(int,float)) and isinstance(b,(int,float)): assert abs(float(a)-float(b))<=tol
 else: assert a==b

def main():
 ap=argparse.ArgumentParser();ap.add_argument('out',type=Path);args=ap.parse_args();out=args.out
 assert not out.exists();out.mkdir(parents=True)
 result_path=RUN/'result.json';arrays_path=RUN/'q1-arrays.npz';assert ident(result_path)['sha256']==R13_RESULT_SHA;assert ident(arrays_path)['sha256']==R13_ARRAYS_SHA
 result=json.loads(result_path.read_text());assert result['status']=='admitted_diagnostic'
 r12p=R12/'run-1/result.json';r12a=R12/'run-1/native-arrays.npz';assert ident(r12p)['sha256']==R12_RESULT_SHA;assert ident(r12a)['sha256']==R12_ARRAYS_SHA
 prior=json.loads(r12p.read_text());assert prior['r11_admission']==ident(R11/'admitted-1/admission.json')
 assert result['r12_result']==ident(r12p) and result['r12_arrays']==ident(r12a)
 a=mod(R11/'analyze.py','r11',ANALYZE_SHA);v=mod(R11/'validate.py','r11v',a.VSHA);u=a.mod(a.U,'r10h',a.USHA);h=u.helper()
 ad=json.loads((R11/'admitted-1/admission.json').read_text());tokens,terminal=v.parse(a.exact(ad['trace']));assert len(tokens)==2907 and terminal==ad['terminal']
 refs_ad=json.loads(a.exact(ad['decoder_admission']).read_text());refs={s:u.load_luma(a.exact(refs_ad['r9_stages'][s])) for s in ('original','coding_input')}
 prior_units={r['token']:r for r in prior['units']};invoked={k:t for k,t in tokens.items() if t['stages']};assert len(invoked)==2187
 r12=np.load(r12a,allow_pickle=False);r12_arrays={k:r12[k] for k in r12.files};r12.close()
 r13=np.load(arrays_path,allow_pickle=False);r13_arrays={k:r13[k] for k in r13.files};r13.close()
 shape=(1080,1920);frames={s:np.full(shape,np.nan) for s in ('original','coding_input','raw','baseline_fp','q32_fp','q1_fp')}
 frames['original']=refs['original'];frames['coding_input']=refs['coding_input'];offset=0;po=0
 for key,t in tokens.items():
  z=t['begin'];x,y,w,hh=(z[k] for k in ('x','y','w','h'));vh=min(hh,1080-y);sl=np.s_[y:y+vh,x:x+w];pred=t['predictor'][:vh].astype(float)/4
  frames['raw'][sl]=t.get('raw_inverse',t['predictor'])[:vh].astype(float)/4
  if key in invoked:
   row=prior_units[key];n=z['n'];pix=w*hh;assert row['coefficient_offset']==offset and row['pixel_offset']==po
   frames['baseline_fp'][sl]=r12_arrays['fp_baseline_inverse'][po:po+pix].reshape(hh,w)[:vh].astype(float)/4
   frames['q32_fp'][sl]=r12_arrays['fp_q32_inverse'][po:po+pix].reshape(hh,w)[:vh].astype(float)/4
   frames['q1_fp'][sl]=r13_arrays['q1_inverse'][po:po+pix].reshape(hh,w)[:vh].astype(float)/4
   offset+=n;po+=pix
  else:
   for s in ('baseline_fp','q32_fp','q1_fp'):frames[s][sl]=pred
 assert offset==r12_arrays['fp_baseline_q'].size and po==r12_arrays['fp_baseline_inverse'].size
 for roi,box in BOXES.items():
  ref=a.crop(frames['original'],box)
  for name in ('baseline_fp','q32_fp'):
   d=a.descriptor(u,h,ref,a.crop(frames[name],box));prior_name='fp_baseline' if name=='baseline_fp' else 'fp_q32';close(d,prior['fixed_roi'][roi]['stages'][prior_name])
 manifest={'status':'prepared','source_fields':{'original':ident(refs_ad['r9_stages']['original']['path']),'coding_input':ident(refs_ad['r9_stages']['coding_input']['path']),'r11_trace':ident(ad['trace']['path']),'r13_result':ident(result_path),'r13_arrays':ident(arrays_path),'r12_result':ident(r12p),'r12_arrays':ident(r12a)},'stages':list(frames),'rois':{}}
 try: font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',12)
 except OSError: font=None
 for roi,(x,y,w,hgt) in BOXES.items():
  names=('original','coding_input','raw','baseline_fp','q32_fp','q1_fp');pad=18;labelh=20;canvas=Image.new('L',(3*w+4*pad,2*(hgt+labelh)+3*pad),0);draw=ImageDraw.Draw(canvas);entries=[]
  for i,name in enumerate(names):
   rr=i//3;cc=i%3;crop=np.rint(np.clip(frames[name][y:y+hgt,x:x+w],0,255)).astype('uint8');im=Image.fromarray(crop,'L');px=pad+cc*(w+pad);py=pad+rr*(hgt+labelh+pad);canvas.paste(im,(px,py+labelh));draw.text((px,py),name,fill=255,font=font);entries.append({'stage':name,'xywh':[px,py+labelh,w,hgt],'pixels_native':True})
  p=out/f'{roi}-6panel.png';canvas.save(p);manifest['rois'][roi]={'xywh':[x,y,w,hgt],'panel':ident(p),'entries':entries,'rounding':'np.rint then uint8; source arrays already /4','resized':False}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'status':'complete','manifest':ident(out/'manifest.json')}))
if __name__=='__main__':main()
