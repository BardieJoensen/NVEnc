#!/usr/bin/env python3
"""Native-context still for local representability evidence; no motion claim."""
import json
from PIL import Image,ImageDraw,ImageFont
from study import ROOT,x
case='e05-1460';d=ROOT/case;n=72;model=d/'represent-prior_ar-16.txt';raw=d/'representability-still.yuv'
x.run([ROOT/'apply_grain',d/'fixed-picture.ivf',raw,2,n+96,1,model],d,'representability-still')
# Native YUV source/base paths are 240-frame raw references. Only the synthesis is one frame.
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16);w,h=320,240
canvas=Image.new('RGB',(w*3,(h+36)*2));draw=ImageDraw.Draw(canvas)
for row,(kind,xx,yy) in enumerate([('Quiet',1640,152),('Stochastic',1592,968)]):
 cx=max(0,min(1920-w,xx-w//2));cy=max(0,min(1080-h,yy-h//2))
 for col,(tag,path,frame) in enumerate([('Original',d/'source.yuv',n),('Fixed base',d/'base.yuv',n),('Legal AR scale16',raw,0)]):
  cmd=['ffmpeg','-v','error','-threads','4','-f','rawvideo','-pixel_format','yuv420p10le','-video_size','1920x1080','-framerate','24','-color_range','tv','-colorspace','bt709','-i',path,'-vf',f'select=eq(n\\,{frame}),crop={w}:{h}:{cx}:{cy}','-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','-']
  b=x.run(cmd,binary=True);ox,oy=col*w,row*(h+36);canvas.paste(Image.frombytes('RGB',(w,h),b),(ox,oy+36));draw.text((ox+5,oy+8),kind+' - '+tag,font=font,fill='white');draw.rectangle((ox+xx-cx,oy+36+yy-cy,ox+xx-cx+32,oy+36+yy-cy+32),outline='red')
canvas.save(d/'representability-context.png');raw.unlink()
x.dump(d/'representability-visual.json',{'frame':n,'quiet_xy':[1640,152],'texture_xy':[1592,968],'model':str(model),'seed':12345,'note':'One legal seed only for illustration; inference uses32-seed data. Native crop, BT709 limited10bit to8bit RGB. No temporal claim.'})
