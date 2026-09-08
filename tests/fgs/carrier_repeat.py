#!/usr/bin/env python3
"""Repeat AV1 compression of one pinned raw base and grain table.

The FGS analyzer and denoiser do not run here. Pixel comparisons with grain
disabled can reproduce variability in the remaining pipeline, without
attributing it to a specific hardware, driver, or encoder component. Matching
repeats cannot establish universal determinism. This is an offline trial.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import time

import filmgrn
from production_compare import identity, run, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True,
                        help='Pins source/table hashes, frame count, binary and encode arguments')
    parser.add_argument('--scanner', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=4)
    args = parser.parse_args()
    if not 2 <= args.repeats <= 8:
        parser.error('Use 2..8 repeats')
    manifest = json.loads(args.manifest.read_text())
    source, table, binary = [Path(manifest[key]) for key in ['source', 'table', 'binary']]
    identities = {str(path): identity(path) for path in [source, table, binary]}
    for key, path in [('source', source), ('table', table), ('binary', binary)]:
        if sha(path) != manifest[key + '_sha256']:
            raise ValueError('Changed pinned ' + key)
    with source.open('rb') as handle:
        if not handle.readline().startswith(b'YUV4MPEG2 '):
            raise ValueError('A raw Y4M base is required')
    if not any(entry['apply_grain'] for entry in filmgrn.load(table)):
        raise ValueError('The table must contain active synthesis')
    if any(flag in manifest['arguments'] for flag in
           ['-i', '-o', '--av1-film-grain', '--film-grain-table', '--film-grain-table-out']):
        raise ValueError('Manifest must leave source, output and grain routing to the harness')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = dict(complete=False, started_at=time.time(), manifest=manifest,
                  manifest_sha256=sha(args.manifest), harness_sha256=sha(__file__),
                  scanner_sha256=sha(args.scanner), runs=[], comparisons=[])

    def save():
        temporary = args.output_dir / 'report.tmp'
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(args.output_dir / 'report.json')

    save()
    try:
        # Finish the timed encodes before CPU decoding begins.
        for repeat in range(args.repeats):
            if shutil.disk_usage(args.output_dir).free < 30 * 1024**3:
                raise RuntimeError('Less than 30 GiB scratch space remains')
            directory = args.output_dir / f'run-{repeat + 1}'
            directory.mkdir()
            output = directory / 'output.mkv'
            command = [str(binary), '-i', str(source), *manifest['arguments'],
                       '--film-grain-table', str(table), '-o', str(output)]
            seconds = run(command, directory / 'encode.log', 1200)
            completion = re.search(r'encoded (\d+) frames,',
                                   (directory / 'encode.log').read_text(errors='replace'))
            if not completion or int(completion[1]) != manifest['frames']:
                raise RuntimeError('Unexpected encoder frame count')
            report['runs'].append(dict(name=directory.name, command=command, seconds=seconds,
                bytes=output.stat().st_size, sha256=sha(output), frames=int(completion[1])))
            save()
            print(directory.name, 'encoded', round(seconds, 2), 'seconds', flush=True)
        decoded = {}
        for row in report['runs']:
            directory = args.output_dir / row['name']
            output = directory / 'output.mkv'
            run([str(args.scanner), str(output)], directory / 'scan.json', 1200)
            scan = json.loads((directory / 'scan.json').read_text())
            if not (scan.get('complete') and scan.get('verdict') == 'stable'
                    and scan.get('criterion') == 'synthesis_texture_v1'
                    and scan.get('packets') == manifest['frames'] and scan.get('errors') == 0):
                raise RuntimeError('Synthesis scan failed')
            row['scan'] = scan
            row['decoded_sha256'], row['timeline_sha256'] = {}, {}
            decoded[row['name']] = {}
            for grain in [0, 1]:
                md5 = directory / f'grain-{grain}.framemd5'
                run(['ffmpeg', '-v', 'error', '-xerror', '-nostdin', '-c:v', 'libdav1d',
                     '-threads', '2', '-filmgrain', str(grain), '-i', str(output),
                     '-map', '0:v:0', '-an', '-sn', '-pix_fmt', 'yuv420p10le',
                     '-fps_mode', 'passthrough', '-f', 'framemd5', str(md5)],
                    directory / f'decode-{grain}.log', 1200)
                lines = [line for line in md5.read_text().splitlines()
                         if line and not line.startswith('#')]
                if len(lines) != manifest['frames']:
                    raise RuntimeError('Unexpected decoded frame count')
                pixels = [line.rsplit(',', 1)[1].strip() for line in lines]
                timeline = [','.join(line.split(',')[:4]) for line in lines]
                decoded[row['name']][str(grain)] = pixels
                row['decoded_sha256'][str(grain)] = hashlib.sha256('\n'.join(pixels).encode()).hexdigest()
                row['timeline_sha256'][str(grain)] = hashlib.sha256('\n'.join(timeline).encode()).hexdigest()
            row['grain_on_off_differ'] = row['decoded_sha256']['0'] != row['decoded_sha256']['1']
            if not row['grain_on_off_differ']:
                raise RuntimeError('The active table did not affect decoded pixels')
            save()
        first = report['runs'][0]
        for row in report['runs'][1:]:
            if row['timeline_sha256'] != first['timeline_sha256']:
                raise RuntimeError('Repeat timestamp sequence changed')
            differences = {str(grain): [i for i, (a, b) in enumerate(zip(
                decoded[first['name']][str(grain)], decoded[row['name']][str(grain)])) if a != b]
                for grain in [0, 1]}
            report['comparisons'].append(dict(reference=first['name'], repeat=row['name'],
                different_frames=differences, base_pixels_identical=not differences['0'],
                rendered_pixels_identical=not differences['1']))
        for path, before in identities.items():
            if identity(path) != before:
                raise RuntimeError('Pinned input changed during the test: ' + path)
        report.update(complete=True, finished_at=time.time())
    except Exception as error:
        report.update(error=str(error), failed_at=time.time())
        raise
    finally:
        save()
    print(json.dumps(report['comparisons']), flush=True)


if __name__ == '__main__':
    main()
