#!/usr/bin/env python3
"""Audit all-frame realized block/SB quantizer maps at the diagnostic rectangle."""
import json
import numpy as np
from study import ROOT,x
from texture import BOXES
for case,tags in [('e04',['detail','qp4','qp8','budget5']),('e05-1440',['detail2','qp4','qp4-tx32','budget1'])]:
 d=ROOT/case;xx,yy,w,h=next(iter(BOXES[case].values()));out={}
 for tag in tags:
  rows=[]
  for n in range(96,336):
   a=np.loadtxt(d/(tag+'-trace')/f'blocks-{n:04d}-a0-o0.csv',delimiter=',',ndmin=2);left=np.maximum(xx,a[:,3]);right=np.minimum(xx+w,a[:,3]+a[:,5]);top=np.maximum(yy,a[:,4]);bottom=np.minimum(yy+h,a[:,4]+a[:,6]);area=np.maximum(0,right-left)*np.maximum(0,bottom-top);mask=area>0
   assert area.sum()==w*h
   q=a[mask,7];assert np.all(q==a[mask,8]),(case,tag,n)
   if tag.startswith('budget'):assert np.all(q==16)
   rows.append({'frame':n-96,'min':float(q.min()),'max':float(q.max()),'mean':float(np.average(q,weights=area[mask]))})
  out[tag]={'min':min(r['min'] for r in rows),'max':max(r['max'] for r in rows),'mean':float(np.mean([r['mean'] for r in rows])),'all240_spatial_coverage_exact':True,'final_block_q_matches_sb_q':True,'frames':rows}
 x.dump(d/'realized-quantizer-maps.json',out);print(case,{k:{kk:v for kk,v in val.items() if kk!='frames'} for k,val in out.items()})
