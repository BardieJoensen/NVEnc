#!/usr/bin/env python3
"""Decode every band of sharp grain curves, including a point-budget negative.

These generated pictures have known clean pixels. Per-band checks prevent a
large region from hiding excess grain in another brightness range. They are
bounded amplitude controls, not a universal perceptual or HDR display metric.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time

import numpy as np

import fidelity_compare as fc


CASES = {
    'steps_sdr': dict(bits=8, bands=12),
    'steps_pq': dict(bits=10, bands=12, color='pq'),
    'steps_hlg': dict(bits=10, bands=12, color='hlg'),
    'changing_curve': dict(bits=8, bands=12, change=True),
    'point_budget_sdr': dict(bits=8, bands=20, preserve=True),
    'point_budget_pq': dict(bits=10, bands=20, color='pq', preserve=True),
}


def generate(root, spec):
    bands, frames, height = spec['bands'], 48, 432
    width, bits = bands * 64, spec['bits']
    ds = 1 << (bits - 8)
    dtype = np.uint8 if bits == 8 else np.uint16
    levels = (np.linspace(32, 224, bands) if bands == 12
              else (np.arange(bands) + 0.5) * 256 / bands) * ds
    ideal = np.broadcast_to(np.repeat(levels, 64), (height, width))
    clean = np.rint(ideal).astype(dtype)
    chroma = np.full((height // 2, width // 2), 128 * ds, dtype=dtype)
    rng = np.random.default_rng(0xF1DE117)
    with (root / 'source.y4m').open('wb') as y4m, (root / 'source.yuv').open('wb') as raw:
        y4m.write(f'YUV4MPEG2 W{width} H{height} F24:1 Ip A1:1 {"C420mpeg2" if bits == 8 else "C420p10"}\n'.encode())
        for frame in range(frames):
            flip = int(spec.get('change', False) and frame >= frames // 2)
            sigmas = np.repeat(np.where((np.arange(bands) + flip) % 2, 2, 10), 64) * ds
            noisy = np.clip(np.rint(ideal + rng.normal(size=(height, width)) * sigmas),
                            0, (1 << bits) - 1).astype(dtype)
            y4m.write(b'FRAME\n')
            for plane in [noisy, chroma, chroma]:
                raw.write(plane.tobytes())
                y4m.write(plane.tobytes())
    return dict(frames=frames, width=width, height=height, bits=bits,
                source_sha256=fc.sha(root / 'source.y4m'), raw_sha256=fc.sha(root / 'source.yuv')), clean


def decode_and_measure(directory, source, info, clean, bands):
    bits, width, height, frames = [info[k] for k in ['bits', 'width', 'height', 'frames']]
    dtype = np.uint8 if bits == 8 else np.uint16
    pix = 'yuv420p' if bits == 8 else 'yuv420p10le'
    pictures = {'source': source / 'source.yuv'}
    for grain in [0, 1]:
        path = directory / f'grain-{grain}.yuv'
        fc.command(['ffmpeg', '-v', 'error', '-xerror', '-nostdin', '-c:v', 'libdav1d',
                    '-threads', '2', '-filmgrain', str(grain), '-i', str(directory / 'output.mkv'),
                    '-map', '0:v:0', '-an', '-sn', '-pix_fmt', pix, '-fps_mode', 'passthrough',
                    '-f', 'rawvideo', str(path)], directory / f'decode-{grain}.log')
        pictures[str(grain)] = path
    expected = frames * width * height * 3 // 2 * np.dtype(dtype).itemsize
    if any(p.stat().st_size != expected for p in pictures.values()):
        raise ValueError('Incomplete source or decoded pictures')
    mapped = {k: np.memmap(p, dtype=dtype, mode='r').reshape(frames, -1)[:, :width * height].reshape(frames, height, width)
              for k, p in pictures.items()}
    rows = []
    for band in range(bands):
        crop = np.s_[height // 2 + 24:-24, band * 64 + 16:(band + 1) * 64 - 16]
        residual = {k: a[:, crop[0], crop[1]].astype(float) - clean[crop] for k, a in mapped.items()}
        sigmas = {k: value.std(axis=(1, 2)) for k, value in residual.items()}
        ratio = sigmas['1'] / sigmas['source']
        rows.append(dict(band=band, ratios=ratio.tolist(), median=float(np.median(ratio[8:])),
                         minimum=float(ratio.min()), maximum=float(ratio.max())))
    return dict(bands=rows, grain_on_off_identical=fc.sha(pictures['0']) == fc.sha(pictures['1']),
                decoded_hashes={k: fc.sha(p) for k, p in pictures.items() if k != 'source'})


def check(case, candidate):
    if case['spec'].get('preserve'):
        return ([] if candidate['grain_on_off_identical'] and candidate['source_fallbacks'] == case['source']['frames']
                else ['point-budget negative did not consistently preserve source without synthesis'])
    errors = []
    for band in candidate['bands']:
        if not (0.85 <= band['median'] <= 1.10 and 0.75 <= band['minimum'] and band['maximum'] <= 1.25):
            errors.append(f"band {band['band']} grain amplitude outside bounds")
    if candidate['source_fallbacks'] != 0:
        errors.append('representable controlled curve needlessly preserved whole source frames')
    if not candidate['strength_refit_frames']:
        errors.append('controlled sharp curve did not exercise occupied-bin recovery')
    return errors


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--scanner', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--cases', choices=list(CASES), nargs='+', default=list(CASES))
    args = p.parse_args()
    if len(args.cases) != len(set(args.cases)):
        p.error('duplicate case selection')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = dict(complete=False, passed=False, started_at=time.time(), cases=[],
                  candidate_sha256=fc.sha(args.candidate), baseline_sha256=fc.sha(args.baseline),
                  scanner_sha256=fc.sha(args.scanner), harness_sha256=fc.sha(__file__))

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
            info, clean = generate(root, spec)
            case = dict(name=name, spec=spec, source=info, arms={})
            report['cases'].append(case)
            for arm, encoder in [('previous_auto', args.baseline), ('candidate', args.candidate)]:
                directory = root / arm
                row = fc.encode(encoder, directory, root / 'source.y4m', spec, 20, True, info['frames'], 0.1)
                scan = subprocess.run([str(args.scanner), str(directory / 'output.mkv')],
                                      capture_output=True, text=True, check=True, timeout=120)
                row['scan'] = json.loads(scan.stdout)
                if not (row['scan'].get('complete') and row['scan'].get('verdict') == 'stable'
                        and row['scan'].get('criterion') == 'synthesis_texture_v1'
                        and row['scan'].get('packets') == info['frames']):
                    raise ValueError('Incomplete or unsafe synthesis scan')
                row.update(decode_and_measure(directory, root, info, clean, spec['bands']))
                case['arms'][arm] = row
                save()
            candidate = case['arms']['candidate']
            case['errors'] = check(case, candidate)
            case['bytes_vs_previous_auto_percent'] = 100 * (candidate['bytes'] / case['arms']['previous_auto']['bytes'] - 1)
            print(name, 'size%', round(case['bytes_vs_previous_auto_percent'], 2),
                  'fallback', candidate['source_fallbacks'], 'errors', case['errors'], flush=True)
            save()
        report.update(complete=True, passed=not any(c['errors'] for c in report['cases']), finished_at=time.time())
    except Exception as e:
        report['error'] = str(e)
        raise
    finally:
        save()
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
