#!/usr/bin/env python3
"""Prepare an offline retention study and compare its measured operating points.

Neither subcommand runs encoders, probes, metrics or production services.
Planning uses retained source manifests. Comparison uses actual primary-video
bytes and matching metric definitions; it never treats equal QVBR as equal size.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def one_value(arguments, option):
    if arguments.count(option) != 1:
        raise ValueError('expected exactly one ' + option)
    index = arguments.index(option) + 1
    if index == len(arguments):
        raise ValueError('missing value for ' + option)
    return arguments[index]


def with_quality(arguments, qvbr, mode):
    result = list(arguments)
    one_value(result, '--qvbr')
    result[result.index('--qvbr') + 1] = str(qvbr)
    grain = one_value(result, '--av1-film-grain')
    index = result.index('--av1-film-grain')
    if mode == 'plain':
        del result[index:index + 2]
    else:
        grain = [part for part in grain.split(',')
                 if not part.startswith(('retain=', 'retain-max='))]
        grain += ['retain=auto', 'retain-max=0.1'] if mode == 'auto' else ['retain=0']
        result[index + 1] = ','.join(grain)
    return result


def prepare(manifest, output_root, offsets=(0, -1, -2)):
    output_root = Path(output_root)
    if not output_root.is_absolute():
        raise ValueError('output root must be absolute')
    if not offsets or len(set(offsets)) != len(offsets) or 0 not in offsets:
        raise ValueError('quality offsets must be unique and include the current setting')
    binaries = manifest['binaries']
    for key in ('production', 'qualified_auto'):
        if not Path(binaries[key]['path']).is_absolute() or not re.fullmatch('[0-9a-f]{64}', binaries[key]['sha256']):
            raise ValueError('pin absolute encoder path and SHA-256: ' + key)
    jobs, names, cases = [], set(), []
    for case in manifest['cases']:
        name = case['name']
        if not re.fullmatch('[a-z0-9_]+', name) or name in names:
            raise ValueError('case names must be unique simple identifiers')
        names.add(name)
        if not re.fullmatch('[0-9a-f]{64}', case['sha256']) or not Path(case['source']).is_absolute():
            raise ValueError('pin original source path and SHA-256')
        if case.get('source_kind') not in ('original', 'lossless_original_excerpt'):
            raise ValueError('original provenance is required; a library transcode is not a reference')
        if not isinstance(case['frames'], int) or isinstance(case['frames'], bool) or case['frames'] <= 0:
            raise ValueError('positive frame count required')
        prefix, arguments = case.get('prefix', []), case['arguments']
        if any(flag in prefix + arguments for flag in ('-i', '-o', '--frames', '--log-level')):
            raise ValueError('input, output, frame count and logging belong to the planner')
        qvbr = float(one_value(arguments, '--qvbr'))
        quality_points = [qvbr + offset for offset in offsets]
        if any(not math.isfinite(q) or q <= 0 or q > 63 for q in quality_points):
            raise ValueError('explicit QVBR must be in (0, 63]')
        reference_id = fingerprint({key: case.get(key) for key in
                                    ('sha256', 'frames', 'prefix', 'video_properties')})
        cases.append(dict(name=name, reference_id=reference_id, source=case['source'],
                          source_sha256=case['sha256'], identity=case['identity'],
                          source_kind=case['source_kind'], frames=case['frames'],
                          content_class=case['content_class'], role=case.get('role', 'benchmark'),
                          video_properties=case['video_properties'], anchor_qvbr=qvbr))
        for offset, quality in zip(offsets, quality_points):
            for mode in ('current_fgs', 'auto', 'plain'):
                binary_key = 'production' if mode == 'current_fgs' else 'qualified_auto'
                binary = binaries[binary_key]
                arm = f'{mode}_q{quality:g}'
                command = [binary['path'], *prefix, '-i', case['source'], '--frames', str(case['frames']),
                           *with_quality(arguments, quality, mode), '--log-level', 'debug',
                           '-o', str(output_root / name / arm / 'output.mkv')]
                jobs.append(dict(case=name, arm=arm, mode=mode, qvbr=quality,
                                 anchor=offset == 0, reference_id=reference_id,
                                 binary_sha256=binary['sha256'], command=command))
        # Separates the branch/binary change from the retention setting itself.
        binary = binaries['qualified_auto']
        jobs.append(dict(case=name, arm='candidate_fixed_control', mode='candidate_fixed_control',
                         qvbr=qvbr, anchor=True, reference_id=reference_id,
                         binary_sha256=binary['sha256'], command=[binary['path'], *prefix,
                         '-i', case['source'], '--frames', str(case['frames']),
                         *with_quality(arguments, qvbr, 'current_fgs'), '--log-level', 'debug',
                         '-o', str(output_root / name / 'candidate_fixed_control' / 'output.mkv')]))
    if not cases:
        raise ValueError('no source cases')
    return dict(schema=1, status='prepared_not_executed', manifest_sha256=fingerprint(manifest),
                binaries=copy.deepcopy(binaries), cases=cases, jobs=jobs,
                limits=['No execution or production activation is performed by this planner.',
                        'Verify source/binary hashes, frame alignment and playback metadata before scoring.',
                        'Measure complete primary-video packet bytes; QVBR is not a size match.',
                        'Keep grain-on playback scores separate from grain-off diagnostic scores.',
                        'Record HDR display/transfer assumptions and metric model revisions.',
                        'Use quality checks and blinded playback review before ranking a mode.',
                        'Extend the measured quality range when no size match is available.'],
                deferred=['GPU execution and decode/quality sweeps after repair.',
                          'Bounded SVT reference settings must be calibrated at matching sizes.',
                          'Controlled timing repeats after the host workload permits them.'])


def compare(rows, size_tolerance=0.03):
    if not math.isfinite(size_tolerance) or not 0 <= size_tolerance <= 0.1:
        raise ValueError('size tolerance must be between 0 and 0.1')
    identities = set()
    for row in rows:
        identity = (row['case'], row['arm'])
        if identity in identities:
            raise ValueError('duplicate operating point')
        identities.add(identity)
        if not isinstance(row['video_bytes'], int) or isinstance(row['video_bytes'], bool) or row['video_bytes'] <= 0:
            raise ValueError('positive complete video packet bytes required')
        if not re.fullmatch('[0-9a-f]{64}', row['reference_id']):
            raise ValueError('reference identity is required')
        if not isinstance(row.get('quality_checks_passed'), bool):
            raise ValueError('explicit quality-check status required')
        for metric in row.get('metrics', {}).values():
            if not metric.get('definition') or not math.isfinite(metric['value']):
                raise ValueError('finite metric and pinned definition required')
    comparisons = []
    for auto in (row for row in rows if row['mode'] == 'auto' and row.get('anchor')):
        for mode in ('current_fgs', 'plain', 'svt'):
            candidates = [row for row in rows if row['case'] == auto['case'] and row['mode'] == mode
                          and row['reference_id'] == auto['reference_id'] and row['quality_checks_passed']]
            result = dict(case=auto['case'], auto_arm=auto['arm'], comparison_mode=mode,
                          target_video_bytes=auto['video_bytes'], status='missing_valid_comparison',
                          visible_quality_gain='not_established_by_numeric_scores')
            if not auto['quality_checks_passed']:
                result['status'] = 'auto_failed_quality_checks'
            elif candidates:
                candidate = min(candidates, key=lambda row: abs(row['video_bytes'] / auto['video_bytes'] - 1))
                gap = candidate['video_bytes'] / auto['video_bytes'] - 1
                result.update(comparison_arm=candidate['arm'], measured_size_gap_percent=100 * gap,
                              status='matched' if abs(gap) <= size_tolerance + 1e-12 else 'needs_more_size_points')
                deltas, incompatible = {}, []
                for name in sorted(set(auto.get('metrics', {})) | set(candidate.get('metrics', {}))):
                    a, b = auto.get('metrics', {}).get(name), candidate.get('metrics', {}).get(name)
                    if a and b and a['definition'] == b['definition']:
                        deltas[name] = a['value'] - b['value']
                    else:
                        incompatible.append(name)
                if result['status'] == 'matched':
                    result.update(auto_minus_comparison_metrics=deltas,
                                  missing_or_incompatible_metrics=incompatible)
            comparisons.append(result)
    return dict(schema=1, comparison_type='measured_size', size_tolerance=size_tolerance,
                comparisons=comparisons, production_policy_changed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='operation', required=True)
    plan = commands.add_parser('prepare')
    plan.add_argument('--manifest', type=Path, required=True)
    plan.add_argument('--encode-output-root', type=Path, required=True)
    plan.add_argument('--output', type=Path, required=True)
    summarize = commands.add_parser('compare')
    summarize.add_argument('--results', type=Path, required=True)
    summarize.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.operation == 'prepare':
        result = prepare(json.loads(args.manifest.read_text()), args.encode_output_root)
    else:
        result = compare(json.loads(args.results.read_text())['rows'])
    with args.output.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')


if __name__ == '__main__':
    main()
