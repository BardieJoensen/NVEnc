#!/usr/bin/env python3
"""Encode and render the pinned real-film ripple/mesh regression, including a negative."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import numpy as np
import fixtures


def run(command, log):
    with log.open('w') as handle:
        subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, check=True)


def frame(path, seconds, grain=None):
    command = ['ffmpeg', '-v', 'error', '-threads', '2']
    if grain is not None:
        command += ['-c:v', 'libdav1d', '-filmgrain', str(grain)]
    command += ['-ss', str(seconds), '-i', str(path), '-map', '0:v:0', '-frames:v', '1',
                '-pix_fmt', 'yuv420p10le', '-threads', '2', '-f', 'rawvideo', '-']
    data = subprocess.run(command, capture_output=True, check=True).stdout
    if len(data) != 1920 * 1080 * 3:
        raise RuntimeError('Missing or incorrectly sized regression frame')
    return np.frombuffer(data, dtype='<u2')[:1920 * 1080].astype(np.int16)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nvencc', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=fixtures.DEFAULT_ROOT)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    pinned = fixtures.verify(args.root, json.loads(fixtures.MANIFEST.read_text()),
                             ['gentlemen_clip', 'gentlemen_mesh_negative'])
    source = Path(pinned['gentlemen_clip']['path'])
    negative = Path(pinned['gentlemen_mesh_negative']['path'])
    repo = Path(__file__).resolve().parents[2]
    scanner = args.output / 'scan'
    flags = shlex.split(subprocess.check_output(
        ['pkg-config', '--cflags', '--libs', '--static', 'libavformat', 'libavcodec', 'libavutil'], text=True))
    run(['g++', '-std=c++17', '-O2', '-I', str(repo / 'NVEncCore'),
         str(repo / 'tests/fgs/scan_bitstream.cpp'), '-o', str(scanner), *flags], args.output / 'build-scan.log')
    rejected = subprocess.run([str(scanner), str(negative)], capture_output=True, text=True)
    if rejected.returncode != 1:
        raise RuntimeError('Known visible periodic mesh was not rejected: ' + rejected.stdout)
    negative_report = json.loads(rejected.stdout)
    if negative_report.get('criterion') != 'synthesis_texture_v1':
        raise RuntimeError('Wrong scanner policy')
    output = args.output / 'candidate.mkv'
    command = [str(args.nvencc), '--avsw', '-i', str(source), '--codec', 'av1', '--output-depth', '10',
               '--qvbr', '30', '--max-bitrate', '50000', '--preset', 'quality', '--tune', 'hq',
               '--lookahead', '32', '--lookahead-level', '3', '--aq', '--aq-temporal',
               '--av1-film-grain', 'denoise=auto,chroma=auto,denoiser=bilateral', '-o', str(output)]
    run(command, args.output / 'encode.log')
    run([str(scanner), str(output)], args.output / 'scan.json')
    scan = json.loads((args.output / 'scan.json').read_text())
    if scan.get('verdict') != 'stable' or not scan.get('complete') or scan.get('packets') != 3600:
        raise RuntimeError('Candidate did not pass the complete 3600-frame grain scan')
    run(['ffmpeg', '-v', 'error', '-xerror', '-threads', '4', '-c:v', 'libdav1d', '-i', str(output),
         '-map', '0:v:0', '-an', '-f', 'null', '-'], args.output / 'decode.log')
    samples = []
    for seconds in [24, 66, 84.5]:
        reference = frame(source, seconds)
        on = frame(output, seconds, 1); off = frame(output, seconds, 0)
        # These three known contaminated fits must preserve the source instead
        # of synthesizing grain. Ordinary-grain positive controls live in KAT
        # and the libaom oracle stages, so disabling all synthesis cannot pass.
        if not np.array_equal(on, off):
            raise RuntimeError(f'Rejected scene still synthesizes luma grain at {seconds}s')
        mae = float(np.abs(on.astype(float) - reference).mean())
        if mae > 8.0:
            raise RuntimeError(f'Source picture was not preserved at {seconds}s: 10-bit MAE={mae}')
        samples.append({'seconds': seconds, 'luma_grain_on_off_identical': True, 'luma_mae_10bit': mae})
    if np.array_equal(frame(negative, 84.5, 1), frame(negative, 84.5, 0)):
        raise RuntimeError('Negative did not render its known mesh; decoder check is ineffective')
    report = {'candidate_sha256': hashlib.sha256(args.nvencc.read_bytes()).hexdigest(),
              'fixtures': pinned, 'negative_scan': negative_report, 'candidate_scan': scan,
              'source_preservation': samples, 'encode_command': command}
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
