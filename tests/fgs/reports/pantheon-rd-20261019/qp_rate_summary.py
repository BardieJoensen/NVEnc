#!/usr/bin/env python3
"""Visible-area shirt QP state for the complete two-pass analysis/rate factorial."""
import hashlib
import json
import numpy as np
from analyze import ROOT, BOXES, x

d=ROOT/'parent/h264-qp';xx,yy,w,h=BOXES['e05-1440']['shirt']
xs=np.arange(120)*16;ys=np.arange(68)*16
wx=np.maximum(0,np.minimum(xs+16,xx+w)-np.maximum(xs,xx))
wy=np.maximum(0,np.minimum(ys+16,min(yy+h,1080))-np.maximum(ys,yy))
weights=wy[:,None]*wx[None,:];assert weights.sum()==w*h
out={}
for folder,tag in [('aq1-validated','x264-aq1-2x1'),('search11-validated','x264-search11-2x0'),
                   ('search11-3x-validated','x264-search11-3x1'),('search8-3x-validated','x264-search8-3x0')]:
    path=d/folder;p=path/'qp-state.i8';receipt=json.loads((path/'receipt.json').read_text())
    assert hashlib.sha256(p.read_bytes()).hexdigest()==receipt['map']['sha256']
    assert receipt['unique_complete_grids'] and receipt['rows']==336*8160
    audit=json.loads((ROOT/'parent/crosscodec/e05-1440'/tag/'packet-window-audit.json').read_text())
    assert audit['within_1pct'] and audit['output']['sha256']==receipt['input']['sha256']
    a=np.fromfile(p,dtype='i1').reshape(336,68,120)
    series=np.einsum('fyx,yx->f',a,weights)/weights.sum()
    out[tag]={'midpoint5':float(series[[212,214,216,218,220]].mean()),
              'all240':float(series[96:336].mean()),'actual_mbps':audit['actual_mbps'],
              'receipt':x.fingerprint(path/'receipt.json')}
x.dump(d/'shirt-rate-qp-summary.json',{'scope':'QP_Y decoder state, including skipped MBs; not proof quantization ran. Different modes/transforms prevent interpreting the QP index alone as preservation.',
    'roi_xywh':[xx,yy,w,h],'arms':out,'script':x.fingerprint(__file__)})
print(out)
