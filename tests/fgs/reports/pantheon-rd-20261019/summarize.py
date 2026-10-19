#!/usr/bin/env python3
"""Compact measured evidence, preserving source artifact hashes and screen limits."""
import json
from pathlib import Path
import numpy as np
from analyze import ROOT, x

out=ROOT/'parent/summary';out.mkdir(exist_ok=True)
rows=[]
for case in ('e04','e05-1440'):
    source=json.loads((ROOT/'fixtures'/case/'validity.json').read_text())['source_mbps']
    for p in sorted((ROOT/'parent/scores'/case).glob('*-result.json')):
        tag=p.name[:-len('-result.json')];r=json.loads(p.read_text())
        tp=p.with_name(tag+'-texture.json');texture=json.loads(tp.read_text())
        cross=tag.startswith(('x264','x265'));d=ROOT/'parent'/('crosscodec' if cross else 'real')/case/tag
        if tag=='q32-tx32':d=ROOT/'worker'/(case+'-q32-control')
        cp=d/'command.json';command=json.loads(cp.read_text())
        wall=sum(a['seconds'] for a in command['passes']) if cross else command.get('seconds')
        if wall is None:wall=command['log_reported_total_execution_ms']/1000
        roi={}
        for name,v in texture['midpoint_summary'].items():
            hf=v['target']['hf_sigma']/v['source']['hf_sigma']-1
            acf=abs(v['target']['acf1']-v['source']['acf1'])
            roi[name]={**v,'hf_relative_error':hf,'acf1_abs_error':acf,
                       'provisional_hf_acf_pass':abs(hf)<=.1 and acf<=.05}
        control=d/'controls.json'
        evidence=[p,tp,cp]
        row={'case':case,'tag':tag,'source_mbps':source,'actual_mbps':r['actual_mbps'],
             'source_rate_multiple':r['actual_mbps']/source,'encode_seconds':wall,
             'encoded_frames':336,'wall_seconds_per_input_second':wall/(336/(24000/1001 if case=='e04' else 24)),
             'runtime_scope':('two passes, four x265 pool workers/two frame threads' if tag.startswith('x265') else 'two passes, four x264 threads') if cross else ('application-reported execution, lp1' if tag=='q32-tx32' else 'instrumented SVT wall, lp1'),
             'scores':{k:r[k] for k in ('vmaf','vmaf_neg','vmaf_p1_excluding_frame0','ssimu2',
                  'ssimu2_p5','butter_2norm','butter_max_p95','psnr_y','ssim','ciede2000')},
             'banding':{k:r['pooled'][k] for k in ('cambi','cambi_source','cambi_full_reference')},
             'midpoint_texture':roi}
        if control.exists():
            c=json.loads(control.read_text());row['controls']=c['summary'];row['face']=c.get('face');evidence.append(control)
            if cross:
                quiet=[z for z in c['tiles'] if z['kind']=='quiet']
                deltas=[z['candidate']['hf_sigma']-z['source']['hf_sigma'] for z in quiet]
                row['quiet_hf_signed_delta']={'count':len(deltas),'mean':float(np.mean(deltas)),
                    'p95':float(np.percentile(deltas,95)),'max':float(max(deltas)),
                    'worst_tile':max(quiet,key=lambda z:z['candidate']['hf_sigma']-z['source']['hf_sigma'])}
        if cross:
            ap=d/'packet-window-audit.json';a=json.loads(ap.read_text())
            assert a['within_1pct'] and abs(a['actual_mbps']-r['actual_mbps'])<1e-9
            row['rate_target_mbps']=a['target_mbps'];evidence.append(ap)
            dp=d/'decoder-validation.json';dv=json.loads(dp.read_text());assert dv['all336_allplanes_cpu_NVDEC_exact']
            evidence.append(dp)
        else:
            dp=p.with_name(tag+'-validation.json');dv=json.loads(dp.read_text());assert dv['all240_allplanes_app_dav1d_exact'];evidence.append(dp)
        row['evidence']=[x.fingerprint(z) for z in evidence];rows.append(row)
x.dump(out/'results.json',{'scope':'Known fixtures; provisional numerical screens, no playback or production qualification.',
    'screen':{'hf_relative_abs_max':.1,'acf1_abs_max':.05},'arms':rows})

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,axes=plt.subplots(1,2,figsize=(11,5.5))
pool=[r for r in rows if r['case']=='e05-1440' and r['tag'] not in ('q32-tx32','budget0')]
for name,ax in zip(('shirt','background'),axes):
    ax.axvspan(-10,10,color='green',alpha=.08);ax.axhspan(0,.05,color='green',alpha=.08)
    for r in pool:
        v=r['midpoint_texture'][name]
        label=r['tag']+' ('+format(r['actual_mbps'],'.2f')+' Mbps)'
        ax.scatter(100*v['hf_relative_error'],v['acf1_abs_error'],s=42,label=label)
    ax.set(title='E05 '+name,xlabel='HF amplitude error (%)',ylabel='ACF1 absolute error')
    ax.axvline(-10,color='gray',lw=.5);ax.axvline(10,color='gray',lw=.5);ax.axhline(.05,color='gray',lw=.5)
    ax.grid(alpha=.2)
fig.suptitle('Amplitude and spatial structure must both pass; green overlap is only a provisional screen')
handles,labels=axes[0].get_legend_handles_labels()
fig.legend(handles,labels,loc='lower center',ncol=3,fontsize=8)
fig.tight_layout(rect=[0,.19,1,.95])
fig.savefig(out/'texture-frontier.png',dpi=170);plt.close(fig)

for case,roi_name in [('e04','purple'),('e05-1440','shirt')]:
    tags=['budget1','high2x','x264-search11-3x1','x265-grain-2x1','x265-grain-2x0']
    available=[tag for tag in tags if any(r['case']==case and r['tag']==tag for r in rows)]
    if not available:continue
    fig,axes=plt.subplots(3,1,figsize=(11,8),sharex=True,layout='constrained')
    fps=24000/1001 if case=='e04' else 24
    for i,tag in enumerate(available):
        t=json.loads((ROOT/'parent/scores'/case/(tag+'-texture.json')).read_text())['frames']
        seconds=np.arange(240)/fps
        roi=[f['roi'][roi_name] for f in t]
        if i==0:axes[0].plot(seconds,[z['source']['hf_sigma'] for z in roi],color='black',label='Original',lw=1.5)
        axes[0].plot(seconds,[z['target']['hf_sigma'] for z in roi],label=tag,lw=.9)
        axes[1].plot(seconds,[abs(z['target']['acf1']-z['source']['acf1']) for z in roi],label=tag,lw=.9)
        edge=[(n/fps,f['strong_horizontal_edge']['gradient_mae']) for n,f in enumerate(t) if 'strong_horizontal_edge' in f]
        axes[2].plot([z[0] for z in edge],[z[1] for z in edge],label=tag,lw=.9,marker='.',ms=3)
    axes[0].set(ylabel='ROI HF amplitude');axes[1].set(ylabel='ROI ACF1 absolute error')
    axes[2].set(ylabel='Sampled full-frame edge MAE',xlabel='Scored-window time (seconds)')
    axes[1].axhline(.05,color='gray',ls='--',lw=.7)
    for ax in axes:ax.grid(alpha=.2)
    axes[0].legend(fontsize=8,ncol=2)
    fig.suptitle(case+' full-window traces; fixed coordinates cross different content and are not playback evidence')
    fig.savefig(out/(case+'-temporal.png'),dpi=150);plt.close(fig)
print('Summarized',len(rows),'validated scored arms:',out)
