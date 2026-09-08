#!/usr/bin/env python3
"""Offline comparison using explicit production arguments and retained sources.

The manifest pins source identities and supplies the actual flow arguments.
Only the film-grain retention option changes between arms. Encodes and their
validation run sequentially; outputs never enter a library replacement flow.
File-size ratios are measured against current default retention, not old auto.
"""
import argparse
import copy
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


def grain_arguments(arguments, auto, extra=()):
    args = list(arguments)
    if args.count('--av1-film-grain') != 1:
        raise ValueError('Exactly one film-grain argument is required')
    i = args.index('--av1-film-grain') + 1
    options = [x for x in args[i].split(',') if not x.startswith('retain=')]
    if auto:
        options.append('retain=auto')
        options.extend(extra)
    args[i] = ','.join(options)
    return args


def reuse_baseline_encoding(prior, case, expected_command, directory, report_path):
    """Reuse only an exact completed encode; all validation runs again below.

    A stopped experiment may contain a completed baseline and an incomplete
    candidate. The baseline row is written only after encoder completion and
    hashing. Its flags, source identity, frame count and bytes must still match.
    """
    matches = [r for r in prior['runs'] if r['case'] == case['name'] and r['arm'] == 'old-default-a']
    if not matches:
        return None
    if len(matches) != 1:
        raise RuntimeError('Ambiguous cached baseline')
    source_cases = [c for c in prior['manifest']['cases'] if c['name'] == case['name']]
    if len(source_cases) != 1:
        raise RuntimeError('Ambiguous cached source')
    for key in ['source', 'identity', 'sha256', 'frames', 'video_properties']:
        if source_cases[0].get(key) != case.get(key):
            raise RuntimeError('Cached baseline source changed: ' + key)
    row = copy.deepcopy(matches[0])
    def without_output(argv):
        result = list(argv)
        if result.count('-o') != 1:
            raise RuntimeError('Ambiguous cached output argument')
        result[result.index('-o') + 1] = '<output>'
        return result
    if without_output(row['command']) != without_output(expected_command):
        raise RuntimeError('Cached baseline encode arguments changed')
    original = Path(row['command'][row['command'].index('-o') + 1])
    if (row['frames'] != case['frames'] or original.stat().st_size != row['bytes']
            or sha(original) != row['sha256']):
        raise RuntimeError('Cached baseline encoded artifact changed')
    (directory / 'output.mkv').symlink_to(original.resolve())
    row['reused_encoding_from'] = str(report_path)
    row['validation_reused'] = False
    for key in ['scan', 'video', 'decoded_sha256', 'timeline_sha256']:
        row.pop(key, None)
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--scanner', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--timeout', type=int, default=14400)
    p.add_argument('--reuse-baseline', type=Path,
                   help='Reuse exact completed baseline encodes; rerun their validation')
    args = p.parse_args()
    manifest = json.loads(args.manifest.read_text())
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = dict(complete=False, started_at=time.time(), manifest=manifest,
                  manifest_sha256=sha(args.manifest), harness_sha256=sha(__file__),
                  baseline_sha256=sha(args.baseline), candidate_sha256=sha(args.candidate),
                  scanner_sha256=sha(args.scanner), runs=[], comparisons=[])
    prior = json.loads(args.reuse_baseline.read_text()) if args.reuse_baseline else None
    if prior:
        if prior['baseline_sha256'] != report['baseline_sha256']:
            raise RuntimeError('Cached baseline encoder changed')
        report['reuse_baseline_report_sha256'] = sha(args.reuse_baseline)

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
                        *grain_arguments(case['arguments'], '-auto-' in arm,
                                         case.get('candidate_grain_options', [])),
                        '--log-level', 'debug', '-o', str(output)]
                if prior and arm == 'old-default-a':
                    row = reuse_baseline_encoding(prior, case, argv, directory, args.reuse_baseline)
                    if row is not None:
                        report['runs'].append(row)
                        save()
                        print(case['name'], arm, 'reusing encode; validation pending', flush=True)
                        continue
                elapsed = run(argv, directory / 'encode.log', args.timeout)
                log = (directory / 'encode.log').read_text(errors='replace')
                finish = re.search(r'encoded (\d+) frames, ([\d.]+) fps', log)
                if not finish:
                    raise RuntimeError('Missing encoder completion: ' + str(directory))
                row = dict(case=case['name'], arm=arm, command=argv, seconds=elapsed,
                           frames=int(finish[1]), fps=float(finish[2]), bytes=output.stat().st_size,
                           sha256=sha(output), fallback_frames=[int(x) for x in re.findall(
                               r'fgs-model frame=(\d+)[^\n]*sourceFallback=1', log)],
                           fresh_model_frames=[int(x) for x in re.findall(
                               r'fgs-model frame=(\d+)[^\n]*freshModel=1', log)])
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
                row['timeline_sha256'] = {}
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
                    timeline = [','.join(x.split(',')[:4]) for x in lines]
                    row['timeline_sha256'][str(grain)] = hashlib.sha256('\n'.join(timeline).encode()).hexdigest()
                save()
            baseline = next(r for r in rows if r['arm'] == 'old-default-a')
            for row in rows:
                pause = case.get('baseline_pause_seconds', 0.0) if row is baseline else 0.0
                if not 0 <= pause < row['seconds']:
                    raise RuntimeError('Invalid recorded timing exclusion')
                row['intentional_pause_seconds'] = pause
                row['active_seconds'] = row['seconds'] - pause
                row['timing_comparison_paired'] = not bool(baseline.get('reused_encoding_from'))
            for row in rows:
                row['bytes_vs_production_percent'] = 100 * (row['bytes'] / baseline['bytes'] - 1)
                row['seconds_vs_production_percent'] = 100 * (row['active_seconds'] / baseline['active_seconds'] - 1)
                row['fallback_percent'] = 100 * len(row['fallback_frames']) / row['frames']
                row['within_extra_size_percent'] = {str(v): row['bytes'] <= baseline['bytes'] * (1 + v / 100)
                                                   for v in [5, 10, 20]}
                if row['arm'] == 'new-default-a' and row['decoded_sha256'] != baseline['decoded_sha256']:
                    raise RuntimeError('Default-mode decoded pixels changed')
                if row['timeline_sha256'] != baseline['timeline_sha256']:
                    raise RuntimeError('Candidate decoded timestamps changed')
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
