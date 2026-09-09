#!/usr/bin/env python3
"""Build a Tdarr video-payload budget from complete, validated paired trials.

No source download or encode is performed. The plugin verifies the exact source
and candidate again before a fresh encode. Container/audio bytes are excluded.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time

from production_compare import identity, sha
from trial_admission import byte_budget, probe_video_only, validated_pair


def build(config, output):
    candidate = config['expected_candidate_sha256']
    percent = config.get('maximum_extra_percent', '10')
    result = dict(schema='fgs_tdarr_budget_reference_v1', created_at=time.time(),
                  candidate_sha256=candidate, maximum_extra_percent=percent,
                  references=[], budget_scope='complete primary-video packet bytes')
    for item in config['cases']:
        report_path = Path(item['report'])
        before_report = identity(report_path)
        report = json.loads(report_path.read_text())
        case, baseline, _ = validated_pair(report, item['case'], candidate)
        encoded = report_path.parent / case['name'] / 'old-default-a' / 'output.mkv'
        before_video = identity(encoded)
        if encoded.stat().st_size != baseline['bytes'] or sha(encoded) != baseline['sha256']:
            raise ValueError('Measured baseline file changed')
        probe_video_only(encoded)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                '-show_packets', '-show_entries', 'packet=size', '-of', 'csv=p=0',
                                str(encoded)], capture_output=True, text=True, check=True, timeout=1800)
        if probe.stderr.strip():
            raise ValueError('Baseline packet probe reported errors: ' + probe.stderr[-2000:])
        sizes = []
        for line in probe.stdout.splitlines():
            if not line.strip():
                continue
            first = line.split(',')[0]
            if not first.isdigit() or int(first) <= 0:
                raise ValueError('Invalid baseline video packet size')
            sizes.append(int(first))
        if len(sizes) != case['frames']:
            raise ValueError('Baseline packet count does not match validated frames')
        total = sum(sizes)
        byte_budget(total, percent)
        command = baseline['command']
        if command.count('--qvbr') != 1:
            raise ValueError('The Tdarr trial reference requires a measured QVBR encode')
        result['references'].append(dict(
            case=case['name'], source_path=case['source'], source_sha256=case['sha256'],
            source_aliases=item.get('source_aliases', []),
            source_bytes=case['identity']['size'], frames=case['frames'],
            qvbr=float(command[command.index('--qvbr') + 1]), baseline_video_bytes=total,
            baseline_sha256=baseline['sha256'], baseline_binary_sha256=report['baseline_sha256'],
            comparison=str(report_path), comparison_sha256=sha(report_path)))
        if identity(report_path) != before_report or identity(encoded) != before_video:
            raise ValueError('Baseline evidence changed during reference creation')
    if not result['references']:
        raise ValueError('At least one measured source is required')
    paths = set()
    for row in result['references']:
        if not isinstance(row['source_aliases'], list):
            raise ValueError('Source aliases must be explicit absolute paths')
        for name in [row['source_path'], *row['source_aliases']]:
            if not isinstance(name, str) or not name.startswith('/'):
                raise ValueError('Source aliases must be explicit absolute paths')
            canonical = name.replace('/media/merged-storage/media/', '/media/', 1) if name.startswith('/media/merged-storage/media/') else name
            if canonical in paths:
                raise ValueError('Ambiguous measured source path or alias')
            paths.add(canonical)
    with output.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build(json.loads(args.config.read_text()), args.output)
    print(f"Wrote {len(result['references'])} complete measured references")
