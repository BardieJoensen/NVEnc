#!/usr/bin/env python3
"""Check decoded retention cost/fidelity against the preceding auto candidate."""
import argparse
import json
from pathlib import Path
import statistics

from fidelity_compare import CASES
from texture_residual import CASES as TEXTURES


def check(report, previous, residual):
    errors = []

    def require(condition, message):
        if not condition:
            errors.append(message)

    for name, value in [('candidate', report), ('previous', previous)]:
        require(value.get('complete') and len(value.get('cases', [])) == len(CASES)
                and {c['name'] for c in value.get('cases', [])} == set(CASES),
                name + ': all 16 unique controlled cases are required')
    require(residual.get('complete') and len(residual.get('cases', [])) == len(TEXTURES)
            and {c['name'] for c in residual.get('cases', [])} == TEXTURES,
            'all eight texture-residual cases are required')
    if errors:
        return errors
    old = {c['name']: c for c in previous['cases']}
    for case in report['cases']:
        name = case['name']
        require(case.get('complete'), name + ': incomplete')
        require(case['source'] == old[name]['source'], name + ': source changed')
        for key, current in case['arms'].items():
            require(current['qp'] == 20, name + ': quality setting changed')
            require(all(m.get('retain', 0) <= current['retain_max'] + 1e-6 for m in current['model_frames']),
                    name + ': retention ceiling exceeded')
            if key not in old[name]['arms']:
                continue
            reference = old[name]['arms'][key]
            if name == 'strength_steps':
                require(current['source_fallbacks'] == 0 and bool(current['strength_refit_frames']),
                        'sharp representable curve did not recover')
                require(current['bytes'] < reference['bytes'] * 0.55,
                        'sharp curve lost the measured cost reduction')
                continue  # Per-band correctness is required by strength_recovery_regression.py.
            old_ratio = statistics.median(t['output_sigma'] / t['source_sigma'] for t in reference['flat_trace'][8:])
            new_ratio = statistics.median(t['output_sigma'] / t['source_sigma'] for t in current['flat_trace'][8:])
            require(old_ratio - 0.03 <= new_ratio < 1.10, name + ': flat grain amplitude regressed')
            if name in TEXTURES and key == 'max-0.1-qp20':
                require(current['separation']['frame_detail_transfer_gain'] >=
                        reference['separation']['frame_detail_transfer_gain'] - 0.005,
                        name + ': measured picture-detail transfer regressed')
        current = case['arms']['max-0.1-qp20']
        reference = old[name]['arms']['max-0.1-qp20']
        if name == 'detail_fine':
            require(current['bytes'] < reference['bytes'] * 0.95,
                    'fine directional detail lost the measured cost reduction')
        if name == 'detail_coarse':
            require(current['bytes'] < reference['bytes'] * 0.99,
                    'coarse directional detail lost the measured cost reduction')
        if name == 'changing_strength':
            ratios = [r['output_sigma'] / r['source_sigma'] for r in current['flat_trace'][24:]]
            require(len(ratios) == 24 and min(ratios) > 0.85 and max(ratios) < 1.10,
                    'changing strength lost amplitude or overshot')
    for case in residual['cases']:
        prior = case['arms']['production']['median_hf_residual_ratio']
        current = case['arms']['max-0.1-qp20']['median_hf_residual_ratio']
        require(prior - 0.05 <= current <= 1.10,
                case['name'] + ': texture-region residual loss or excess')
    return errors


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--previous', type=Path, required=True)
    p.add_argument('--residual', type=Path, required=True)
    args = p.parse_args()
    errors = check(*(json.loads(path.read_text()) for path in [args.report, args.previous, args.residual]))
    print(json.dumps(dict(passed=not errors, errors=errors), indent=2))
    raise SystemExit(bool(errors))
