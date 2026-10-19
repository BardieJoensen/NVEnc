#!/usr/bin/env python3
"""Paired visible-area H264 QP-state allocation, including same-frame contrast."""
import hashlib
import json
import numpy as np
from analyze import ROOT, x, BOXES

case='e05-1440';d=ROOT/'parent/h264-qp';receipts={};maps={}
for arm,folder in [('aq05','baseline-validated'),('aq10','aq1-validated')]:
    r=json.loads((d/folder/'receipt.json').read_text());p=d/folder/'qp-state.i8'
    assert hashlib.sha256(p.read_bytes()).hexdigest()==r['map']['sha256']
    assert r['unique_complete_grids'] and r['rows']==336*8160
    maps[arm]=np.fromfile(p,dtype='i1').reshape(336,68,120).astype(float)
    receipts[arm]=r
def weights(box):
    xx,yy,w,h=box;xs=np.arange(120)*16;ys=np.arange(68)*16
    wx=np.maximum(0,np.minimum(xs+16,xx+w)-np.maximum(xs,xx))
    wy=np.maximum(0,np.minimum(ys+16,min(yy+h,1080))-np.maximum(ys,yy))
    return wy[:,None]*wx[None,:]
whole=weights([0,0,1920,1080]);assert whole.sum()==1920*1080
regions={**BOXES[case],'face':[160,600,500,480]};series={}
for name,box in regions.items():
    roi=weights(box);outside=whole-roi;assert np.all(outside>=0)
    by={}
    for arm,m in maps.items():
        by[arm]={'roi':np.einsum('fyx,yx->f',m,roi)/roi.sum(),
                 'outside':np.einsum('fyx,yx->f',m,outside)/outside.sum(),
                 'whole':np.einsum('fyx,yx->f',m,whole)/whole.sum()}
    series[name]=[]
    for n in range(240):
        f=n+96;row={'frame':n,**{a:{k:float(z[f]) for k,z in v.items()} for a,v in by.items()}}
        row['relative_roi_minus_outside_change']=(row['aq10']['roi']-row['aq10']['outside'])-(row['aq05']['roi']-row['aq05']['outside'])
        series[name].append(row)
summary={}
for name,rows in series.items():
    summary[name]={}
    for label,pool in [('all240',rows),('midpoint5',[rows[n] for n in (116,118,120,122,124)]),('frame120',[rows[120]])]:
        summary[name][label]={a:{k:float(np.mean([r[a][k] for r in pool])) for k in ['roi','outside','whole']} for a in maps}
        summary[name][label]['relative_roi_minus_outside_change']=float(np.mean([r['relative_roi_minus_outside_change'] for r in pool]))
frames={a:r['probe']['frames'] for a,r in receipts.items()}
assert all(frames['aq05'][i]['pts']==frames['aq10'][i]['pts'] for i in range(336))
keyframes={a:[i for i,f in enumerate(v) if f['key_frame']] for a,v in frames.items()}
type_changes=[i for i in range(336) if frames['aq05'][i]['pict_type']!=frames['aq10'][i]['pict_type']]
rates={a:json.loads((ROOT/'parent/crosscodec'/case/tag/'packet-window-audit.json').read_text())['actual_mbps']
       for a,tag in [('aq05','x264-2x0'),('aq10','x264-aq1-2x1')]}
assert abs(rates['aq10']/rates['aq05']-1)<=.01
x.dump(d/'allocation-comparison.json',{'scope':'Visible-area QP_Y state, including skipped MBs; not proof residual quantization ran. Combined allocation/search contrast.',
    'rates':rates,'keyframes':keyframes,'picture_type_changed_frames':type_changes,'summary':summary,'frames':series,
    'receipt_provenance':{a:x.fingerprint(d/folder/'receipt.json') for a,folder in [('aq05','baseline-validated'),('aq10','aq1-validated')]}})
print(json.dumps({'rates':rates,'keyframes':keyframes,'picture_type_changes':len(type_changes),'summary':summary},indent=2))
