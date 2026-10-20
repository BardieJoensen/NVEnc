#!/usr/bin/env python3
"""Direct paired comparison of rate-calibrated libaom tune policies."""
import hashlib,json,os,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
ROOT=Path(os.environ.get('PANTHEON_SOURCEBUDGET_ROOT','/tmp/downloads/codex-work/pantheon-sourcebudget-20261020'))
case,other=sys.argv[1:];assert case=='e05-1440'
tags=['aom-1x1',other];assert other.startswith('aom-psnr-')
read=lambda p:json.loads(p.read_text())
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
paths={t:ROOT/'worker/runs'/case/t for t in tags}
runs=[read(paths[t]/'command.json') for t in tags]
assess=[read(paths[t]/'assessment.json') for t in tags]
sums=[read(ROOT/'parent/summary'/case/t/'summary.json') for t in tags]
controls=[read(paths[t]/'controls.json') for t in tags]
traces=[read(ROOT/'parent/scores'/case/(t+'-texture.json')) for t in tags]
for i,t in enumerate(tags):
    r,a,z=runs[i],assess[i],sums[i]
    assert (r['case'],r['tag'])==(case,t) and r['settings']['tune']==['ssim','psnr'][i]
    assert r['status']=='encoded' and r['returncode']==0 and a['matched_comparison_eligible']
    assert .99<=a['relative_source_rate']<=1
    if i==0:assert z==read(Path(__file__).resolve().parent/'aom-result.json')
    else:assert z['tune_policy']==r['settings']['tune']
    snapshot=r['passes']['pass1']['pass1_stats_snapshot']
    assert sha(snapshot['path'])==snapshot['sha256']
    assert z['rate']==a['actual_mbps']==r['packet_window']['actual_mbps']
    for k in ['command','assessment','controls','texture','metrics','decoder_validation','decode_identity','score_identity']:
        v=z['provenance'][k];assert sha(v['path'])==v['sha256']
    assert sha(paths[t]/'out.mkv')==r['mkv_output']['sha256']==a['output']['sha256']
    assert z['decoder_set']==['libdav1d','libaom-av1','av1_cuvid']
    assert z['controls']==controls[i]['summary']
a,b=runs
assert a['input']==b['input'] and a['validity']==b['validity'] and a['historical_input_validation']==b['historical_input_validation']
assert a['ffmpeg']==b['ffmpeg'] and a['ffprobe']==b['ffprobe']
assert {k:v for k,v in a['settings'].items() if k!='tune'}=={k:v for k,v in b['settings'].items() if k!='tune'}
for name in ['pass1','pass2']:
    ca,cb=[list(r['commands'][name]) for r in runs]
    for cmd in [ca,cb]:
        for flag in ['-tune','-b:v','-passlogfile']:cmd[cmd.index(flag)+1]='DECLARED_VARIABLE'
        if name=='pass2':cmd[-1]='OUTPUT_PATH'
    assert ca==cb,'Undeclared command difference.'
assert runs[0]['passes']['pass1']['pass1_stats_snapshot']['sha256']==runs[1]['passes']['pass1']['pass1_stats_snapshot']['sha256']
ratio=assess[1]['actual_mbps']/assess[0]['actual_mbps'];assert abs(ratio-1)<=.01
assert len(controls[0]['tiles'])==len(controls[1]['tiles'])==12870
for left,right in zip(controls[0]['tiles'],controls[1]['tiles']):
    assert all(left[k]==right[k] for k in ['frame','x','y','kind','outside_target','source','baseline'])
assert len(traces[0]['frames'])==len(traces[1]['frames'])==240
assert traces[0]['roi_xywh']==traces[1]['roi_xywh']
for left,right in zip(traces[0]['frames'],traces[1]['frames']):
    assert left['frame']==right['frame']
    for roi in traces[0]['roi_xywh']:assert left['roi'][roi]['source']==right['roi'][roi]['source']
