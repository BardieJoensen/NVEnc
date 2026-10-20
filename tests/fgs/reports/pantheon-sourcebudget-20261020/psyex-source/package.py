#!/usr/bin/env python3
"""Freeze R14 selected evidence and native-size stills; no new codec operation."""
import datetime as dt, hashlib, importlib.util, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

P=Path(__file__).resolve().parent
ROOT=P.parents[1]
R11=ROOT/'parent/psyex-coeff-r11'
R13=ROOT/'worker/psyex-r13-fine'

def ident(p):
    p=Path(p).resolve()
    with p.open('rb') as f: sha=hashlib.file_digest(f,'sha256').hexdigest()
    return dict(path=str(p),sha256=sha,size=p.stat().st_size)

def load(p,name,sha):
    assert ident(p)['sha256']==sha
    s=importlib.util.spec_from_file_location(name,p)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def main():
    out=P/'package-1';out.mkdir(exist_ok=False)
    rp=P/'run-1/result.json';ap=P/'run-1/native-arrays.npz'
    assert ident(rp)['sha256']=='0dcfb0f808ae9a34d0c707de828a4dd5ad88cc23a2bda3c0971585a0476008b8'
    assert ident(ap)['sha256']=='c8bdbaf904334a00c710ae89d34d65272af0b50be5898b2c18c8679226821592'
    result=json.loads(rp.read_text());assert result['status']=='admitted_diagnostic'
    a=load(R11/'analyze.py','r14_pack_analysis','44b8037c2a922b7e893cd66c8488f3683c45b8859400ff6b082bd0910286f64e')
    v=a.mod(a.V,'r14_pack_validator',a.VSHA);u=a.mod(a.U,'r14_pack_units',a.USHA)
    adp=R11/'admitted-1/admission.json'
    assert ident(adp)['sha256']=='f9aba0b6b1d5d8b73c606698130a64e46ec0bc7f55a6d7363ea113bd45e1548a'
    ad=json.loads(adp.read_text());tokens,terminal=v.parse(a.exact(ad['trace']))
    assert len(tokens)==2907 and terminal==ad['terminal']
    priorp=R13/'run-1/result.json'
    assert ident(priorp)==result['r13_result']
    prior=json.loads(priorp.read_text());priorap=a.exact(prior['q1_arrays'])
    with np.load(ap,allow_pickle=False) as z: arrays={k:z[k] for k in z.files}
    with np.load(priorap,allow_pickle=False) as z: old={k:z[k] for k in z.files}
    frames={s:u.load_luma(a.exact(result[s])) for s in ('original','coding_input')}
    frames.update({s:np.full((1080,1920),np.nan) for s in ('captured_raw','captured_q1','original_raw','original_q1')})
    invmask=np.zeros((1080,1920),bool)
    rows={r['token']:r for r in result['units']};assert set(rows)==set(tokens)
    counts=dict(tokens=len(tokens),invoked=0,unchanged=0,visible_pixels=0,source_changed=0,padding_pixels=0,padding_changed=0,raw_coefficients_changed=0)
    geometry={k:{} for k in a.BOXES};po=co=0
    for key,t in tokens.items():
        z=t['begin'];r=rows[key];assert r['begin']==z
        x,y,w,h=(z[k] for k in ('x','y','w','h'));vh=min(h,1080-y);sl=np.s_[y:y+vh,x:x+w]
        invoked=bool(t['stages']);assert r['invoked']==invoked
        counts['invoked' if invoked else 'unchanged']+=1
        for roi,(rx,ry,rw,rh) in a.BOXES.items():
            pixels=max(0,min(x+w,rx+rw)-max(x,rx))*max(0,min(y+vh,ry+rh)-max(y,ry))
            if pixels:
                g=f"{'invoked' if invoked else 'unchanged'}:{w}x{h}:type{z['type']}"
                entry=geometry[roi].setdefault(g,dict(units=0,pixels=0));entry['units']+=1;entry['pixels']+=pixels
        frames['captured_raw'][sl]=t.get('raw_inverse',t['predictor'])[:vh].astype(float)/4
        if invoked:
            assert r['pixel_offset']==po and r['source_offset']==po and r['coefficient_offset']==co
            assert np.array_equal(arrays['source'][po:po+w*h].reshape(h,w)[:vh],np.asarray(frames['original'][sl]*4,dtype='<u2'))
            for name,src,field in [('captured_q1',old,'q1_inverse'),('original_raw',arrays,'raw_inverse'),('original_q1',arrays,'inverse')]:
                frames[name][sl]=src[field][po:po+w*h].reshape(h,w)[:vh].astype(float)/4
            invmask[sl]=True
            for k,val in r['changes'].items(): counts[k]+=val
            po+=w*h;co+=z['n']
        else:
            for name in ('captured_q1','original_raw','original_q1'):frames[name][sl]=t['predictor'][:vh].astype(float)/4
    assert counts['invoked']==2187 and counts['unchanged']==720
    assert po==arrays['inverse'].size==old['q1_inverse'].size and co==arrays['q'].size
    manifest=dict(status='complete',generated_utc=dt.datetime.now(dt.timezone.utc).isoformat(),script=ident(__file__),result=ident(rp),arrays=ident(ap),units='8bit luma rounded from exact native10bit/4; native-size, no resampling',playback=False,rois={})
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',12)
    names=list(frames)
    for roi,(x,y,w,h) in a.BOXES.items():
        for name in names: assert np.isfinite(frames[name][y:y+h,x:x+w]).all()
        expected=result['fixed_roi'][roi];assert int(invmask[y:y+h,x:x+w].sum())==expected['invoked_pixels']
        pad=18;label=20;canvas=Image.new('L',(3*w+4*pad,2*(h+label)+3*pad),0);draw=ImageDraw.Draw(canvas)
        for i,name in enumerate(names):
            px=pad+(i%3)*(w+pad);py=pad+(i//3)*(h+label+pad)
            crop=np.rint(np.clip(frames[name][y:y+h,x:x+w],0,255)).astype('uint8')
            canvas.paste(Image.fromarray(crop),(px,py+label));draw.text((px,py),name,font=font,fill=255)
        path=out/f'{roi}-6panel.png';canvas.save(path)
        manifest['rois'][roi]=dict(xywh=[x,y,w,h],panel=ident(path),stages=names)
    mp=out/'visual-manifest.json';mp.write_text(json.dumps(manifest,indent=2)+'\n')
    compact={k:result[k] for k in ('status','scope','script','build','library','contract','controls','q1_tables','r13_result','original','coding_input','fixed_roi','array_file','all_new_C_runtime_exact')}
    compact.update(result=ident(rp),receipt=ident(P/'run-1/receipt.json'),outer_receipt=ident(P/'run-1-execution.json'),counts=counts,roi_geometry=geometry,visual_manifest=ident(mp))
    cp=out/'compact-result.json';cp.write_text(json.dumps(compact,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(compact=ident(cp),visual_manifest=ident(mp),counts=counts,roi_geometry=geometry)))

if __name__=='__main__': main()
