#!/usr/bin/env python3
"""Fixture-specific acceptance checks for repeatable-detail protection.

These controls cover the deterministic 48-frame experiment. They are not
thresholds for arbitrary films or a claim about subjective watchability.
The rejected full-retention prototype must fail the matched-size checks.
"""
import argparse
import json
from pathlib import Path
import statistics


def check(report):
    failures = []

    def require(condition, message):
        if not condition:
            failures.append(message)

    require(report.get('complete'), 'experiment incomplete')
    cases = {c['name']: c for c in report['cases']}
    required = ['woven_detail', 'woven_motion', 'woven_disappear', 'woven_coarse',
                'flat_coarse', 'detail_weak', 'pq_woven']
    if not all(name in cases for name in required):
        return failures + ['missing required fixtures']
    for name in required:
        require(cases[name].get('complete') and cases[name]['source']['frames'] == 48,
                name + ': requires the complete 48-frame fixture')
    for name in ['woven_detail', 'woven_motion', 'pq_woven'] + (
            ['woven_motion_odd'] if 'woven_motion_odd' in cases else []):
        case = cases[name]
        baseline = case['arms']['old-auto']
        candidate = case['arms'].get(case.get('no_larger_arm'))
        require(candidate is not None, name + ': no candidate fits baseline size')
        if candidate:
            require(candidate['bytes'] <= baseline['bytes'], name + ': size increased')
            gain = candidate['separation']['frame_detail_transfer_gain']
            old_gain = baseline['separation']['frame_detail_transfer_gain']
            require(gain >= old_gain + (0.02 if name == 'pq_woven' else 0.025),
                    name + ': lost matched-size detail benefit')

    cut = cases['woven_disappear']['arms']
    require(all(new['texture_base_error_sigma'] <= old['texture_base_error_sigma'] * 1.05 + 0.03
                for old, new in zip(cut['old-auto']['flat_trace'][24:], cut['new-auto']['flat_trace'][24:])),
            'texture removal: persistent base error after cut')
    for name in ['woven_coarse', 'flat_coarse']:
        arms = cases[name]['arms']
        require(arms['new-auto']['bytes'] <= arms['old-auto']['bytes'] * 1.05,
                name + ': unnecessary fixed-QP cost on coarse-grain control')
        ratios = [statistics.median(t['output_sigma'] / t['source_sigma'] for t in arms[arm]['flat_trace'][8:])
                  for arm in ['old-auto', 'new-auto']]
        require(abs(ratios[1] - ratios[0]) < 0.03, name + ': coarse-grain amplitude changed')
    for name in ['detail_weak'] + (['woven_weak'] if 'woven_weak' in cases else []):
        arms = cases[name]['arms']
        require(arms['old-auto']['decoded_hashes']['grain-0.yuv'] ==
                arms['new-auto']['decoded_hashes']['grain-0.yuv'], name + ': weak-grain base changed')
        require(arms['new-auto']['bytes'] <= arms['old-auto']['bytes'] * 1.01,
                name + ': weak-grain size increased')
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    failures = check(json.loads(args.report.read_text()))
    print(json.dumps(dict(passed=not failures, failures=failures), indent=2))
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
