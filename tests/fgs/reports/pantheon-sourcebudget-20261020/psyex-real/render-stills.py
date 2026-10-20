#!/usr/bin/env python3
import hashlib,json,sys,datetime
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
W,H=1920,1080
BOXES={'shirt':(1200,650,200,100),'background':(950,50,250,180),'face':(160,600,500,480)}
ROOT=Path('/tmp/downloads/codex-work/pantheon-sourcebudget-20261020')
R15=ROOT/'parent/psyex-real-r15/admitted-1'
R8=ROOT/'parent/psyex-boundary-r9/admitted-1'
EXPECTED={
 'original':'c2798d9c00f53bdbe7041575249b353a478a8f5557bc4dd5b61d9ae03f13ea12',
 'r8_final':'8e540b11034f78a76c6a7b7732c2386eee2b3647137dffab9ab5f1930fcd1985',
 'r15_final':'711fc12f37beba0babfddfa92fba6715f92f679e49517cee5651503418f5a82f',
}
# corrected expected original is supplied by admission; assert it literally below too.
def ident(p):
 p=Path(p).resolve(); h=hashlib.sha256();
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return {'path':str(p),'sha256':h.hexdigest(),'size':p.stat().st_size}
def load_luma(p):
 b=Path(p).read_bytes(); assert len(b)==W*H*3, (p,len(b))
 a=np.frombuffer(b,dtype='<u2',count=W*H).reshape(H,W)
 return np.rint(a.astype(np.float64)/4).clip(0,255).astype(np.uint8)
def main():
 out=Path(sys.argv[1]); assert not out.exists(); out.mkdir(parents=True)
 r15a=json.loads((R15/'admission.json').read_text()); r8a=json.loads((R8/'admission.json').read_text())
 assert r15a['status']=='admitted' and r8a['status']=='admitted'
 assert r15a['source_boundaries']['original']['sha256']==EXPECTED['original']
 assert r8a['stages']['original']['sha256']==EXPECTED['original']
 paths={'original':R15/'original.yuv','r8_final':R8/'postloop.yuv','r15_final':R15/'postloop.yuv'}
 ids={k:ident(v) for k,v in paths.items()}
 assert ids['original']['sha256']==EXPECTED['original']
 assert ids['r8_final']['sha256']==EXPECTED['r8_final']
 assert ids['r15_final']['sha256']==EXPECTED['r15_final']
 frames={k:load_luma(v) for k,v in paths.items()}
 try: font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
 except OSError: font=None
 manifest={'status':'complete','frame':216,'scored_frame':120,'dimensions':[W,H], 'pix_fmt':'yuv420p10le','rounding':'uint16 LE luma divided by 4 once, rounded/clipped to uint8','resized':False,'playback_observed':False,'inputs':ids,'rois':{}}
 for name,(x,y,w,h) in BOXES.items():
  pad,labelh=18,24; canvas=Image.new('L',(3*w+4*pad,h+labelh+2*pad),0); d=ImageDraw.Draw(canvas); entries=[]
  for i,k in enumerate(('original','r8_final','r15_final')):
   crop=frames[k][y:y+h,x:x+w]; assert crop.shape==(h,w)
   px=pad+i*(w+pad); py=pad; canvas.paste(Image.fromarray(crop,'L'),(px,py+labelh)); d.text((px,py),k,fill=255,font=font)
   entries.append({'stage':k,'xywh':[px,py+labelh,w,h],'pixels_native':True})
  p=out/f'{name}-3panel.png'; canvas.save(p)
  manifest['rois'][name]={'xywh':[x,y,w,h],'panel':ident(p),'entries':entries}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print(json.dumps({'status':'complete','manifest':ident(out/'manifest.json')}))
if __name__=='__main__': main()
