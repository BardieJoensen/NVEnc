#!/usr/bin/env python3
"""Paired texture diagnostics. HF residuals include texture, grain and artifacts.

Fixed-ROI temporal correlation is descriptive, not motion compensated. Midpoint
ROIs are interpreted locally; full-window traces expose transitions and failures.
"""
import argparse, json, subprocess
import numpy as np
import investigate as x

BOXES={'e04':{'purple':[1400,200,400,400]},'e05-1420':{'shirt':[500,800,200,150],'background':[1400,100,300,300]},'e05-1440':{'shirt':[1200,650,200,100],'background':[950,50,250,180]},'e05-1460':{'shirt':[800,430,100,80],'forearm':[800,790,150,60]}}

def corr(a,b):
    a=a-a.mean();b=b-b.mean();den=np.sqrt(np.mean(a*a)*np.mean(b*b))
    return float(np.mean(a*b)/den) if den>1e-9 else None

def desc(a):
    r=x.high_pass(a);s=float(r.std())
    return {'mean':float(a.mean()),'hf_sigma':s*(8/5)**.5,**{f'acf{k}':float(x.autocorr(r,k)) if s>1e-9 else None for k in (1,2,3,4,8)}}

def reader(p):
    return subprocess.Popen(['ffmpeg','-v','error','-threads','4','-i',str(p),'-frames:v',str(x.N),'-pix_fmt','yuv420p10le','-f','rawvideo','-'],stdout=subprocess.PIPE)

def frame(p):
    b=p.stdout.read(x.W*x.H*3)
    assert len(b)==x.W*x.H*3
    a=np.frombuffer(b,np.uint16).astype(np.float32)/4
    return a[:x.W*x.H].reshape(x.H,x.W),a[x.W*x.H:x.W*x.H*5//4].reshape(x.H//2,x.W//2),a[x.W*x.H*5//4:].reshape(x.H//2,x.W//2)

def analyze(case,tag,path,base=None):
    d=x.ROOT/case; boxes=BOXES[case]
    readers=[reader(d/'ref.mkv'),reader(path)]+([reader(base)] if base else [])
    out={'case':case,'tag':tag,'path':str(path),'base':str(base) if base else None,'roi_xywh':boxes,'frames':[],'brightness_color_samples':[]};prev={};prevthumb=None
    try:
        for n in range(x.N):
            frames=[frame(p) for p in readers];src,enc=frames[:2]
            arms={'source':src[0],'target':enc[0]}
            if base:arms['synthesis']=enc[0]-frames[2][0]
            thumb=src[0][::16,::16];cut=float(np.mean(np.abs(thumb-prevthumb))) if prevthumb is not None else None;prevthumb=thumb.copy()
            row={'frame':n,'source_mean_abs_temporal_change':cut,'roi':{}}
            for name,(cx,cy,w,h) in boxes.items():
                reg={k:a[cy:cy+h,cx:cx+w] for k,a in arms.items()};rr={k:x.high_pass(a) for k,a in reg.items()}
                row['roi'][name]={k:desc(a) for k,a in reg.items()}
                row['roi'][name]['paired_hf_correlation']=corr(rr['source'],rr['target'])
                for k,r in rr.items():
                    key=(name,k);row['roi'][name][k]['temporal_hf_corr']=corr(prev[key],r) if key in prev else None;prev[key]=r.copy()
            if n%12==0 or n in (120,134):
                hp={k:x.high_pass(a)[::8,::8] for k,a in arms.items()}
                yy=src[0][1:-1:8,1:-1:8];uu=src[1][::4,::4][:yy.shape[0],:yy.shape[1]];vv=src[2][::4,::4][:yy.shape[0],:yy.shape[1]]
                # Source-conditioned bins avoid selecting different regions per arm.
                masks={f'Y{lo}-{hi}':(yy>=lo)&(yy<hi) for lo,hi in ((16,48),(48,80),(80,112),(112,160),(160,220),(220,236))}
                masks.update({'low_chroma':(np.abs(uu-128)+np.abs(vv-128))<20,'high_chroma':(np.abs(uu-128)+np.abs(vv-128))>=40})
                bins={}
                for key,mask in masks.items():
                    if mask.sum()<50:continue
                    bins[key]={'pixels':int(mask.sum()),**{k:float(r[mask].std()*(8/5)**.5) for k,r in hp.items()}}
                sy=src[0];ey=enc[0];sg=np.abs(sy[:,1:]-sy[:,:-1]);eg=np.abs(ey[:,1:]-ey[:,:-1]);edge=sg>12
                row['strong_horizontal_edge']={'count':int(edge.sum()),'gradient_ratio':float(eg[edge].sum()/sg[edge].sum()) if edge.any() else None,'gradient_mae':float(np.abs(eg[edge]-sg[edge]).mean()) if edge.any() else None}
                row['plane_mean_shift']=[float((e-s).mean()) for s,e in zip(src,enc)]
                out['brightness_color_samples'].append({'frame':n,'bins':bins})
            out['frames'].append(row)
    finally:
        for p in readers:
            p.stdout.close()
            if p.poll() is None:p.terminate()
            p.wait()
    mids=(120,126,132,138,144) if case=='e04' else (116,118,120,122,124)
    summary={}
    for name in boxes:
        summary[name]={}
        for arm in ('source','target')+ (('synthesis',) if base else ()):
            vals=[out['frames'][n]['roi'][name][arm] for n in mids]
            summary[name][arm]={k:float(np.mean([v[k] for v in vals if v[k] is not None])) if any(v[k] is not None for v in vals) else None for k in vals[0]}
        summary[name]['paired_hf_correlation']=float(np.mean([out['frames'][n]['roi'][name]['paired_hf_correlation'] for n in mids]))
    out['midpoint_summary']=summary
    x.dump(d/(tag+'-texture.json'),out);print(case,tag,json.dumps(summary),flush=True)
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('case',choices=x.CASES);p.add_argument('tag');p.add_argument('path',type=x.pathlib.Path);p.add_argument('--base',type=x.pathlib.Path);a=p.parse_args();analyze(a.case,a.tag,a.path,a.base)
