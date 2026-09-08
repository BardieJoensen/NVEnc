#!/usr/bin/env python3
"""Check cost, detail and texture-region residual on the directional prototype.

The HF residual measurement includes quantization error. Its bounds apply to
these generated textures, not to arbitrary films or HDR display appearance.
"""
import json
from pathlib import Path
import statistics
import sys

from fidelity_compare import CASES as CONTROLLED_CASES
from texture_residual import CASES as TEXTURE_CASES


def check(report, residual):
    errors=[]
    def require(ok, message):
        if not ok: errors.append(message)
    require(report.get('complete') and len(report.get('cases',[]))==len(CONTROLLED_CASES)
            and {c['name'] for c in report.get('cases',[])}==set(CONTROLLED_CASES),
            'requires all 16 unique controlled cases')
    require(residual.get('complete') and len(residual.get('cases',[]))==len(TEXTURE_CASES)
            and {c['name'] for c in residual.get('cases',[])}==TEXTURE_CASES,
            'requires all eight unique texture residual cases')
    for c in report.get('cases',[]):
        name=c['name'];require(c.get('complete'),name+': incomplete')
        new=c['arms']['max-0.1-qp20']; baseline=c['baseline']
        for row in c['arms'].values():
            require(all(m.get('retain',0)<=row['retain_max']+1e-6 for m in row['model_frames']),name+': retention ceiling exceeded')
        old_ratio=statistics.median(t['output_sigma']/t['source_sigma'] for t in baseline['flat_trace'][8:])
        new_ratio=statistics.median(t['output_sigma']/t['source_sigma'] for t in new['flat_trace'][8:])
        require(new_ratio>=old_ratio-0.03 and new_ratio<1.10,name+': flat-region grain amplitude regressed')
        if name=='changing_strength':
            ratios=[t['output_sigma']/t['source_sigma'] for t in new['flat_trace'][24:]]
            require(len(ratios)==24 and min(ratios)>.85 and max(ratios)<1.10,'transition grain sag or overshoot')
            require(new['bytes']<c['previous_auto']['bytes']*.65,'transition cost recovery lost')
        if name=='strength_steps':
            require(new['decoded_hashes']==c['previous_auto']['decoded_hashes'],'unrepresentable curve lost source-preserving fallback')
        key=c.get('within_production_size')
        if key:
            matched=c['arms'][key]
            require(matched['bytes']<=baseline['bytes'],name+': false size-bound claim')
            matched_ratio=statistics.median(t['output_sigma']/t['source_sigma'] for t in matched['flat_trace'][8:])
            require(matched_ratio>=old_ratio-.03 and matched_ratio<1.10,
                    name+': matched-size grain amplitude regressed')
            if name in ['detail_fine','detail_coarse','detail_weak','woven_detail','woven_motion',
                        'woven_motion_odd','woven_coarse','pq_woven','pq_detail']:
                require(matched['separation']['frame_detail_transfer_gain']>=baseline['separation']['frame_detail_transfer_gain']-.01,
                        name+': matched-size detail regressed')
    for c in residual.get('cases',[]):
        old=c['arms']['production']['median_hf_residual_ratio']
        controlled=next(row for row in report['cases'] if row['name']==c['name'])
        keys={'max-0.1-qp20'}
        if controlled.get('within_production_size'):
            keys.add(controlled['within_production_size'])
        for key in sorted(keys):
            require(key in c['arms'],c['name']+': missing matched-size texture measurement')
            if key not in c['arms']: continue
            new=c['arms'][key]['median_hf_residual_ratio']
            require(new<=1.10 and new>=old-.05,
                    c['name']+': '+key+': texture-region residual excess or loss')
    return errors


if __name__=='__main__':
    failures=check(json.loads(Path(sys.argv[1]).read_text()),json.loads(Path(sys.argv[2]).read_text()))
    print(json.dumps(dict(passed=not failures,failures=failures),indent=2))
    raise SystemExit(bool(failures))
