#!/usr/bin/env python3
"""Source-referenced regressions for repaired one-frame grain flashes.

Private media stays in the fixture store. This checks decoded picture texture,
including a pinned negative, rather than treating apply_grain=0 as a defect.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

import numpy as np
import fixtures

START = 355.9
FRAMES = 16
PATCH = (736, 768, 32, 32)  # reviewed, static, uniform part of the foreground shirt
CASES = {
    'amphibia': dict(source='amphibia_flicker_source', negative='amphibia_flicker_negative',
                     start=START, frames=FRAMES, patch=PATCH, seek='00:05:40', encode_frames=720),
    'losttapes': dict(source='losttapes_recovery_source', negative='losttapes_recovery_negative',
                     start=90.12, frames=8, patch=(288, 560, 16, 16), seek='00:01:00', encode_frames=1080),
    'southpark': dict(source='southpark_flicker_source', negative='southpark_flicker_negative',
                     start=1145.14, frames=8, patch=(96, 1056, 16, 16), seek='00:18:10', encode_frames=1560),
}


def assess(source, candidate, patch=PATCH):
    if source.shape != candidate.shape or source.ndim != 3 or not len(source):
        raise ValueError('missing or mismatched decoded pictures')
    x, y, width, height = patch
    if min(x, y) < 0 or min(width, height) <= 0 or x + width > source.shape[2] or y + height > source.shape[1]:
        raise ValueError('review patch outside decoded picture')
    source = source.astype(np.float32)
    candidate = candidate.astype(np.float32)
    if not np.isfinite(source).all() or not np.isfinite(candidate).all():
        raise ValueError('non-finite decoded picture')
    source_sd = source[:, y:y+height, x:x+width].std(axis=(1, 2))
    if source_sd.max() > 0.3:
        raise ValueError('pinned source patch is no longer uniform; check alignment')
    candidate_sd = candidate[:, y:y+height, x:x+width].std(axis=(1, 2))
    rms = np.sqrt(np.mean((candidate - source) ** 2, axis=(1, 2)))
    # Limits are specific to the pinned SDR/QVBR34 scenes. The known defects
    # reach about 2.8/3.38/17 SD in the originally uniform patches, versus <0.06 for
    # source-preserving frames. Also reject a blurred/blank/shifted picture.
    return dict(passed=bool(candidate_sd.max() <= 0.3 and rms.max() <= 4.0),
                source_patch_sd=source_sd.tolist(), output_patch_sd=candidate_sd.tolist(),
                source_rms=rms.tolist(), texture_limit=0.3, source_rms_limit=4.0)


def decode(path, prefix, start=START, frames=FRAMES):
    probe = json.loads(subprocess.check_output(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
         'stream=start_time,codec_name', '-of', 'json', str(path)], timeout=30))
    stream = probe['streams'][0]
    command = ['ffmpeg', '-hide_banner', '-nostdin', '-copyts', '-threads', '2']
    if stream['codec_name'] == 'av1':
        command += ['-c:v', 'libdav1d', '-filmgrain', '1']
    # Avoid ambiguous accurate-seek handling of nonzero-start Matroska excerpts.
    # Those excerpts are short; trim their original displayed PTS.
    if abs(float(stream.get('start_time', 0))) < 0.1:
        command += ['-ss', str(start)]
    command += ['-i', str(path), '-map', '0:v:0', '-an', '-sn', '-frames:v', str(frames),
                '-fps_mode', 'passthrough', '-vf', f'trim=start={start},format=gray16le,showinfo',
                '-filter_threads', '1', '-f', 'rawvideo', '-']
    prefix.with_suffix('.command.json').write_text(json.dumps(command, indent=2) + '\n')
    with prefix.with_suffix('.log').open('w') as log:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=log, check=True, timeout=180)
    if len(result.stdout) != frames * 1080 * 1920 * 2:
        raise RuntimeError('missing decoded regression frames')
    times = [float(t) for t in re.findall(r' n:\s*\d+ pts:\s*-?\d+ pts_time:([0-9.]+)',
                                         prefix.with_suffix('.log').read_text())][:frames]
    if len(times) != frames or any(b <= a for a, b in zip(times, times[1:])):
        raise RuntimeError('incomplete or non-increasing decoded timestamps')
    pixels = np.frombuffer(result.stdout, dtype='<u2').reshape(frames, 1080, 1920)
    return times, pixels.astype(np.float32) / 256.0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nvencc', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=fixtures.DEFAULT_ROOT)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--candidate-video', type=Path, help='review an already recorded candidate encode')
    parser.add_argument('--case', choices=CASES, default='amphibia')
    args = parser.parse_args()
    case = CASES[args.case]
    args.output.mkdir(parents=True, exist_ok=True)
    pinned = fixtures.verify(args.root, json.loads(fixtures.MANIFEST.read_text()),
                             [case['source'], case['negative']])
    source_path = Path(pinned[case['source']]['path'])
    candidate = args.candidate_video or args.output / 'candidate.mkv'
    if args.candidate_video is None:
        command = [str(args.nvencc), '--avhw', '--timestamp-passthrough', '--allow-other-negative-pts',
                   '--video-track', '1', '-i', str(source_path), '--codec', 'av1', '--output-depth', '10',
                   '--qvbr', '34', '--max-bitrate', '50000', '--preset', 'quality', '--tune', 'hq',
                   '--lookahead', '32', '--lookahead-level', '3', '--aq', '--aq-temporal',
                   '--av1-film-grain', 'denoise=auto,chroma=auto,denoiser=bilateral',
                   '--colormatrix', 'auto', '--colorprim', 'auto', '--transfer', 'auto', '--colorrange', 'auto',
                   '--seek', case['seek'], '--frames', str(case['encode_frames']), '-o', str(candidate)]
        (args.output / 'encode-command.json').write_text(json.dumps(command, indent=2) + '\n')
        with (args.output / 'encode.log').open('w') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=240)
    source_pts, source = decode(source_path, args.output / 'source', case['start'], case['frames'])
    negative_pts, negative = decode(Path(pinned[case['negative']]['path']), args.output / 'negative', case['start'], case['frames'])
    candidate_pts, picture = decode(candidate, args.output / 'candidate', case['start'], case['frames'])
    if source_pts != negative_pts or source_pts != candidate_pts:
        raise RuntimeError('source, negative and candidate frames are not aligned')
    positive_control = assess(source, source, case['patch'])
    negative_result = assess(source, negative, case['patch'])
    candidate_result = assess(source, picture, case['patch'])
    report = dict(candidate_sha256=hashlib.sha256(args.nvencc.read_bytes()).hexdigest(),
                  candidate_video=str(candidate), candidate_video_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),
                  case=args.case, fixtures=pinned, seconds=source_pts, patch=case['patch'], units='8-bit-equivalent full-range grayscale',
                  positive_control=positive_control, negative=negative_result, candidate=candidate_result,
                  scope='Pinned flash and source fidelity only; not a universal flicker or quality certificate')
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    if not positive_control['passed'] or negative_result['passed']:
        raise RuntimeError('decoded texture regression did not separate its controls')
    if not candidate_result['passed']:
        raise RuntimeError('candidate failed the source-referenced grain flash regression')
    print('PASS: known grain flash rejected, source texture retained by candidate')


if __name__ == '__main__':
    main()
