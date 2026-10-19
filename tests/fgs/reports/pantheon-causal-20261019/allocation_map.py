#!/usr/bin/env python3
"""One fixed allocation intervention: -12 qindex for lost, flat source texture.

Two-pass research map, all frames and SBs, not hand-selected ROI coordinates.
Within each 64x64 SB, require >= half 16x16 tiles to be source-flat (smoothed
gradient p95 < .75 code/pixel), source HP sigma >= .4 code, and reconstructed
HP sigma < .75 source. Quiet areas/strong edges do not independently qualify.
No positive qindex penalty is imposed; matched-rate RC supplies the tradeoff.
"""
import sys,json,pathlib
import numpy as np
from scipy.ndimage import gaussian_filter
import grain_model as g
x=g.x
def make(case):
    d=x.ROOT/case;p=d/'all-input.yuv'
    if not p.exists():x.run(['ffmpeg','-v','error','-threads','4','-i',d/'input.mkv','-pix_fmt','yuv420p10le','-f','rawvideo',p],d,'all-input-raw')
    src=np.memmap(p,dtype='<u2',mode='r',shape=(336,1920*1080*3//2))
    rp=d/'b-baseline-recon.yuv'
    if not rp.exists():
        sel=json.loads((d/'b-baseline-selection.json').read_text());rp=d/(sel['tag']+'-recon.yuv')
    rec=np.memmap(rp,dtype='<u2',mode='r',shape=src.shape)
    maps=np.zeros((336,17,30),dtype=np.int8);rows=[]
    for n in range(336):
        s=src[n,:1920*1080].reshape(1080,1920).astype(np.float32)/4;b=rec[n,:1920*1080].reshape(1080,1920).astype(np.float32)/4
        sm=gaussian_filter(s,2);dy,dx=np.gradient(sm);grad=np.hypot(dx,dy)
        def tiles(a):return a[:1072].reshape(67,16,120,16).transpose(0,2,1,3)
        def sig(a):return (a[:,:,1:-1,1:-1]-(a[:,:,:-2,1:-1]+a[:,:,2:,1:-1]+a[:,:,1:-1,:-2]+a[:,:,1:-1,2:])*.25).std(axis=(2,3))
        hs=sig(tiles(s));hb=sig(tiles(b))
        eligible=(np.percentile(tiles(grad),95,axis=(2,3))<.75)&(hs>=.4)&(hb<.75*hs)
        pad=np.zeros((68,120),dtype=np.int8);pad[:67]=eligible
        counts=pad.reshape(17,4,30,4).sum(axis=(1,3));totals=np.full((17,30),16);totals[-1]=12
        maps[n][counts/totals>=.5]=-12
        rows.append({'frame':n,'boosted_sbs':int((maps[n]!=0).sum()),'sbs':510})
    maps.tofile(d/'allocation-map.bin');x.dump(d/'allocation-map.json',{'shape':list(maps.shape),'dtype':'int8','delta_qindex':-12,'frames':rows,'criteria':__doc__})
    print(case,'boosted fraction',float((maps!=0).mean()),flush=True)
if __name__=='__main__':make(sys.argv[1])
