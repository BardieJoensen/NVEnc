#!/usr/bin/env python3
"""Offline comparison using explicit production arguments and retained sources.

The manifest pins source identities and supplies the actual flow arguments.
Only the film-grain retention option changes between arms. Encodes run
sequentially; independent CPU validation can overlap with a bounded worker
count. Outputs never enter a library replacement flow.
File-size ratios are measured against current default retention, not old auto.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def verify_source(case, verified):
    """Hash a repeated UHD source once, retaining per-case identity checks."""
    path = Path(case['source'])
    before = identity(path)
    if before != case['identity']:
        raise RuntimeError('Source identity changed: ' + case['name'])
    expected = case.get('sha256')
    key = str(path.resolve())
    prior = verified.get(key)
    if expected:
        if prior and prior['identity'] == before:
            if prior['sha256'] != expected:
                raise RuntimeError('Conflicting source hash: ' + case['name'])
        else:
            if sha(path) != expected or identity(path) != before:
                raise RuntimeError('Source hash or identity changed: ' + case['name'])
            verified[key] = dict(identity=before, sha256=expected)


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


def reuse_baseline_encoding(prior, case, expected_command, directory, report_path,
                            arm='old-default-a'):
    """Reuse only an exact completed encode; all validation runs again below.

    A stopped experiment may contain a completed baseline and an incomplete
    candidate. The baseline row is written only after encoder completion and
    hashing. Its flags, source identity, frame count and bytes must still match.
    The optional arm extends the original baseline-only interface to candidates;
    the caller must also verify the appropriate binary hash before reuse.
    """
    matches = [r for r in prior['runs'] if r['case'] == case['name'] and r['arm'] == arm]
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


def decode_validation(directory, grain, frames, timeout, threads):
    """One independent full decode; only the caller updates the shared report."""
    md5 = directory / f'grain-{grain}.framemd5'
    seconds = run(['ffmpeg', '-v', 'error', '-xerror', '-nostdin', '-c:v', 'libdav1d',
                   '-threads', str(threads), '-filmgrain', str(grain),
                   '-i', str(directory / 'output.mkv'), '-map', '0:v:0', '-an', '-sn',
                   '-pix_fmt', 'yuv420p10le', '-fps_mode', 'passthrough',
                   '-f', 'framemd5', str(md5)], directory / f'decode-{grain}.log', timeout)
    lines = [line for line in md5.read_text().splitlines() if line and not line.startswith('#')]
    if len(lines) != frames:
        raise RuntimeError('Decoded frame count mismatch: ' + str(directory))
    pixels = [line.rsplit(',', 1)[1].strip() for line in lines]
    timeline = [','.join(line.split(',')[:4]) for line in lines]
    return dict(grain=str(grain), seconds=seconds,
                decoded_sha256=hashlib.sha256('\n'.join(pixels).encode()).hexdigest(),
                timeline_sha256=hashlib.sha256('\n'.join(timeline).encode()).hexdigest())


def check_reuse_binaries(prior, baseline_sha256, candidate_sha256, all_arms):
    if prior['baseline_sha256'] != baseline_sha256:
        raise RuntimeError('Cached baseline encoder changed')
    if all_arms and prior['candidate_sha256'] != candidate_sha256:
        raise RuntimeError('Cached candidate encoder changed')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--scanner', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--timeout', type=int, default=14400)
    reuse = p.add_mutually_exclusive_group()
    reuse.add_argument('--reuse-baseline', type=Path,
                   help='Reuse exact completed baseline encodes; rerun their validation')
    reuse.add_argument('--reuse-encodes', type=Path,
                       help='Reuse exact completed encodes of either binary; rerun all validation')
    p.add_argument('--validation-workers', type=int, default=1,
                   help='Independent CPU decode jobs, 1..4; encodes remain sequential')
    p.add_argument('--decode-threads', type=int, default=2)
    args = p.parse_args()
    if not 1 <= args.validation_workers <= 4 or not 1 <= args.decode_threads <= 8:
        p.error('Use 1..4 validation workers and 1..8 decoder threads')
    manifest = json.loads(args.manifest.read_text())
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = dict(complete=False, started_at=time.time(), manifest=manifest,
                  manifest_sha256=sha(args.manifest), harness_sha256=sha(__file__),
                  baseline_sha256=sha(args.baseline), candidate_sha256=sha(args.candidate),
                  scanner_sha256=sha(args.scanner), validation_workers=args.validation_workers,
                  decode_threads=args.decode_threads, runs=[], comparisons=[], case_validations=[])
    reuse_path = args.reuse_baseline or args.reuse_encodes
    prior = json.loads(reuse_path.read_text()) if reuse_path else None
    if prior:
        check_reuse_binaries(prior, report['baseline_sha256'], report['candidate_sha256'],
                             bool(args.reuse_encodes))
        report['reuse_encoding_report_sha256'] = sha(reuse_path)

    def save():
        temp = args.output_dir / 'report.tmp'
        temp.write_text(json.dumps(report, indent=2) + '\n')
        os.replace(temp, args.output_dir / 'report.json')

    save()
    try:
        verified_sources = {}
        for case in manifest['cases']:
            path = Path(case['source'])
            verify_source(case, verified_sources)
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
                if prior and (args.reuse_encodes or arm == 'old-default-a'):
                    row = reuse_baseline_encoding(prior, case, argv, directory, reuse_path, arm)
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
            validation_started = time.monotonic()
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
                row['decode_seconds'] = {}
            with ThreadPoolExecutor(max_workers=args.validation_workers) as workers:
                futures = {workers.submit(decode_validation,
                    args.output_dir / row['case'] / row['arm'], grain, case['frames'],
                    args.timeout, args.decode_threads): row for row in rows for grain in [0, 1]}
                for future in as_completed(futures):
                    row, result = futures[future], future.result()
                    grain = result['grain']
                    row['decoded_sha256'][grain] = result['decoded_sha256']
                    row['timeline_sha256'][grain] = result['timeline_sha256']
                    row['decode_seconds'][grain] = result['seconds']
                    save()
                    print(case['name'], row['arm'], 'full decode grain=' + grain,
                          'complete', flush=True)
            report['case_validations'].append(dict(case=case['name'],
                seconds=time.monotonic() - validation_started, workers=args.validation_workers))
            baseline = next(r for r in rows if r['arm'] == 'old-default-a')
            for row in rows:
                pause = case.get('baseline_pause_seconds', 0.0) if row is baseline else 0.0
                if not 0 <= pause < row['seconds']:
                    raise RuntimeError('Invalid recorded timing exclusion')
                row['intentional_pause_seconds'] = pause
                row['active_seconds'] = row['seconds'] - pause
                row['timing_comparison_paired'] = not bool(
                    baseline.get('reused_encoding_from') or row.get('reused_encoding_from'))
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
