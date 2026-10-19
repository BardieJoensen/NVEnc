#!/usr/bin/env python3
"""Offline reconstruction-aware stochastic covariance model, no ROI fitting.

Train: frames 16k (plus immediate neighbors only for source stationarity),
checkerboard 32px tiles on 48px grid, excluding all established diagnostic ROIs.
Reject source edges/gradients, moving structure and temporally persistent HF.
Fit source/base covariance separately, never classify their pixel error as grain.
One model per detected interval; source lower-quartile amplitude cap per intensity.
That cap is not a guarantee of quiet-region protection (held-out tests fail it).
Native AV1 AR model and intensity curve; calibration uses training tiles only.
"""
import sys,json,pathlib
import numpy as np
from scipy.ndimage import gaussian_filter
HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'pantheon-independent-20261019'))
import investigate as x
from texture import BOXES
N,W,H=240,1920,1080
KNOTS=np.array([0,16,32,48,64,80,96,112,136,160,192,216,235,255])
POS=[(dy,dx) for dy in range(-3,1) for dx in range(-3,4) if dy<0 or dx<0]

def planes(mm,n):
    f=mm[n];return [f[:W*H].reshape(H,W),f[W*H:W*H*5//4].reshape(H//2,W//2),f[W*H*5//4:].reshape(H//2,W//2)]
def mm(p):return np.memmap(p,dtype='<u2',mode='r',shape=(N,W*H*3//2))
def hp(a):return a[1:-1,1:-1]-(a[:-2,1:-1]+a[2:,1:-1]+a[1:-1,:-2]+a[1:-1,2:])*.25
def ac(a,b):
    a=a-a.mean();b=b-b.mean();return float(np.mean(a*b)/(np.std(a)*np.std(b)+1e-9))
def spectrum(tile):
    # Remove a planar trend, not a decoded-base prediction error.
    yy,xx=np.mgrid[:32,:32];xx=xx-15.5;yy=yy-15.5
    z=tile-tile.mean();z=z-xx*(z*xx).sum()/(xx*xx).sum()-yy*(z*yy).sum()/(yy*yy).sum()
    f=np.fft.fft2(z*np.outer(np.hanning(32),np.hanning(32)))
    return (f.real*f.real+f.imag*f.imag)
def exclude(case,c,xx,yy):
    scale=1 if c==0 else 2
    return any(xx*scale<bx+bw+32 and (xx+32)*scale>bx-32 and yy*scale<by+bh+32 and (yy+32)*scale>by-32 for bx,by,bw,bh in BOXES[case].values())

def collect(case):
    d=x.ROOT/case;src=mm(d/'source.yuv');base=mm(d/'base.yuv')
    thumbs=np.stack([planes(src,n)[0][::16,::16].astype(float)/4 for n in range(N)])
    cuts=[0]+[int(n+1) for n,v in enumerate(np.mean(np.abs(np.diff(thumbs,axis=0)),axis=(1,2))) if v>8]+[N]
    rows=[];specs=[]
    for n in range(16,N-1,16):
        shot=next(i for i in range(len(cuts)-1) if cuts[i]<=n<cuts[i+1])
        if min(n-cuts[shot],cuts[shot+1]-n)<2:continue
        for c,(S,B,P,Q) in enumerate(zip(planes(src,n),planes(base,n),planes(src,n-1),planes(src,n+1))):
            S=S.astype(float)/4;B=B.astype(float)/4;P=P.astype(float)/4;Q=Q.astype(float)/4
            sm=gaussian_filter(S,2);pm=gaussian_filter(P,2);qm=gaussian_filter(Q,2)
            rh=S-sm;ph=P-pm;qh=Q-qm
            gy,gx=np.gradient(sm);grad=np.hypot(gx,gy)
            for iy,yy in enumerate(range(8,S.shape[0]-40,48)):
                for ix,xx in enumerate(range(8,S.shape[1]-40,48)):
                    if (ix+iy)%2 or exclude(case,c,xx,yy):continue
                    sl=np.s_[yy:yy+32,xx:xx+32];s=S[sl];b=B[sl]
                    g=float(np.percentile(grad[sl],95));motion=float(max(np.mean(np.abs(sm[sl]-pm[sl])),np.mean(np.abs(sm[sl]-qm[sl]))))
                    temporal=max(abs(ac(rh[sl],ph[sl])),abs(ac(rh[sl],qh[sl])))
                    if g>0.75 or np.ptp(sm[sl])>8 or motion>1.5 or temporal>.35:continue
                    sh=float(hp(s).std());bh=float(hp(b).std())
                    rows.append([n,shot,c,xx,yy,float(s.mean()),sh,bh,g,motion,temporal])
                    specs.append([spectrum(s),spectrum(b)])
        print(case,'training frame',n,'tiles',len(rows),flush=True)
    np.savez_compressed(d/'grain-training.npz',rows=np.array(rows),spectra=np.array(specs),cuts=np.array(cuts))
    x.dump(d/'grain-training.json',{'columns':['frame','shot','plane','x','y','mean','source_hp_sigma','base_hp_sigma','smooth_gradient_p95','smooth_temporal_mae','source_temporal_hf_corr_max'],'rows':rows,'cuts':cuts,'excluded_rois':BOXES[case],'training_frames':list(range(16,N-1,16))})

def fit(case):
    d=x.ROOT/case;data=np.load(d/'grain-training.npz');rows=data['rows'];specs=data['spectra'];cuts=data['cuts'];models=[]
    # High-frequency floor suppresses coherent low-frequency prediction/trend error.
    fy,fx=np.meshgrid(np.fft.fftfreq(32),np.fft.fftfreq(32),indexing='ij');mask=(fx*fx+fy*fy)>.06**2
    for shot in range(len(cuts)-1):
        channels=[]
        for c in range(3):
            ids=np.flatnonzero((rows[:,1]==shot)&(rows[:,2]==c));rr=rows[ids]
            if len(ids)<12:channels.append({'coeff':[0]*24,'target':[0.]*14,'tiles':len(ids)});continue
            # Positive missing covariance from source/base spectra, not error spectrum.
            ps=np.median(specs[ids,0],axis=0);pb=np.median(specs[ids,1],axis=0)
            p=np.maximum(ps-pb,0)*mask
            cov=np.fft.ifft2(p).real;v=float(cov[0,0])
            A=np.array([[cov[(a[0]-b[0])%32,(a[1]-b[1])%32] for b in POS] for a in POS]);b=np.array([cov[dy%32,dx%32] for dy,dx in POS])
            coeff=np.linalg.solve(A+np.eye(24)*max(v*.05,1e-6),b) if v>1e-6 else np.zeros(24)
            coeff=np.clip(np.rint(coeff*128),-128,127).astype(int)
            target=[];support=[]
            for knot in KNOTS:
                pool=rr[np.abs(rr[:,5]-knot)<=16]
                if len(pool)<8:target.append(0.);support.append(len(pool));continue
                missing=np.sqrt(np.maximum(pool[:,6]**2-pool[:,7]**2,0))
                # Source-based lower-quartile cap; not a spatial quiet-region guarantee.
                qcap=float(np.percentile(pool[:,6],25));goal=min(float(np.median(missing)),qcap)
                target.append(goal);support.append(len(pool))
            channels.append({'coeff':coeff.tolist(),'target':target,'tiles':len(ids),'support':support})
        models.append({'start':int(cuts[shot]),'end':int(cuts[shot+1]),'channels':channels})
    x.dump(d/'grain-fit.json',{'knots':KNOTS.tolist(),'models':models,'note':'Targets are five-tap HP sigma in 8-bit units; calibrate native synth on training tiles only.'})
    write(case,calibrated=False)

def write(case,calibrated=False):
    d=x.ROOT/case;doc=json.loads((d/'grain-fit.json').read_text());lines=[]
    for n in range(N):
        m=next(m for m in doc['models'] if m['start']<=n<m['end']);parts=[str((12345+n*7919)%65536),'10','3','7','0']
        for c,ch in enumerate(m['channels']):
            # Calibration starts with constant legal amplitude per plane (native synthesis is linear before clipping).
            scales=ch.get('scales',[64]*14) if calibrated else [64 if v>0 else 0 for v in ch['target']]
            knots=KNOTS if c==0 else np.array([0,32,64,96,128,160,192,216,235,255])
            vals=np.interp(knots,KNOTS,scales).round().astype(int)
            parts+=[str(len(knots))]+[str(v) for pair in zip(knots,vals) for v in pair]
            parts += list(map(str,ch['coeff']))+(['0'] if c else [])
        lines.append(' '.join(parts))
    (d/('model.txt' if calibrated else 'calibration-model.txt')).write_text('\n'.join(lines)+'\n')

def calibrate(case):
    d=x.ROOT/case;data=np.load(d/'grain-training.npz');rows=data['rows'];base=mm(d/'base.yuv');syn=mm(d/'calibration.yuv');doc=json.loads((d/'grain-fit.json').read_text())
    sigma=[]
    for row in rows:
        n,_,c,xx,yy=map(int,row[:5]);a=planes(syn,n)[c][yy:yy+32,xx:xx+32].astype(float);b=planes(base,n)[c][yy:yy+32,xx:xx+32].astype(float)
        sigma.append(float(hp((a-b)/4).std()))
    sigma=np.array(sigma)
    for shot,m in enumerate(doc['models']):
        for c,ch in enumerate(m['channels']):
            scales=[]
            for knot,goal in zip(KNOTS,ch['target']):
                ids=(rows[:,1]==shot)&(rows[:,2]==c)&(np.abs(rows[:,5]-knot)<=16)
                observed=float(np.median(sigma[ids])) if ids.any() else 0
                scales.append(int(np.clip(round(64*goal/observed),0,255)) if observed>.005 else 0)
            ch['scales']=scales
    x.dump(d/'grain-fit.json',doc);write(case,True)

if __name__=='__main__':
    action,case=sys.argv[1:];globals()[action](case)
