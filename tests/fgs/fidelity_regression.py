#!/usr/bin/env python3
"""Check decoded, fixture-specific regressions in a fidelity_compare report.

These limits cover the deterministic 48-frame sources, not arbitrary footage.
The rejected first prototype must fail the weak-grain and transition checks.
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
    expected = ['detail_fine', 'detail_coarse', 'detail_weak', 'changing_strength', 'strength_steps']
    if not all(name in cases for name in expected):
        return failures + ['missing required fixtures']
    for name in expected:
        require(cases[name].get('complete') and cases[name]['source']['frames'] == 48,
                name + ': requires the complete 48-frame fixture')
    for name in ['detail_fine', 'detail_coarse']:
        case = cases[name]
        baseline = case['arms']['old-auto']
        candidate = case['arms'].get(case.get('no_larger_arm'))
        require(candidate is not None, name + ': no candidate fits baseline size')
        if candidate:
            require(candidate['bytes'] <= baseline['bytes'], name + ': size increased')
            require(candidate['separation']['detail_transfer_gain'] >=
                    baseline['separation']['detail_transfer_gain'] + 0.06,
                    name + ': lost matched-size detail gain')
    weak = cases['detail_weak']['arms']
    require(weak['old-auto']['decoded_hashes']['grain-0.yuv'] ==
            weak['new-auto']['decoded_hashes']['grain-0.yuv'],
            'weak grain: decoded base changed')
    # Correcting strength-knot positions intentionally changes synthesized
    # samples. Preserve the base exactly and bound amplitude change instead.
    require(all(abs(new['output_sigma'] - old['output_sigma']) < 0.01 * old['source_sigma']
                for old, new in zip(weak['old-auto']['flat_trace'], weak['new-auto']['flat_trace'])),
            'weak grain: unnecessary synthesized-amplitude change')
    require(weak['new-auto']['bytes'] <= weak['old-auto']['bytes'] * 1.01,
            'weak grain: unnecessary size increase')

    changing = cases['changing_strength']['arms']['new-auto']
    # Logs identify whether fallback occurs once or repeatedly. Rendered grain
    # confirms that its amplitude does not sag between fallback frames.
    frames = changing.get('source_fallback_frames')
    if frames is None:
        frames = [f['frame'] for f in changing['model_frames'] if f.get('source_fallback')]
    require(bool(frames) and frames[0] == 24 and frames[-1] < 40 and
            frames == list(range(frames[0], frames[-1] + 1)),
            'strength transition: fallback must be contiguous and recover')
    ratios = [r['output_sigma'] / r['source_sigma'] for r in changing['flat_trace'][24:]]
    require(len(ratios) == 24 and min(ratios) > 0.85 and max(ratios) < 1.10,
            'strength transition: decoded grain amplitude dropped or overshot')

    steps = cases['strength_steps']['arms']
    require(steps['new-auto']['source_fallbacks'] == 48,
            'unrepresentable strength steps: source not consistently retained')
    errors = {name: statistics.median(abs(r['output_sigma'] / r['source_sigma'] - 1)
                                    for r in steps[name]['flat_trace'])
              for name in ['old-auto', 'new-auto']}
    require(errors['new-auto'] < errors['old-auto'] / 2,
            'unrepresentable strength steps: rendered amplitude did not improve')
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    failures = check(json.loads(args.report.read_text()))
    print(json.dumps(dict(passed=not failures, failures=failures), indent=2))
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
