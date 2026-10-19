#!/usr/bin/env python3
"""Native-pixel diagnostic crops, synchronized lossless previews and plots.

Preview RGB PNG/H.264 is 8-bit; metrics always use unrendered 10-bit YUV.
No resizing of crops. Labels occupy additional pixels outside the image.
"""
import argparse, json
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import investigate as x

def main(case,tags):
    d=x.ROOT/case; n=134 if case=='e04' else 120
    paths=[d/'ref.mkv']+[d/(t+'-decoded.mkv') for t in tags]
    labels=['Original H.264']+tags
    box=(1400,200,400,400) if case=='e04' else {'e05-1420':(450,650,600,400),'e05-1440':(930,440,600,400),'e05-1460':(700,400,600,500)}[case]
    cx,cy,w,h=box;cols=min(3,len(paths));rows=(len(paths)+cols-1)//cols
    canvas=Image.new('RGB',(cols*w,rows*(h+36)),(20,20,20));draw=ImageDraw.Draw(canvas)
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16)
    for i,(p,label) in enumerate(zip(paths,labels)):
        b=x.run(['ffmpeg','-v','error','-threads','4','-i',p,'-vf',f'select=eq(n\\,{n}),crop={w}:{h}:{cx}:{cy}','-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','-'],binary=True)
        im=Image.frombytes('RGB',(w,h),b);xx=(i%cols)*w;yy=(i//cols)*(h+36)
        canvas.paste(im,(xx,yy+36));draw.text((xx+6,yy+7),label,font=font,fill='white')
    canvas.save(d/'comparison-crops.png')
    # Full-frame source/context and per-arm stills, direct output with common tags.
    for p,label in zip(paths,labels):
        out=d/(label.replace(' ','_')+f'-frame{n}.png')
        if not out.exists():x.run(['ffmpeg','-v','error','-threads','4','-i',p,'-vf',f'select=eq(n\\,{n})','-frames:v','1','-pix_fmt','rgb24',out],d,label.replace(' ','_')+'-still')
    # Limit synchronized clip to original + two selected comparisons at native
    # crop size. Lossless H.264 after documented 10->8 bit preview conversion.
    cmd=['/usr/bin/ffmpeg','-v','error','-y']
    for p in paths[:3]:cmd+=['-threads','4','-i',p]
    graph=[]
    for i,label in enumerate(labels[:3]):
        graph.append(f'[{i}:v]trim=end_frame=240,setpts=PTS-STARTPTS,crop={w}:{h}:{cx}:{cy},format=yuv420p,pad=iw:ih+36:0:36:black,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text={label}:fontcolor=white:fontsize=16:x=6:y=7[v{i}]')
    graph.append(''.join(f'[v{i}]' for i in range(min(3,len(paths))))+f'hstack=inputs={min(3,len(paths))}[out]')
    cmd+=['-filter_complex_threads','2','-filter_complex',';'.join(graph),'-map','[out]','-frames:v',240,'-an','-c:v','libx264','-preset','fast','-qp','0','-threads','4',*x.COLOR,d/'comparison-synchronized.mkv']
    x.run(cmd,d,'comparison-synchronized')
    available=[t for t in tags if (d/(t+'-texture.json')).exists()]
    if available:
        fig,ax=plt.subplots(3,1,figsize=(12,8),sharex=True)
        source_done=False
        for tag in available:
            doc=json.loads((d/(tag+'-texture.json')).read_text());region=next(iter(doc['roi_xywh']))
            for arm in (('source','target') if not source_done else ('target',)):
                source_done=True;label='original' if arm=='source' else tag
                vals=[f['roi'][region][arm] for f in doc['frames']]
                for a,key in zip(ax,('hf_sigma','acf1','temporal_hf_corr')):a.plot(np.arange(240)/x.CASES[case][2],[v[key] for v in vals],label=label,lw=1)
        for a,title in zip(ax,('HF amplitude, 8-bit luma units','Spatial residual ACF, lag 1','Temporal residual correlation, fixed ROI; motion confounded')):a.set_ylabel(title);a.grid(alpha=.2)
        ax[0].legend(ncol=2,fontsize=8);ax[-1].set_xlabel('Seconds within scored window');fig.suptitle(case+' — '+region+'; fixed ROI may cross scene cuts');fig.tight_layout();fig.savefig(d/'texture-temporal.png',dpi=140);plt.close(fig)
    x.dump(d/'visuals.json',{'frame':n,'crop_xywh':box,'labels':labels,'paths':list(map(str,paths)),'preview':'Native-size crop, 8-bit preview conversion, lossless H264 qp0 after labels; use 10-bit decoded sources for metrics. No actual user player/display playback tested.'})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('case',choices=x.CASES);p.add_argument('tags',nargs='+');a=p.parse_args();main(a.case,a.tags)
