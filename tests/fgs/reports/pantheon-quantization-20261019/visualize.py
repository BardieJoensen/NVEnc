#!/usr/bin/env python3
"""Native-resolution synchronized views; 8-bit previews, no playback claim."""
import sys,json
from PIL import Image,ImageDraw,ImageFont
from study import ROOT,x
case,budget=sys.argv[1:];timebase='1001/24000' if case=='e04' else '1/24';d=ROOT/case;n=134 if case=='e04' else 120
low='qp4' if case=='e04' else 'qp4-tx32';base='detail' if case=='e04' else 'detail2'
# The baseline render is new; baseline metric scores are reused only after exact identity.
x.decode(d/(base+'.mkv'),d/'baseline-decoded.mkv',96,0)
paths=[d/'ref.mkv',d/'baseline-decoded.mkv',d/(low+'-decoded.mkv'),d/(budget+'-decoded.mkv')]
v=json.loads((d/'validity.json').read_text());rates=[v['source_mbps']]+[json.loads((d/(tag+'-encode.json')).read_text())['rate_mbps'] for tag in [base,low,budget]]
labels=[f'Original H264 {rates[0]:.2f} Mbps',f'Baseline {rates[1]:.2f} Mbps',f'Low q16'+(' TX32' if case!='e04' else '')+f' {rates[2]:.2f} Mbps',f'ROI q16'+(' TX32' if case!='e04' else '')+f' {rates[3]:.2f} Mbps ({100*(rates[3]/rates[0]-1):+.1f}%)']
box=[1400,200,400,400] if case=='e04' else [930,440,600,400];cx,cy,w,h=box
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16)
canvas=Image.new('RGB',(2*w,2*(h+36)));draw=ImageDraw.Draw(canvas)
for i,(p,label) in enumerate(zip(paths,labels)):
 b=x.run(['ffmpeg','-v','error','-threads','4','-i',p,'-vf',f'select=eq(n\\,{n}),crop={w}:{h}:{cx}:{cy}','-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','-'],binary=True)
 xx=i%2*w;yy=i//2*(h+36);canvas.paste(Image.frombytes('RGB',(w,h),b),(xx,yy+36));draw.text((xx+6,yy+8),label,font=font,fill='white')
canvas.save(d/'quantization-crops.png')
cmd=['/usr/bin/ffmpeg','-v','error','-y']
for p in paths:cmd+=['-threads','4','-i',p]
g=[]
for i,label in enumerate(labels):g.append(f'[{i}:v]trim=end_frame=240,settb={timebase},setpts=N,crop={w}:{h}:{cx}:{cy},format=yuv420p,pad=iw:ih+36:0:36:black,drawtext=expansion=none:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text={label}:fontcolor=white:fontsize=16:x=6:y=8[v{i}]')
g+=['[v0][v1]hstack=2[top]','[v2][v3]hstack=2[bottom]','[top][bottom]vstack=2[out]']
cmd+=['-filter_complex_threads','2','-filter_complex',';'.join(g),'-map','[out]','-frames:v','240','-an','-c:v','libx264','-qp','0','-preset','fast','-threads','4',*x.COLOR,d/'quantization-synchronized.mkv'];x.run(cmd,d,'quantization-synchronized')
# Whole frame source/budget/baseline stills permit visual inspection outside the target.
for p,label,tag in zip(paths,labels,['original','baseline',low,budget]):
 out=d/(tag+f'-frame{n}.png')
 x.run(['ffmpeg','-v','error','-y','-threads','4','-i',p,'-vf',f'select=eq(n\\,{n})','-frames:v','1','-pix_fmt','rgb24',out],d,label.replace(' ','_')+'-still')
x.dump(d/'visuals.json',{'paths':list(map(str,paths)),'labels':labels,'frame':n,'crop_xywh':box,'preview':'Native-size image crops, 10-to-8 bit preview conversion, lossless x264 qp0 after labels; scored original 10bit YUV separately. Playback/display not verified.'})
