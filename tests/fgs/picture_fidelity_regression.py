#!/usr/bin/env python3
"""Offline source-labelled gradient, colour-detail and transition regression.

All arms use QP 20 and the same retention cap. Measurements use every decoded
frame, including start-up and cuts; grain-off and grain-on pictures are checked
separately. These small controls are not a universal perceptual quality score.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time

import numpy as np

import fidelity_compare as fc
import quality_metrics


CASES = {
    'sdr8_gradient_clean': dict(kind='gradient', sigma=0),
    'sdr10_gradient_clean': dict(kind='gradient', sigma=0, bits=10),
    'sdr8_gradient_fade': dict(kind='gradient', sigma=6, fade=True),
    'pq_gradient_clean': dict(kind='gradient', sigma=0, bits=10, color='pq'),
    'pq_gradient_fade': dict(kind='gradient', sigma=6, fade=True, bits=10, color='pq'),
    'hlg_gradient_fade': dict(kind='gradient', sigma=6, fade=True, bits=10, color='hlg'),
    'sdr8_colour_clean': dict(kind='colour', sigma=6, chroma=(0, 0)),
    'sdr10_colour_clean': dict(kind='colour', sigma=6, chroma=(0, 0), bits=10),
    'pq_colour_clean': dict(kind='colour', sigma=6, chroma=(0, 0), bits=10, color='pq'),
    'colour_noisy': dict(kind='colour', sigma=6, chroma=(3, 3)),
    'colour_asymmetric': dict(kind='colour', sigma=6, chroma=(3, 0)),
    'pq_colour_asymmetric': dict(kind='colour', sigma=6, chroma=(3, 0), bits=10, color='pq'),
    'chroma_flat': dict(kind='flat', sigma=6, chroma=(3, 3)),
    'colour_motion_cut': dict(kind='colour', sigma=6, chroma=(0, 0), motion=True, cut=True),
    'hlg_colour_motion': dict(kind='colour', sigma=6, chroma=(3, 3), motion=True,
                              bits=10, color='hlg'),
    'grain_cut': dict(kind='gradient', sigma=6, grain_cut=True),
    'source_fallback_transition': dict(kind='transition', sigma=6),
    'narrow_weak_transition': dict(kind='transition', sigma=6, weak_sigma=1),
    'quiet_regions': dict(kind='regions', sigma=6, quiet=True),
}


def clean_frame(spec, frame, frames=48, width=768, height=432):
    """Return independently specified clean picture and source grain strengths."""
    bits = spec.get('bits', 8)
    ds = 1 << (bits - 8)
    yy, xx = np.mgrid[:height, :width]
    cy, cx = np.mgrid[:height // 2, :width // 2]
    sigma = spec['sigma']
    if spec.get('grain_cut'):
        sigma = 2 if frames // 3 <= frame < 2 * frames // 3 else 8
    if spec['kind'] == 'gradient':
        y = np.empty((height, width))
        for band, (lo, hi) in enumerate([(18, 42), (80, 112), (32, 220)]):
            sl = slice(band * height // 3, (band + 1) * height // 3)
            y[sl] = lo + (hi - lo) * xx[sl] / (width - 1)
        if spec.get('fade'):
            scale = 1 - 0.8 * frame / (frames - 1)
            y = 16 + (y - 16) * scale
            sigma *= scale
    else:
        bands = 20 if spec['kind'] == 'transition' and frames // 3 <= frame < 2 * frames // 3 else 12
        band = np.minimum(bands - 1, xx * bands // width)
        y = np.linspace(32, 224, bands)[band]
        if bands == 20:
            sigma = np.where(band % 2, spec.get('weak_sigma', 2), 10)
        if spec.get('quiet'):
            sigma = np.where(band % 2, 0, sigma)
    c = [np.full((height // 2, width // 2), 128.0) for _ in range(2)]
    if spec['kind'] == 'colour' and not (spec.get('cut') and frame >= frames // 2):
        # Chroma-only diagonal and horizontal structure. The lower half is a
        # source-defined flat control; luma does not reveal the colour detail.
        dx = frame if spec.get('motion') else 0
        dy = frame * 0.5 if spec.get('motion') else 0
        mask = cy < height // 4
        c[0][mask] += (6 * np.sin(2 * np.pi * (cx + cy - dx - dy) / 12))[mask]
        c[1][mask] += (5 * np.sin(2 * np.pi * (cy - dy) / 9))[mask]
    dtype = np.uint8 if bits == 8 else np.uint16
    planes = [np.rint(p * ds).astype(dtype) for p in [y] + c]
    return planes, sigma, spec.get('chroma', (0, 0))


def generate(root, spec, frames=48):
    width, height, bits = 768, 432, spec.get('bits', 8)
    ds = 1 << (bits - 8)
    dtype = np.uint8 if bits == 8 else np.uint16
    rng = np.random.default_rng(0xC010AFADE)
    paths = [root / name for name in ['source.y4m', 'source.yuv', 'ideal.yuv']]
    with paths[0].open('wb') as y4m, paths[1].open('wb') as source, paths[2].open('wb') as ideal:
        y4m.write(f'YUV4MPEG2 W{width} H{height} F24:1 Ip A1:1 {"C420mpeg2" if bits == 8 else "C420p10"}\n'.encode())
        for frame in range(frames):
            clean, sy, sc = clean_frame(spec, frame, frames, width, height)
            y4m.write(b'FRAME\n')
            for p, sigma in zip(clean, [sy] + list(sc)):
                noisy = np.clip(np.rint(p.astype(float) + rng.normal(size=p.shape) * sigma * ds),
                                0, (1 << bits) - 1).astype(dtype)
                y4m.write(noisy.tobytes())
                source.write(noisy.tobytes())
                ideal.write(p.tobytes())
    return dict(width=width, height=height, bits=bits, frames=frames,
                hashes={p.name: fc.sha(p) for p in paths})


def planes_at(mapped, frame, width, height):
    count = width * height
    row = mapped[frame]
    return [row[:count].reshape(height, width),
            row[count:count * 5 // 4].reshape(height // 2, width // 2),
            row[count * 5 // 4:].reshape(height // 2, width // 2)]


def gradient_metrics(picture, ideal, ds):
    rows = []
    height = len(ideal)
    for band in range(3):
        crop = (slice(band * height // 3 + 16, (band + 1) * height // 3 - 16), slice(24, -24))
        residual = (picture[crop].astype(float) - ideal[crop]) / ds
        profile = residual.mean(axis=0)
        smooth = np.convolve(profile, np.array([1, 4, 6, 4, 1]) / 16, mode='valid')
        rows.append(dict(bias=float(profile.mean()), profile_rmse=float(np.sqrt(np.mean(smooth ** 2))),
                         contour_p99=float(np.quantile(np.abs(smooth[8:] - smooth[:-8]), .99)),
                         noise_sigma=float(residual.std())))
    return rows


def colour_metrics(picture, ideal, ds):
    crop = (slice(16, len(ideal) // 2 - 16), slice(24, -24))
    # These source-labelled patterns contain no underlying ramp or texture.
    # Their AC amplitude measures the intended colour pattern. A three-tap
    # highpass alone disproportionately measures the 8-bit quantization steps
    # of a weak sinusoid; keep that diagnostic separate from picture transfer.
    target = ideal[crop].astype(float)
    target -= target.mean()
    detail = picture[crop].astype(float)
    detail -= detail.mean()
    power = float(np.sum(target * target))
    fine_target = quality_metrics.highpass(ideal.astype(float))[crop]
    fine_detail = quality_metrics.highpass(picture.astype(float))[crop]
    fine_power = float(np.sum(fine_target * fine_target))
    residual = (picture.astype(float) - ideal) / ds
    flat = residual[len(ideal) // 2 + 16:-16, 24:-24]
    return dict(gain=float(np.sum(detail * target) / power) if power else None,
                highpass_gain=float(np.sum(fine_detail * fine_target) / fine_power) if fine_power else None,
                detail_error_sigma=float(residual[crop].std()), flat_sigma=float(flat.std()),
                flat_bias=float(flat.mean()))


def measure(root, directory, spec, info, decode=True):
    width, height, bits, frames = [info[k] for k in ['width', 'height', 'bits', 'frames']]
    output_bits = info.get('output_bits', bits)
    ds = 1 << (output_bits - 8)
    paths = dict(source=root / 'source.yuv', ideal=root / 'ideal.yuv')
    for grain in [0, 1]:
        path = directory / f'grain-{grain}.yuv'
        if decode:
            fc.command(['ffmpeg', '-v', 'error', '-xerror', '-nostdin', '-c:v', 'libdav1d',
                    '-threads', '2', '-filmgrain', str(grain), '-i', str(directory / 'output.mkv'),
                    '-map', '0:v:0', '-an', '-sn', '-pix_fmt', 'yuv420p' if output_bits == 8 else 'yuv420p10le',
                    '-fps_mode', 'passthrough', '-f', 'rawvideo', str(path)], directory / f'decode-{grain}.log')
        paths['off' if grain == 0 else 'on'] = path
    mapped = {}
    for k, p in paths.items():
        depth = bits if k in ['source', 'ideal'] else output_bits
        dtype = np.uint8 if depth == 8 else np.uint16
        expected = frames * width * height * 3 // 2 * np.dtype(dtype).itemsize
        if p.stat().st_size != expected:
            raise ValueError('Incomplete source, reference or decoded pictures')
        mapped[k] = np.memmap(p, dtype=dtype, mode='r').reshape(frames, -1)
    trace = []
    for frame in range(frames):
        pictures = {k: planes_at(v, frame, width, height) for k, v in mapped.items()}
        if output_bits != bits:
            for k in ['source', 'ideal']:
                pictures[k] = [p.astype(float) * 2 ** (output_bits - bits) for p in pictures[k]]
        row = dict(frame=frame)
        row['synth_chroma_sigma'] = [float(((a.astype(float) - b) / ds).std())
                                     for a, b in zip(pictures['on'][1:], pictures['off'][1:])]
        for name in ['source', 'off', 'on']:
            item = dict(chroma=[colour_metrics(p, r, ds) for p, r in zip(pictures[name][1:], pictures['ideal'][1:])])
            if spec['kind'] == 'gradient':
                item['gradient'] = gradient_metrics(pictures[name][0], pictures['ideal'][0], ds)
            # Measure noise only inside source-labelled flat luma regions.
            elif spec['kind'] in ['transition', 'regions']:
                bands = 20 if spec['kind'] == 'transition' and frames // 3 <= frame < 2 * frames // 3 else 12
                regions = []
                for band in range(bands):
                    crop = (slice(24, -24), slice((band * width + bands - 1) // bands + 10,
                                                (band + 1) * width // bands - 10))
                    residual = (pictures[name][0][crop].astype(float) - pictures['ideal'][0][crop]) / ds
                    regions.append(dict(bias=float(residual.mean()), noise_sigma=float(residual.std())))
                item['regions'] = regions
            row[name] = item
        trace.append(row)
    return dict(trace=trace, decoded_hashes={k: fc.sha(paths[k]) for k in ['off', 'on']})


def summarize(row):
    trace = row['trace']
    result = {}
    for name in ['source', 'off', 'on']:
        chroma = []
        for component in range(2):
            values = [f[name]['chroma'][component] for f in trace]
            gains = [r['gain'] for r in values if r['gain'] is not None]
            chroma.append(dict(gain_median=float(np.median(gains)) if gains else None,
                               gain_min=min(gains) if gains else None,
                               flat_sigma_median=float(np.median([r['flat_sigma'] for r in values])),
                               flat_bias_max=max(abs(r['flat_bias']) for r in values)))
        result[name] = dict(chroma=chroma)
        if 'gradient' in trace[0][name]:
            result[name]['gradient'] = {
                key: max(abs(v[key]) for f in trace for v in f[name]['gradient'])
                for key in ['bias', 'profile_rmse', 'contour_p99']}
    return result


def negative_controls():
    # Prove these measurements see contouring and colour blur, including when
    # luma is unchanged. This is independent of the encoder implementation.
    clean, _, _ = clean_frame(CASES['sdr10_gradient_clean'], 0)
    banded = np.rint(clean[0].astype(float) / 32) * 32
    gradient = gradient_metrics(banded, clean[0], 4)
    clean, _, _ = clean_frame(CASES['sdr8_colour_clean'], 0)
    blurred = clean[1].astype(float)
    for _ in range(2):
        padded = np.pad(blurred, 1, mode='edge')
        blurred = sum(padded[dy:dy + len(blurred), dx:dx + blurred.shape[1]]
                      for dy in range(3) for dx in range(3)) / 9
    colour = colour_metrics(blurred, clean[1], 1)
    passed = max(r['profile_rmse'] for r in gradient) > 1 and colour['gain'] < .7
    return dict(passed=passed, eight_code_contours=gradient, blurred_colour=colour)


def check(case):
    candidate = case['arms']['candidate']
    summary = candidate['summary']
    previous = case['arms']['previous_auto']['summary']
    errors = []
    for name in ['off', 'on']:
        for c in range(2):
            r = summary[name]['chroma'][c]
            if r['gain_median'] is not None:
                # Separate filter loss from the encoder's own quantization.
                # The plain arm has identical source, bit depth and QP.
                ratios = [f[name]['chroma'][c]['gain'] / p['off']['chroma'][c]['gain']
                          for f, p in zip(candidate['trace'], case['arms']['plain']['trace'])
                          if f[name]['chroma'][c]['gain'] is not None]
                if np.median(ratios) < .95 or min(ratios) < .90:
                    errors.append(f'{name} chroma {c} loses colour detail beyond plain compression')
            if r['flat_bias_max'] > .5:
                errors.append(f'{name} chroma {c} shifts flat colour mean')
        if 'gradient' in summary[name]:
            for key, absolute, allowance in [('bias', .5, .15), ('profile_rmse', .65, .15), ('contour_p99', 1., .25)]:
                if summary[name]['gradient'][key] > max(absolute, previous[name]['gradient'][key] + allowance):
                    errors.append(f'{name} gradient {key} increased')
    for frame, plain_frame in zip(candidate['trace'], case['arms']['plain']['trace']):
        for c, sigma in enumerate(case['spec'].get('chroma', (0, 0))):
            if sigma == 0 and frame['synth_chroma_sigma'][c] != 0:
                errors.append(f'chroma {c} synthesized grain into a source-clean colour component')
                return errors
            source_sigma = frame['source']['chroma'][c]['flat_sigma']
            if source_sigma < 1.5:
                continue
            plain_sigma = plain_frame['off']['chroma'][c]['flat_sigma']
            actual = frame['on']['chroma'][c]['flat_sigma']
            if not min(.75 * source_sigma, .95 * plain_sigma) <= actual <= max(1.25 * source_sigma, 1.05 * plain_sigma):
                errors.append(f'chroma {c} grain energy changed in a source-defined flat region')
                return errors
    if case['spec']['kind'] in ['gradient', 'transition', 'regions']:
        field = 'gradient' if case['spec']['kind'] == 'gradient' else 'regions'
        # Ignore almost-clean source noise, where a ratio is not meaningful.
        for frame, plain_frame in zip(candidate['trace'], case['arms']['plain']['trace']):
            for a, b, p in zip(frame['on'][field], frame['source'][field], plain_frame['off'][field]):
                if b['noise_sigma'] < .5 and a['noise_sigma'] > max(.5, p['noise_sigma'] + .25):
                    errors.append('synthesized grain was introduced into a source-quiet region')
                    return errors
                if b['noise_sigma'] < 2:
                    if a['noise_sigma'] > max(b['noise_sigma'] * 1.25, b['noise_sigma'] + .5, p['noise_sigma'] + .25):
                        errors.append('local grain overshot a weak source region')
                        return errors
                    continue
                # Weak source grain can already be reduced by ordinary lossy
                # compression. A source-preserving fallback is compared with
                # that measured control, not an impossible lossless promise.
                low = min(.75 * b['noise_sigma'], .95 * p['noise_sigma'])
                high = max(1.25 * b['noise_sigma'], 1.05 * p['noise_sigma'])
                if not low <= a['noise_sigma'] <= high:
                    errors.append('local decoded grain amplitude changed across gradient/transition')
                    return errors
        if case['spec']['kind'] == 'transition':
            frames = case['source']['frames']
            needed = set(range(frames // 3, 2 * frames // 3))
            actual = set(candidate['source_fallback_frames'])
            if not needed.issubset(actual) or any(f >= 2 * frames // 3 + 12 for f in actual):
                errors.append('unrepresentable transition was not preserved with timely recovery')
    return errors


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--scanner', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--reuse-baseline', type=Path)
    p.add_argument('--output-depth', type=int, choices=[8, 10], help='Override depth for every arm; input precision stays unchanged')
    p.add_argument('--cases', choices=list(CASES), nargs='+', default=list(CASES))
    args = p.parse_args()
    if len(args.cases) != len(set(args.cases)):
        p.error('duplicate cases')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = dict(complete=False, passed=False, started_at=time.time(), cases=[],
                  candidate_sha256=fc.sha(args.candidate), baseline_sha256=fc.sha(args.baseline),
                  scanner_sha256=fc.sha(args.scanner), harness_sha256=fc.sha(__file__),
                  helpers_sha256={n: fc.sha(Path(__file__).with_name(n))
                                  for n in ['fidelity_compare.py', 'quality_metrics.py', 'fgs_kat.py']},
                  negative_controls=negative_controls())
    reuse = None
    if args.reuse_baseline:
        reuse = json.loads((args.reuse_baseline / 'report.json').read_text())
        if not reuse['complete'] or any(reuse.get(k) != report[k] for k in
                ['baseline_sha256', 'scanner_sha256', 'harness_sha256', 'helpers_sha256']):
            raise ValueError('Cached baseline binary or harness does not match')

    def save():
        tmp = args.output_dir / 'report.tmp'
        tmp.write_text(json.dumps(report, indent=2) + '\n')
        tmp.replace(args.output_dir / 'report.json')

    save()
    try:
        for name in args.cases:
            spec = CASES[name]
            root = args.output_dir / name
            root.mkdir()
            info = generate(root, spec)
            if args.output_depth is not None:
                info['output_bits'] = args.output_depth
            case = dict(name=name, spec=spec, source=info, arms={})
            report['cases'].append(case)
            for arm, encoder in [('plain', args.baseline), ('previous_auto', args.baseline), ('candidate', args.candidate)]:
                if arm != 'candidate' and reuse is not None:
                    old = next(c for c in reuse['cases'] if c['name'] == name)
                    row = old['arms'][arm]
                    old_dir = args.reuse_baseline / name / arm
                    if old['source'] != info or row['file_sha256'] != fc.sha(old_dir / 'output.mkv') or any(
                            row['decoded_hashes'][key] != fc.sha(old_dir / f'grain-{grain}.yuv')
                            for grain, key in [(0, 'off'), (1, 'on')]):
                        raise ValueError('Cached baseline source/output does not match')
                    case['arms'][arm] = row
                    continue
                directory = root / arm
                encode_spec = dict(spec, bits=info.get('output_bits', info['bits']))
                row = fc.encode(encoder, directory, root / 'source.y4m', encode_spec, 20, arm != 'plain',
                                info['frames'], .1 if arm != 'plain' else None, film_grain=arm != 'plain')
                scan = subprocess.run([str(args.scanner), str(directory / 'output.mkv')],
                                      capture_output=True, text=True, check=True, timeout=120)
                row['scan'] = json.loads(scan.stdout)
                if not (row['scan'].get('complete') and row['scan'].get('verdict') == 'stable'
                        and row['scan'].get('criterion') == 'synthesis_texture_v1'
                        and row['scan'].get('packets') == info['frames']):
                    raise ValueError('Incomplete or unsafe synthesis scan')
                row.update(measure(root, directory, spec, info))
                row['summary'] = summarize(row)
                case['arms'][arm] = row
                save()
            case['errors'] = check(case)
            case['bytes_vs_previous_auto_percent'] = 100 * (case['arms']['candidate']['bytes'] / case['arms']['previous_auto']['bytes'] - 1)
            print(name, 'size%', round(case['bytes_vs_previous_auto_percent'], 2), 'errors', case['errors'], flush=True)
            save()
        report.update(complete=True, passed=report['negative_controls']['passed'] and not any(c['errors'] for c in report['cases']),
                      finished_at=time.time())
    except Exception as e:
        report['error'] = str(e)
        raise
    finally:
        save()
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
