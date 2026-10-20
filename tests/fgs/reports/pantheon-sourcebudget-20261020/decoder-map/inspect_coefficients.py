#!/usr/bin/env python3
"""Inspect every admitted coefficient-bearing unit intersecting frozen ROIs."""
import json,pathlib,hashlib,sys
import numpy as np
P=pathlib.Path(__file__).resolve().parent;A=P/'admitted-1'
def ident(p):return dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size=p.stat().st_size)
a=json.loads((A/'admission.json').read_text());assert a['status']=='admitted'
for k in ('units','leaves'):assert ident(pathlib.Path(a['artifacts'][k]['path']))==a['artifacts'][k]
assert ident(pathlib.Path(a['payload']['path']))==a['payload']
units=json.loads((A/'units.json').read_text());leaves=json.loads((A/'leaves.json').read_text());data=pathlib.Path(a['payload']['path']).read_bytes();result={}
for name,(x,y,w,h) in {'shirt':(1200,650,200,100),'background':(950,50,250,180),'face':(160,600,500,480)}.items():
 rows=[]
 for t in units:
  area=max(0,min(x+w,t['x']+t['w'])-max(x,t['x']))*max(0,min(y+h,t['y']+t['h'])-max(y,t['y']))
  if not area or t['category']!=4:continue
  c=np.frombuffer(data,dtype='<i4',count=t['coeff_count'],offset=t['coeff_offset']);leaf=leaves[t['leaf']]
  rows.append(dict(id=t['id'],leaf=t['leaf'],roi_intersection_area=area,xywh=[t[k] for k in ('x','y','w','h')],tx_type=t['tx_type'],eob=t['eob'],coeff_count=t['coeff_count'],nonzero=int((c!=0).sum()),nonzero_beyond_index0=int((c[1:]!=0).sum()),coded_qindex=t['coded_qindex'],mode=leaf['mode'],inter=leaf['inter'],refs=leaf['refs']))
 result[name]=dict(xywh=[x,y,w,h],all_intersecting_EOBpositive_units=rows)
out=P/'coefficient-inspection-2.json';assert not out.exists()
out.write_text(json.dumps(dict(scope='Every admitted coefficient-present unit in frozen ROIs; beyond-index0 means AC only for DCT_DCT. Counts are not coded bits or encoder prequantization evidence.',admission=ident(A/'admission.json'),script=ident(pathlib.Path(__file__)),python=ident(pathlib.Path(sys.executable)),roi=result),indent=2)+'\n')
print(ident(out))
