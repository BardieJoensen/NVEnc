#!/usr/bin/env python3
"""Separate already-observed optimizer-only and mixed paths without new encodes."""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.ndimage import minimum_filter, maximum_filter
from aom_tu_binding import identity
from analyze_aom_tu import masked_hf, STAGES

p=argparse.ArgumentParser();p.add_argument('validation',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
v=json.loads(args.validation.read_text());assert v['status']=='admitted'
for key in ('maps','tu_records'):
    assert identity(v['artifacts'][key]['path'])==v['artifacts'][key]
a=np.load(v['artifacts']['maps']['path'],allow_pickle=False)
r=json.loads(Path(v['artifacts']['tu_records']['path']).read_text())
own=a['owner'];assert own.min()>=0 and own.max()<len(r)
flags=np.array([x['metadata']['quant_flags'] for x in r])[own]
exercised=a['exercised'].astype(bool)
assert set(np.unique(flags[exercised])).issubset({7,15})
same_owner=minimum_filter(own,3,mode='constant',cval=-1)==maximum_filter(own,3,mode='constant',cval=-2)
maps={k:a[k].astype(float)/4 for k in STAGES}
result={'script':identity(__file__),'admission':identity(args.validation),
        'dependencies':{'stage_analysis':identity(Path(__file__).with_name('analyze_aom_tu.py'))},
        'scope':'One observed final generation. Flags7 initial-to-final isolates invoked optimizer; flags15 combines optimizer and dropout. Groups contain different TUs and cannot be compared as randomized treatment arms. Same-owner 3x3 HF support; no legal counterfactual, coded-bit or playback claim.',
        'roi':{}}
for name,(x,y,w,h) in {'shirt':(1200,650,200,100),'background':(950,50,250,180),'face':(160,600,500,480),'full_frame':(0,0,1920,1080)}.items():
    sl=np.s_[y:y+h,x:x+w];out={'xywh':[x,y,w,h],'full_pixels':w*h,'groups':{}}
    for label,eligible in [('optimizer_only',exercised&(flags==7)),('optimizer_and_dropout',exercised&(flags==15)),('unexercised',~exercised)]:
        mask=eligible[sl]
        hf_mask=((minimum_filter(eligible.astype(np.uint8),3,mode='constant')>0)&same_owner)[sl][1:-1,1:-1]
        group={'pixels':int(mask.sum()),'intersecting_records':int(np.unique(own[sl][mask]).size),'stages':{}}
        for stage,image in maps.items():
            err=(image[sl]-maps['source'][sl])[mask]
            group['stages'][stage]={'mse':float(np.mean(err*err)) if err.size else None,
                                     'hf':masked_hf(image[sl],maps['source'][sl],hf_mask)}
        for before,after in [('raw','initial'),('initial','final')]:
            delta=(maps[after][sl]-maps[before][sl])[mask]
            group[before+'_to_'+after]={'changed_pixels':int(np.count_nonzero(delta)),
                                       'mse':float(np.mean(delta*delta)) if delta.size else None}
        out['groups'][label]=group
    assert sum(g['pixels'] for g in out['groups'].values())==w*h
    result['roi'][name]=out
with args.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
print(json.dumps({name:{label:{'pixels':g['pixels'],'HF':{s:z['hf']['hf_sigma'] for s,z in g['stages'].items()}} for label,g in roi['groups'].items()} for name,roi in result['roi'].items() if name!='full_frame'},indent=2))
