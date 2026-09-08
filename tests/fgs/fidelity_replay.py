#!/usr/bin/env python3
"""Verify a pixel-preserving implementation change against a completed experiment.

Re-encode every fixed-QP and matched-size candidate arm, decode every frame with
grain enabled and disabled, and require exact prior raw-pixel hashes. Metrics
can then be reused through this explicit evidence link, without relabelling
the old experiment's binary. Also require a complete current syntax scan.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

from fidelity_compare import encode, sha


def decoded_hash(path, bits, grain, expected_bytes):
    command = ['ffmpeg', '-v', 'error', '-xerror', '-nostdin', '-c:v', 'libdav1d',
               '-threads', '2', '-filmgrain', str(grain), '-i', str(path), '-map', '0:v:0',
               '-an', '-sn', '-pix_fmt', 'yuv420p' if bits == 8 else 'yuv420p10le',
               '-fps_mode', 'passthrough', '-f', 'rawvideo', '-']
    digest = hashlib.sha256()
    count = 0
    with path.with_name(f'replay-decode-{grain}.log').open('w') as log, tempfile.TemporaryFile(dir=path.parent) as raw:
        result = subprocess.run(command, stdout=raw, stderr=log, timeout=120)
        raw.seek(0)
        for chunk in iter(lambda: raw.read(1 << 20), b''):
            count += len(chunk)
            digest.update(chunk)
    if result.returncode != 0 or count != expected_bytes:
        raise RuntimeError('Incomplete replay decode: ' + str(path))
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prior', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--scanner', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    prior = json.loads((args.prior / 'report.json').read_text())
    if not prior.get('complete'):
        raise RuntimeError('Prior experiment is incomplete')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = dict(complete=False, started_at=time.time(), prior_report=str(args.prior / 'report.json'),
                  prior_report_sha256=sha(args.prior / 'report.json'),
                  prior_candidate_sha256=prior['candidate_sha256'], candidate_sha256=sha(args.candidate),
                  scanner_sha256=sha(args.scanner), harness_sha256=sha(__file__), runs=[])

    def save():
        tmp = args.output_dir / 'report.tmp'
        tmp.write_text(json.dumps(report, indent=2) + '\n')
        tmp.replace(args.output_dir / 'report.json')

    save()
    for case in prior['cases']:
        root = args.prior / case['name']
        info = case['source']
        for name, expected in info['hashes'].items():
            if sha(root / name) != expected:
                raise RuntimeError('Prior source changed: ' + str(root / name))
        arms = list(dict.fromkeys(['new-auto'] + ([case['no_larger_arm']] if case['no_larger_arm'] else [])))
        for arm in arms:
            old = case['arms'][arm]
            old_dir = root / arm
            if sha(old_dir / 'output.mkv') != old['file_sha256']:
                raise RuntimeError('Prior candidate encoding changed')
            for name, expected in old['decoded_hashes'].items():
                if sha(old_dir / name) != expected:
                    raise RuntimeError('Prior decoded pixels changed')
            directory = args.output_dir / case['name'] / arm
            directory.parent.mkdir(exist_ok=True)
            row = encode(args.candidate, directory, root / 'source.y4m', case['spec'], old['qp'], True, info['frames'])
            row.update(case=case['name'], arm=arm, prior_encoded_sha256=old['file_sha256'], decoded_hashes={})
            expected_bytes = info['frames'] * info['width'] * info['height'] * 3 // 2 * (1 if info['bits'] == 8 else 2)
            for grain in [0, 1]:
                name = f'grain-{grain}.yuv'
                row['decoded_hashes'][name] = decoded_hash(directory / 'output.mkv', info['bits'], grain, expected_bytes)
                if row['decoded_hashes'][name] != old['decoded_hashes'][name]:
                    raise RuntimeError('Replay pixels changed: ' + str(directory) + ' ' + name)
            result = subprocess.run([str(args.scanner), '--syntax-only', str(directory / 'output.mkv')],
                                    capture_output=True, text=True, timeout=120)
            (directory / 'syntax.json').write_text(result.stdout)
            row['syntax'] = json.loads(result.stdout)
            if (result.returncode or not row['syntax'].get('complete') or row['syntax'].get('verdict') != 'stable'
                    or row['syntax'].get('packets') != info['frames']):
                raise RuntimeError('Replay syntax check failed: ' + str(directory))
            report['runs'].append(row)
            save()
            print(case['name'], arm, 'all decoded pixels identical; syntax valid', flush=True)
        for name, expected in info['hashes'].items():
            if sha(root / name) != expected:
                raise RuntimeError('Source changed during replay')
    report.update(complete=True, finished_at=time.time())
    save()


if __name__ == '__main__':
    main()
