#!/usr/bin/env python3
"""Offline, full decoded-frame HDR metadata traces and comparisons.

Compare parsed Dolby Vision/HDR10+ fields, HDR10 static metadata and timestamps
on every displayed frame. HEVC-only raw RPU side data is not comparable with
AV1's parsed T.35 metadata. MDCV values are normalized to AV1's specified
0.16/18.14/24.8 fixed-point representations, not compared as rational strings.
This adds no work to normal Tdarr validation.
"""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
from itertools import zip_longest
import json
from pathlib import Path
import subprocess
import threading
import time
import xml.etree.ElementTree as ET

from production_compare import identity, sha

TYPES = {'Mastering display metadata', 'Content light level metadata',
         'Dolby Vision Metadata', 'HDR Dynamic Metadata SMPTE2094-40 (HDR10+)'}


def canonical(element, mastering=False):
    attrs = dict(element.attrib)
    if mastering and element.tag == 'side_datum' and attrs.get('key') != 'side_data_type':
        key = attrs['key']
        if key in {'red_x', 'red_y', 'green_x', 'green_y', 'blue_x', 'blue_y',
                   'white_point_x', 'white_point_y', 'min_luminance', 'max_luminance'}:
            denominator = 16384 if key == 'min_luminance' else 256 if key == 'max_luminance' else 65536
            value = Fraction(attrs['value']) * denominator
            if value < 0:
                raise ValueError('Negative mastering display metadata')
            attrs['value'] = str(int(value + Fraction(1, 2)))
    return [element.tag, sorted(attrs.items()), [canonical(c, mastering) for c in element]]


def metadata_row(frame, index):
    metadata = {}
    for side in frame.findall('./side_data_list/side_data'):
        kind = side.attrib['type']
        if kind not in TYPES:
            continue
        if kind in metadata:
            raise ValueError('Duplicate HDR side data on one frame')
        value = canonical(side, kind == 'Mastering display metadata')
        metadata[kind] = hashlib.sha256(json.dumps(value, separators=(',', ':')).encode()).hexdigest()
    return dict(frame=index, pts=frame.attrib.get('pts_time'), metadata=metadata)


