#!/usr/bin/env python3
"""Measure optional auto-retention costs against pinned production-default evidence.

Known clean pictures separate real detail from retained noise. Reuses previous
hashed baselines, and reports both fixed-QP and bounded-size comparisons. This
is an offline experiment and does not enforce production file-size policy.
"""
import argparse
import json
from pathlib import Path
import statistics
import subprocess
import time

import fidelity_compare as fc


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--scanner', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--cases', help='Comma-separated subset; default all reference cases')
    p.add_argument('--limits', default='0.5,0.1,0')
    p.add_argument('--match-limit', type=float, default=0.1)
    args = p.parse_args()
    prior = json.loads((args.reference / 'report.json').read_text())
    if not prior.get('complete'):
        raise RuntimeError('Incomplete reference')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = dict(complete=False, reference_sha256=fc.sha(args.reference / 'report.json'),
                  candidate_sha256=fc.sha(args.candidate), scanner_sha256=fc.sha(args.scanner),
                  harness_sha256=fc.sha(__file__), started_at=time.time(), cases=[])

    def save():
        temp = args.output_dir / 'report.tmp'
        temp.write_text(json.dumps(report, indent=2) + '\n')
        temp.replace(args.output_dir / 'report.json')

    save()
    try:
        selected = args.cases.split(',') if args.cases else [c['name'] for c in prior['cases']]
        for old in prior['cases']:
            if old['name'] not in selected:
                continue
            source = args.reference / old['name']
            for name, digest in old['source']['hashes'].items():
                if fc.sha(source / name) != digest:
                    raise RuntimeError('Changed source: ' + str(source / name))
            baseline = old['arms']['old-default']
            previous = old['arms']['new-auto']
            # Pin the retained measured artifact, not just a copied row.
            for row in [baseline, previous]:
                encoded = Path(row['command'][row['command'].index('-o') + 1])
                if fc.sha(encoded) != row['file_sha256']:
                    raise RuntimeError('Changed baseline artifact: ' + str(encoded))
            case = dict(name=old['name'], source=old['source'], baseline=baseline,
                        previous_auto=previous, arms={}, complete=False)
            report['cases'].append(case)
            root = args.output_dir / old['name']; root.mkdir()

            def encode(limit, qp, measure):
                key = f'max-{limit:g}-qp{qp}'
                if key in case['arms']:
                    return key, case['arms'][key]
                directory = root / key
                row = fc.encode(args.candidate, directory, source/'source.y4m',
                                old['spec'], qp, True, old['source']['frames'], limit)
                scan = subprocess.run([str(args.scanner), str(directory/'output.mkv')],
                                      capture_output=True, text=True, check=True, timeout=120)
                row['scan'] = json.loads(scan.stdout)
                s = row['scan']
                if not (s.get('complete') and s.get('verdict') == 'stable'
                        and s.get('criterion') == 'synthesis_texture_v1'
                        and s.get('packets') == old['source']['frames']):
                    raise RuntimeError('Unsafe or incomplete synthesis: ' + key)
                row['retain_max'] = limit
                row['bytes_vs_production_percent'] = 100 * (row['bytes'] / baseline['bytes'] - 1)
                if measure:
                    row.update(fc.measure(directory, source, old['source']))
                    row['median_grain_ratio'] = statistics.median(
                        t['output_sigma']/t['source_sigma'] for t in row['flat_trace'][8:])
                case['arms'][key] = row
                save()
                return key, row

            for limit in map(float, args.limits.split(',')):
                key, row = encode(limit, 20, True)
                print(old['name'],key,'size%',round(row['bytes_vs_production_percent'],2),
                      'fallback',row['source_fallbacks'],'fresh',len(row['fresh_model_frames']),flush=True)
            for qp in range(20, 33):
                key, row = encode(args.match_limit, qp, False)
                if row['bytes'] <= baseline['bytes']:
                    if 'separation' not in row:
                        row.update(fc.measure(root/key, source, old['source']))
                    case['within_production_size'] = key
                    break
            case['complete'] = True
            save()
        if len(report['cases']) != len(selected):
            raise RuntimeError('Unknown or duplicate selected case')
        report.update(complete=True, finished_at=time.time())
    except Exception as error:
        report.update(error=str(error), failed_at=time.time())
        save()
        raise
    save()
    print('COMPLETE', flush=True)


if __name__ == '__main__':
    main()
