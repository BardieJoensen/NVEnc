#!/usr/bin/env python3
"""Compact reporting only: reuse verified metrics without rerunning GPU jobs."""
import json,pathlib,csv
import numpy as np
import grain_model as g
x=g.x;HERE=pathlib.Path(__file__).resolve().parent
OLD=pathlib.Path('/media/merged-storage/cold-storage/docker-apps/pantheon-independent-investigation')
TAGS={'e04':'nv-fgs-10.0294','e05-1440':'nv-fgs-9.67652','e05-1420':'nv-fgs-9.00141','e05-1460':'nv-fgs-7.77255'}
rows=[];summary={}
for case,oldtag in TAGS.items():
    d=x.ROOT/case;summary[case]={}
    arms=[('A base',OLD/case,oldtag+'-base'),('A existing',OLD/case,oldtag),('A reconstruction-aware',d,'a-model')]
    if case in ('e04','e05-1440'):arms += [('B baseline',d,'b-base'),('B allocation',d,'b-allocation')]
    rate=json.loads((d/'a-rate.json').read_text())['fixed_picture_mbps']
    for name,root,tag in arms:
        a=json.loads((root/(tag+'-result.json')).read_text());p=a['pooled'];doc=json.loads((root/('metrics-cuda-'+tag+'.json')).read_text())
        r={'case':case,'arm':name,'mbps':a.get('actual_mbps',rate),'vmaf':a['vmaf'],'neg':a['vmaf_neg'],'vmaf_p1':a['vmaf_p1_excluding_frame0'],'neg_p1':float(np.percentile([f['metrics']['vmaf_neg'] for f in doc['frames'][1:]],1)),'ssimu2':a['ssimu2'],'ssimu2_p5':a['ssimu2_p5'],'butter_p95_max':a['butter_max_p95'],'psnr_y':a['psnr_y'],'ssim':a['ssim'],'cambi_fr_mean':p['cambi_full_reference']['mean'],'cambi_fr_max':p['cambi_full_reference']['max']}
        rows.append(r)
    for name in ('a-heldout-controls','a-color-controls','b-whole-window-controls'):
        if (d/(name+'.json')).exists():
            a=json.loads((d/(name+'.json')).read_text());summary[case][name]={k:v for k,v in a.items() if k not in ('tiles','chroma_tiles')}
    for tag in ('a-base','a-existing','a-model','b-base','b-allocation'):
        if (d/(tag+'-texture.json')).exists():summary[case][tag]=json.loads((d/(tag+'-texture.json')).read_text())['midpoint_summary']
    if (d/'b-allocation-qmaps.json').exists():
        q=json.loads((d/'b-allocation-qmaps.json').read_text());summary[case]['b-qindex-example']=q['frames'][134 if case=='e04' else 120]
    if (d/'b-stages.json').exists():summary[case]['b-stages']=json.loads((d/'b-stages.json').read_text())['stages']
    if (d/'b-all-stage-hashes.json').exists():
        a=json.loads((d/'b-all-stage-hashes.json').read_text());summary[case]['stage_changed_frame_counts']={key:sum(f['differences'].get(key,{}).get('changed_samples',0)>0 for f in a) for key in ('original -> coding_input','tf -> coding_input','pre_sb_dlf -> post_dlf','post_dlf -> final')}
with (HERE/'metrics.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
x.dump(HERE/'results.json',{'metrics':rows,'details':summary})
lines=['| Case / arm | Mbps | VMAF / NEG | VMAF p1 / NEG p1 | SSIMU2 / p5 | Butter p95(max) | PSNR Y / SSIM | CAMBI FR mean / max |','|---|---:|---:|---:|---:|---:|---:|---:|']
for r in rows:
    lines.append(f"| {r['case']} / {r['arm']} | {r['mbps']:.6f} | {r['vmaf']:.2f} / {r['neg']:.2f} | {r['vmaf_p1']:.2f} / {r['neg_p1']:.2f} | {r['ssimu2']:.2f} / {r['ssimu2_p5']:.2f} | {r['butter_p95_max']:.2f} | {r['psnr_y']:.2f} / {r['ssim']:.4f} | {r['cambi_fr_mean']:.4f} / {r['cambi_fr_max']:.4f} |")
(HERE/'METRICS.md').write_text('# Full-window metrics\n\nA uses fixed encoded bases; the experimental arm is an offline native synthesis render, not a new AV1 bitstream. Historical A base/existing scores are reused only after fresh pixel-exact native/FFmpeg validation. B uses matched-rate isolated SVT encodes. Rates count video packet bytes, not container size. VMAF/NEG p1 exclude frame0; all other scores include all240. CAMBI is supplementary CPU banding analysis with16 workers; all required full-reference metric paths are GPU. Butter/CAMBI lower is better.\n\n'+'\n'.join(lines)+'\n')
