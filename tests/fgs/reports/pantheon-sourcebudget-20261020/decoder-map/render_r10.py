#!/usr/bin/env python3
import pathlib,json,hashlib,sys
import numpy as np
from PIL import Image,ImageDraw
P=pathlib.Path(__file__).resolve().parent;A=P/'admitted-1';R=P.parent/'psyex-boundary-r9/admitted-1';out=P/'visuals-1';out.mkdir(exist_ok=False)
W,H=1920,1080
st={k:np.fromfile(R/(k+'.yuv'),dtype='<u2',count=W*H).reshape(H,W).astype(float)/4 for k in ('original','coding_input','preloop','postloop')};st['predictor']=np.fromfile(A/'predictor.y',dtype='<u2').reshape(H,W).astype(float)/4
cat=np.load(A/'category.npy');owner=np.load(A/'owner.npy');units=json.loads((A/'units.json').read_text());leaves=json.loads((A/'leaves.json').read_text());q=np.zeros((H,W),dtype=np.uint8)
for u in units:q[u['y']:u['y']+u['h'],u['x']:u['x']+u['w']]=u['coded_qindex']
colors=np.array([[0,0,0],[193,68,14],[233,168,48],[105,158,207],[59,135,88]],dtype=np.uint8)
Image.fromarray(colors[cat]).save(out/'full-category-map.png')
stages=('original','coding_input','predictor','preloop','postloop');obs={}
for name,(x,y,w,h) in {'shirt':(1200,650,200,100),'background':(950,50,250,180),'face':(160,600,500,480)}.items():
 im=Image.new('RGB',(w*6,h+40),'black');draw=ImageDraw.Draw(im)
 for i,k in enumerate(stages):im.paste(Image.fromarray(np.clip(np.rint(st[k][y:y+h,x:x+w]),0,255).astype('uint8'),'L'),(w*i,40));draw.text((w*i+3,5),k,fill='white')
 im.paste(Image.fromarray(colors[cat[y:y+h,x:x+w]]),(w*5,40));draw.text((w*5+3,5),'syntax category',fill='white');im.save(out/(name+'-stages.png'))
 obs[name]={'xywh':[x,y,w,h],'pixels':w*h,'category_pixels':{str(i):int(np.sum(cat[y:y+h,x:x+w]==i)) for i in (1,2,3,4)},'qindex_histogram':{str(k):int(n) for k,n in zip(*np.unique(q[y:y+h,x:x+w],return_counts=True))},'exact_predictor_equals_preloop_fraction':float(np.mean(st['predictor'][y:y+h,x:x+w]==st['preloop'][y:y+h,x:x+w]))}
(out/'README.md').write_text('Native luma geometry,10bit/4 thenrounded8bit solely for stilldisplay. Columns original,coding_input,native local predictor mosaic,preloop,postloop,syntax map. Category1 brown=skipmode;2 amber=block no residual;3 blue=EOB0 TU;4 green=EOBpositive TU. Predictor mosaic is sequential local predictors, not coherent no-residual-frame counterfactual. No motion/playback. Raw10 admitted samples remain authoritative.\n')
(out/'observations.json').write_text(json.dumps(obs,indent=2)+'\n')
manifest={str(f.name):{'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'size':f.stat().st_size} for f in out.iterdir() if f.is_file()};(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(obs,indent=2))
