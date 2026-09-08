#!/usr/bin/env python3
"""Offline comparison using explicit production arguments and retained sources.

The manifest pins source identities and supplies the actual flow arguments.
Only the film-grain retention option changes between arms. Encodes and their
validation run sequentially; outputs never enter a library replacement flow.
File-size ratios are measured against current default retention, not old auto.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def identity(path):
    st = Path(path).stat()
    return dict(size=st.st_size, mtime_ns=st.st_mtime_ns, inode=st.st_ino, device=st.st_dev)


def run(argv, log, timeout):
    start = time.monotonic()
    with log.open('w') as handle:
        subprocess.run(argv, stdout=handle, stderr=subprocess.STDOUT, check=True, timeout=timeout)
    return time.monotonic() - start


def grain_arguments(arguments, auto):
    args = list(arguments)
    if args.count('--av1-film-grain') != 1:
        raise ValueError('Exactly one film-grain argument is required')
    i = args.index('--av1-film-grain') + 1
    options = [x for x in args[i].split(',') if not x.startswith('retain=')]
    if auto:
        options.append('retain=auto')
    args[i] = ','.join(options)
    return args


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--scanner', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--timeout', type=int, default=14400)
    args = p.parse_args()
    manifest = json.loads(args.manifest.read_text())
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = dict(complete=False, started_at=time.time(), manifest=manifest,
                  manifest_sha256=sha(args.manifest), harness_sha256=sha(__file__),
                  baseline_sha256=sha(args.baseline), candidate_sha256=sha(args.candidate),
                  scanner_sha256=sha(args.scanner), runs=[], comparisons=[])

    def save():
        temp = args.output_dir / 'report.tmp'
        temp.write_text(json.dumps(report, indent=2) + '\n')
        os.replace(temp, args.output_dir / 'report.json')

    save()
    try:
        for case in manifest['cases']:
            path = Path(case['source'])
            if identity(path) != case['identity']:
                raise RuntimeError('Source identity changed: ' + case['name'])
            if case.get('sha256') and sha(path) != case['sha256']:
                raise RuntimeError('Source hash changed: ' + case['name'])
            schedule = case.get('schedule', ['old-default-a', 'new-auto-a'])
            for arm in schedule:
                if arm not in ['old-default-a', 'old-default-b', 'new-auto-a', 'new-auto-b', 'new-default-a']:
                    raise ValueError('Unknown arm: ' + arm)
                if shutil.disk_usage(args.output_dir).free < 30 * 1024**3:
                    raise RuntimeError('Trial volume has less than 30 GiB free')
                directory = args.output_dir / case['name'] / arm
                directory.mkdir(parents=True)
                output = directory / 'output.mkv'
                binary = args.baseline if arm.startswith('old-') else args.candidate
                argv = [str(binary), *case['prefix'], '-i', str(path),
                        *grain_arguments(case['arguments'], '-auto-' in arm),
                        '--log-level', 'debug', '-o', str(output)]
                elapsed = run(argv, directory / 'encode.log', args.timeout)
                log = (directory / 'encode.log').read_text(errors='replace')
                finish = re.search(r'encoded (\d+) frames, ([\d.]+) fps', log)
                if not finish:
                    raise RuntimeError('Missing encoder completion: ' + str(directory))
                row = dict(case=case['name'], arm=arm, command=argv, seconds=elapsed,
                           frames=int(finish[1]), fps=float(finish[2]), bytes=output.stat().st_size,
                           sha256=sha(output), fallback_frames=[int(x) for x in re.findall(
                               r'fgs-model frame=(\d+)[^\n]*sourceFallback=1', log)])
                if row['frames'] != case['frames']:
                    raise RuntimeError('Encoder frame count mismatch: ' + str(directory))
                report['runs'].append(row)
                save()
                print(json.dumps({k: row[k] for k in ['case', 'arm', 'seconds', 'frames', 'bytes']}), flush=True)
            # Do not interleave CPU decoding with timed encodes of the same case.
            rows = [r for r in report['runs'] if r['case'] == case['name']]
            for row in rows:
                directory = args.output_dir / row['case'] / row['arm']
                output = directory / 'output.mkv'
                run([str(args.scanner), str(output)], directory / 'scan.json', args.timeout)
                row['scan'] = json.loads((directory / 'scan.json').read_text())
                s = row['scan']
                if not (s.get('complete') and s.get('verdict') == 'stable'
                        and s.get('criterion') == 'synthesis_texture_v1'
                        and s.get('packets') == row['frames'] and s.get('errors') == 0):
                    raise RuntimeError('Grain scan failed: ' + str(directory))
                probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                        '-show_streams', '-of', 'json', str(output)],
                                       capture_output=True, text=True, check=True, timeout=120)
                row['video'] = json.loads(probe.stdout)['streams'][0]
                for key, value in case['video_properties'].items():
                    if row['video'].get(key) != value:
                        raise RuntimeError('Changed video property ' + key + ': ' + str(directory))
                row['decoded_sha256'] = {}
                for grain in [0, 1]:
                    md5 = directory / f'grain-{grain}.framemd5'
                    run(['ffmpeg', '-v', 'error', '-xerror', '-nostdin', '-c:v', 'libdav1d',
                         '-threads', '2', '-filmgrain', str(grain), '-i', str(output),
                         '-map', '0:v:0', '-an', '-sn', '-pix_fmt', 'yuv420p10le',
                         '-fps_mode', 'passthrough', '-f', 'framemd5', str(md5)],
                        directory / f'decode-{grain}.log', args.timeout)
                    lines = [x for x in md5.read_text().splitlines() if x and not x.startswith('#')]
                    if len(lines) != case['frames']:
                        raise RuntimeError('Decoded frame count mismatch: ' + str(directory))
                    # Compare pixel payloads separately from timestamp/container identity.
                    hashes = [x.rsplit(',', 1)[1].strip() for x in lines]
                    row['decoded_sha256'][str(grain)] = hashlib.sha256('\n'.join(hashes).encode()).hexdigest()
                save()
            baseline = next(r for r in rows if r['arm'] == 'old-default-a')
            for row in rows:
                row['bytes_vs_production_percent'] = 100 * (row['bytes'] / baseline['bytes'] - 1)
                row['seconds_vs_production_percent'] = 100 * (row['seconds'] / baseline['seconds'] - 1)
                row['fallback_percent'] = 100 * len(row['fallback_frames']) / row['frames']
                row['within_extra_size_percent'] = {str(v): row['bytes'] <= baseline['bytes'] * (1 + v / 100)
                                                   for v in [5, 10, 20]}
                if row['arm'] == 'new-default-a' and row['decoded_sha256'] != baseline['decoded_sha256']:
                    raise RuntimeError('Default-mode decoded pixels changed')
            for name in ['old-default', 'new-auto']:
                pair = [r for r in rows if r['arm'].startswith(name)]
                if len(pair) == 2:
                    report['comparisons'].append(dict(case=case['name'], mode=name,
                        repeat_pixels_identical=pair[0]['decoded_sha256'] == pair[1]['decoded_sha256']))
            if identity(path) != case['identity']:
                raise RuntimeError('Source changed during trial: ' + case['name'])
            save()
        report.update(complete=True, finished_at=time.time())
    except Exception as error:
        report.update(error=str(error), failed_at=time.time())
        save()
        raise
    save()
    print('COMPLETE', flush=True)


if __name__ == '__main__':
    main()
