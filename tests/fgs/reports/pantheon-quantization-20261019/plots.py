#!/usr/bin/env python3
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from study import ROOT,OLD
for case,tags in [('e04',['qp4','qp8','budget5']),('e05-1440',['qp4','qp4-tx32','budget1'])]:
 d=ROOT/case;fps=json.loads((d/'validity.json').read_text())['fps'];region='purple' if case=='e04' else 'shirt'
 docs={'baseline':json.loads((OLD/case/'b-base-texture.json').read_text()),**{t:json.loads((d/(t+'-texture.json')).read_text()) for t in tags}}
 fig,ax=plt.subplots(3,1,figsize=(12,9),sharex=True)
 arms=[('original',docs['baseline'],'source')]+[(t,v,'target') for t,v in docs.items()]
 for label,doc,arm in arms:
  vals=[f['roi'][region][arm] for f in doc['frames']]
  for a,key in zip(ax,['hf_sigma','acf1','temporal_hf_corr']):a.plot(np.arange(240)/fps,[v[key] for v in vals],label=label,lw=1)
 for a,ylabel in zip(ax,['HF amplitude (8-bit luma units)','Residual spatial ACF lag 1','Fixed-ROI temporal HF correlation']):a.set_ylabel(ylabel);a.grid(alpha=.2)
 ax[0].legend(ncol=3);ax[-1].set_xlabel('Seconds within scored window');fig.suptitle(case+' '+region+' — computed temporal evidence; fixed ROI crosses content changes; no playback observation');fig.tight_layout();fig.savefig(d/'temporal-evidence.png',dpi=140);plt.close(fig)
for c in ['e05-1460','e04']:
 d=ROOT/c;doc=json.loads((d/'representability-native.json').read_text());p=next(p for p in doc['probes'] if p['shape']=='prior_ar' and p['scale']==16)
 fig,ax=plt.subplots(figsize=(7,4));positions=np.arange(2);source=[doc['controls'][k]['source_conditional_hf'] for k in ['quiet','texture']];vals=[[v['conditional_hf'] for v in p['stats'][k]] for k in ['quiet','texture']];means=[np.mean(v) for v in vals]
 ax.bar(positions-.16,source,.3,label='Original conditioned HF');ax.bar(positions+.16,means,.3,label='Native AR scale 16, mean32 seeds');ax.errorbar(positions+.16,means,yerr=[[m-min(v) for m,v in zip(means,vals)],[max(v)-m for m,v in zip(means,vals)]],fmt='none',color='black',capsize=4,label='Seed range (not CI)')
 ax.set_xticks(positions,['Quiet','Stochastic']);ax.set_ylabel('Conditioned HF amplitude, 8-bit luma units');ax.set_title(f'{c} frame{doc["frame"]}: same constant base code{doc["base_10bit_code"]}');ax.legend(fontsize=8);ax.grid(axis='y',alpha=.2);fig.tight_layout();fig.savefig(d/'representability-ranges.png',dpi=160);plt.close(fig)
