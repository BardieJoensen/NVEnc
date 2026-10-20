#!/usr/bin/env python3
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
import numpy as np
W,H=1920,1080
BOXES={'shirt':(1200,650,200,100),'background':(950,50,250,180),'face':(160,600,500,480)}
HELPER=Path('/home/bardie/git-repos/NVEnc/tests/fgs/reports/pantheon-sourcebudget-20261020/analyze_psyex_boundary.py'); HELPER_SHA='1027e9a0ec2a5f3b12a6aa908b97cad185df615fe48852a8acbe4daf5fb22ea3'; CONTROL=Path('/media/merged-storage/cold-storage/docker-apps/pantheon-quantization-20261019/e05-1440/whole-window-controls.json'); CONTROL_SHA='bd6a6bfef9b96dbdbc41fbbc136701ec2be2b2030e11e37a7b7ae08e0dc72884'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ident(p):p=Path(p).resolve();return {'path':str(p),'sha256':sha(p),'size':p.stat().st_size}
def exact(d):assert ident(d['path'])=={k:d[k] for k in ('path','sha256','size')};return Path(d['path'])
def load_luma(p):
 a=np.fromfile(p,dtype='<u2');assert a.size==W*H or a.size==W*H*3//2
 if a.size!=W*H:a=a[:W*H]
 assert int(a.max())<=1023;return a.reshape(H,W).astype(float)/4
def main():
 if not __debug__: raise RuntimeError('optimized Python prohibited; run without -O')
 ap=argparse.ArgumentParser();ap.add_argument('admitted',type=Path);ap.add_argument('output',type=Path);ap.add_argument('--validator-sha',required=True);a=ap.parse_args();assert not a.output.exists()
 ad=json.loads((a.admitted/'admission.json').read_text());assert ad['status']=='admitted' and ad['dimensions']==[W,H]; assert ad['script']['sha256']==a.validator_sha and ident(ad['script']['path'])==ad['script']
 for k in ('helper','build_pins','trace','payload','independent_events','pristine_receipt'): exact(ad[k])
 assert sha(HELPER)==HELPER_SHA;sp=importlib.util.spec_from_file_location('h',HELPER);h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h)
 paths={s:exact(ad['r9_stages'][s]) for s in ('original','coding_input','postloop')};paths['predictor']=exact(ad['artifacts']['predictor']);paths['preloop']=exact(ad['artifacts']['preloop']);st={s:load_luma(p) for s,p in paths.items()};
 out={}
 for n,(x,y,w,hh) in BOXES.items():
  src=st['original'][y:y+hh,x:x+w];out[n]={'xywh':[x,y,w,hh],'source_pixels':int(src.size),'stages':{}}
  for s in ('original','coding_input','predictor','preloop','postloop'):
   z=st[s][y:y+hh,x:x+w];d=h.luma_pair(src,z);d['pixel_mse']=float(np.mean((z-src)**2));d['pixel_support']=int(z.size);out[n]['stages'][s]=d
 result={'status':'complete','argv':[str(x) for x in sys.argv],'python':sys.executable,'scope':'SINGLEFRAME_FULL_ROI_SUPPLEMENT','frame':120,'input_frame':216,'admission':ident(a.admitted/'admission.json'),'validator':ad['script'],'helper':ident(HELPER),'controls':ident(CONTROL),'control_sha_expected':CONTROL_SHA,'stages':{s:ident(p) for s,p in paths.items()},'full_roi':out,'script':ident(Path(__file__)),'interpretation':'Full connected fixed ROI descriptors only; pixel support is reported separately from descriptor center/evaluable counts.'}
 a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
if __name__=='__main__':main()
