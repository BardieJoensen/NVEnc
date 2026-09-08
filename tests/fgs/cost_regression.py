#!/usr/bin/env python3
"""Accept the bounded cost experiment using decoded evidence, not size alone."""
import json
from pathlib import Path
import sys


def check(report):
    errors = []
    def require(ok, message):
        if not ok:
            errors.append(message)
    require(report.get('complete'), 'incomplete cost experiment')
    require(len(report.get('cases', [])) == 16, 'requires all 16 controlled cases')
    for case in report.get('cases', []):
        name = case['name']
        require(case.get('complete'), name + ': incomplete')
        new = case['arms']['max-0.5-qp20']
        old = case['previous_auto']
        if name != 'changing_strength':
            require(new['decoded_hashes'] == old['decoded_hashes'], name + ': unrelated default-auto pixels changed')
        else:
            ratios = [t['output_sigma']/t['source_sigma'] for t in new['flat_trace'][24:]]
            require(len(ratios) == 24 and min(ratios) > 0.85 and max(ratios) < 1.10,
                    'current-frame retry lost grain amplitude or overshot')
            require(new['bytes'] < old['bytes'] * 0.65,
                    'current-frame retry did not materially reduce transition cost')
        for key, row in case['arms'].items():
            require(all(m.get('retain', 0) <= row['retain_max'] + 1e-6 for m in row['model_frames']),
                    name + '/' + key + ': residual blend exceeds requested ceiling')
        if name == 'strength_steps':
            for key in ['max-0.5-qp20', 'max-0.1-qp20', 'max-0-qp20']:
                require(case['arms'][key]['decoded_hashes'] == old['decoded_hashes'],
                        'unrepresentable strength steps lost source-preserving fallback')
        key = case.get('within_production_size')
        if key:
            require(case['arms'][key]['bytes'] <= case['baseline']['bytes'],
                    name + ': claimed production size bound is false')
    return errors


if __name__ == '__main__':
    failures = check(json.loads(Path(sys.argv[1]).read_text()))
    print(json.dumps(dict(passed=not failures, failures=failures), indent=2))
    raise SystemExit(bool(failures))
