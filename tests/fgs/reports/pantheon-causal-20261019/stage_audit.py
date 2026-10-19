#!/usr/bin/env python3
"""Full-frame stage hashes/differences and measured spatial allocation maps."""
import sys,json,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import grain_model as g
from texture import BOXES
x=g.x
def rows(p):
    a=np.atleast_2d(np.loadtxt(p,delimiter=','))
    return np.array(list({int(r[0]):r for r in a}.values()))
def audit(case):
    d=x.ROOT/case;out=[]
    for n in range(240):
        ar={};hashes={}
        for stage in ('original','tf','coding_input','pre_sb_dlf','post_dlf','final'):
            paths=list((d/'trace').glob(f'{stage}-{n+96:04d}-*.yuv'))
            if not paths:continue
            assert len(paths)==1
            b=paths[0].read_bytes();hashes[stage]=hashlib.sha256(b).hexdigest();ar[stage]=np.frombuffer(b,dtype='<u2')
        dif={}
        for a,b in [('original','coding_input'),('tf','coding_input'),('pre_sb_dlf','post_dlf'),('post_dlf','final')]:
            if a not in ar or b not in ar:continue
            z=ar[a].astype(np.int16)-ar[b].astype(np.int16)
            dif[a+' -> '+b]={'changed_samples':int(np.count_nonzero(z)),'mae_8bit':float(np.abs(z).mean()/4),'max_abs_8bit':float(np.abs(z).max()/4)}
        out.append({'frame':n,'sha256':hashes,'differences':dif})
    x.dump(d/'b-all-stage-hashes.json',out)
    sel=json.loads((d/'b-allocation-selection.json').read_text());td=__import__('pathlib').Path(sel['trace']);mp=np.fromfile(d/'allocation-map.bin',dtype='i1').reshape(336,17,30);maps=[]
    for n in range(240):
        a=rows(next((d/'trace').glob(f'sb-{n+96:04d}-*.csv')));b=rows(next(td.glob(f'sb-{n+96:04d}-*.csv')))
        assert len(a)==len(b)==510
        def qm(ar):
            q=np.zeros((17,30));seen=set()
            for r in ar:
                k,xx,yy,size,qindex,base,count=r
                assert size==64 and k==int(yy//64)*30+int(xx//64)
                assert k not in seen;seen.add(k);q[int(yy//64),int(xx//64)]=qindex
            return q
        qa,qb=qm(a),qm(b);base=float(b[0,5]);intended=mp[n+96]
        # delta_q_res normalizes to legal qindex; compare actual values, not just map.
        maps.append({'frame':n,'baseline_base':float(a[0,5]),'intervention_base':base,'baseline_q_mean':float(qa.mean()),'intervention_q_mean':float(qb.mean()),'intervention_vs_framebase_values':np.unique(qb-base).tolist(),'intended_selected_sbs':int((intended!=0).sum()),'selected_actual_mean':float(qb[intended!=0].mean()) if (intended!=0).any() else None,'regions':{}})
        for name,(cx,cy,w,h) in BOXES[case].items():
            yy,xx=np.mgrid[:17,:30];weights=np.maximum(0,np.minimum(xx*64+64,cx+w)-np.maximum(xx*64,cx))*np.maximum(0,np.minimum(yy*64+64,cy+h)-np.maximum(yy*64,cy))
            maps[-1]['regions'][name]={'baseline_q':float(np.average(qa,weights=weights)),'intervention_q':float(np.average(qb,weights=weights)),'selected_coverage':float(np.average(intended!=0,weights=weights))}
        if n==(134 if case=='e04' else 120):
            fig,axes=plt.subplots(1,3,figsize=(15,5));vmin=min(qa.min(),qb.min());vmax=max(qa.max(),qb.max())
            for ax,ar,label in zip(axes,[qa,qb,intended],['Baseline actual SB qindex','Intervention actual SB qindex','Requested delta map']):
                im=ax.imshow(ar,extent=[0,1920,1088,0],interpolation='nearest',vmin=vmin if ar is not intended else -12,vmax=vmax if ar is not intended else 0)
                ax.set_ylim(1080,0)
                for name,(xx,yy,w,h) in BOXES[case].items():ax.add_patch(Rectangle((xx,yy),w,h,fill=False,edgecolor='red',lw=1.5));ax.text(xx,yy,name,color='red',fontsize=8)
                ax.set_title(label);fig.colorbar(im,ax=ax,shrink=.65)
            fig.suptitle(f'{case}, scored frame {n}; 64x64 SB coordinates, cropped bottom row');fig.tight_layout();fig.savefig(d/'b-qindex-maps.png',dpi=130);plt.close(fig)
    x.dump(d/'b-allocation-qmaps.json',{'frames':maps,'all240_spatial_indices_verified':True,'note':'qindex is the encoder quantization index, not QP and not measured bit allocation. Actual SB qindex after initialization/normalization is logged.'})
    print(case,'stage/map audit complete',flush=True)
if __name__=='__main__':audit(sys.argv[1])
