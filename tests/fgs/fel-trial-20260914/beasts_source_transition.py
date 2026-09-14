"""Bounded source review around the reconstructed clip's grain transitions."""
from pathlib import Path
import json
import numpy as np
from PIL import Image,ImageDraw
from fel_clip import inputs,reconstructed,base_rgb,rgb_to_pq10,ROOT
from measure_reconstruction import rgb_pixels,preview

directory=ROOT/'clips/1f373204e9b8d9b771a9-20'
bl,el=inputs(directory);rgb=reconstructed(bl,el);omitted=reconstructed(bl,el,mode='noresidual')
# Pin the relocated runtime to an exact full-resolution image already measured
# in the isolated container before using it for these additional stills.
control=rgb_pixels(rgb,56)
assert np.array_equal(control,np.load(directory/'fel_reconstructed-strongest.npy'))
pq=rgb_to_pq10(rgb);noel=rgb_to_pq10(omitted)
frames=[26,27,29,30,31,53,54,55,99,100]
pics=[];rows=[];previous=None
for n in frames:
    image=preview(rgb_pixels(rgb,n))
    canvas=Image.new('RGB',(image.width,image.height+30),'black');canvas.paste(image,(0,30))
    ImageDraw.Draw(canvas).text((8,8),f'Reconstructed source | frame {n}',fill='white');pics.append(canvas)
    values={}
    for label,clip in [('reconstructed',pq),('without_residual',noel),('base',bl)]:
        with clip.get_frame(n) as f:
            y=np.asarray(f[0]).astype(np.float32)
            active=y[300:1860,128:3712]
            # A directional high-pass observation of source texture. Motion,
            # edges and reconstruction also contribute; it is not a noise oracle.
            residual=active[1:-1,1:-1]-(active[1:-1,:-2]+active[1:-1,2:]+active[:-2,1:-1]+active[2:,1:-1])/4
            values[label]=dict(active_mean=float(active.mean()),highpass_rms=float(np.sqrt(np.mean(residual**2))))
    rows.append(dict(frame=n,source_luma_10bit=values))
sheet=Image.new('RGB',(pics[0].width*2,pics[0].height*5))
for k,pic in enumerate(pics):sheet.paste(pic,((k%2)*pic.width,(k//2)*pic.height))
sheet.save(directory/'source-transition-review.png')
(ROOT/'results/beasts-source-transition.json').write_text(json.dumps(dict(
    container_reference_frame_56_exact_match=True,frames=rows,
    limit='High-pass RMS includes edges/motion; selected SDR-mapped stills cannot determine full HDR playback visibility or diagnose the encoder policy alone.'),indent=2)+'\n')
print('Source transition review complete; relocated runtime matches saved native reference')