changes={}
for kind in ['all','quiet','edge','flat_texture','other']:
    pairs=[(l['candidate'],r['candidate'],l['source']) for l,r in zip(controls[0]['tiles'],controls[1]['tiles']) if kind=='all' or l['kind']==kind]
    changes[kind]={'tiles':len(pairs),'ssim':controls[0]['summary'][kind]['candidate'],'psnr':controls[1]['summary'][kind]['candidate'],
        'mse_worse_count':sum(r['mse']>l['mse'] for l,r,s in pairs),
        'hf_error_worse_count':sum(abs(r['hf_sigma']-s['hf_sigma'])>abs(l['hf_sigma']-s['hf_sigma']) for l,r,s in pairs)}
quiet_hf_tails={}
for i,label in enumerate(['ssim','psnr']):
    vals=[r['candidate']['hf_sigma']-r['source']['hf_sigma'] for r in controls[i]['tiles'] if r['kind']=='quiet']
    quiet_hf_tails[label]={'count':len(vals),'min':min(vals),'p95':float(np.percentile(vals,95)),
                           'max':max(vals),'positive_count':sum(v>0 for v in vals)}
result={'case':case,'tags':tags,'actual_mbps':[a['actual_mbps'] for a in assess],'psnr_over_ssim_rate':ratio,
    'requested_kbps':[r['request_kbps'] for r in runs],
    'wall_seconds_336':[r['wall_seconds'] for r in runs],
    'same_pass1_stats':runs[0]['passes']['pass1']['pass1_stats_snapshot']['sha256']==runs[1]['passes']['pass1']['pass1_stats_snapshot']['sha256'],
    'keyframe_display_positions':[[i for i,p in enumerate(r['mkv_packets']) if 'K' in p['flags']] for r in runs],
    'texture':{roi:{label:sums[i]['texture'][roi][tags[i]]|{'source_hf_correlation':assess[i]['texture_screen'][roi]['source_hf_correlation'],'screen':assess[i]['texture_screen'][roi]} for i,label in enumerate(['ssim','psnr'])} for roi in traces[0]['roi_xywh']},
    'quiet_signed_hf_tails':quiet_hf_tails,
    'metrics':{label:sums[i]['metrics'][tags[i]] for i,label in enumerate(['ssim','psnr'])},'controls':changes,
    'face':{label:controls[i]['face']['candidate'] for i,label in enumerate(['ssim','psnr'])},
    'provenance':{t:{'summary':{'path':str(ROOT/'parent/summary'/case/t/'summary.json'),'sha256':sha(ROOT/'parent/summary'/case/t/'summary.json')}} for t in tags},
    'script_sha256':sha(__file__),'playback_observed':False,
    'scope':'Rate-calibrated tune-policy contrast: tune and requested TBR may differ, achieved packet rates are matched; encoder decisions are not held fixed.'}
out=ROOT/'parent/summary'/case/(other+'-paired-ssim.json');assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n')
fig,axes=plt.subplots(len(traces[0]['roi_xywh']),4,figsize=(19,8),squeeze=False)
for row,roi in enumerate(traces[0]['roi_xywh']):
    for col,field in enumerate(['hf_sigma','acf1','paired_hf_correlation','temporal_hf_corr']):
        ax=axes[row,col]
        series=[('source',traces[0],'source'),('SSIM',traces[0],'target'),('PSNR',traces[1],'target')]
        if field=='paired_hf_correlation':series=series[1:]
        for label,trace,arm in series:
            values=[v['roi'][roi][field] if field=='paired_hf_correlation' else v['roi'][roi][arm][field] for v in trace['frames']]
            ax.plot(range(240),[np.nan if z is None else z for z in values],label=label,linewidth=1)
        ax.set_title(roi+': '+field);ax.set_xlabel('Scored frame');ax.grid(alpha=.2)
        if col==0:ax.legend(fontsize=8)
fig.suptitle('Rate-calibrated tune policies; fixed-coordinate temporal correlation is not motion compensated')
fig.tight_layout();fig.savefig(out.with_suffix('.png'),dpi=140);plt.close(fig)
print(json.dumps(result,indent=2))
