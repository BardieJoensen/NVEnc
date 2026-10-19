#!/usr/bin/env python3
"""Summarize measured temporal synthesis behavior, without claiming playback."""
import json,numpy as np
import grain_model as g
x=g.x
for case in ('e04','e05-1440','e05-1420','e05-1460'):
    d=x.ROOT/case;a=json.loads((d/'a-model-texture.json').read_text());fit=json.loads((d/'grain-fit.json').read_text());out={'note':'Fixed-ROI correlations are motion/scene confounded. Model intervals come from source-thumbnail thresholding, not verified scene cuts. No temporal blending; independent seed per display frame.','regions':{}}
    cuts={m['start'] for m in fit['models'] if m['start']}
    for name in a['roi_xywh']:
        rows=[];valid=[]
        for n,f in enumerate(a['frames']):
            r=f['roi'][name];corr=r['synthesis']['temporal_hf_corr']
            if r['synthesis']['hf_sigma']>.1 and corr is not None:valid.append(corr)
            if n:
                old=a['frames'][n-1]['roi'][name]
                rows.append({'frame':n,'model_boundary':n in cuts,'source_frame_mae':f['source_mean_abs_temporal_change'],'source_hf_change':r['source']['hf_sigma']-old['source']['hf_sigma'],'synthesis_hf_change':r['synthesis']['hf_sigma']-old['synthesis']['hf_sigma'],'source_mean':r['source']['mean']})
        out['regions'][name]={'active_synthesis_frame_pairs':len(valid),'median_synthesis_temporal_corr':float(np.median(valid)) if valid else None,'largest_synthesis_amplitude_jumps':sorted(rows,key=lambda r:abs(r['synthesis_hf_change']),reverse=True)[:12],'all_model_boundaries':[r for r in rows if r['model_boundary']]}
    x.dump(d/'a-temporal-audit.json',out)
