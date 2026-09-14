"""Source-referenced stills of the four encoded windows; no perceptual verdict."""
from pathlib import Path
import json
import numpy as np
import vapoursynth as vs
from PIL import Image, ImageDraw
from fel_clip import core, bounded, base_rgb
from measure_reconstruction import preview, difference

T=Path('/trial')


def decoded_still(output, n, mode):
    # The isolated FFMS2 build reports an empty frame on these AV1 files.
    # Use explicitly selected host libdav1d output instead; metadata/counts and
    # timestamps were independently checked by validate_outputs.py.
    path=output.parent/f'review-frame-{n}.yuv'
    words=np.fromfile(path,dtype='<u2')
    assert words.size==3840*2160*3//2
    planes=[words[:3840*2160].reshape(2160,3840)]
    planes.extend(x.reshape(1080,1920) for x in np.split(words[3840*2160:],2))
    blank=core.std.BlankClip(width=3840,height=2160,format=vs.YUV420P10,length=1)
    def copy_planes(n,f):
        out=f.copy()
        for p,values in enumerate(planes):np.copyto(np.asarray(out[p]),values)
        return out
    decoded=core.std.ModifyFrame(blank,clips=blank,selector=copy_planes)
    return bounded(core.std.SetFrameProps(decoded,_Matrix=9,_Transfer=16,_Primaries=9,
        _ColorRange=1,_ChromaLocation=2 if mode=='hdr10base-fps-corrected' else 0,_FieldBased=0))


def sheet(images, labels, path):
    width,height=images[0].size
    output=Image.new('RGB',(width*len(images),height+34),'black')
    draw=ImageDraw.Draw(output)
    for k,(picture,label) in enumerate(zip(images,labels)):
        output.paste(picture,(k*width,34));draw.text((k*width+8,8),label,fill='white')
    output.save(path)


def main():
    rows=[]
    for directory in sorted((T/'clips').glob('*-20')):
        summary=json.loads((directory/'reconstruction-summary.json').read_text())
        n=summary['strongest_residual_frame']
        reference=np.load(directory/'fel_reconstructed-strongest.npy')
        images=[preview(reference)];crops=[preview(reference[824:1336,1664:2176].repeat(4,0).repeat(4,1))]
        labels=['Reconstructed reference | frame '+str(n)]
        row=dict(name=directory.name,frame=n,outputs=[])
        for mode in ['default','noresidual','hdr10base-fps-corrected']:
            output=T/'outputs'/(directory.name+'-'+mode)/'candidate-pq-av1.mkv'
            decoded=decoded_still(output,n,mode)
            rgb=base_rgb(decoded)
            with rgb.get_frame(0) as f:
                pixels=np.stack([np.asarray(f[p]) for p in range(3)],axis=-1)
            images.append(preview(pixels))
            crops.append(preview(pixels[824:1336,1664:2176].repeat(4,0).repeat(4,1)))
            labels.append(mode+' AV1')
            row['outputs'].append(dict(mode=mode,versus_reconstructed_rgb=difference(
                pixels[::4,::4].astype(np.int32),reference[::4,::4].astype(np.int32))))
            del rgb,decoded,pixels
        sheet(images,labels,directory/'encoded-comparison.png')
        sheet(crops,labels,directory/'encoded-native-centre-crop.png')
        rows.append(row)
        (T/'results/output-still-review.json').write_text(json.dumps(dict(
            selection='Strongest mean residual frame in each encoded window; this is not a full-film visual review.',
            mapping='Same fixed 100-nit Reinhard/BT.709/sRGB preview for all four pictures; no Dolby display trims.',
            crop={'x':1664,'y':824,'width':512,'height':512,'scale':1},
            metrics_domain='PQ RGB16, sample every fourth pixel. Difference from reconstruction is not independent proof of reconstruction correctness or perceptual improvement.',
            rows=rows),indent=2)+'\n')
        print(directory.name,'review frames complete',flush=True)


if __name__=='__main__':main()
