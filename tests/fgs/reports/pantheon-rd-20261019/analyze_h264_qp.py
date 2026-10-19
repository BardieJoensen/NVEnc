#!/usr/bin/env python3
"""Paired visible-area H264 QP-state allocation, including same-frame contrast."""
import hashlib
import json
import sys
import numpy as np
from analyze import ROOT, x, BOXES

case='e05-1440';d=ROOT/'parent/h264-qp';receipts={};maps={}
variant=sys.argv[1] if len(sys.argv)>1 else 'aq1';assert variant in ('aq1','aq2')
other='aq10' if variant=='aq1' else 'aq20'
folders=[('aq05','baseline-validated'),(other,variant+'-validated')]
tags=[('aq05','x264-2x0'),(other,'x264-'+variant+'-2x1')]
for arm,folder in folders:
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
        row['relative_roi_minus_outside_change']=(row[other]['roi']-row[other]['outside'])-(row['aq05']['roi']-row['aq05']['outside'])
        series[name].append(row)
summary={}
for name,rows in series.items():
    summary[name]={}
    for label,pool in [('all240',rows),('midpoint5',[rows[n] for n in (116,118,120,122,124)]),('frame120',[rows[120]])]:
        summary[name][label]={a:{k:float(np.mean([r[a][k] for r in pool])) for k in ['roi','outside','whole']} for a in maps}
        summary[name][label]['relative_roi_minus_outside_change']=float(np.mean([r['relative_roi_minus_outside_change'] for r in pool]))
frames={a:r['probe']['frames'] for a,r in receipts.items()}
assert all(frames['aq05'][i]['pts']==frames[other][i]['pts'] for i in range(336))
keyframes={a:[i for i,f in enumerate(v) if f['key_frame']] for a,v in frames.items()}
type_changes=[i for i in range(336) if frames['aq05'][i]['pict_type']!=frames[other][i]['pict_type']]
audits={a:json.loads((ROOT/'parent/crosscodec'/case/tag/'packet-window-audit.json').read_text()) for a,tag in tags}
for a,audit in audits.items():
    assert audit['within_1pct'] and abs(audit['actual_mbps']/audit['target_mbps']-1)<=.01
    assert receipts[a]['input']['sha256']==audit['output']['sha256']
    assert (audit['source_mbps'],audit['target_mbps'])==(audits['aq05']['source_mbps'],audits['aq05']['target_mbps'])
rates={a:audit['actual_mbps'] for a,audit in audits.items()}
assert abs(rates[other]/rates['aq05']-1)<=.01
dest='allocation-comparison.json' if variant=='aq1' else 'allocation-comparison-aq2.json'
x.dump(d/dest,{'scope':'Visible-area QP_Y state, including skipped MBs; not proof residual quantization ran. Combined allocation/search contrast.',
    'rates':rates,'keyframes':keyframes,'picture_type_changed_frames':type_changes,'summary':summary,'frames':series,
    'receipt_provenance':{a:x.fingerprint(d/folder/'receipt.json') for a,folder in folders}})
print(json.dumps({'rates':rates,'keyframes':keyframes,'picture_type_changes':len(type_changes),'summary':summary},indent=2))
