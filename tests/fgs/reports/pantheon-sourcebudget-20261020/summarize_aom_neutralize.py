#!/usr/bin/env python3
"""Pair admitted source-pixel neutralization with its byte-identical off policy."""
import hashlib,json,os,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(os.environ.get('PANTHEON_SOURCEBUDGET_ROOT','/tmp/downloads/codex-work/pantheon-sourcebudget-20261020'))
run_tag,=sys.argv[1:];case='e05-1440';new_tag='aom-neutralize-'+run_tag
labels=['baseline_psnr','source_neutralized'];tags=['aom-psnr-1x2',new_tag]
dirs=[ROOT/'worker/runs'/case/tags[0],ROOT/'parent/source-neutralize/runs'/run_tag]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def identity(p):return {'path':str(p),'sha256':sha(p)}
def read(p):return json.loads(p.read_text())
provenance={};runs=[];assess=[];controls=[];traces=[];metrics=[]
for label,tag,d in zip(labels,tags,dirs):
    paths={'run':d/'command.json','assessment':d/'assessment.json','controls':d/'controls.json',
           'decoder_validation':d/'decoder-validation.json',
           'texture':ROOT/'parent/scores'/case/(tag+'-texture.json'),
           'metrics':ROOT/'parent/scores'/case/(tag+'-result.json'),
           'decode_identity':ROOT/'parent/scores'/case/(tag+'-decoded.decode-identity.json'),
           'score_identity':ROOT/'parent/scores'/case/(tag+'-score-identity.json'),
           'packet_window':d/'packet-window.json',
           **{prefix:ROOT/'parent/scores'/case/(prefix+'-'+tag+'.json') for prefix in ('metrics-cuda','ssimu2','butter')}}
    data={k:read(p) for k,p in paths.items()};provenance[label]={k:identity(p) for k,p in paths.items()}
    r,a,c,t,m=[data[k] for k in ('run','assessment','controls','texture','metrics')]
    assert r['status']=='encoded' and r['returncode']==0
    assert a['matched_comparison_eligible'] and a['practical_rate_eligible'] and .99<=a['relative_source_rate']<=1
    assert a['all336_decoder_identity'] and a['all240_scored_planes_match']
    assert data['decoder_validation']['all336_allplanes_libaom_dav1d_NVDEC_exact']
    assert sha(d/'out.mkv')==a['output']['sha256']==data['decoder_validation']['output']['sha256']==data['decode_identity']['input']['sha256']
    assert sha(d/'dav1d-decoded.yuv')==data['decoder_validation']['decoded_raw']['sha256']
    assert sha(ROOT/'parent/scores'/case/(tag+'-decoded.mkv'))==data['score_identity']['distorted']['sha256']
    assert sha(ROOT/'parent/scores'/case/'ref.mkv')==data['score_identity']['reference']['sha256']
    assert m['encode']==str(d/'out.mkv') and abs(m['actual_mbps']-a['actual_mbps'])<1e-10
    assert a['controls']==c['summary'] and a['face']==c['face']
    assert len(c['tiles'])==12870 and len(t['frames'])==240
    assert len({(v['frame'],v['x'],v['y']) for v in c['tiles']})==12870
    assert len({v['frame'] for v in c['tiles']})==15 and all(0<=v['frame']<240 for v in c['tiles'])
    assert [v['frame'] for v in t['frames']]==list(range(240))
    assert len(data['metrics-cuda']['frames'])==len(data['ssimu2'])==len(data['butter'])==240
    assert [v['frameNum'] for v in data['metrics-cuda']['frames']]==list(range(240))
    assert sha(a['script']['path'])==a['script']['sha256']
    assert abs(data['packet_window']['actual_mbps']-a['actual_mbps'])<1e-10
    if label=='source_neutralized':assert a['packet_receipt']['sha256']==sha(paths['packet_window'])
    runs.append(r);assess.append(a);controls.append(c);traces.append(t);metrics.append(m)
assert runs[0]['input']['sha256']==runs[1]['input']['sha256']
assert runs[0]['passes']['pass1']['pass1_stats_snapshot']['sha256']==runs[1]['stats_original']['sha256']
assert runs[0]['request_kbps']==runs[1]['request_kbps']==11671
admission_path=ROOT/'parent/source-neutralize'/(run_tag+'-validated.json');admission=read(admission_path)
assert admission['status']=='admitted' and admission['arm']=='on'
assert admission['provenance']['run']==identity(dirs[1]/'command.json')
assert assess[1]['source_pixel_admission']['sha256']==sha(admission_path)
provenance['admission']=identity(admission_path)
off_path=Path(admission['provenance']['control']['path']);off=read(off_path)
assert admission['provenance']['control']==identity(off_path)
assert off['status']=='admitted' and off['arm']=='off' and off['exact_installed_ivf']
assert off['provenance']['build']==admission['provenance']['build']
assert off['summary']['selected']==off['summary']['effective']
assert off['all_coded_events_matched'] and off['all336_source_indices_bound'] and off['selected_effective_bijection']
off_run_path=Path(off['provenance']['run']['path']);off_run=read(off_run_path)
assert off['provenance']['run']==identity(off_run_path)
assert off_run['output']['sha256']==runs[0]['ivf_sha256']==sha(off_run['output']['path'])
provenance['off_control']=identity(off_path)
ratio=assess[1]['actual_mbps']/assess[0]['actual_mbps'];assert abs(ratio-1)<=.01
assert traces[0]['roi_xywh']==traces[1]['roi_xywh']
for l,r in zip(controls[0]['tiles'],controls[1]['tiles']):
    assert all(l[k]==r[k] for k in ('frame','x','y','kind','outside_target','source','baseline'))
