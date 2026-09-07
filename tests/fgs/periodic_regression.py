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
import decoded_sequence


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
    pixels = np.frombuffer(data, dtype='<u2').astype(np.int16)
    ysize = 1920 * 1080; csize = ysize // 4
    return {'luma': pixels[:ysize], 'chroma_u': pixels[ysize:ysize+csize],
            'chroma_v': pixels[ysize+csize:]}


def grain_concentration(on, off):
    """Measure decoded grain, independently of the fitted AR coefficients.

    Average Hann-windowed 64x64 periodograms over the active picture, then
    report the energy in the strongest 1% of frequency bins. The pinned
    visible mesh concentrates over 10%; the reviewed ordinary-grain shot
    is below 4%. Eight percent is a fixture regression limit, not a general
    perceptual-quality threshold (coarse film grain needs other controls).
    """
    delta = (on - off).reshape(1080, 1920).astype(float)
    blocks = delta[160:928].reshape(12, 64, 30, 64).transpose(0, 2, 1, 3).reshape(-1, 64, 64)
    blocks -= blocks.mean(axis=(1, 2), keepdims=True)
    window = np.hanning(64)
    power = (abs(np.fft.fft2(blocks * window[None, :, None]
                           * window[None, None, :])) ** 2).mean(axis=0)
    return float(np.sort(power.ravel())[-41:].sum() / power.sum()) if power.sum() else 0.0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nvencc', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=fixtures.DEFAULT_ROOT)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    pinned = fixtures.verify(args.root, json.loads(fixtures.MANIFEST.read_text()),
                             ['gentlemen_clip', 'gentlemen_mesh_negative', 'gentlemen_guard_positive'])
    source = Path(pinned['gentlemen_clip']['path'])
    negative = Path(pinned['gentlemen_mesh_negative']['path'])
    positive = Path(pinned['gentlemen_guard_positive']['path'])
    repo = Path(__file__).resolve().parents[2]
    scanner = args.output / 'scan'
    flags = shlex.split(subprocess.check_output(
        ['pkg-config', '--cflags', '--libs', '--static', 'libavformat', 'libavcodec', 'libavutil'], text=True))
    run(['g++', '-std=c++17', '-O2', '-I', str(repo / 'NVEncCore'),
         str(repo / 'tests/fgs/scan_bitstream.cpp'), '-o', str(scanner), *flags], args.output / 'build-scan.log')
    inspector = args.output / 'fgs-grain-inspect'
    display_flags = shlex.split(subprocess.check_output(
        ['pkg-config', '--cflags', '--libs', 'libavformat', 'libavcodec', 'libavutil', 'dav1d'], text=True))
    run(['g++', '-std=c++17', '-O2', '-Wall', str(repo / 'tools/fgs/grain_inspect.cpp'),
         '-o', str(inspector), *display_flags], args.output / 'build-inspector.log')
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
    sequences = {}; decoders = {}
    for name, path in [('positive', positive), ('negative', negative), ('candidate', output)]:
        measurements = args.output / (name + '-display.csv')
        run([str(inspector), str(path), str(measurements)], args.output / (name + '-display.log'))
        # Progress JSON goes to stderr as well; completion is the final line.
        decoder = json.loads((args.output / (name + '-display.log')).read_text().splitlines()[-1])
        if not decoder.get('complete') or decoder.get('measured_frames') != 3600:
            raise RuntimeError(name + ' decoded picture measurement was incomplete')
        decoders[name] = decoder
        sequences[name] = decoded_sequence.load(measurements)
    whole_sequence = decoded_sequence.compare(sequences['candidate'], sequences['positive'])
    negative_sequence = decoded_sequence.compare(sequences['negative'], sequences['positive'])
    (args.output / 'decoded-sequence.json').write_text(json.dumps(
        dict(candidate=whole_sequence, negative=negative_sequence, decoders=decoders), indent=2) + '\n')
    if negative_sequence['passed']:
        raise RuntimeError('Known mesh did not fail the whole-sequence decoded check')
    if not whole_sequence['passed']:
        raise RuntimeError('Whole-sequence texture/temporal change requires review; see decoded-sequence.json')
    samples = []
    for seconds in [24, 66, 84.5]:
        reference = frame(source, seconds)
        on = frame(output, seconds, 1); off = frame(output, seconds, 0)
        # Rejecting a bad fit changes the temporal hold state: the earlier
        # 24-second shot can acquire a fresh, ordinary-grain fit. Check its
        # decoded texture rather than requiring every old bad shot to be silent.
        # The two jacket fits must still preserve the source without synthesis.
        planes = {}
        for plane in reference:
            identical = np.array_equal(on[plane], off[plane])
            if seconds in (66, 84.5) and not identical:
                raise RuntimeError(f'Rejected scene still synthesizes {plane} grain at {seconds}s')
            mae = float(np.abs(on[plane].astype(float) - reference[plane]).mean())
            if mae > 8.0:
                raise RuntimeError(f'Source {plane} was not preserved at {seconds}s: 10-bit MAE={mae}')
            planes[plane] = dict(grain_on_off_identical=bool(identical), mae_10bit=mae)
        concentration = grain_concentration(on['luma'], off['luma'])
        if concentration > 0.08:
            raise RuntimeError(f'Decoded periodic grain at {seconds}s: concentration={concentration}')
        samples.append({'seconds': seconds, 'planes': planes, 'decoded_grain_top_1pct_energy': concentration})
    negative_concentration = grain_concentration(frame(negative, 84.5, 1)['luma'], frame(negative, 84.5, 0)['luma'])
    if negative_concentration <= 0.08:
        raise RuntimeError('Known mesh did not fail the decoded-texture check')
    report = {'candidate_sha256': hashlib.sha256(args.nvencc.read_bytes()).hexdigest(),
              'fixtures': pinned, 'negative_scan': negative_report, 'candidate_scan': scan,
              'source_preservation': samples, 'negative_decoded_grain_top_1pct_energy': negative_concentration,
              'decoded_sequence': whole_sequence, 'negative_decoded_sequence': negative_sequence,
              'inspector_sha256': hashlib.sha256(inspector.read_bytes()).hexdigest(),
              'encode_command': command}
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
