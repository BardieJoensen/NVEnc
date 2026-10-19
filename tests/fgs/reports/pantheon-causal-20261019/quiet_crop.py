#!/usr/bin/env python3
"""Native context around the worst held-out quiet-luma over-graining tile."""
import json
from PIL import Image,ImageDraw,ImageFont
import grain_model as g
x=g.x;d=x.ROOT/'e05-1460'
rows=json.loads((d/'a-heldout-controls.json').read_text())['tiles']
r=max((r for r in rows if r['kind']=='quiet'),key=lambda r:r['model']['hf_sigma']-r['source']['hf_sigma'])
n=r['frame'];w,h=480,360;cx=max(0,min(1920-w,r['x']-w//2));cy=max(0,min(1080-h,r['y']-h//2))
canvas=Image.new('RGB',(w*3,h+36));draw=ImageDraw.Draw(canvas);font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16)
for i,(tag,label) in enumerate([('ref','Original H.264'),('a-existing-decoded','Existing model'),('a-model-decoded','Reconstruction-aware model')]):
    b=x.run(['ffmpeg','-v','error','-threads','4','-i',d/(tag+'.mkv'),'-vf',f'select=eq(n\\,{n}),crop={w}:{h}:{cx}:{cy}','-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','-'],binary=True)
    canvas.paste(Image.frombytes('RGB',(w,h),b),(i*w,36));draw.text((i*w+5,8),label,font=font,fill='white')
    draw.rectangle((i*w+r['x']-cx,r['y']-cy+36,i*w+r['x']-cx+32,r['y']-cy+68),outline='red',width=1)
canvas.save(d/'a-quiet-regression-crop.png');x.dump(d/'a-quiet-regression-crop.json',{'tile':r,'frame':n,'crop_xywh':[cx,cy,w,h],'note':'Worst held-out quiet luma amplitude excess; diagnostic selection, not representative frequency. Native pixels, 8-bit preview.'})
