#!/usr/bin/env python3
"""Visualize the bounded native seed probe without extrapolating to other models."""
import hashlib,json,os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(os.environ.get('PANTHEON_SOURCEBUDGET_ROOT','/tmp/downloads/codex-work/pantheon-sourcebudget-20261020'))
d=ROOT/'parent/grain-fixed-input';r=json.loads((d/'result.json').read_text());s=json.loads((d/'selection.json').read_text())
assert hashlib.sha256((d/'selection.json').read_bytes()).hexdigest()==r['selection']['sha256']
assert hashlib.sha256((d/'crops-and-masks.npz').read_bytes()).hexdigest()==r['crops']['sha256']
assert len(r['stats'])==32 and r['native_base_matches_validated_allplanes']
fig,ax=plt.subplots(figsize=(9,4));summary={}
for label,color in [('quiet','tab:blue'),('texture','tab:orange')]:
    vals=[v['regions'][label]['conditional_output_hf'] for v in r['stats']]
    lo,hi=s['controls'][label]['interval_10pct'];ax.plot(range(32),vals,'.-',color=color,label=label+' output')
    ax.axhspan(lo,hi,color=color,alpha=.18,label=label+' source ±10%')
    summary[label]={'conditional_hf_mean':float(np.mean(vals)),
        'whole_tile_output_acf1_mean':float(np.mean([v['regions'][label]['output']['acf1'] for v in r['stats']])),
        'endpoint_occupancy_max':max(v['regions'][label]['conditional_endpoint_occupancy'] for v in r['stats'])}
ax.set(xlabel='Fixed seed index',ylabel='HF amplitude (8-bit scale)',title='One unchanged base/frame; white AR, scale16 only')
ax.legend(ncols=2,fontsize=8);fig.tight_layout();fig.savefig(d/'seed-amplitudes.png',dpi=160)
ratio=[v['regions']['texture']['conditional_output_hf']/v['regions']['quiet']['conditional_output_hf'] for v in r['stats']]
summary['texture_over_quiet_ratio']={'mean':float(np.mean(ratio)),'min':min(ratio),'max':max(ratio)}
summary['input_result_sha256']=hashlib.sha256((d/'result.json').read_bytes()).hexdigest()
(d/'descriptive-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
