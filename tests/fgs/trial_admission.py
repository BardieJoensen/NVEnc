#!/usr/bin/env python3
"""Publish a size-bounded, validated trial output into a separate staging folder.

Requires a complete production_compare report and a full baseline encode of the
same input. The default limit is 10% above that baseline's video-only file size.
An oversized candidate selects keep_source; it never substitutes the baseline,
raises the quantizer, disables a fidelity guard, or replaces a library file.
This is an additional trial gate, not a perceptual-quality certification.
"""
import argparse
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

from production_compare import identity, sha


def byte_budget(baseline_bytes, extra_percent='10'):
    if type(baseline_bytes) is not int or baseline_bytes <= 0:
        raise ValueError('A positive measured baseline size is required')
    try:
        extra = Decimal(str(extra_percent))
    except InvalidOperation as error:
        raise ValueError('Invalid extra-size percent') from error
    if not extra.is_finite() or not 0 <= extra <= 100:
        raise ValueError('Extra-size percent must be finite and in 0..100')
    return int(Decimal(baseline_bytes) * (100 + extra) / 100)


def validated_pair(report, case_name, expected_candidate_sha256):
    if report.get('complete') is not True or report.get('error'):
        raise ValueError('A complete successful trial is required')
    if (not re.fullmatch(r'[0-9a-f]{64}', expected_candidate_sha256)
            or report.get('candidate_sha256') != expected_candidate_sha256):
        raise ValueError('Candidate binary is not the expected build')
    cases = [c for c in report['manifest']['cases'] if c['name'] == case_name]
    if len(cases) != 1:
        raise ValueError('The case must occur exactly once')
    case = cases[0]
    pair = []
    for arm in ['old-default-a', 'new-auto-a']:
        rows = [r for r in report['runs'] if r['case'] == case_name and r['arm'] == arm]
        if len(rows) != 1:
            raise ValueError('Missing or ambiguous completed baseline/candidate')
        row = rows[0]
        scan = row.get('scan', {})
        if (row['frames'] != case['frames'] or case['frames'] <= 0
                or scan.get('complete') is not True or scan.get('errors') != 0
                or scan.get('packets') != case['frames']
                or scan.get('criterion') != 'synthesis_texture_v1'
                or scan.get('verdict') != 'stable'):
            raise ValueError('Incomplete frame or synthesis validation')
        for field in ['decoded_sha256', 'timeline_sha256']:
            values = row.get(field, {})
            if set(values) != {'0', '1'} or not all(
                    re.fullmatch(r'[0-9a-f]{64}', v) for v in values.values()):
                raise ValueError('Both full grain-on/off decodes are required')
        for key, value in case['video_properties'].items():
            if row.get('video', {}).get(key) != value:
                raise ValueError('Video properties changed')
        pair.append(row)
    if pair[0]['timeline_sha256'] != pair[1]['timeline_sha256']:
        raise ValueError('Baseline and candidate timestamps differ')
    return case, pair[0], pair[1]


def probe_video_only(path):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                            'stream=codec_type,codec_name', '-of', 'json', str(path)],
                           capture_output=True, text=True, check=True, timeout=120)
    streams = json.loads(probe.stdout).get('streams', [])
    # FFprobe can include side_data_list even with this restricted selection.
    # Dolby Vision metadata belongs to the video stream; it is not another track.
    if (len(streams) != 1 or streams[0].get('codec_name') != 'av1'
            or streams[0].get('codec_type') != 'video'):
        raise ValueError('A video-only AV1 baseline and candidate are required')


def admit(report_path, case_name, expected_candidate_sha256, output_dir, extra_percent='10'):
    report_path, output_dir = Path(report_path), Path(output_dir)
    report_identity = identity(report_path)
    report = json.loads(report_path.read_text())
    case, baseline, candidate = validated_pair(report, case_name, expected_candidate_sha256)
    # Directory components come from a local report, but must not escape it.
    if not re.fullmatch(r'[A-Za-z0-9_-]+', case_name):
        raise ValueError('Invalid case directory name')
    source = Path(case['source'])
    if identity(source) != case['identity'] or sha(source) != case['sha256']:
        raise ValueError('Trial source changed')
    paths = []
    before = {}
    for row in [baseline, candidate]:
        path = report_path.parent / case_name / row['arm'] / 'output.mkv'
        before[str(path)] = identity(path)
        if path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise ValueError('Completed encoded artifact changed')
        # Inspect the actual container: CLI spellings or inherited tracks
        # must not let copied audio conceal video growth.
        probe_video_only(path)
        paths.append(path)
    limit = byte_budget(baseline['bytes'], extra_percent)
    accepted = candidate['bytes'] <= limit
    decision = dict(schema='fgs_trial_admission_v1', created_at=time.time(),
        case=case_name, report=str(report_path.resolve()), report_sha256=sha(report_path),
        candidate_binary_sha256=expected_candidate_sha256,
        baseline_binary_sha256=report['baseline_sha256'],
        source=str(source), source_sha256=case['sha256'],
        baseline_bytes=baseline['bytes'], candidate_bytes=candidate['bytes'],
        maximum_candidate_bytes=limit, maximum_extra_percent=str(extra_percent),
        bytes_vs_baseline_percent=100 * (candidate['bytes'] / baseline['bytes'] - 1),
        decision='stage_candidate' if accepted else 'keep_source',
        reason='within_measured_budget' if accepted else 'candidate_exceeds_measured_budget',
        staged_output=None, library_replacement=False,
        budget_scope='complete video-only file; not a source-file or sampled-size estimate',
        validation_scope='complete synthesis/decode/timeline/declared-color checks; not a perceptual certification')
    output_dir.mkdir(parents=True, exist_ok=False)
    temporary = output_dir / 'candidate.partial'
    try:
        if accepted:
            # Separate copy: later changes to a retained experiment must not
            # mutate an admitted artifact through a hardlink or symlink.
            with paths[1].open('rb') as src, temporary.open('xb') as dst:
                shutil.copyfileobj(src, dst, 4 * 1024**2)
                dst.flush()
                os.fsync(dst.fileno())
            if temporary.stat().st_size > limit or sha(temporary) != candidate['sha256']:
                raise ValueError('Staged candidate changed or exceeded the budget')
        if (identity(source) != case['identity'] or identity(report_path) != report_identity
                or any(identity(p) != before[str(p)] for p in paths)):
            raise ValueError('Evidence changed during admission')
        if accepted:
            target = output_dir / 'candidate.mkv'
            temporary.chmod(0o444)
            temporary.rename(target)
            decision.update(staged_output=str(target.resolve()), staged_sha256=candidate['sha256'])
        with (output_dir / 'decision.json').open('x') as handle:
            json.dump(decision, handle, indent=2)
            handle.write('\n')
    except BaseException:
        temporary.unlink(missing_ok=True)
        (output_dir / 'candidate.mkv').unlink(missing_ok=True)
        raise
    return decision


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--expected-candidate-sha256', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--max-extra-percent', default='10')
    args = parser.parse_args()
    decision = admit(args.report, args.case, args.expected_candidate_sha256,
                     args.output_dir, args.max_extra_percent)
    print(json.dumps(decision, indent=2))
    # A keep decision is not a decoder error, but automated promotion must stop.
    return 0 if decision['decision'] == 'stage_candidate' else 3


if __name__ == '__main__':
    raise SystemExit(main())
