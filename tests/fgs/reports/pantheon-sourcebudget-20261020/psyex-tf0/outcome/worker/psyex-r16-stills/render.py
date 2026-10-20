#!/usr/bin/env python3
"""Render bound R16/R8/original native-size luma stills; no metrics or enhancement."""
import datetime, hashlib, json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
W,H=1920,1080
BOXES={'shirt':(1200,650,200,100),'background':(950,50,250,180),'face':(160,600,500,480)}
ROOT=Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020')
R16A=ROOT/'parent/psyex-tf0-r16-refine/r16-refine-tbr10042-observations/admitted'
R8A=ROOT/'parent/psyex-boundary-r9/admitted-1'
R16_ADMISSION_SHA='a86db1bcc3e4ff49b8e0aa66dfc601ac8bc7b67bb4415b3886263df7daaf50ab'
R8_ADMISSION_SHA='f6a7a6d3221f15fb789419a43cd3f1b61372ffb99e325cd1ee131962ed5be7fc'
R16_SELECTED_COMMAND_SHA='00bb9243453fb55f1c878842e2ecfd3760f8403144e1e5b507530477a03ef497'
R16_DECODER_CHECK_SHA='fb4574fb7f601471956ffa0b7ea983f7235a25408c200cc1e5bd53f2c74ee304'
ORIGINAL_SHA='c2798d9c00f53bdbe7041575249b353a478a8f5557bc4dd5b61d9ae03f13ea12'
R8_POST_SHA='8e540b11034f78a76c6a7b7732c2386eee2b3647137dffab9ab5f1930fcd1985'
R16_POST_SHA='1ef3ad3dd6cce1b008fdc737a21f49d46f5fce4f708774dfdfc74093f2ca790b'

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()
def ident(p):
 p=Path(p).resolve(); return {'path':str(p),'sha256':sha(p),'size':p.stat().st_size}
def exact(p, expected=None):
 d=ident(p)
 if expected is not None: assert d['sha256']==expected,(p,d,expected)
 return d
def load_luma(p):
 b=Path(p).read_bytes(); assert len(b)==W*H*3,(p,len(b))
 a=np.frombuffer(b,dtype='<u2',count=W*H).reshape(H,W)
 # Established convention: divide native 10-bit luma by 4 once, round/clip to uint8.
 return np.rint(a.astype(np.float64)/4).clip(0,255).astype(np.uint8)
def main():
 assert not __debug__ is False, 'optimized Python prohibited'
 assert len(sys.argv)==2
 out=Path(sys.argv[1]); assert not out.exists(); out.mkdir(parents=True)
 started=datetime.datetime.now(datetime.timezone.utc).isoformat()
 r16p=R16A/'admission.json'; r8p=R8A/'admission.json'
 r16id=exact(r16p,R16_ADMISSION_SHA); r8id=exact(r8p,R8_ADMISSION_SHA)
 r16=json.loads(r16p.read_text()); r8=json.loads(r8p.read_text())
 assert r16['status']=='admitted' and r8['status']=='admitted'
 assert r16['case']=='e05-1440'
 selected=exact(ROOT/'worker/psyex-r16-calibration-refine/runs/e05-1440/r16-refine-tbr10042/command.json',R16_SELECTED_COMMAND_SHA)
 assert r16['original_receipt']['sha256']==R16_SELECTED_COMMAND_SHA
 dec=exact(ROOT/'worker/psyex-r16-calibration-refine/runs/e05-1440/r16-refine-tbr10042/decoder-validation/decoder-validation.json',R16_DECODER_CHECK_SHA)
 decj=json.loads(Path(dec['path']).read_text()); assert decj['status']=='admitted'
 assert decj.get('all336_allplanes_app_dav1d_libaom_NVDEC_exact') is True
 inputs={
  'original':R16A/'original.yuv',
  'r8_final':R8A/'postloop.yuv',
  'r16_final':R16A/'postloop.yuv',
 }
 ids={k:exact(v) for k,v in inputs.items()}
 assert ids['original']['sha256']==ORIGINAL_SHA
 assert ids['r8_final']['sha256']==R8_POST_SHA
 assert ids['r16_final']['sha256']==R16_POST_SHA
 frames={k:load_luma(v) for k,v in inputs.items()}
 try: font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
 except OSError: font=None
 manifest={'status':'complete','frame':216,'scored_frame':120,'dimensions':[W,H], 'pix_fmt':'yuv420p10le','rounding':'uint16 LE luma divided by 4 once, rounded/clipped to uint8','resized':False,'enhancement':'none','playback_observed':False,'admission':r16id,'r8_admission':r8id,'selected_command':selected,'decoder_check':dec,'inputs':ids,'rois':{}}
 for name,(x,y,w,h) in BOXES.items():
  pad,labelh=18,24; canvas=Image.new('L',(3*w+4*pad,h+labelh+2*pad),0); draw=ImageDraw.Draw(canvas); entries=[]
  for i,k in enumerate(('original','r8_final','r16_final')):
   crop=frames[k][y:y+h,x:x+w]; assert crop.shape==(h,w)
   px=pad+i*(w+pad); py=pad; canvas.paste(Image.fromarray(crop,'L'),(px,py+labelh)); draw.text((px,py),k,fill=255,font=font)
   entries.append({'stage':k,'xywh':[px,py+labelh,w,h],'pixels_native':True})
  p=out/f'{name}-3panel.png'; canvas.save(p)
  manifest['rois'][name]={'xywh':[x,y,w,h],'panel':ident(p),'entries':entries}
 manifest_path=out/'manifest.json'; manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
 execution={'status':'complete','argv':sys.argv,'started_utc':started,'ended_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'script':ident(__file__),'manifest':ident(manifest_path),'inputs':ids,'admission':r16id,'r8_admission':r8id,'selected_command':selected,'decoder_check':dec}
 (out/'execution.json').write_text(json.dumps(execution,indent=2)+'\n')
 print(json.dumps({'status':'complete','manifest':ident(manifest_path),'execution':ident(out/'execution.json')}))
if __name__=='__main__': main()