for l,r in zip(traces[0]['frames'],traces[1]['frames']):
    assert l['frame']==r['frame']
    for roi in traces[0]['roi_xywh']:assert l['roi'][roi]['source']==r['roi'][roi]['source']
changes={}
for kind in ('all','quiet','edge','flat_texture','other'):
    pairs=[(l['candidate'],r['candidate'],l['source']) for l,r in zip(controls[0]['tiles'],controls[1]['tiles']) if kind=='all' or l['kind']==kind]
    changes[kind]={'tiles':len(pairs),**{label:controls[i]['summary'][kind]['candidate'] for i,label in enumerate(labels)},
        'mse_worse_count':sum(r['mse']>l['mse'] for l,r,s in pairs),
        'hf_error_worse_count':sum(abs(r['hf_sigma']-s['hf_sigma'])>abs(l['hf_sigma']-s['hf_sigma']) for l,r,s in pairs)}
quiet={};metric_summary={}
for i,label in enumerate(labels):
    vals=[r['candidate']['hf_sigma']-r['source']['hf_sigma'] for r in controls[i]['tiles'] if r['kind']=='quiet']
    quiet[label]={'count':len(vals),'min':min(vals),'p95':float(np.percentile(vals,95)),'max':max(vals),'positive_count':sum(v>0 for v in vals)}
    m=metrics[i];metric_summary[label]={k:m[k] for k in ('actual_mbps','vmaf','vmaf_neg','vmaf_p1_excluding_frame0','ssimu2','ssimu2_p5','butter_max_p95','psnr_y','ssim')}
    metric_summary[label]['cambi_fr_mean']=m['pooled']['cambi_full_reference']['mean'];metric_summary[label]['cambi_fr_max']=m['pooled']['cambi_full_reference']['max']
result={'case':case,'tags':tags,'actual_mbps':[a['actual_mbps'] for a in assess],
    'source_mbps':assess[1]['source_mbps'],'on_over_off_rate':ratio,'requested_kbps':[r['request_kbps'] for r in runs],
    'runtime':{'installed_baseline_both_passes_seconds':runs[0]['wall_seconds'],
        'neutralized_instrumented_pass2_seconds':runs[1]['pass2_wall_seconds'],
        'scope':'Replay reused original first-pass statistics; no end-to-end neutralized runtime measured.'},
    'source_intervention':admission['summary'],
    'texture':{roi:{'source':traces[0]['midpoint_summary'][roi]['source'],
        **{label:traces[i]['midpoint_summary'][roi]['target']|{'screen':assess[i]['texture_screen'][roi]} for i,label in enumerate(labels)}} for roi in traces[0]['roi_xywh']},
    'metrics':metric_summary,'controls':changes,'quiet_signed_hf_tails':quiet,
    'face':{label:controls[i]['face']['candidate'] for i,label in enumerate(labels)},
    'provenance':provenance,'script':identity(__file__),'playback_observed':False,
    'scope':'Source-pixel contrast with retained analysis and possible downstream coding feedback; known-fixture numeric screen only.'}
out=ROOT/'parent/source-neutralize'/(run_tag+'-summary.json');assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n')
fig,axes=plt.subplots(len(traces[0]['roi_xywh']),4,figsize=(19,8),squeeze=False)
for row,roi in enumerate(traces[0]['roi_xywh']):
    for col,field in enumerate(('hf_sigma','acf1','paired_hf_correlation','temporal_hf_corr')):
        ax=axes[row,col];series=[('source',traces[0],'source'),(labels[0],traces[0],'target'),(labels[1],traces[1],'target')]
        if field=='paired_hf_correlation':series=series[1:]
        for label,trace,arm in series:
            vals=[v['roi'][roi][field] if field=='paired_hf_correlation' else v['roi'][roi][arm][field] for v in trace['frames']]
            ax.plot(range(240),[np.nan if v is None else v for v in vals],label=label,linewidth=1)
        ax.set_title(roi+': '+field);ax.set_xlabel('Scored frame');ax.grid(alpha=.2)
        if col==0:ax.legend(fontsize=7)
fig.suptitle('Source-pixel contrast; fixed-coordinate temporal correlation is not motion compensated')
fig.tight_layout();fig.savefig(out.with_suffix('.png'),dpi=140);plt.close(fig)
print(json.dumps({k:result[k] for k in ('actual_mbps','on_over_off_rate','texture','metrics','face')},indent=2))