def record(source, directory, expected_frames, expected_sha256, timeout=18000, threads=2):
    source, directory = Path(source), Path(directory)
    before = identity(source)
    if sha(source) != expected_sha256:
        raise ValueError('Source SHA-256 changed')
    if expected_frames <= 0 or not 1 <= threads <= 8 or timeout <= 0:
        raise ValueError('Invalid frame count, thread count or timeout')
    directory.mkdir(parents=True, exist_ok=False)
    report = dict(complete=False, source=str(source), source_sha256=expected_sha256,
                  source_identity=before, expected_frames=expected_frames,
                  harness_sha256=sha(__file__), started_at=time.time())
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                            '-show_streams', '-of', 'json', str(source)],
                           capture_output=True, text=True, check=True, timeout=120)
    report['stream'] = json.loads(probe.stdout)['streams'][0]
    command = ['ffprobe', '-v', 'error', '-threads', str(threads), '-err_detect', 'explode',
               '-select_streams', 'v:0', '-show_frames', '-show_entries',
               'frame=pts_time,side_data_list', '-of', 'xml', str(source)]
    report['command'] = command
    count = 0
    counts = Counter()
    previous_pts = None
    try:
        with (directory / 'decode.log').open('wb') as log, (directory / 'frames.jsonl').open('x') as trace:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=log)
            timer = threading.Timer(timeout, process.kill)
            timer.start()
            try:
                for event, node in ET.iterparse(process.stdout, events=['end']):
                    if node.tag != 'frame':
                        continue
                    row = metadata_row(node, count)
                    if row['pts'] is None:
                        raise ValueError('A decoded frame has no timestamp')
                    pts = Fraction(row['pts'])
                    if previous_pts is not None and pts <= previous_pts:
                        raise ValueError('Non-increasing displayed frame timestamps')
                    previous_pts = pts
                    counts.update(row['metadata'].keys())
                    trace.write(json.dumps(row, separators=(',', ':')) + '\n')
                    count += 1
                    node.clear()
                if process.wait() != 0:
                    raise RuntimeError('Metadata decoding failed or timed out')
            finally:
                timer.cancel()
                if process.poll() is None:
                    process.kill()
                process.wait()
                process.stdout.close()
        if (directory / 'decode.log').stat().st_size:
            raise RuntimeError('Decoder reported an error; inspect decode.log')
        if count != expected_frames or not counts:
            raise ValueError('Unexpected decoded frame count or no HDR metadata')
        if identity(source) != before:
            raise ValueError('Source changed during metadata decoding')
        report.update(complete=True, frames=count, metadata_frame_counts=dict(counts),
                      trace_sha256=sha(directory / 'frames.jsonl'), finished_at=time.time())
    except BaseException as error:
        report.update(error=str(error), frames=count, failed_at=time.time())
        raise
    finally:
        (directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def compare_rows(reference, candidate):
    failures = []
    count = 0
    for a, b in zip_longest(reference, candidate):
        if a is None or b is None:
            raise ValueError('Metadata trace lengths differ')
        if a['frame'] != count or b['frame'] != count:
            raise ValueError('Missing or reordered trace frames')
        differences = []
        if a['pts'] != b['pts']:
            differences.append('timestamp')
        for kind in sorted(set(a['metadata']) | set(b['metadata'])):
            if a['metadata'].get(kind) != b['metadata'].get(kind):
                differences.append(kind)
        if differences:
            failures.append(dict(frame=count, differences=differences))
        count += 1
    if count == 0:
        raise ValueError('Empty metadata traces')
    return dict(passed=not failures, frames=count, different_frames=len(failures),
                first_differences=failures[:30])


def compare(reference, candidate):
    paths = [Path(reference), Path(candidate)]
    reports = []
    for path in paths:
        report = json.loads((path / 'report.json').read_text())
        if report.get('complete') is not True or report.get('trace_sha256') != sha(path / 'frames.jsonl'):
            raise ValueError('Incomplete or changed metadata trace')
        reports.append(report)
    stream_failures = compare_streams(reports[0]['stream'], reports[1]['stream'])
    with (paths[0] / 'frames.jsonl').open() as a, (paths[1] / 'frames.jsonl').open() as b:
        result = compare_rows(map(json.loads, a), map(json.loads, b))
    if any(result['frames'] != r['frames'] for r in reports):
        raise ValueError('Trace/report frame counts differ')
    result['traces'] = [str(p.resolve()) for p in paths]
    result['source_sha256'] = [r['source_sha256'] for r in reports]
    result['stream_failures'] = stream_failures
    result['passed'] = result['passed'] and not stream_failures
    return result


def compare_streams(reference, candidate):
    failures = []
    for key in ['width', 'height', 'pix_fmt', 'color_range', 'color_space',
                'color_transfer', 'color_primaries', 'sample_aspect_ratio']:
        if reference.get(key) != candidate.get(key):
            failures.append(key)
    def dovi(stream):
        return next((v for v in stream.get('side_data_list', [])
                     if v.get('side_data_type') == 'DOVI configuration record'), None)
    a, b = dovi(reference), dovi(candidate)
    if bool(a) != bool(b):
        failures.append('Dolby Vision configuration presence')
    elif a:
        expected_profile = a['dv_profile']
        if candidate.get('codec_name') == 'av1' and reference.get('codec_name') == 'hevc':
            if expected_profile != 8 or a.get('el_present_flag') != 0:
                failures.append('Unverified Dolby Vision source-profile conversion')
            expected_profile = 10
        if b['dv_profile'] != expected_profile:
            failures.append('Dolby Vision output profile')
        for key in ['rpu_present_flag', 'el_present_flag', 'bl_present_flag',
                    'dv_bl_signal_compatibility_id']:
            if a.get(key) != b.get(key):
                failures.append('Dolby Vision ' + key)
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    rec = sub.add_parser('record')
    rec.add_argument('--source', type=Path, required=True)
    rec.add_argument('--expected-sha256', required=True)
    rec.add_argument('--frames', type=int, required=True)
    rec.add_argument('--output-dir', type=Path, required=True)
    rec.add_argument('--threads', type=int, default=2)
    cmp = sub.add_parser('compare')
    cmp.add_argument('--reference', type=Path, required=True)
    cmp.add_argument('--candidate', type=Path, required=True)
    args = parser.parse_args()
    result = (record(args.source, args.output_dir, args.frames, args.expected_sha256, threads=args.threads)
              if args.mode == 'record' else compare(args.reference, args.candidate))
    print(json.dumps(result, indent=2))
    return 0 if result.get('passed', result.get('complete')) else 2


if __name__ == '__main__':
    raise SystemExit(main())
