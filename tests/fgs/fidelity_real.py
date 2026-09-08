#!/usr/bin/env python3
"""Offline fidelity pilot on pinned private clips, including an ABBA timing run.

No library files are replaced. Short-clip sizes are diagnostic, not estimates
for a whole film. Timing on a shared GPU includes other workloads.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

import numpy as np

import fixtures
import periodic_regression


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def run(argv, log):
    started = time.monotonic()
    with log.open('w') as handle:
        subprocess.run(argv, stdout=handle, stderr=subprocess.STDOUT, check=True, timeout=1800)
    return time.monotonic() - started


def probe(path):
    fields = 'width,height,pix_fmt,color_range,color_space,color_transfer,color_primaries,r_frame_rate,nb_read_packets'
    result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_packets',
                             '-show_entries', 'stream=' + fields, '-of', 'json', str(path)],
                            capture_output=True, text=True, check=True, timeout=300)
    return json.loads(result.stdout)['streams'][0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--scanner', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=fixtures.DEFAULT_ROOT)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(fixtures.MANIFEST.read_text())
    names = ['taxi_clip', 'silo_clip', 'alien_clip', 'gentlemen_clip']
    pinned = fixtures.verify(args.root, manifest, names)
    source_probes = {name: probe(pinned[name]['path']) for name in names}
    report = dict(complete=False, started_at=time.time(), fixtures=pinned, runs=[],
                  baseline_sha256=sha(args.baseline), candidate_sha256=sha(args.candidate),
                  scanner_sha256=sha(args.scanner), harness_sha256=sha(__file__), source_probes=source_probes)

    def save():
        tmp = args.output_dir / 'report.tmp'
        tmp.write_text(json.dumps(report, indent=2) + '\n')
        os.replace(tmp, args.output_dir / 'report.json')

    save()
    # Run the longer timing sample first, in ABBA order. No decoding/scanning
    # from this experiment runs concurrently with these four encodes.
    schedule = [('gentlemen_clip', arm, auto) for arm, auto in
                [('old-auto-a', True), ('new-auto-a', True), ('new-auto-b', True), ('old-auto-b', True)]]
    for name in names[:-1]:
        schedule += [(name, arm, auto) for arm, auto in
                     [('old-default', False), ('new-default', False), ('old-auto', True), ('new-auto', True)]]
    for name, arm, auto in schedule:
        directory = args.output_dir / name / arm
        directory.mkdir(parents=True)
        output = directory / 'output.mkv'
        binary = args.baseline if arm.startswith('old-') else args.candidate
        opts = 'denoise=auto,chroma=auto,denoiser=bilateral' + (',retain=auto' if auto else '')
        argv = [str(binary), '--avsw', '-i', pinned[name]['path'], '--codec', 'av1',
                '--output-depth', '10', '--qvbr', '30', '--max-bitrate', '50000',
                '--preset', 'quality', '--tune', 'hq', '--lookahead', '32',
                '--lookahead-level', '3', '--aq', '--aq-temporal', '--av1-film-grain', opts,
                '--log-level', 'debug', '-o', str(output)]
        elapsed = run(argv, directory / 'encode.log')
        log = (directory / 'encode.log').read_text()
        finish = re.search(r'encoded (\d+) frames, ([\d.]+) fps', log)
        if not finish:
            raise RuntimeError('Missing completed encode: ' + str(directory))
        # These pinned FFV1 inputs contain one complete frame per packet.
        if int(finish[1]) != int(source_probes[name]['nb_read_packets']):
            raise RuntimeError('Source/output frame count changed: ' + str(directory))
        row = dict(clip=name, arm=arm, command=argv, seconds=elapsed,
                   frames=int(finish[1]), fps=float(finish[2]), bytes=output.stat().st_size,
                   sha256=sha(output), fallback_frames=[int(v) for v in re.findall(
                       r'fgs-model frame=(\d+)[^\n]*sourceFallback=1', log)])
        report['runs'].append(row)
        save()
        print(json.dumps({k:v for k,v in row.items() if k not in ['command','fallback_frames']}), flush=True)

    for row in report['runs']:
        directory = args.output_dir / row['clip'] / row['arm']
        output = directory / 'output.mkv'
        row['probe'] = probe(output)
        for key in ['width', 'height', 'color_range', 'color_space', 'color_transfer', 'color_primaries', 'r_frame_rate']:
            expected = source_probes[row['clip']].get(key)
            if expected is not None and expected != row['probe'].get(key):
                raise RuntimeError('Source property changed: ' + key + ' in ' + str(output))
        run([str(args.scanner), str(output)], directory / 'scan.json')
        scan = json.loads((directory / 'scan.json').read_text())
        if not scan.get('complete') or scan.get('verdict') != 'stable' or scan.get('packets') != row['frames']:
            raise RuntimeError('Incomplete or unsafe grain scan: ' + str(output))
        row['scan'] = scan
        # Hash decoded planes in both playback modes; this also rejects a
        # decoder error or missing frames, and checks the unchanged default.
        row['decoded_sha256'] = {}
        for grain in [0, 1]:
            md5 = directory / f'grain-{grain}.framemd5'
            run(['ffmpeg', '-v', 'error', '-xerror', '-nostdin', '-c:v', 'libdav1d',
                 '-threads', '2', '-filmgrain', str(grain), '-i', str(output),
                 '-map', '0:v:0', '-an', '-sn', '-pix_fmt', 'yuv420p10le',
                 '-fps_mode', 'passthrough', '-f', 'framemd5', str(md5)], directory / f'decode-{grain}.log')
            lines = [line for line in md5.read_text().splitlines() if not line.startswith('#')]
            if len(lines) != row['frames']:
                raise RuntimeError('Incomplete decoded sequence: ' + str(output))
            row['decoded_sha256'][str(grain)] = hashlib.sha256('\n'.join(lines).encode()).hexdigest()
        if row['clip'] == 'gentlemen_clip':
            row['jacket_samples'] = []
            for seconds in [24, 66, 84.5]:
                source = periodic_regression.frame(Path(pinned[row['clip']]['path']), seconds)
                on = periodic_regression.frame(output, seconds, 1)
                off = periodic_regression.frame(output, seconds, 0)
                sample = dict(seconds=seconds, planes={})
                for plane in source:
                    identical = bool(np.array_equal(on[plane], off[plane]))
                    mae = float(np.abs(on[plane].astype(float) - source[plane]).mean())
                    if (seconds in [66, 84.5] and not identical) or mae > 8.0:
                        raise RuntimeError('Jacket source-preservation regression: ' + str(output))
                    sample['planes'][plane] = dict(grain_on_off_identical=identical, mae_10bit=mae)
                sample['concentration'] = periodic_regression.grain_concentration(on['luma'], off['luma'])
                if sample['concentration'] > 0.08:
                    raise RuntimeError('Decoded periodic grain: ' + str(output))
                row['jacket_samples'].append(sample)
        save()

    for name in names[:-1]:
        defaults = [r for r in report['runs'] if r['clip'] == name and r['arm'].endswith('default')]
        if defaults[0]['decoded_sha256'] != defaults[1]['decoded_sha256']:
            raise RuntimeError('Default decoded output changed: ' + name)
    if fixtures.verify(args.root, manifest, names) != pinned:
        raise RuntimeError('Input fixtures changed')
    report.update(complete=True, finished_at=time.time(), default_pixels_unchanged=True)
    save()
    print('COMPLETE', flush=True)


if __name__ == '__main__':
    main()
